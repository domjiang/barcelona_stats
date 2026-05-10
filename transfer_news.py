"""Transfer news from Spanish sports RSS feeds."""

import re
import hashlib
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
    # Common patterns: "El deseo de X", "X aprieta", "X interesa", "X, objetivo"
    patterns = [
        r'(?:fichaje|traspaso|salida|llegada|incorporación)\s+de\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,2})',
        r'(?:deseo|objetivo|candidato|prioridad)\s+de\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,2})',
        r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+\s[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)(?:\s*(?:,|y|se|es|será|podría|suena|interesa|apunta))',
    ]
    players = []
    for pat in patterns:
        matches = re.findall(pat, text)
        players.extend(matches)
    return list(dict.fromkeys(players))[:3]  # dedupe, max 3


def fetch_transfer_news() -> list[dict]:
    """Fetch and filter transfer-related news from RSS feeds."""
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

            # Filter: must contain transfer keywords
            if not any(re.search(kw, text.lower()) for kw in KW_TRANSFER):
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

            articles.append({
                "id": article_id,
                "title": title,
                "link": entry.get("link", ""),
                "source": source,
                "published": published,
                "category": category,
                "players": players,
            })

    articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    return articles[:60]  # cap at 60
