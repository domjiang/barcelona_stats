"""Stadium image fetching via Wikipedia API."""

import os
import shutil
import requests
import unicodedata
import urllib.parse

STADIUMS_DIR = os.path.join(os.path.dirname(__file__), "static", "stadiums")
HEADERS = {"User-Agent": "BarcelonaStats/1.0 (https://github.com/domjiang/barcelona_stats)"}

os.makedirs(STADIUMS_DIR, exist_ok=True)


def _normalize_name(name: str) -> str:
    n = name.lower().strip()
    n = "".join(c for c in unicodedata.normalize("NFKD", n) if unicodedata.category(c) != "Mn")
    return n


def _wiki_api(params: dict) -> dict:
    url = "https://en.wikipedia.org/w/api.php"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _commons_api(params: dict) -> dict:
    url = "https://commons.wikimedia.org/w/api.php"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _search_wikipedia(stadium_name: str) -> str | None:
    """Search Wikipedia for the correct article title for a stadium."""
    data = _wiki_api({
        "action": "query", "list": "search",
        "srsearch": f"{stadium_name} stadium football",
        "srlimit": 5, "format": "json", "formatversion": 2,
    })
    pages = data.get("query", {}).get("search", [])
    if not pages:
        return None
    # Prefer exact-ish match
    norm = _normalize_name(stadium_name)
    for p in pages:
        if _normalize_name(p["title"]) == norm or norm in _normalize_name(p["title"]):
            return p["title"]
    return pages[0]["title"]


def _get_page_image(page_title: str) -> dict | None:
    """Get the main image from a Wikipedia page."""
    data = _wiki_api({
        "action": "query", "prop": "pageimages",
        "titles": page_title,
        "piprop": "thumbnail|name|original",
        "pithumbsize": 500,
        "format": "json", "formatversion": 2,
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        return None
    page = pages[0]
    thumb = page.get("thumbnail", {})
    original = page.get("original", {})
    if not thumb:
        return None
    return {
        "thumbnail_url": thumb.get("source", ""),
        "original_url": original.get("source", ""),
        "title": page_title,
        "attribution": "Wikipedia",
    }


def _commons_search(stadium_name: str) -> dict | None:
    """Fallback: search Wikimedia Commons for stadium images."""
    data = _commons_api({
        "action": "query", "generator": "search",
        "gsrsearch": f"{stadium_name} stadium",
        "gsrnamespace": 6, "gsrlimit": 3,
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": 500,
        "format": "json", "formatversion": 2,
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    first = pages[0]
    info = (first.get("imageinfo") or [{}])[0]
    return {
        "thumbnail_url": info.get("thumburl", ""),
        "original_url": info.get("url", ""),
        "title": first.get("title", ""),
        "attribution": info.get("extmetadata", {}).get("Artist", {}).get("value", "Wikimedia Commons"),
    }


def _download_image(url: str, filename: str) -> str | None:
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".jpg"
        path = os.path.join(STADIUMS_DIR, f"{filename}{ext}")
        with open(path, "wb") as f:
            f.write(resp.content)
        return f"/static/stadiums/{filename}{ext}"
    except Exception:
        return None


def get_stadium_image(stadium_name: str) -> dict | None:
    """Get stadium image URL + metadata. Returns None if not found."""
    if not stadium_name:
        return None

    # Step 1: Wikipedia pageimage
    title = _search_wikipedia(stadium_name)
    if title:
        img = _get_page_image(title)
        if img:
            safe_name = _normalize_name(stadium_name).replace(" ", "_")
            path = _download_image(img["thumbnail_url"], safe_name)
            if path:
                return {"image_path": path, "attribution": f"Wikipedia: {title}"}

    # Step 2: Commons search fallback
    commons = _commons_search(stadium_name)
    if commons:
        safe_name = _normalize_name(stadium_name).replace(" ", "_")
        path = _download_image(commons["thumbnail_url"], safe_name)
        if path:
            return {"image_path": path, "attribution": commons["attribution"]}

    return None
