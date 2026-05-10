"""Football-Data.org v4 API client for FC Barcelona matches."""

import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.football-data.org/v4"
BARCA_TEAM_ID = 81
CURRENT_SEASON = 2025


class FootballDataAPI:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing API key. Get a free key at https://www.football-data.org/client/register "
                "and set FOOTBALL_DATA_API_KEY in a .env file."
            )
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": self.api_key})

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_team_matches(self, team_id: int = BARCA_TEAM_ID, season: int = CURRENT_SEASON) -> list[dict]:
        """Fetch all matches for a team in a given season across all competitions."""
        data = self._get(f"/teams/{team_id}/matches", params={"season": season, "limit": 200})
        return data.get("matches", [])

    @staticmethod
    def format_match(m: dict) -> dict:
        """Convert a raw API match object into our frontend-friendly format."""
        status = m.get("status", "SCHEDULED")
        utc_str = m.get("utcDate", "")
        dt = None
        if utc_str:
            try:
                dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        score = m.get("score", {})
        full_time = score.get("fullTime", {}) if score else {}

        return {
            "id": m.get("id"),
            "date": dt.isoformat() if dt else utc_str,
            "date_display": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "TBD",
            "status": status,
            "matchday": m.get("matchday"),
            "competition": (m.get("competition", {}) or {}).get("name", "Unknown"),
            "competition_emblem": (m.get("competition", {}) or {}).get("emblem"),
            "home_team": (m.get("homeTeam", {}) or {}).get("shortName", "TBD"),
            "home_crest": (m.get("homeTeam", {}) or {}).get("crest"),
            "away_team": (m.get("awayTeam", {}) or {}).get("shortName", "TBD"),
            "away_crest": (m.get("awayTeam", {}) or {}).get("crest"),
            "home_score": full_time.get("home"),
            "away_score": full_time.get("away"),
            "winner": score.get("winner") if score else None,
            "venue": m.get("venue"),
        }

    def get_all_matches_formatted(self, team_id: int = BARCA_TEAM_ID, season: int = CURRENT_SEASON) -> list[dict]:
        raw = self.get_team_matches(team_id, season)
        return [self.format_match(m) for m in raw]
