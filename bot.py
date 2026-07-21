import asyncio
import hashlib
import html
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sources import SOURCES


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Політехнік").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
CHECK_INTERVAL_SECONDS = max(60, int(os.getenv("CHECK_INTERVAL_SECONDS", "300")))
MAX_DRAFTS_PER_SCAN = max(1, int(os.getenv("MAX_DRAFTS_PER_SCAN", "12")))
BOOTSTRAP_SKIP_EXISTING = os.getenv("BOOTSTRAP_SKIP_EXISTING", "true").lower() == "true"
DB_PATH = BASE_DIR / os.getenv("DB_FILE", "politehnik.db")
KYIV_TZ = ZoneInfo("Europe/Kyiv")
ONLY_TODAY_NEWS = os.getenv("ONLY_TODAY_NEWS", "true").lower() == "true"
HTTP_TIMEOUT = max(5, int(os.getenv("HTTP_TIMEOUT", "20")))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("politehnik")
logging.getLogger("httpx").setLevel(logging.WARNING)

LEVEL_LABELS = {
    1: "🔴 I рівень — Львів і Львівська політехніка",
    2: "🟠 II рівень — Освіта України",
    3: "🟡 III рівень — Світова освіта",
    4: "🟢 IV рівень — Рейтинг інститутів",
    5: "🔵 V рівень — Telegram",
    6: "⚪ VI рівень — Українські новини",
    7: "🟣 VII рівень — Моніторинг персоналій",
}

KEYWORDS = [
    "львівська політехніка",
    "студент",
    "студенти",
    "наука",
    "освіта",
    "грант",
    "erasmus",
    "акредитація",
    "лабораторія",
    "інститут",
    "університет",
    "ректор",
    "проректор",
    "міжнародний проєкт",
    "міжнародний проект",
    "рейтинг університетів",
    "стартап",
    "штучний інтелект",
    "безпілотні системи",
    "оборонні технології",
    "інновації",
    "вступ",
    "нмт",
    "стипендія",
    "гуртожиток",
    "патент",
    "працевлаштування випускників",
    "академічна мобільність",
    "horizon europe",
]

PERSON_KEYWORDS = [
    "наталія шаховська",
    "шаховська наталія",
    "наталії шаховської",
    "наталію шаховську",
    "наталією шаховською",
    "шаховська",
]

HIGH_VALUE_KEYWORDS = [
    "львівська політехніка",
    "ректор",
    "проректор",
    "вступ",
    "нмт",
    "акредитація",
    "грант",
    "лабораторія",
    "патент",
    "міжнародний проєкт",
    "міжнародний проект",
    "рейтинг",
    "стипендія",
    "гуртожиток",
]

BLOCK_KEYWORDS = [
    "гороскоп",
    "астролог",
    "лотерея",
    "ставки на спорт",
    "курс валют",
    "рецепт",
    "шоу-бізнес",
]

monitor_task: asyncio.Task | None = None
monitor_paused = False
scan_lock = asyncio.Lock()


@dataclass
class Article:
    source: str
    level: int
    title: str
    url: str
    summary: str
    published: str
    score: int = 0


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db_connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS seen_articles (
                fingerprint TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                level INTEGER NOT NULL,
                original_title TEXT NOT NULL,
                original_summary TEXT NOT NULL,
                article_url TEXT NOT NULL,
                post_title TEXT NOT NULL,
                post_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_message_id INTEGER,
                media_type TEXT,
                media_file_id TEXT,
                created_at INTEGER NOT NULL,
                published_message_id INTEGER
            );
            """
        )


def get_meta(key: str, default: str = "") -> str:
    with db_connect() as db:
        row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    with db_connect() as db:
        db.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def canonical_title(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-zа-яіїєґ0-9 ]+", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def article_fingerprint(url: str, title: str) -> str:
    clean_url = url.split("#", 1)[0].strip()
    raw = clean_url or canonical_title(title)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_seen(article: Article) -> bool:
    fingerprint = article_fingerprint(article.url, article.title)
    with db_connect() as db:
        if db.execute(
            "SELECT 1 FROM seen_articles WHERE fingerprint = ?", (fingerprint,)
        ).fetchone():
            return True

        recent = db.execute(
            "SELECT title FROM seen_articles WHERE created_at > ? ORDER BY created_at DESC LIMIT 250",
            (int(time.time()) - 3 * 24 * 3600,),
        ).fetchall()

    current = canonical_title(article.title)
    for row in recent:
        old = canonical_title(row["title"])
        if current and old and SequenceMatcher(None, current, old).ratio() >= 0.88:
            return True
    return False


def mark_seen(article: Article) -> None:
    fingerprint = article_fingerprint(article.url, article.title)
    with db_connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO seen_articles(fingerprint, title, url, source, created_at) "
            "VALUES(?, ?, ?, ?, ?)",
            (fingerprint, article.title, article.url, article.source, int(time.time())),
        )


def score_article(article: Article) -> int:
    text = f"{article.title} {article.summary}".lower()
    if any(word in text for word in BLOCK_KEYWORDS):
        return -100

    hits = sum(1 for keyword in KEYWORDS if keyword in text)
    strong_hits = sum(1 for keyword in HIGH_VALUE_KEYWORDS if keyword in text)
    score = hits * 2 + strong_hits * 3

    if article.level == 1:
        score += 8
    elif article.level == 2:
        score += 5
    elif article.level == 3:
        score += 2
    elif article.level == 4:
        score += 1
    elif article.level == 5:
        score += 2
    elif article.level == 6:
        score += 0

    person_hits = sum(1 for keyword in PERSON_KEYWORDS if keyword in text)
    if person_hits:
        score += 25 + min(person_hits, 3) * 2

    if "львівська політехніка" in text:
        score += 15
    if any(token in text for token in ("україна", "українськ", "львів")):
        score += 2
    return score


def is_relevant(article):
    return True



def _datetime_from_struct(value: Any) -> datetime | None:
    """Перетворює feedparser time_struct на timezone-aware UTC datetime."""
    if not value:
        return None
    try:
        return datetime(*value[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str) -> datetime | None:
    """Розбирає RFC 2822 та ISO 8601 дати з RSS/HTML."""
    value = normalize_text(value)
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
    except (TypeError, ValueError, OverflowError):
        pass

    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KYIV_TZ)
        return parsed
    except ValueError:
        return None


def _is_today_kyiv(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KYIV_TZ).date() == datetime.now(KYIV_TZ).date()


def _extract_date_from_json_ld(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("datePublished", "dateCreated", "uploadDate"):
            if data.get(key):
                return str(data[key])
        for value in data.values():
            found = _extract_date_from_json_ld(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _extract_date_from_json_ld(item)
            if found:
                return found
    return ""


def _publisher_from_google_title(title: str) -> tuple[str, str]:
    """Повертає чистий заголовок і назву реального видання з Google News."""
    parts = re.split(r"\s[-–—]\s", normalize_text(title))
    if len(parts) >= 2 and 1 < len(parts[-1]) <= 70:
        return " — ".join(parts[:-1]).strip(), parts[-1].strip()
    return normalize_text(title), ""


def _is_google_news_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host.endswith("news.google.com") or host.endswith("google.com")


def inspect_article_page(url: str) -> tuple[str, datetime | None, str]:
    """
    Відкриває сторінку і повертає:
    (канонічне/кінцеве посилання, дата публікації, назва сайту).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124 Safari/537.36"
        ),
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }

    try:
        response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return url, None, ""

    final_url = response.url
    soup = BeautifulSoup(response.text, "html.parser")

    # Канонічне або OpenGraph-посилання. Для Google беремо тільки зовнішній домен.
    candidates: list[str] = []
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical and canonical.get("href"):
        candidates.append(urljoin(final_url, canonical["href"]))

    og_url = soup.find("meta", attrs={"property": "og:url"})
    if og_url and og_url.get("content"):
        candidates.append(urljoin(final_url, og_url["content"]))

    # Google News іноді містить зовнішнє посилання у звичайному <a>.
    if _is_google_news_url(final_url):
        for anchor in soup.find_all("a", href=True):
            candidate = urljoin(final_url, anchor["href"])
            host = urlparse(candidate).netloc.lower()
            if host and "google." not in host and not host.endswith("gstatic.com"):
                candidates.append(candidate)
                break

    for candidate in candidates:
        if candidate.startswith(("http://", "https://")):
            if not _is_google_news_url(candidate) or not _is_google_news_url(final_url):
                final_url = candidate
                break

    date_value = ""
    meta_date_selectors = [
        ("property", "article:published_time"),
        ("property", "og:published_time"),
        ("name", "date"),
        ("name", "pubdate"),
        ("name", "publish-date"),
        ("name", "datePublished"),
        ("itemprop", "datePublished"),
    ]
    for attr, key in meta_date_selectors:
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            date_value = tag["content"]
            break

    if not date_value:
        time_tag = soup.find("time")
        if time_tag:
            date_value = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)

    if not date_value:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                payload = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            date_value = _extract_date_from_json_ld(payload)
            if date_value:
                break

    site_name = ""
    site_meta = soup.find("meta", attrs={"property": "og:site_name"})
    if site_meta and site_meta.get("content"):
        site_name = normalize_text(site_meta["content"])

    return final_url, _parse_datetime(date_value), site_name


def entry_publication_datetime(entry: Any) -> datetime | None:
    parsed = _datetime_from_struct(entry.get("published_parsed"))
    if parsed is None:
        parsed = _datetime_from_struct(entry.get("updated_parsed"))
    if parsed is None:
        parsed = _parse_datetime(entry.get("published", "") or entry.get("updated", ""))
    return parsed


def _request_with_retries(url: str, *, timeout: int = HTTP_TIMEOUT) -> requests.Response:
    """HTTP GET із повторними спробами для тимчасових 429/5xx помилок."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/atom+xml, text/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.HTTPError(
                    f"{response.status_code} Server Error",
                    response=response,
                )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)

    assert last_error is not None
    raise last_error


def fetch_rss_source_sync(source: dict[str, Any]) -> list[Article]:
    response = _request_with_retries(source["url"])
    parsed = feedparser.parse(response.content)

    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(f"Некоректна RSS-стрічка: {getattr(parsed, 'bozo_exception', '')}")

    articles: list[Article] = []
    for entry in parsed.entries[:40]:
        raw_title = normalize_text(entry.get("title", ""))
        url = entry.get("link", "").strip()
        summary = normalize_text(
            entry.get("summary", "") or entry.get("description", "")
        )
        if not raw_title or not url:
            continue

        published_dt = entry_publication_datetime(entry)
        title, google_publisher = _publisher_from_google_title(raw_title)

        # Для прямих RSS не відкриваємо кожну сторінку без потреби.
        # Перевірка сторінки потрібна лише коли RSS не дав дату.
        real_url = url
        page_date: datetime | None = None
        page_site = ""
        if published_dt is None:
            real_url, page_date, page_site = inspect_article_page(url)

        effective_date = published_dt or page_date
        if ONLY_TODAY_NEWS and not _is_today_kyiv(effective_date):
            continue

        source_name = page_site or google_publisher or source["name"]
        article = Article(
            source=source_name,
            level=int(source["level"]),
            title=title,
            url=real_url,
            summary=summary,
            published=effective_date.isoformat() if effective_date else "",
        )
        article.score = score_article(article)
        articles.append(article)

    return articles


def fetch_html_source_sync(source: dict[str, Any]) -> list[Article]:
    """Читає сторінки новин сайтів, які не мають стабільного RSS."""
    response = _request_with_retries(source["url"])
    soup = BeautifulSoup(response.text, "html.parser")

    base_host = urlparse(response.url).netloc.lower()
    link_pattern = source.get("link_pattern", "")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        title = normalize_text(anchor.get_text(" ", strip=True))
        if len(title) < 18:
            continue

        absolute_url = urljoin(response.url, anchor["href"])
        parsed_url = urlparse(absolute_url)
        if parsed_url.scheme not in {"http", "https"}:
            continue
        if parsed_url.netloc.lower() != base_host:
            continue
        if link_pattern and not re.search(link_pattern, parsed_url.path):
            continue

        clean_url = absolute_url.split("#", 1)[0]
        if clean_url in seen_urls:
            continue

        seen_urls.add(clean_url)
        candidates.append((title, clean_url))
        if len(candidates) >= int(source.get("max_items", 20)):
            break

    articles: list[Article] = []
    for title, url in candidates:
        final_url, page_date, page_site = inspect_article_page(url)
        if ONLY_TODAY_NEWS and not _is_today_kyiv(page_date):
            continue

        # Короткий опис беремо з meta description самої статті.
        summary = ""
        try:
            article_response = _request_with_retries(final_url)
            article_soup = BeautifulSoup(article_response.text, "html.parser")
            description = (
                article_soup.find("meta", attrs={"property": "og:description"})
                or article_soup.find("meta", attrs={"name": "description"})
            )
            if description and description.get("content"):
                summary = normalize_text(description["content"])
        except requests.RequestException:
            pass

        article = Article(
            source=page_site or source["name"],
            level=int(source["level"]),
            title=title,
            url=final_url,
            summary=summary,
            published=page_date.isoformat() if page_date else "",
        )
        article.score = score_article(article)
        articles.append(article)

    return articles


def fetch_source_sync(source: dict[str, Any]) -> list[Article]:
    source_type = source.get("type", "rss").lower()
    if source_type == "html":
        return fetch_html_source_sync(source)
    return fetch_rss_source_sync(source)


async def fetch_source(source: dict[str, Any]) -> list[Article]:
    try:
        return await asyncio.to_thread(fetch_source_sync, source)
    except Exception as exc:
        logger.warning("Не вдалося прочитати %s: %s", source["name"], exc)
        return []


def clean_google_news_title(title: str) -> str:
    clean_title, _ = _publisher_from_google_title(title)
    return clean_title


def local_prepare_post(article: Article) -> tuple[str, str]:
    title = clean_google_news_title(article.title)
    summary = article.summary
    summary = re.sub(r"\s*(Читати далі|Read more).*", "", summary, flags=re.IGNORECASE)

    if summary and canonical_title(summary) != canonical_title(title):
        text = summary[:1200].strip()
    else:
        text = "Деталі події — у першоджерелі."

    return title[:220], text


def openai_rewrite_sync(article: Article, mode: str = "normal") -> tuple[str, str]:
    if not OPENAI_API_KEY:
        return local_prepare_post(article)

    length_instruction = {
        "short": "Текст має містити 2–3 короткі речення.",
        "long": "Текст має містити 5–7 змістовних речень.",
        "rewrite": "Перепиши текст іншим формулюванням, не змінюючи фактів.",
        "normal": "Текст має містити 3–5 речень.",
    }.get(mode, "Текст має містити 3–5 речень.")

    prompt = f"""
Ти редактор українського Telegram-каналу «{CHANNEL_NAME}» про освіту, науку,
студентське життя та розвиток університетів.

Підготуй нейтральну новину українською мовою. Не вигадуй фактів, дат, цитат,
цифр чи посад. Не роби сенсаційних висновків. {length_instruction}
Поверни ТІЛЬКИ JSON такого формату:
{{"title":"...","text":"..."}}

Джерело: {article.source}
Оригінальний заголовок: {article.title}
Оригінальний опис: {article.summary}
Посилання: {article.url}
""".strip()

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "input": prompt,
            "temperature": 0.4,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    output_text = data.get("output_text", "")
    if not output_text:
        pieces: list[str] = []
        for output in data.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    pieces.append(content.get("text", ""))
        output_text = "".join(pieces)

    output_text = output_text.strip().strip("`")
    if output_text.startswith("json"):
        output_text = output_text[4:].strip()
    parsed = json.loads(output_text)
    return normalize_text(parsed["title"])[:220], normalize_text(parsed["text"])[:3000]


async def prepare_post(article: Article, mode: str = "normal") -> tuple[str, str]:
    try:
        return await asyncio.to_thread(openai_rewrite_sync, article, mode)
    except Exception as exc:
        logger.warning("AI-редагування не спрацювало, використовую локальний текст: %s", exc)
        return local_prepare_post(article)


def create_draft(article: Article, post_title: str, post_text: str) -> int:
    with db_connect() as db:
        cursor = db.execute(
            """
            INSERT INTO drafts(
                source, level, original_title, original_summary, article_url,
                post_title, post_text, status, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                article.source,
                article.level,
                article.title,
                article.summary,
                article.url,
                post_title,
                post_text,
                int(time.time()),
            ),
        )
        return int(cursor.lastrowid)


def get_draft(draft_id: int) -> sqlite3.Row | None:
    with db_connect() as db:
        return db.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()


def update_draft(draft_id: int, **fields: Any) -> None:
    allowed = {
        "post_title",
        "post_text",
        "status",
        "admin_message_id",
        "media_type",
        "media_file_id",
        "published_message_id",
    }
    safe = {key: value for key, value in fields.items() if key in allowed}
    if not safe:
        return
    assignments = ", ".join(f"{key} = ?" for key in safe)
    values = list(safe.values()) + [draft_id]
    with db_connect() as db:
        db.execute(f"UPDATE drafts SET {assignments} WHERE id = ?", values)


def format_admin_preview(draft: sqlite3.Row) -> str:
    level_label = LEVEL_LABELS.get(draft["level"], "Новина")
    media_note = ""
    if draft["media_type"]:
        media_note = f"\n🖼 Медіа: {draft['media_type']} додано"

    return (
        f"{level_label}\n"
        f"📊 Оцінка: ручна перевірка\n"
        f"👤 Персоналія: {'Наталія Шаховська' if any(k in (draft['original_title'] + ' ' + draft['original_summary']).lower() for k in PERSON_KEYWORDS) else '—'}\n"
        f"🗞 Джерело: {html.escape(draft['source'])}{media_note}\n\n"
        f"<b>{html.escape(draft['post_title'])}</b>\n\n"
        f"{html.escape(draft['post_text'])}\n\n"
        f"🔗 <a href=\"{html.escape(draft['article_url'])}\">Першоджерело</a>\n\n"
        f"<i>Щоб змінити текст або додати фото/відео, відповідай на це повідомлення.</i>"
    )


def format_channel_post(draft: sqlite3.Row) -> str:
    source_name = normalize_text(draft["source"]) or "Першоджерело"
    source_url = html.escape(draft["article_url"], quote=True)
    subscribe = ""
    if CHANNEL_URL:
        subscribe = (
            f'\n\n🎓 <a href="{html.escape(CHANNEL_URL, quote=True)}">'
            f'Приєднатися до «{html.escape(CHANNEL_NAME)}»</a>'
        )

    return (
        f"<b>{html.escape(draft['post_title'])}</b>\n\n"
        f"{html.escape(draft['post_text'])}\n\n"
        f'🔗 Джерело: <a href="{source_url}">{html.escape(source_name)}</a>'
        f"{subscribe}"
    )

def draft_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Опублікувати", callback_data=f"publish:{draft_id}"),
                InlineKeyboardButton("❌ Відхилити", callback_data=f"reject:{draft_id}"),
            ],
            [
                InlineKeyboardButton("📏 Скоротити", callback_data=f"short:{draft_id}"),
                InlineKeyboardButton("📖 Розширити", callback_data=f"long:{draft_id}"),
            ],
            [
                InlineKeyboardButton("🔄 Переписати", callback_data=f"rewrite:{draft_id}"),
                InlineKeyboardButton("✏️ Як редагувати", callback_data=f"edithelp:{draft_id}"),
            ],
        ]
    )


async def send_draft_preview(application: Application, draft_id: int) -> None:
    draft = get_draft(draft_id)
    if not draft:
        return
    message = await application.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=format_admin_preview(draft),
        parse_mode=ParseMode.HTML,
        reply_markup=draft_keyboard(draft_id),
        disable_web_page_preview=True,
    )
    update_draft(draft_id, admin_message_id=message.message_id)


async def refresh_draft_preview(context: ContextTypes.DEFAULT_TYPE, draft_id: int) -> None:
    draft = get_draft(draft_id)
    if not draft or not draft["admin_message_id"]:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=ADMIN_CHAT_ID,
            message_id=draft["admin_message_id"],
            text=format_admin_preview(draft),
            parse_mode=ParseMode.HTML,
            reply_markup=draft_keyboard(draft_id),
            disable_web_page_preview=True,
        )
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


async def scan_sources(application: Application, force: bool = False) -> tuple[int, int]:
    async with scan_lock:
        found = 0
        drafted = 0
        first_boot = get_meta("bootstrapped", "0") != "1"

        logger.info("Починаю перевірку %s джерел", len(SOURCES))
        source_results = await asyncio.gather(
            *(fetch_source(source) for source in SOURCES)
        )

        for source, group in zip(SOURCES, source_results):
            logger.info(
                "Джерело «%s»: отримано %s актуальних матеріалів",
                source["name"],
                len(group),
            )

        articles = [article for group in source_results for article in group]
        articles.sort(key=lambda item: (item.level, -item.score))
        logger.info("Усього сьогоднішніх матеріалів після фільтра дати: %s", len(articles))

        for article in articles:
            if is_seen(article):
                continue

            found += 1

            if first_boot and BOOTSTRAP_SKIP_EXISTING and not force:
                mark_seen(article)
                continue

            if not is_relevant(article):
                # Нерелевантне теж позначаємо, щоб не аналізувати кожні 5 хвилин.
                mark_seen(article)
                continue

            if drafted >= MAX_DRAFTS_PER_SCAN:
                # Не позначаємо, щоб матеріал потрапив у наступний прохід.
                continue

            try:
                post_title, post_text = await prepare_post(article)
                draft_id = create_draft(article, post_title, post_text)
                await send_draft_preview(application, draft_id)
                mark_seen(article)
                drafted += 1
                logger.info("Створено чернетку №%s: %s", draft_id, article.title)
            except Exception:
                logger.exception("Не вдалося створити чернетку: %s", article.title)

        if first_boot:
            set_meta("bootstrapped", "1")
        set_meta("last_scan", str(int(time.time())))

        logger.info("Перевірка завершена: нових=%s, чернеток=%s", found, drafted)
        return found, drafted


async def monitor_loop(application: Application) -> None:
    logger.info(
        "Автоматичний моніторинг активний; перевірка кожні %s секунд",
        CHECK_INTERVAL_SECONDS,
    )
    await asyncio.sleep(3)

    while True:
        try:
            if monitor_paused:
                logger.info("Моніторинг призупинено")
            else:
                await scan_sources(application)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Помилка циклу моніторингу")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def post_init(application: Application) -> None:
    global monitor_task
    init_db()
    monitor_task = asyncio.create_task(monitor_loop(application))
    logger.info("Моніторинг запущено, інтервал %s секунд", CHECK_INTERVAL_SECONDS)


async def post_shutdown(application: Application) -> None:
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


def is_admin(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == ADMIN_CHAT_ID)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.effective_message.reply_text("⛔️ Цей бот приватний.")
        return
    await update.effective_message.reply_text(
        "✅ Бот «Політехнік» працює.\n\n"
        "/check — перевірити джерела зараз\n"
        "/status — стан моніторингу\n"
        "/pause — призупинити\n"
        "/resume — продовжити\n"
        "/testpost — тестова публікація"
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    message = await update.effective_message.reply_text("🔎 Перевіряю всі джерела…")
    found, drafted = await scan_sources(context.application, force=True)
    await message.edit_text(
        f"✅ Перевірку завершено.\nНових матеріалів: {found}\nСтворено чернеток: {drafted}"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    with db_connect() as db:
        pending = db.execute(
            "SELECT COUNT(*) AS count FROM drafts WHERE status = 'pending'"
        ).fetchone()["count"]
        published = db.execute(
            "SELECT COUNT(*) AS count FROM drafts WHERE status = 'published'"
        ).fetchone()["count"]
    last_scan = int(get_meta("last_scan", "0") or 0)
    last_text = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(last_scan)) if last_scan else "ще не було"
    await update.effective_message.reply_text(
        f"🤖 Моніторинг: {'⏸ призупинено' if monitor_paused else '▶️ працює'}\n"
        f"Інтервал: {CHECK_INTERVAL_SECONDS // 60} хв\n"
        f"Остання перевірка: {last_text}\n"
        f"Чернеток очікує: {pending}\n"
        f"Опубліковано: {published}\n"
        f"AI: {'увімкнений' if OPENAI_API_KEY else 'вимкнений'}"
    )


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global monitor_paused
    if not is_admin(update):
        return
    monitor_paused = True
    await update.effective_message.reply_text("⏸ Автоматичний моніторинг призупинено.")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global monitor_paused
    if not is_admin(update):
        return
    monitor_paused = False
    await update.effective_message.reply_text("▶️ Автоматичний моніторинг продовжено.")


async def testpost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"✅ Тестовий пост від бота «{html.escape(CHANNEL_NAME)}».",
        parse_mode=ParseMode.HTML,
    )
    await update.effective_message.reply_text("✅ Тест опубліковано.")


async def publish_draft(context: ContextTypes.DEFAULT_TYPE, draft: sqlite3.Row) -> int:
    text = format_channel_post(draft)
    if draft["media_type"] == "photo" and draft["media_file_id"]:
        message = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=draft["media_file_id"],
            caption=text[:1024],
            parse_mode=ParseMode.HTML,
        )
    elif draft["media_type"] == "video" and draft["media_file_id"]:
        message = await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=draft["media_file_id"],
            caption=text[:1024],
            parse_mode=ParseMode.HTML,
        )
    else:
        message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text[:4096],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    return message.message_id


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or query.message.chat.id != ADMIN_CHAT_ID:
        return
    await query.answer()

    action, draft_id_text = query.data.split(":", 1)
    draft_id = int(draft_id_text)
    draft = get_draft(draft_id)
    if not draft:
        await query.answer("Чернетку не знайдено", show_alert=True)
        return

    if action == "publish":
        if draft["status"] != "pending":
            await query.answer("Цю чернетку вже оброблено", show_alert=True)
            return
        try:
            message_id = await publish_draft(context, draft)
            update_draft(
                draft_id,
                status="published",
                published_message_id=message_id,
            )
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ Чернетку №{draft_id} опубліковано.")
        except TelegramError as exc:
            await query.message.reply_text(f"❌ Помилка публікації:\n{exc}")
        return

    if action == "reject":
        update_draft(draft_id, status="rejected")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"🗑 Чернетку №{draft_id} відхилено.")
        return

    if action == "edithelp":
        await query.message.reply_text(
            "✏️ Відповідай на повідомлення з чернеткою:\n"
            "• текстом — щоб замінити текст поста;\n"
            "• фото — щоб додати фото;\n"
            "• відео — щоб додати відео.\n\n"
            "Формат текстового редагування:\n"
            "Перший рядок — заголовок.\n"
            "Після порожнього рядка — основний текст."
        )
        return

    mode = {"short": "short", "long": "long", "rewrite": "rewrite"}.get(action)
    if mode:
        article = Article(
            source=draft["source"],
            level=draft["level"],
            title=draft["original_title"],
            url=draft["article_url"],
            summary=draft["original_summary"],
            published="",
        )
        await query.message.reply_text("⏳ Оновлюю чернетку…")
        title, text = await prepare_post(article, mode)
        update_draft(draft_id, post_title=title, post_text=text)
        await refresh_draft_preview(context, draft_id)


async def reply_editor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update) or not update.effective_message.reply_to_message:
        return

    replied_id = update.effective_message.reply_to_message.message_id
    with db_connect() as db:
        draft = db.execute(
            "SELECT * FROM drafts WHERE admin_message_id = ? AND status = 'pending'",
            (replied_id,),
        ).fetchone()
    if not draft:
        return

    if update.effective_message.photo:
        file_id = update.effective_message.photo[-1].file_id
        update_draft(draft["id"], media_type="photo", media_file_id=file_id)
        await update.effective_message.reply_text("✅ Фото додано до чернетки.")
        await refresh_draft_preview(context, draft["id"])
        return

    if update.effective_message.video:
        file_id = update.effective_message.video.file_id
        update_draft(draft["id"], media_type="video", media_file_id=file_id)
        await update.effective_message.reply_text("✅ Відео додано до чернетки.")
        await refresh_draft_preview(context, draft["id"])
        return

    text = (update.effective_message.text or "").strip()
    if not text:
        return
    parts = re.split(r"\n\s*\n", text, maxsplit=1)
    if len(parts) == 2:
        new_title, new_text = parts[0].strip(), parts[1].strip()
    else:
        new_title, new_text = draft["post_title"], text
    update_draft(draft["id"], post_title=new_title[:220], post_text=new_text[:3000])
    await update.effective_message.reply_text("✅ Текст чернетки оновлено.")
    await refresh_draft_preview(context, draft["id"])


async def forwarded_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """V рівень: пересланий у бот пост перетворюється на ручну чернетку."""
    if not is_admin(update):
        return
    message = update.effective_message
    if message.reply_to_message:
        return
    if not (message.forward_origin or message.forward_date):
        return

    raw_text = (message.text or message.caption or "").strip()
    if not raw_text:
        await message.reply_text("Не вдалося отримати текст із пересланого допису.")
        return

    first_line, *rest = raw_text.splitlines()
    article = Article(
        source="Пересланий Telegram-допис",
        level=5,
        title=first_line[:220],
        url="https://t.me/",
        summary="\n".join(rest).strip() or raw_text,
        published="",
    )
    title, text = await prepare_post(article)
    draft_id = create_draft(article, title, text)

    if message.photo:
        update_draft(draft_id, media_type="photo", media_file_id=message.photo[-1].file_id)
    elif message.video:
        update_draft(draft_id, media_type="video", media_file_id=message.video.file_id)

    await send_draft_preview(context.application, draft_id)
    await message.reply_text(f"✅ Створено чернетку №{draft_id}.")


def validate_config() -> list[str]:
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN")
    if not ADMIN_CHAT_ID:
        errors.append("ADMIN_CHAT_ID")
    if not CHANNEL_ID:
        errors.append("CHANNEL_ID")
    return errors


def main() -> None:
    missing = validate_config()
    if missing:
        raise RuntimeError(f"Не заповнено змінні у .env: {', '.join(missing)}")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("pause", pause_command))
    application.add_handler(CommandHandler("resume", resume_command))
    application.add_handler(CommandHandler("testpost", testpost_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(
            filters.Chat(ADMIN_CHAT_ID)
            & (filters.TEXT | filters.PHOTO | filters.VIDEO)
            & ~filters.COMMAND,
            reply_editor,
        ),
        group=0,
    )
    application.add_handler(
        MessageHandler(
            filters.Chat(ADMIN_CHAT_ID)
            & (filters.FORWARDED)
            & (filters.TEXT | filters.PHOTO | filters.VIDEO),
            forwarded_post_handler,
        ),
        group=1,
    )

    logger.info("Бот запущено")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
