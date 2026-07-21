# Прямі джерела без Google News.
# type="rss" — читаємо RSS/Atom.
# type="html" — читаємо сторінку новин і відкриваємо сьогоднішні матеріали.

SOURCES = [
    # I рівень — Львів і Львівська політехніка
    {
        "name": "Львівська політехніка",
        "level": 1,
        "type": "html",
        "url": "https://lpnu.ua/news",
        "link_pattern": r"^/news/",
        "max_items": 25,
    },
    {
        "name": "ZAXID.NET",
        "level": 1,
        "type": "rss",
        "url": "https://zaxid.net/rss/",
    },

    # II рівень — освіта України
    {
        "name": "Міністерство освіти і науки України",
        "level": 2,
        "type": "html",
        "url": "https://mon.gov.ua/timeline?type=posts",
        "link_pattern": r"^/news/",
        "max_items": 25,
    },
    {
        "name": "Освіта.ua",
        "level": 2,
        "type": "rss",
        "url": "https://osvita.ua/rss/",
    },
    {
        "name": "Українська правда. Життя",
        "level": 2,
        "type": "rss",
        "url": "https://life.pravda.com.ua/rss/",
    },
    {
        "name": "Українська правда",
        "level": 2,
        "type": "rss",
        "url": "https://www.pravda.com.ua/rss/view_news/",
    },
    {
        "name": "Укрінформ",
        "level": 2,
        "type": "rss",
        "url": "https://www.ukrinform.ua/rss/block-lastnews",
    },

    # III рівень — світова освіта та наука
    {
        "name": "Euronews",
        "level": 3,
        "type": "rss",
        "url": "https://www.euronews.com/rss?level=theme&name=next",
    },
    {
        "name": "Le Monde Education",
        "level": 3,
        "type": "rss",
        "url": "https://www.lemonde.fr/en/education/rss_full.xml",
    },

    # IV рівень — університети, інновації та суспільство
    {
        "name": "Європейська правда",
        "level": 4,
        "type": "rss",
        "url": "https://www.eurointegration.com.ua/rss/",
    },
    {
        "name": "Інтерфакс-Україна",
        "level": 4,
        "type": "rss",
        "url": "https://interfax.com.ua/news/last.rss",
    },

    # V рівень — Telegram додається пересиланням повідомлень боту.
]
