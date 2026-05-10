"""Flask web app — FC Barcelona 2025/26 season match dashboard."""

import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from api_client import FootballDataAPI
from espn_client import get_match_events

load_dotenv()

app = Flask(__name__)

# In-memory cache
_cache: dict = {
    "matches": [],
    "last_updated": None,
    "error": None,
}
# { match_id: { "goals": [...], "cards": [...] } }
_events_cache: dict = {}
_events_last_fetched: dict[str, datetime] = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 5 * 60  # 5 minutes
EVENTS_TTL_SECONDS = 60 * 60  # 1 hour for events


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
    live = []
    finished = []
    upcoming = []
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


def _enrich_with_events(matches: list[dict]):
    """Fetch ESPN events for recent/live matches in background."""
    global _events_cache, _events_last_fetched
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    now = datetime.now(timezone.utc)

    for m in matches:
        mid = str(m["id"])

        # Skip if recently fetched
        with _cache_lock:
            last = _events_last_fetched.get(mid)
            if last and (now - last).total_seconds() < EVENTS_TTL_SECONDS:
                continue

        # Only fetch for: live matches, finished within 30 days, or upcoming within 3 days
        status = m["status"]
        try:
            mdate = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            mdate = None

        should_fetch = (
            status in ("IN_PLAY", "PAUSED")
            or (status == "FINISHED" and mdate and mdate > thirty_days_ago)
            or (mdate and mdate > now and mdate - now < timedelta(days=3))
        )

        if not should_fetch:
            continue

        try:
            events = get_match_events(
                competition=m.get("competition", ""),
                home_team=m.get("home_team", ""),
                away_team=m.get("away_team", ""),
                match_date=m.get("date", ""),
            )
            if events.get("found"):
                with _cache_lock:
                    _events_cache[mid] = {"goals": events["goals"], "cards": events["cards"]}
                    _events_last_fetched[mid] = now
        except Exception:
            pass  # Silently skip ESPN failures

        time.sleep(3)  # Be gentle with ESPN's API


def refresh_cache():
    global _cache
    try:
        api = FootballDataAPI()
        matches = api.get_all_matches_formatted()
        categorized = categorize(matches)
        stats = _compute_stats(matches)
        with _cache_lock:
            _cache = {
                "matches": matches,
                "finished": categorized["finished"],
                "upcoming": categorized["upcoming"],
                "live": categorized["live"],
                "stats": stats,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "error": None,
            }
        # Start background thread to fetch events
        t = threading.Thread(target=_enrich_with_events, args=(matches,), daemon=True)
        t.start()
    except Exception as e:
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
        ).total_seconds() >= CACHE_TTL_SECONDS

    if needs_refresh:
        refresh_cache()

    with _cache_lock:
        # Attach events to matches
        def attach_events(matches):
            result = []
            for m in (matches or []):
                m = dict(m)
                m["events"] = _events_cache.get(str(m["id"]), {})
                result.append(m)
            return result

        return jsonify({
            "last_updated": _cache["last_updated"],
            "finished": attach_events(_cache.get("finished", [])),
            "upcoming": attach_events(_cache.get("upcoming", [])),
            "live": attach_events(_cache.get("live", [])),
            "stats": _cache.get("stats", {}),
            "error": _cache.get("error"),
        })


@app.route("/api/match/<int:match_id>/events")
def api_match_events(match_id):
    """Fetch events for a specific match on-demand."""
    mid = str(match_id)

    # Check cache
    with _cache_lock:
        cached = _events_cache.get(mid)
        last = _events_last_fetched.get(mid)
        now = datetime.now(timezone.utc)
        if cached and last and (now - last).total_seconds() < EVENTS_TTL_SECONDS:
            return jsonify({"events": cached, "cached": True})

    # Find the match in our data
    with _cache_lock:
        all_matches = _cache.get("matches", [])
    match_data = None
    for m in all_matches:
        if str(m["id"]) == mid:
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
            result = {"goals": events["goals"], "cards": events["cards"]}
            with _cache_lock:
                _events_cache[mid] = result
                _events_last_fetched[mid] = now
            return jsonify({"events": result, "cached": False})
        return jsonify({"events": {"goals": [], "cards": []}, "found": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    refresh_cache()
    with _cache_lock:
        return jsonify({"last_updated": _cache["last_updated"], "error": _cache.get("error")})


if __name__ == "__main__":
    refresh_cache()
    app.run(host="0.0.0.0", port=5000, debug=True)
