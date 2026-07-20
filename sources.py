from urllib.parse import quote_plus


def google_news_rss(query: str, language: str = "uk", country: str = "UA") -> str:
    encoded = quote_plus(query)
    return (
        f"https://news.google.com/rss/search?q={encoded}"
        f"&hl={language}&gl={country}&ceid={country}:{language}"
    )


# Кожне джерело має рівень 1–5. Чим менше число, тим вищий пріоритет.
# type="rss" означає, що бот читає RSS/Atom-стрічку.
SOURCES = [
    # I рівень — Львів і Львівська політехніка
    {
        "name": "Львівська політехніка",
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:lpnu.ua ("Львівська політехніка" OR студент OR наука OR освіта)'),
    },
    {
        "name": "Львівська міська рада — освіта",
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:city-adm.lviv.ua (освіта OR університет OR студент OR наука)'),
    },
    {
        "name": "Львівська ОВА — освіта",
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:loda.gov.ua (освіта OR університет OR студент OR наука)'),
    },
    {
        "name": "ZAXID.NET — освіта Львова",
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:zaxid.net ("Львівська політехніка" OR освіта OR університет OR студент)'),
    },
    {
        "name": "Твоє Місто — освіта",
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:tvoemisto.tv (освіта OR університет OR студент OR "Львівська політехніка")'),
    },
    {
        "name": "Дивись.info — освіта",
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:dyvys.info (освіта OR університет OR студент OR "Львівська політехніка")'),
    },

    # II рівень — освіта України
    {
        "name": "МОН України",
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:mon.gov.ua (освіта OR університет OR вступ OR студент OR наука)'),
    },
    {
        "name": "НАЗЯВО",
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:naqa.gov.ua (акредитація OR університет OR якість освіти)'),
    },
    {
        "name": "УЦОЯО",
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:testportal.gov.ua (НМТ OR вступ OR тестування)'),
    },
    {
        "name": "Освіта.ua",
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:osvita.ua (освіта OR університет OR вступ OR НМТ OR студент)'),
    },
    {
        "name": "Українська правда. Життя — освіта",
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:life.pravda.com.ua (освіта OR університет OR студент OR наука)'),
    },
    {
        "name": "Дзеркало тижня — освіта",
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:zn.ua/ukr/EDUCATION (освіта OR університет OR студент OR наука)'),
    },

    # III рівень — світова освіта
    {
        "name": "Times Higher Education",
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:timeshighereducation.com (Ukraine OR Ukrainian) university education'),
    },
    {
        "name": "QS Top Universities",
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:topuniversities.com (Ukraine OR Ukrainian) university ranking'),
    },
    {
        "name": "UNESCO — Ukraine education",
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:unesco.org Ukraine education university science'),
    },
    {
        "name": "European University Association",
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:eua.eu Ukraine university education'),
    },
    {
        "name": "Erasmus+ Ukraine",
        "level": 3,
        "type": "rss",
        "url": google_news_rss('(Erasmus OR Erasmus+) Ukraine students university grant'),
    },

    # IV рівень — рейтинг інститутів та університетів
    {
        "name": "Інститути та університети України",
        "level": 4,
        "type": "rss",
        "url": google_news_rss(
            '(університет OR інститут) '
            '(грант OR патент OR акредитація OR лабораторія OR стартап OR конкурс OR працевлаштування)'
        ),
    },

    # V рівень — Telegram у цій версії додається через пересилання постів боту.
]
