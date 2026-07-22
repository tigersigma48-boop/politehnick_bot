# Джерела, які у твоїх логах уже віддавали матеріали без помилок 403/404.
# type="rss" — RSS/Atom; type="html" — сторінка новин.

SOURCES = [
    {
        "name": "Львівська політехніка",
        "level": 1,
        "type": "html",
        "url": "https://lpnu.ua/news",
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
    {
        "name": "Європейська правда",
        "level": 3,
        "type": "rss",
        "url": "https://www.eurointegration.com.ua/rss/",
    },
    {
        "name": "Інтерфакс-Україна",
        "level": 3,
        "type": "rss",
        "url": "https://interfax.com.ua/news/last.rss",
    },
]
