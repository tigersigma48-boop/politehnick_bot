# Лише освітні джерела. Без загальнополітичних RSS і без Google News.

SOURCES = [
    {
        "name": "Львівська політехніка",
        "level": 1,
        "type": "html",
        "url": "https://lpnu.ua/news",
        "link_pattern": r"^/news/",
        "max_items": 30,
    },
    {
        "name": "Міністерство освіти і науки України",
        "level": 2,
        "type": "html",
        "url": "https://mon.gov.ua/news",
        "link_pattern": r"^/news/",
        "max_items": 30,
    },
    {
        "name": "Освіта.ua",
        "level": 2,
        "type": "rss",
        "url": "https://osvita.ua/rss/",
    },
    {
        "name": "Українська правда. Життя",
        "level": 3,
        "type": "rss",
        "url": "https://life.pravda.com.ua/rss/",
    },
]
