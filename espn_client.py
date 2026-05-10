"""ESPN public API client — match events (goals, cards, subs)."""

import re
import time
from datetime import datetime, timedelta

import requests

# ESPN league codes
ESPN_LEAGUES = {
    "Primera Division": "ESP.1",
    "UEFA Champions League": "UEFA.CHAMPIONS",
    "Copa del Rey": "CDR",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _scoreboard(league: str, date_from: str, date_to: str) -> list[dict]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
    resp = requests.get(url, params={"dates": f"{date_from}-{date_to}"}, headers=HEADERS, timeout=15)
    if resp.status_code >= 400:
        return []
    resp.raise_for_status()
    return resp.json().get("events", [])


def _match_summary(league: str, event_id: str) -> dict:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary"
    resp = requests.get(url, params={"event": event_id}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _normalize(name: str) -> str:
    """Normalize team name for fuzzy matching."""
    import unicodedata
    n = name.lower().strip()
    # Remove accents: "barça" → "barca"
    n = "".join(c for c in unicodedata.normalize("NFKD", n) if unicodedata.category(c) != "Mn")
    n = n.replace("fc ", "").replace("cf ", "")
    # Map common abbreviations
    aliases = {
        "barca": "barcelona",
        "athletic": "athletic club",
        "atleti": "atletico madrid",
        "atletico": "atletico madrid",
        "real madrid": "real madrid",
        "espanyol": "espanyol",
    }
    return aliases.get(n, n)


def find_match(competition: str, home_team: str, away_team: str, match_date: str) -> dict | None:
    """Find an ESPN match event given teams + date from football-data.org."""
    league = ESPN_LEAGUES.get(competition)
    if not league:
        return None

    try:
        dt = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

    # Search +/- 2 days
    date_from = (dt - timedelta(days=2)).strftime("%Y%m%d")
    date_to = (dt + timedelta(days=2)).strftime("%Y%m%d")

    events = _scoreboard(league, date_from, date_to)
    home_norm = _normalize(home_team)
    away_norm = _normalize(away_team)

    for ev in events:
        comps = ev.get("competitions", [{}])[0]
        teams = comps.get("competitors", [])
        if len(teams) < 2:
            continue
        h_name = _normalize(teams[0].get("team", {}).get("displayName", ""))
        a_name = _normalize(teams[1].get("team", {}).get("displayName", ""))

        # Match home vs home and away vs away (or reversed if ESPN has them flipped)
        if (home_norm in h_name and away_norm in a_name) or (home_norm in a_name and away_norm in h_name):
            return {"event_id": ev["id"], "league": league}

    return None


def get_match_events(competition: str, home_team: str, away_team: str, match_date: str) -> dict:
    """Get key events (goals, cards) for a match. Returns empty if not found."""
    match_info = find_match(competition, home_team, away_team, match_date)
    if not match_info:
        return {"goals": [], "cards": [], "found": False}

    summary = _match_summary(match_info["league"], match_info["event_id"])
    key_events = summary.get("keyEvents", [])

    goals = []
    cards = []

    for ev in key_events:
        etype = ev.get("type", {}).get("text", "")
        team_name = ev.get("team", {}).get("displayName", "")
        players = ev.get("participants", [])
        scorer = players[0].get("athlete", {}).get("displayName", "") if players else ""
        minute = ev.get("clock", {}).get("displayValue", "?")

        is_barca = "barcelona" in _normalize(team_name)

        if "Goal" in etype or "Penalty" in etype or "goal" in etype.lower():
            goals.append({
                "minute": minute,
                "scorer": scorer,
                "team": team_name,
                "is_barca": is_barca,
                "type": "PENALTY" if "penalty" in etype.lower() else "REGULAR",
            })
        elif "Card" in etype or "Yellow" in etype or "Red" in etype:
            cards.append({
                "minute": minute,
                "player": scorer,
                "team": team_name,
                "is_barca": is_barca,
                "card": "RED" if "red" in etype.lower() else "YELLOW",
            })

    return {"goals": goals, "cards": cards, "found": True}
