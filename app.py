"""Flask web app — FC Barcelona 2025/26 season match dashboard."""

import os
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from api_client import FootballDataAPI

load_dotenv()

app = Flask(__name__)

# In-memory cache
_cache: dict = {
    "matches": [],
    "last_updated": None,
    "error": None,
}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 5 * 60  # 5 minutes


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

    # Competition breakdown
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

    # Match-by-match for line charts
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
    except Exception as e:
        with _cache_lock:
            _cache["error"] = str(e)


def get_cached_data() -> dict:
    with _cache_lock:
        if _cache["last_updated"] is None:
            return _cache  # triggers refresh below
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(_cache["last_updated"])).total_seconds()
        if age < CACHE_TTL_SECONDS:
            return _cache
    return _cache  # will have stale flag checked below


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
        return jsonify({
            "last_updated": _cache["last_updated"],
            "finished": _cache.get("finished", []),
            "upcoming": _cache.get("upcoming", []),
            "live": _cache.get("live", []),
            "stats": _cache.get("stats", {}),
            "error": _cache.get("error"),
        })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    refresh_cache()
    with _cache_lock:
        return jsonify({"last_updated": _cache["last_updated"], "error": _cache.get("error")})


if __name__ == "__main__":
    refresh_cache()
    app.run(host="0.0.0.0", port=5000, debug=True)
