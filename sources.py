from urllib.parse import quote_plus


def google_news_rss(query: str, language: str = "uk", country: str = "UA") -> str:
    encoded = quote_plus(query)
    return (
        f"https://news.google.com/rss/search?q={encoded}"
        f"&hl={language}&gl={country}&ceid={country}:{language}"
    )


# Чим менше level, тим вищий пріоритет.
# Джерела читаються через Google News RSS із фільтром по сайту.
SOURCES = [
    {
        "name": 'Львівська політехніка',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:lpnu.ua ("Львівська політехніка" OR студент OR вступ OR наука OR освіта OR грант OR стипендія OR гуртожиток)'),
    },
    {
        "name": 'Львівська міська рада — освіта',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:city-adm.lviv.ua (освіта OR університет OR студент OR наука OR молодь)'),
    },
    {
        "name": 'Львівська ОВА — освіта',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:loda.gov.ua (освіта OR університет OR студент OR наука OR молодь)'),
    },
    {
        "name": 'ZAXID.NET',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:zaxid.net ("Львівська політехніка" OR освіта OR університет OR студент OR вступ)'),
    },
    {
        "name": 'Твоє Місто',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:tvoemisto.tv ("Львівська політехніка" OR освіта OR університет OR студент OR вступ)'),
    },
    {
        "name": 'Дивись.info',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:dyvys.info ("Львівська політехніка" OR освіта OR університет OR студент OR вступ)'),
    },
    {
        "name": 'LVIV.MEDIA — освіта',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:lviv.media ("Львівська політехніка" OR освіта OR університет OR студент OR вступ)'),
    },
    {
        "name": 'Гал-Інфо — освіта Львова',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:galinfo.com.ua ("Львівська політехніка" OR освіта OR університет OR студент OR вступ)'),
    },
    {
        "name": 'Суспільне Львів — освіта',
        "level": 1,
        "type": "rss",
        "url": google_news_rss('site:suspilne.media/lviv ("Львівська політехніка" OR освіта OR університет OR студент OR вступ)'),
    },
    {
        "name": 'МОН України',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:mon.gov.ua (освіта OR університет OR вступ OR студент OR наука OR стипендія OR грант)'),
    },
    {
        "name": 'НАЗЯВО',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:naqa.gov.ua (акредитація OR університет OR "якість освіти" OR освітня програма)'),
    },
    {
        "name": 'УЦОЯО',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:testportal.gov.ua (НМТ OR вступ OR тестування OR ЄВІ OR ЄФВВ)'),
    },
    {
        "name": 'Львівський РЦОЯО',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:lv.testportal.gov.ua (НМТ OR вступ OR тестування)'),
    },
    {
        "name": 'Освіта.ua',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:osvita.ua (освіта OR університет OR вступ OR НМТ OR студент OR рейтинг)'),
    },
    {
        "name": 'Освіторія',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:osvitoria.media (освіта OR університет OR вступ OR НМТ OR студент)'),
    },
    {
        "name": 'Українська правда. Життя — освіта',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:life.pravda.com.ua (освіта OR університет OR студент OR наука OR вступ)'),
    },
    {
        "name": 'Дзеркало тижня — освіта',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:zn.ua/ukr (освіта OR університет OR вступ OR студент OR наука)'),
    },
    {
        "name": 'Укрінформ — освіта',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:ukrinform.ua (освіта OR університет OR вступ OR НМТ OR студент OR наука)'),
    },
    {
        "name": 'Суспільне — освіта України',
        "level": 2,
        "type": "rss",
        "url": google_news_rss('site:suspilne.media (освіта OR університет OR вступ OR НМТ OR студент)'),
    },
    {
        "name": 'Times Higher Education',
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:timeshighereducation.com (Ukraine OR Ukrainian) university education ranking', language='en', country='US'),
    },
    {
        "name": 'QS Top Universities',
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:topuniversities.com (Ukraine OR Ukrainian) university ranking', language='en', country='US'),
    },
    {
        "name": 'UNESCO — Ukraine education',
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:unesco.org Ukraine education university science', language='en', country='US'),
    },
    {
        "name": 'European University Association',
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:eua.eu Ukraine university higher education', language='en', country='US'),
    },
    {
        "name": 'Erasmus+',
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:erasmus-plus.ec.europa.eu Ukraine university students Erasmus', language='en', country='US'),
    },
    {
        "name": 'European Education Area',
        "level": 3,
        "type": "rss",
        "url": google_news_rss('site:education.ec.europa.eu Ukraine higher education university students', language='en', country='US'),
    },
    {
        "name": 'Horizon Europe — Україна',
        "level": 4,
        "type": "rss",
        "url": google_news_rss('site:research-and-innovation.ec.europa.eu Ukraine Horizon Europe university research grant', language='en', country='US'),
    },
    {
        "name": 'Українські університети — гранти та інновації',
        "level": 4,
        "type": "rss",
        "url": google_news_rss('(університет OR інститут) (грант OR патент OR акредитація OR лабораторія OR стартап OR інновації OR конкурс OR працевлаштування)'),
    },

    {
        "name": "Львівський портал",
        "level": 1,
        "type": "rss",
        "url": google_news_rss(
            'site:portal.lviv.ua ("Львівська політехніка" OR освіта OR університет OR студент OR вступ OR ректор OR гуртожиток)'
        ),
    },
    {
        "name": "Вголос",
        "level": 1,
        "type": "rss",
        "url": google_news_rss(
            'site:vgolos.ua ("Львівська політехніка" OR освіта OR університет OR студент OR вступ OR ректор OR гуртожиток)'
        ),
    },
    {
        "name": "Варіанти",
        "level": 1,
        "type": "rss",
        "url": google_news_rss(
            'site:varianty.lviv.ua ("Львівська політехніка" OR освіта OR університет OR студент OR вступ OR ректор OR гуртожиток)'
        ),
    },
    {
        "name": "Українські Новини",
        "level": 2,
        "type": "rss",
        "url": google_news_rss(
            'site:ukranews.com/ua ("Львівська політехніка" OR освіта OR університет OR студент OR вступ OR НМТ OR наука)'
        ),
    },
    {
        "name": "Львівич",
        "level": 1,
        "type": "telegram_html",
        "url": "https://t.me/s/lvivych_news",
    },
]
