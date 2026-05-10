"""Transfer news from Spanish sports RSS feeds, filtered for Barcelona, with English translation."""

import re
import hashlib
import json
import requests
from datetime import datetime
import feedparser

RSS_FEEDS = [
    "https://www.marca.com/rss/futbol/barcelona.xml",
    "https://www.mundodeportivo.com/rss/futbol/fc-barcelona.xml",
    "https://www.sport.es/es/rss/barca/rss.xml",
]

# Spanish transfer keywords
KW_IN = [
    "fichaje", "fichar", "fichará", "incorpora", "incorporación", "refuerzo",
    "llega", "llegará", "llegada", "acuerdo.*fichar", "principio de acuerdo",
    "cerrado.*fichaje", "firma", "firmará", "nuevo jugador", "interesa",
    "pretende fichar", "quiere fichar", "objetivo.*fichar", "prioridad",
    "negocia.*fichaje", "contratación", "apunta.*llegar",
]
KW_OUT = [
    "salida", "salir", "saldrá", "vende", "vender", "venderá", "traspaso",
    "marcha", "marchará", "abandonar", "dejar.*club", "oferta por",
    "oferta.*millones", "pretende.*salir", "quiere salir",
    "negocia.*salida", "rescinde", "rescindir",
]
KW_TRANSFER = KW_IN + KW_OUT + [
    "mercado", "rumor", "rumores", "negocia", "negociación", "posible",
    "podría", "interés", "suena", "candidato", "cartera",
]

# Barcelona-specific keywords to filter non-Barça content from the feeds
BARCA_KEYWORDS = [
    "barcelona", "barça", "barca", "culé", "cule", "azulgrana", "blaugrana",
    "camp nou", "spotify camp nou", "fcb", "fc barcelona",
    "xavi", "flick", "lewa", "yamal", "pedri", "gavi", "raphinha",
    "kounde", "araujo", "balde", "de jong", "ter stegen", "cubarsí",
    "ferran torres", "ansu fati", "casadó", "olmo", "dani olmo",
    "laporta", "deco", "joan", "spotify",
]


def _is_barcelona_related(text: str) -> bool:
    """Check if the article is about FC Barcelona specifically."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in BARCA_KEYWORDS)


def _is_english(text: str) -> bool:
    """Rough detection: text is English if >90% of non-space chars are ASCII."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return True
    ascii_count = sum(1 for c in chars if ord(c) < 128)
    return ascii_count / len(chars) > 0.9


def _translate_to_english(text: str) -> str:
    """Translate text to English using Google's public translate endpoint."""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        resp = requests.get(url, params={
            "client": "gtx",
            "sl": "auto",
            "tl": "en",
            "dt": "t",
            "q": text,
        }, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        # Response format: [[["translated text", "original", ...], ...], ...]
        parts = data[0] if data else []
        return "".join(p[0] for p in parts if p and p[0])
    except Exception:
        return text  # Fallback to original


def _classify(text: str) -> str:
    """Classify article as 'in', 'out', or 'rumor'."""
    text_lower = text.lower()
    in_score = sum(1 for kw in KW_IN if re.search(kw, text_lower))
    out_score = sum(1 for kw in KW_OUT if re.search(kw, text_lower))
    if in_score > out_score:
        return "in"
    elif out_score > in_score:
        return "out"
    return "rumor"


def _extract_players(text: str) -> list[str]:
    """Naive player name extraction from Spanish headlines."""
    patterns = [
        r'(?:fichaje|traspaso|salida|llegada|incorporación)\s+de\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,2})',
        r'(?:deseo|objetivo|candidato|prioridad)\s+de\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,2})',
        r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+\s[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)(?:\s*(?:,|y|se|es|será|podría|suena|interesa|apunta))',
    ]
    players = []
    for pat in patterns:
        matches = re.findall(pat, text)
        players.extend(matches)
    return list(dict.fromkeys(players))[:3]


def fetch_transfer_news() -> list[dict]:
    """Fetch, filter, and translate Barcelona transfer news from RSS feeds."""
    articles = []
    seen = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue

        source = feed.feed.get("title", feed_url)

        for entry in feed.entries:
            title = entry.get("title", "")
            desc = entry.get("description", entry.get("summary", ""))
            text = f"{title} {desc}"

            # Filter 1: must contain transfer keywords
            if not any(re.search(kw, text.lower()) for kw in KW_TRANSFER):
                continue

            # Filter 2: must be Barcelona-related
            if not _is_barcelona_related(text):
                continue

            article_id = hashlib.md5(
                (entry.get("id", entry.get("link", title))).encode()
            ).hexdigest()[:16]

            if article_id in seen:
                continue
            seen.add(article_id)

            published = entry.get("published", entry.get("updated", ""))
            category = _classify(text)
            players = _extract_players(f"{title} {desc}")

            # Translate title to English (all RSS feeds are Spanish)
            display_title = title
            if title:
                translated = _translate_to_english(title)
                if translated and translated != title:
                    display_title = translated

            articles.append({
                "id": article_id,
                "title": display_title,
                "original_title": title if display_title != title else "",
                "link": entry.get("link", ""),
                "source": source,
                "published": published,
                "category": category,
                "players": players,
            })

    articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    return articles[:60]
