# FC Barcelona — 2025/26 Season Dashboard

A Python web app that displays **FC Barcelona's complete 2025/26 season** with match events (goals, cards), stats, and visualizations. Auto-refreshes every 5 minutes. Built with Flask, two free public APIs, and Chart.js.

## Features

- **Match events** — goalscorers, minute of goal, penalty goals, yellow/red cards for each match
- **All matches** — past, live, and upcoming in a single dashboard
- **Live indicator** — pulsing red dot + LIVE badge when a match is in progress
- **Match cards** — team crests, scores, venue, competition, matchday, with expandable events
- **Stats bar** — played, wins, draws, losses, goals, points at a glance
- **Charts** — results breakdown (doughnut), points progression (line), goals per match (bar), competition breakdown (stacked bar)
- **Auto-refresh** — polls the server every 5 minutes when the page is open; server re-fetches from APIs when cache expires
- **On-demand events** — click "Load details" on any match card to fetch events for older matches
- **Dark theme** — Barça colors, responsive layout, works on mobile

## Quick Start

### 1. Get a free API key

Sign up at [football-data.org/client/register](https://www.football-data.org/client/register) — no credit card needed, takes 30 seconds. The free tier allows 10 requests/minute.

### 2. Clone & install

```bash
git clone https://github.com/domjiang/barcelona_stats.git
cd barcelona_stats
pip install -r requirements.txt
```

### 3. Set your API key

```bash
# Windows (PowerShell)
echo "FOOTBALL_DATA_API_KEY=your_key_here" > .env

# macOS / Linux
echo "FOOTBALL_DATA_API_KEY=your_key_here" > .env
```

### 4. Run

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Browser     │────▶│  Flask app   │────▶│  football-data    │
│  (Charts.js) │◀────│  (cache 5m)  │◀────│  .org API (free)  │
└──────────────┘     └──────────────┘     └──────────────────┘
                            │
                            │ (background thread, rate-limited)
                            ▼
                     ┌──────────────┐
                     │  ESPN API    │
                     │  (keyEvents) │
                     └──────────────┘
```

- **Match listing**: football-data.org `/teams/81/matches?season=2025` (1 API call per refresh)
- **Match events**: ESPN public scoreboard + summary endpoints (no key needed). Background thread fetches events for recent matches with 3-second delays between calls.
- **Caching**: Match list cached 5 minutes; event data cached 1 hour.
- **Frontend**: polls `/api/matches` every 5 minutes; Chart.js renders charts from finished-match stats.

## Tech Stack

| Layer     | Technology                                      |
|-----------|------------------------------------------------|
| Backend   | Python 3, Flask                                 |
| APIs      | football-data.org v4 (match list) + ESPN (events) |
| Frontend  | Vanilla JS, Chart.js 4                          |
| Styling   | Custom CSS (Barça color scheme)                 |

## Project Structure

```
barcelona_stats/
├── app.py                 # Flask server, caching, stats, event enrichment
├── api_client.py          # football-data.org v4 API wrapper
├── espn_client.py         # ESPN public API — goals, cards, subs
├── requirements.txt       # Python dependencies
├── .env.example           # API key template
├── .gitignore
├── templates/
│   └── index.html         # Dashboard HTML
├── static/
│   ├── css/style.css      # Styles (dark theme, Barça colors)
│   └── js/app.js          # Frontend logic, Chart.js config, event display
└── README.md
```

## Data Shown

| Category | Details |
|----------|---------|
| Finished matches | Score (FT), result badge (W/D/L), competition, date, venue, matchday |
| Match events | Goals (scorer, minute, penalty/regular), cards (yellow/red, player, minute) |
| Live matches | Current score, LIVE badge with pulsing animation, live events |
| Upcoming matches | Date/time, competition |
| Stats | Total played, W/D/L record, goals for/against, points |
| Charts | Win/Draw/Loss doughnut, points progression line, goals per match bar, competition stacked bar |

## APIs Used

| API | Purpose | Key Required | Limit |
|-----|---------|-------------|-------|
| football-data.org v4 | Match list, scores, team info | Free key | 10 req/min |
| ESPN public API | Match events (goals, cards) | None | Public |

## Limitations

- ESPN event data depends on matching by team name + date — occasional misses for non-La Liga matches
- The free football-data.org tier does not include detailed stats (possession, shots, xG, etc.)
- football-data.org rate limit: 10 requests/minute (the 5-minute cache easily stays within this)
- Champions League and Copa del Rey event coverage depends on ESPN's availability
