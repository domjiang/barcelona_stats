"""Flask web app — FC Barcelona 2025/26 season match dashboard."""

import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from api_client import FootballDataAPI
from espn_client import get_match_events
from venues import get_venue
import db
import stadiums as stadium_module
import transfer_news

load_dotenv()

app = Flask(__name__)

# In-memory cache for fast API responses
_cache: dict = {
    "last_updated": None,
    "error": None,
    "finished": [],
    "upcoming": [],
    "live": [],
    "stats": {},
    "all_events": {},
}
_cache_lock = threading.Lock()
CACHE_TTL = 5 * 60  # 5 min
EVENTS_FETCH_DELAY = 3  # sec between ESPN calls


def _compute_stats(matches: list[dict]) -> dict:
    finished = [m for m in matches if m["status"] == "FINISHED"]
    wins = sum(1 for m in finished if m["winner"] == "HOME_TEAM" and m["home_team"] == "Barça"
               or m["winner"] == "AWAY_TEAM" and m["away_team"] == "Barça")
    draws = sum(1 for m in finished if m["winner"] == "DRAW")
    losses = sum(1 for m in finished if m["winner"] and m["winner"] not in ("DRAW", None)
               and not (
                   m["winner"] == "HOME_TEAM" and m["home_team"] == "Barça"
                   or m["winner"] == "AWAY_TEAM" and m["away_team"] == "Barça"
               ))
    gf = sum(
        (m["home_score"] or 0) if m["home_team"] == "Barça" else (m["away_score"] or 0)
        for m in finished
    )
    ga = sum(
        (m["away_score"] or 0) if m["home_team"] == "Barça" else (m["home_score"] or 0)
        for m in finished
    )
    points = wins * 3 + draws

    competitions = {}
    for m in finished:
        comp = m.get("competition", "Unknown")
        if comp not in competitions:
            competitions[comp] = {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0}
        c = competitions[comp]
        c["played"] += 1
        c["gf"] += (m["home_score"] or 0) if m["home_team"] == "Barça" else (m["away_score"] or 0)
        c["ga"] += (m["away_score"] or 0) if m["home_team"] == "Barça" else (m["home_score"] or 0)
        is_win = (m["winner"] == "HOME_TEAM" and m["home_team"] == "Barça") or \
                 (m["winner"] == "AWAY_TEAM" and m["away_team"] == "Barça")
        if is_win:
            c["wins"] += 1
        elif m["winner"] == "DRAW":
            c["draws"] += 1
        else:
            c["losses"] += 1

    timeline = []
    cum_points = 0
    for m in sorted(finished, key=lambda x: x["date"]):
        is_win = (m["winner"] == "HOME_TEAM" and m["home_team"] == "Barça") or \
                 (m["winner"] == "AWAY_TEAM" and m["away_team"] == "Barça")
        is_draw = m["winner"] == "DRAW"
        cum_points += 3 if is_win else (1 if is_draw else 0)
        goals = (m["home_score"] or 0) if m["home_team"] == "Barça" else (m["away_score"] or 0)
        timeline.append({
            "label": f"MD{m.get('matchday', '?')}",
            "opponent": m["away_team"] if m["home_team"] == "Barça" else m["home_team"],
            "points": cum_points,
            "goals": goals,
        })

    return {
        "total": len(matches),
        "played": len(finished),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": gf,
        "goals_against": ga,
        "goal_diff": gf - ga,
        "points": points,
        "competitions": competitions,
        "timeline": timeline,
    }


def categorize(matches: list[dict]) -> dict:
    live = []; finished = []; upcoming = []
    for m in matches:
        s = m["status"]
        if s in ("IN_PLAY", "PAUSED"):
            live.append(m)
        elif s == "FINISHED":
            finished.append(m)
        else:
            upcoming.append(m)
    finished.sort(key=lambda x: x["date"], reverse=True)
    upcoming.sort(key=lambda x: x["date"])
    return {"live": live, "finished": finished, "upcoming": upcoming}


def _enrich_events(matches: list[dict]):
    """Background: fetch ESPN events for recent/live matches, save to DB."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    now = datetime.now(timezone.utc)

    for m in matches:
        mid = m["id"]
        status = m["status"]

        try:
            mdate = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            mdate = None

        should_fetch = (
            status in ("IN_PLAY", "PAUSED")
            or (status == "FINISHED" and mdate and mdate > thirty_days_ago)
        )

        if not should_fetch:
            continue

        # Check DB for existing events
        existing = db.load_events(mid)
        if existing and existing.get("found"):
            if status == "FINISHED":
                continue  # Finished + stored = done
            if not db.is_events_stale(mid):
                continue

        try:
            events = get_match_events(
                competition=m.get("competition", ""),
                home_team=m.get("home_team", ""),
                away_team=m.get("away_team", ""),
                match_date=m.get("date", ""),
            )
            if events.get("found"):
                db.save_events(mid, {"goals": events["goals"], "cards": events["cards"], "found": True})
        except Exception:
            pass

        time.sleep(EVENTS_FETCH_DELAY)


def _load_events_from_db(match_ids: list[int]) -> dict:
    result = {}
    for mid in match_ids:
        ev = db.load_events(mid)
        if ev:
            result[mid] = ev
    return result


def refresh_cache():
    global _cache
    try:
        api = FootballDataAPI()

        # Try DB first
        if not db.is_match_list_stale():
            matches = db.load_matches()
        else:
            matches = api.get_all_matches_formatted()
            db.save_matches(matches)

        categorized = categorize(matches)
        stats = _compute_stats(matches)

        # Load events from DB
        all_ids = [m["id"] for m in matches]
        all_events = _load_events_from_db(all_ids)

        with _cache_lock:
            _cache = {
                "matches": matches,
                "finished": categorized["finished"],
                "upcoming": categorized["upcoming"],
                "live": categorized["live"],
                "stats": stats,
                "all_events": all_events,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "error": None,
            }

        # Background: fetch missing events from ESPN
        needs_events = [
            m for m in matches
            if m["id"] not in all_events or not all_events[m["id"]].get("found")
        ]
        if needs_events:
            t = threading.Thread(target=_enrich_events, args=(needs_events,), daemon=True)
            t.start()

    except Exception as e:
        # Fall back to DB if API fails
        db_matches = db.load_matches()
        if db_matches:
            categorized = categorize(db_matches)
            stats = _compute_stats(db_matches)
            all_ids = [m["id"] for m in db_matches]
            all_events = _load_events_from_db(all_ids)
            with _cache_lock:
                _cache = {
                    "matches": db_matches,
                    "finished": categorized["finished"],
                    "upcoming": categorized["upcoming"],
                    "live": categorized["live"],
                    "stats": stats,
                    "all_events": all_events,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "error": None,
                }
        else:
            with _cache_lock:
                _cache["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/matches")
def api_matches():
    with _cache_lock:
        needs_refresh = _cache["last_updated"] is None or (
            datetime.now(timezone.utc) - datetime.fromisoformat(_cache["last_updated"])
        ).total_seconds() >= CACHE_TTL

    if needs_refresh:
        refresh_cache()

    with _cache_lock:
        events = _cache.get("all_events", {})

        def attach(matches):
            result = []
            for m in (matches or []):
                m = dict(m)
                m["events"] = events.get(m["id"], {})
                is_barca_home = m.get("home_team") in ("Barça", "Barcelona")
                m["is_home"] = is_barca_home
                # Venue + stadium image
                home_team = m.get("home_team", "")
                venue_name = get_venue(home_team)
                m["stadium_name"] = venue_name
                # Embed stadium image URL directly
                if venue_name:
                    cached = db.load_stadium(venue_name)
                    m["stadium_img"] = cached["image_path"] if cached else ""
                else:
                    m["stadium_img"] = ""
                result.append(m)
            return result

        return jsonify({
            "last_updated": _cache["last_updated"],
            "finished": attach(_cache.get("finished", [])),
            "upcoming": attach(_cache.get("upcoming", [])),
            "live": attach(_cache.get("live", [])),
            "stats": _cache.get("stats", {}),
            "error": _cache.get("error"),
        })


@app.route("/api/match/<int:match_id>/events")
def api_match_events(match_id):
    """Fetch events for a specific match on-demand."""
    existing = db.load_events(match_id)
    if existing and existing.get("found"):
        return jsonify({"events": existing, "cached": True})

    with _cache_lock:
        all_matches = _cache.get("matches", [])
    match_data = None
    for m in all_matches:
        if m["id"] == match_id:
            match_data = m
            break

    if not match_data:
        return jsonify({"error": "Match not found"}), 404

    try:
        events = get_match_events(
            competition=match_data.get("competition", ""),
            home_team=match_data.get("home_team", ""),
            away_team=match_data.get("away_team", ""),
            match_date=match_data.get("date", ""),
        )
        if events.get("found"):
            result = {"goals": events["goals"], "cards": events["cards"], "found": True}
            db.save_events(match_id, result)
            with _cache_lock:
                _cache["all_events"][match_id] = result
            return jsonify({"events": result, "cached": False})
        return jsonify({"events": {"goals": [], "cards": [], "found": False}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    refresh_cache()
    with _cache_lock:
        return jsonify({"last_updated": _cache["last_updated"], "error": _cache.get("error")})


@app.route("/api/transfers")
def api_transfers():
    """Return categorized transfer news from DB/cache."""
    if not db.is_transfer_news_stale():
        articles = db.load_transfer_articles()
    else:
        articles = transfer_news.fetch_transfer_news()
        if articles:
            db.upsert_transfer_articles(articles)

    categories = {"in": [], "rumor": [], "out": []}
    for a in articles:
        cat = a.get("category", "rumor")
        if cat in categories:
            categories[cat].append({
                "id": a["id"],
                "title": a["title"],
                "original_title": a.get("original_title", ""),
                "link": a["link"],
                "source": a["source"],
                "published": a.get("published", ""),
                "players": a.get("players", "").split(",") if a.get("players") else [],
            })

    return jsonify({"categories": categories, "stale": db.is_transfer_news_stale()})


@app.route("/api/stadium-image")
def api_stadium_image():
    """Get stadium image for a given venue name."""
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing name"}), 400

    # Check DB
    cached = db.load_stadium(name)
    if cached:
        return jsonify(cached)

    # Fetch from Wikipedia
    result = stadium_module.get_stadium_image(name)
    if result:
        db.save_stadium(name, result["image_path"], result.get("attribution", ""))
        return jsonify(result)

    return jsonify({"image_path": None, "error": "Not found"})


@app.route("/api/transfer-refresh", methods=["POST"])
def api_transfer_refresh():
    articles = transfer_news.fetch_transfer_news()
    if articles:
        db.upsert_transfer_articles(articles)
    return jsonify({"count": len(articles)})


def startup_refresh():
    """Force refresh all data on server start."""
    print("[startup] Refreshing match data...")
    refresh_cache()

    print("[startup] Pre-loading transfer news...")
    try:
        articles = transfer_news.fetch_transfer_news()
        if articles:
            db.upsert_transfer_articles(articles)
            print(f"[startup] Transfer news: {len(articles)} articles loaded")
    except Exception as e:
        print(f"[startup] Transfer news skipped: {e}")

    print("[startup] Pre-loading stadium images for known venues...")
    try:
        with _cache_lock:
            matches = _cache.get("matches", [])
        venues = set()
        for m in matches:
            v = get_venue(m.get("home_team", ""))
            if v:
                venues.add(v)
        for venue in venues:
            if not db.load_stadium(venue):
                try:
                    result = stadium_module.get_stadium_image(venue)
                    if result:
                        db.save_stadium(venue, result["image_path"], result.get("attribution", ""))
                        print(f"[startup] Stadium: {venue} -> {result['image_path']}")
                except Exception:
                    pass
    except Exception as e:
        print(f"[startup] Stadium pre-load skipped: {e}")

    print("[startup] Ready.")


if __name__ == "__main__":
    startup_refresh()
    app.run(host="0.0.0.0", port=5000, debug=True)
