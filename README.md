# FC Barcelona — 2025/26 Season Dashboard

A Python web app that displays **FC Barcelona's complete 2025/26 season** match data with visualizations, auto-refreshing every 5 minutes. Built with Flask and the free [football-data.org](https://www.football-data.org/) API.

## Features

- **All matches** — past, live, and upcoming in a single dashboard
- **Live indicator** — pulsing red dot when a match is in progress
- **Match cards** — team crests, scores, venue, competition, matchday
- **Stats bar** — played, wins, draws, losses, goals, points at a glance
- **Charts** — results breakdown (doughnut), points progression (line), goals per match (bar), competition breakdown (stacked bar)
- **Auto-refresh** — polls the API every 5 minutes when the page is open
- **Dark theme** — Barça colors, responsive layout, works on mobile

## Quick Start

### 1. Get a free API key

Sign up at [football-data.org/client/register](https://www.football-data.org/client/register) — no credit card needed, takes 30 seconds. The free tier allows 10 requests/minute, which is plenty.

### 2. Clone & install

```bash
git clone <repo-url>
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
```

- The Flask server fetches all Barcelona matches for the 2025 season from football-data.org
- Data is cached in memory for 5 minutes to respect API rate limits
- The frontend polls `/api/matches` every 5 minutes
- Chart.js renders visualizations from the finished-match data

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Backend   | Python 3, Flask                     |
| API       | football-data.org v4 (free tier)    |
| Frontend  | Vanilla JS, Chart.js 4              |
| Styling   | Custom CSS (Barça color scheme)     |

## Project Structure

```
barcelona_stats/
├── app.py                 # Flask server, caching, stats computation
├── api_client.py          # football-data.org API wrapper
├── requirements.txt       # Python dependencies
├── .env.example           # API key template
├── .gitignore
├── templates/
│   └── index.html         # Dashboard HTML
├── static/
│   ├── css/style.css      # Styles (dark theme, Barça colors)
│   └── js/app.js          # Frontend logic, Chart.js config
└── README.md
```

## Data Shown

| Category | Details |
|----------|---------|
| Finished matches | Score (FT), result badge (W/D/L), competition, date, venue, matchday |
| Live matches | Current score, LIVE badge with pulsing animation |
| Upcoming matches | Date/time, competition |
| Stats | Total played, W/D/L record, goals for/against, points |
| Charts | Win/Draw/Loss doughnut, points progression line, goals per match bar, competition stacked bar |

## Limitations

- The free football-data.org tier does not include detailed stats (possession, shots, xG, etc.) — only scores and match metadata
- Rate limit: 10 requests/minute (the 5-minute cache easily stays within this)
- Match data depends on football-data.org availability
