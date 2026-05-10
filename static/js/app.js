// FC Barcelona 2025/26 — Frontend Dashboard

const REFRESH_MS = 5 * 60 * 1000;
let charts = {};
let currentTab = "all";

// ===== Init =====
document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    document.getElementById("btn-refresh").addEventListener("click", fetchAndRender);
    fetchAndRender();
    setInterval(fetchAndRender, REFRESH_MS);
});

// ===== Data fetching =====
async function fetchAndRender() {
    try {
        const resp = await fetch("/api/matches");
        const data = await resp.json();
        if (data.error) {
            showError(`API Error: ${data.error}\n\nGet a free key at https://www.football-data.org/client/register`);
        } else {
            hideError();
        }
        render(data);
    } catch (err) {
        showError(`Failed to connect to server: ${err.message}`);
    }
}

// ===== Tab switching =====
function setupTabs() {
    document.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
            const target = "tab-" + tab.dataset.tab;
            const el = document.getElementById(target);
            if (el) el.classList.remove("hidden");
            currentTab = tab.dataset.tab;
        });
    });
}

// ===== Main render =====
function render(data) {
    const all = [...(data.finished || []), ...(data.live || []), ...(data.upcoming || [])]
        .sort((a, b) => new Date(a.date) - new Date(b.date));

    document.getElementById("update-time").textContent =
        "Updated: " + (data.last_updated ? formatTime(data.last_updated) : "never");

    // LIVE dot
    const liveDot = document.getElementById("live-dot");
    const liveCount = document.getElementById("live-count");
    const liveCountNum = data.live ? data.live.length : 0;
    if (liveCountNum > 0) {
        liveDot.classList.remove("hidden");
        liveCount.textContent = liveCountNum;
        liveCount.classList.remove("hidden");
    } else {
        liveDot.classList.add("hidden");
        liveCount.classList.add("hidden");
    }

    // Stats
    const st = data.stats || {};
    document.getElementById("stat-played").textContent = st.played ?? "-";
    document.getElementById("stat-wins").textContent = st.wins ?? "-";
    document.getElementById("stat-draws").textContent = st.draws ?? "-";
    document.getElementById("stat-losses").textContent = st.losses ?? "-";
    document.getElementById("stat-gf").textContent = st.goals_for ?? "-";
    document.getElementById("stat-ga").textContent = st.goals_against ?? "-";
    document.getElementById("stat-points").textContent = st.points ?? "-";

    // Render tab contents
    document.getElementById("tab-all").innerHTML = renderMatchList(all);
    document.getElementById("tab-finished").innerHTML = renderMatchList(data.finished || []);
    document.getElementById("tab-upcoming").innerHTML = renderMatchList(data.upcoming || []);
    document.getElementById("tab-live").innerHTML = renderMatchList(data.live || []);
    document.getElementById("tab-live").classList.toggle("hidden", liveCountNum === 0);

    // Auto-switch to LIVE tab if there are live matches and user isn't viewing charts
    if (liveCountNum > 0) {
        document.getElementById("tab-live").classList.remove("hidden");
    }

    // Charts
    renderCharts(data);
}

// ===== Match list HTML =====
function renderMatchList(matches) {
    if (!matches || matches.length === 0) {
        return '<p style="color:var(--text-muted);text-align:center;padding:40px;">No matches to display</p>';
    }
    return matches.map(m => renderMatchCard(m)).join("");
}

function renderMatchCard(m) {
    const status = m.status;
    const isFinished = status === "FINISHED";
    const isLive = status === "IN_PLAY" || status === "PAUSED";
    const isBarcaHome = m.home_team === "Barça" || m.home_team === "Barcelona";

    let badge = "";
    if (isLive) {
        badge = '<span class="match-badge badge-live">● LIVE ' + (status === "PAUSED" ? "(Paused)" : "") + "</span>";
    } else if (isFinished) {
        const won = (m.winner === "HOME_TEAM" && isBarcaHome) || (m.winner === "AWAY_TEAM" && !isBarcaHome);
        const draw = m.winner === "DRAW";
        if (won) badge = '<span class="match-badge badge-win">W</span>';
        else if (draw) badge = '<span class="match-badge badge-draw">D</span>';
        else badge = '<span class="match-badge badge-loss">L</span>';
    } else {
        badge = '<span class="match-badge badge-upcoming">' + formatDateShort(m.date) + "</span>";
    }

    let scoreHtml = "";
    if (isFinished && m.home_score !== null && m.away_score !== null) {
        scoreHtml = `
            <div class="match-score">
                <span class="score-num">${m.home_score} - ${m.away_score}</span>
                <span class="score-label">FT</span>
            </div>`;
    } else if (isLive && m.home_score !== null && m.away_score !== null) {
        scoreHtml = `
            <div class="match-score">
                <span class="score-num" style="color:var(--live)">${m.home_score} - ${m.away_score}</span>
                <span class="score-label">LIVE</span>
            </div>`;
    } else {
        scoreHtml = `
            <div class="match-score">
                <span class="score-num" style="color:var(--text-muted)">vs</span>
            </div>`;
    }

    const venue = m.venue ? `<br>📍 ${m.venue}` : "";

    return `
        <div class="match-card status-${status}">
            <div class="match-meta">
                <span class="competition">${m.competition}</span>
                <span class="date">${isLive ? "⚡ NOW" : m.date_display}${venue}</span>
                ${m.matchday ? '<span class="date">Matchday ' + m.matchday + "</span>" : ""}
            </div>
            <div class="match-teams">
                <div class="team home">
                    <span>${m.home_team}</span>
                    ${m.home_crest ? `<img src="${m.home_crest}" alt="" onerror="this.remove()">` : ""}
                </div>
                ${scoreHtml}
                <div class="team away">
                    ${m.away_crest ? `<img src="${m.away_crest}" alt="" onerror="this.remove()">` : ""}
                    <span>${m.away_team}</span>
                </div>
            </div>
            ${badge}
        </div>`;
}

// ===== Charts =====
function renderCharts(data) {
    const st = data.stats || {};
    if (st.played === 0) return;

    destroyCharts();

    // WDL Doughnut
    const wdlCtx = document.getElementById("chart-wdl");
    if (wdlCtx) {
        charts.wdl = new Chart(wdlCtx, {
            type: "doughnut",
            data: {
                labels: ["Wins", "Draws", "Losses"],
                datasets: [{
                    data: [st.wins || 0, st.draws || 0, st.losses || 0],
                    backgroundColor: ["#2ecc71", "#f39c12", "#e74c3c"],
                    borderColor: "var(--bg)",
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { position: "bottom", labels: { color: "#e0e0e0" } } }
            }
        });
    }

    // Points progression
    const ptsCtx = document.getElementById("chart-points");
    if (ptsCtx && st.timeline) {
        charts.points = new Chart(ptsCtx, {
            type: "line",
            data: {
                labels: st.timeline.map(t => t.label),
                datasets: [{
                    label: "Points",
                    data: st.timeline.map(t => t.points),
                    borderColor: "#A50044",
                    backgroundColor: "rgba(165,0,68,0.1)",
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: "#A50044",
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: { beginAtZero: true, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    x: { ticks: { color: "#999" }, grid: { display: false } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    // Goals per match
    const goalsCtx = document.getElementById("chart-goals");
    if (goalsCtx && st.timeline) {
        charts.goals = new Chart(goalsCtx, {
            type: "bar",
            data: {
                labels: st.timeline.map(t => t.label),
                datasets: [{
                    label: "Goals",
                    data: st.timeline.map(t => t.goals),
                    backgroundColor: st.timeline.map(t => t.goals > 1 ? "#2ecc71" : t.goals === 1 ? "#f39c12" : "#e74c3c"),
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1, color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    x: { ticks: { color: "#999" }, grid: { display: false } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    // Competitions breakdown
    const compCtx = document.getElementById("chart-competitions");
    if (compCtx && st.competitions) {
        const comps = st.competitions;
        const labels = Object.keys(comps);
        charts.comps = new Chart(compCtx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    { label: "Wins", data: labels.map(c => comps[c].wins), backgroundColor: "#2ecc71", borderRadius: 4 },
                    { label: "Draws", data: labels.map(c => comps[c].draws), backgroundColor: "#f39c12", borderRadius: 4 },
                    { label: "Losses", data: labels.map(c => comps[c].losses), backgroundColor: "#e74c3c", borderRadius: 4 },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    x: { stacked: true, ticks: { color: "#999" }, grid: { display: false } },
                    y: { stacked: true, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } }
                },
                plugins: { legend: { position: "bottom", labels: { color: "#e0e0e0" } } }
            }
        });
    }
}

function destroyCharts() {
    Object.values(charts).forEach(c => c.destroy());
    charts = {};
}

// ===== Helpers =====
function formatTime(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleString();
    } catch { return iso; }
}

function formatDateShort(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    } catch { return "TBD"; }
}

function showError(msg) {
    const el = document.getElementById("error-banner");
    el.textContent = msg;
    el.classList.remove("hidden");
}

function hideError() {
    document.getElementById("error-banner").classList.add("hidden");
}
