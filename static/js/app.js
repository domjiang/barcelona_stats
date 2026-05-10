// FC Barcelona 2025/26 — Frontend Dashboard

const REFRESH_MS = 5 * 60 * 1000;
let charts = {};
let currentData = null;
let stadiumCache = {};

// ===== Init =====
document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    document.getElementById("btn-refresh").addEventListener("click", fetchAndRender);
    document.getElementById("btn-transfer-refresh").addEventListener("click", refreshTransfers);
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
        currentData = data;
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
            if (tab.dataset.tab === "transfers") loadTransfers();
            if (tab.dataset.tab === "charts" && currentData) {
                setTimeout(() => renderCharts(currentData), 100);
            }
        });
    });
}

// ===== Main render =====
function render(data) {
    const all = [...(data.finished || []), ...(data.live || []), ...(data.upcoming || [])]
        .sort((a, b) => new Date(b.date) - new Date(a.date));

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

    // Render match tabs
    document.getElementById("tab-all").innerHTML = renderMatchList(all);
    document.getElementById("tab-finished").innerHTML = renderMatchList(data.finished || []);
    document.getElementById("tab-upcoming").innerHTML = renderMatchList(data.upcoming || []);
    document.getElementById("tab-live").innerHTML = renderMatchList(data.live || []);

    // Lazy tabs
    if (!document.getElementById("tab-charts").classList.contains("hidden")) renderCharts(data);
    if (!document.getElementById("tab-transfers").classList.contains("hidden")) loadTransfers();

    // Load stadium images after DOM update
    setTimeout(loadStadiumImages, 200);
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
    const isBarcaHome = m.is_home;
    const isUpcoming = !isFinished && !isLive;

    // Competition emblem
    const compEmblem = m.competition_emblem
        ? `<img class="comp-emblem" src="${escAttr(m.competition_emblem)}" alt="">`
        : "";

    // Result badge
    let badge = "";
    if (isLive) {
        badge = '<span class="match-badge badge-live">LIVE ' + (status === "PAUSED" ? "(Paused)" : "") + "</span>";
    } else if (isFinished) {
        const won = (m.winner === "HOME_TEAM" && isBarcaHome) || (m.winner === "AWAY_TEAM" && !isBarcaHome);
        const draw = m.winner === "DRAW";
        if (won) badge = '<span class="match-badge badge-win">W</span>';
        else if (draw) badge = '<span class="match-badge badge-draw">D</span>';
        else badge = '<span class="match-badge badge-loss">L</span>';
    } else {
        badge = '<span class="match-badge badge-upcoming">' + formatDateShort(m.date) + "</span>";
    }

    // Score
    let scoreHtml = "";
    if (isFinished && m.home_score !== null && m.away_score !== null) {
        scoreHtml = `<div class="match-score"><span class="score-num">${m.home_score} - ${m.away_score}</span><span class="score-label">FT</span></div>`;
    } else if (isLive && m.home_score !== null && m.away_score !== null) {
        scoreHtml = `<div class="match-score"><span class="score-num" style="color:var(--live)">${m.home_score} - ${m.away_score}</span><span class="score-label">LIVE</span></div>`;
    } else {
        scoreHtml = `<div class="match-score"><span class="score-num" style="color:var(--text-muted)">vs</span></div>`;
    }

    // HOME/AWAY badge
    const venueBadge = isBarcaHome
        ? '<span class="venue-badge home">HOME</span>'
        : '<span class="venue-badge away">AWAY</span>';

    const venueName = m.venue || "";
    const venueText = venueName ? ` — ${venueName}` : "";

    // Stadium image row
    let stadiumRow = "";
    if (venueName) {
        const safeName = venueName.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase();
        stadiumRow = `
            <div class="stadium-row">
                <img class="stadium-thumb" data-stadium="${escAttr(venueName)}"
                     src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='50'><rect fill='%23222240' width='80' height='50'/></svg>"
                     alt="${escAttr(venueName)}">
                <span class="stadium-name">${escHtml(venueName)} ${venueBadge}</span>
            </div>`;
    }

    // Timeline content
    const timelineHtml = renderTimeline(m, isBarcaHome);

    return `
        <div class="match-card status-${status}" data-match-id="${m.id}" onclick="toggleMatch(this, ${m.id})">
            <div class="match-card-header">
                <div class="match-meta">
                    <span class="competition">${compEmblem}${m.competition}</span>
                    <span class="date">${isLive ? "NOW" : m.date_display}${venueText}</span>
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
            </div>
            ${stadiumRow}
            <div class="timeline">${timelineHtml}</div>
            <div class="expand-arrow">▼</div>
        </div>`;
}

function renderTimeline(m, isBarcaHome) {
    const events = m.events || {};
    const goals = events.goals || [];
    const cards = events.cards || [];
    const hasEvents = goals.length > 0 || cards.length > 0;
    const hasFetched = events.found !== undefined;
    const isFinished = m.status === "FINISHED";
    const isLive = m.status === "IN_PLAY" || m.status === "PAUSED";

    if (!isFinished && !isLive) return "";
    if (!hasEvents && !hasFetched) return '<div class="loading-events">Click to load events…</div>';
    if (!hasEvents && hasFetched && !events.found) return '<div class="loading-events">No detailed events available.</div>';
    if (!hasEvents) return '<div class="loading-events">Loading…</div>';

    const barcaTeamName = isBarcaHome ? m.home_team : m.away_team;
    const oppTeamName = isBarcaHome ? m.away_team : m.home_team;

    // Merge and sort events
    const allEvents = [
        ...goals.map(g => ({ ...g, etype: "goal" })),
        ...cards.map(c => ({ ...c, etype: "card" })),
    ];
    allEvents.sort((a, b) => parseMinute(a.minute) - parseMinute(b.minute));

    // Build left/right timeline rows
    let rows = "";
    allEvents.forEach(ev => {
        const isBarca = ev.is_barca;
        const side = isBarca ? "barca" : "opp";

        if (ev.etype === "goal") {
            const isPen = ev.type === "PENALTY";
            const penaltyTag = isPen ? '<span class="timeline-penalty">(P)</span>' : "";
            rows += `
                <div class="timeline-event ${side} event-goal${isBarca ? "" : " opp-goal"}">
                    <span class="timeline-icon"></span>
                    <span class="timeline-text">
                        <span class="timeline-minute">${ev.minute}</span>
                        <span class="timeline-player">${escHtml(ev.scorer)}</span>${penaltyTag}
                    </span>
                </div>`;
        } else {
            const isRed = ev.card === "RED";
            const cardIcon = isRed ? "" : "";
            const cardCls = isRed ? "event-card card-red" : "event-card";
            rows += `
                <div class="timeline-event ${side} ${cardCls}">
                    <span class="timeline-icon">${cardIcon}</span>
                    <span class="timeline-text">
                        <span class="timeline-minute">${ev.minute}</span>
                        <span class="timeline-player">${escHtml(ev.player)}</span>
                    </span>
                </div>`;
        }
    });

    return `
        <div class="timeline-section">
            <div class="timeline-section-title">
                <span style="color:var(--barca-blue)">${escHtml(barcaTeamName)}</span>
                &nbsp;— Match Events —&nbsp;
                <span style="color:var(--text-muted)">${escHtml(oppTeamName)}</span>
            </div>
            <div class="timeline-events">${rows}</div>
        </div>`;
}

function parseMinute(minStr) {
    const m = String(minStr).match(/(\d+)'?(\+(\d+))?/);
    if (!m) return 999;
    return parseInt(m[1]) + (parseInt(m[3]) || 0) * 0.01;
}

// ===== Accordion =====
function toggleMatch(card, matchId) {
    const wasExpanded = card.classList.contains("expanded");
    document.querySelectorAll(".match-card.expanded").forEach(c => c.classList.remove("expanded"));

    if (!wasExpanded) {
        card.classList.add("expanded");
        const events = getMatchEventsFromCache(matchId);
        if (!events || (!events.found && events.found !== false)) {
            fetchMatchEvents(card, matchId);
        }
    }
}

function getMatchEventsFromCache(matchId) {
    if (!currentData) return null;
    const all = [...(currentData.finished || []), ...(currentData.live || []), ...(currentData.upcoming || [])];
    const m = all.find(x => x.id === matchId);
    return m ? m.events : null;
}

async function fetchMatchEvents(card, matchId) {
    const timeline = card.querySelector(".timeline");
    if (!timeline) return;
    timeline.innerHTML = '<div class="loading-events">Loading…</div>';

    try {
        const resp = await fetch(`/api/match/${matchId}/events`);
        const data = await resp.json();
        if (data.events) {
            const all = [...(currentData.finished || []), ...(currentData.live || []), ...(currentData.upcoming || [])];
            const m = all.find(x => x.id === matchId);
            if (m) m.events = data.events;
            if (m) {
                timeline.innerHTML = renderTimeline(m, m.is_home)
                    .replace(/.*<div class="timeline-section">/s, '<div class="timeline-section">');
            }
        } else {
            timeline.innerHTML = '<div class="loading-events">No events available.</div>';
        }
    } catch {
        timeline.innerHTML = '<div class="loading-events">Failed to load.</div>';
    }
}

// ===== Stadium images =====
function loadStadiumImages() {
    const imgs = document.querySelectorAll("img.stadium-thumb[data-stadium]");
    imgs.forEach(img => {
        const name = img.dataset.stadium;
        if (!name) return;
        // Skip if already loaded (src is a real image, not the placeholder)
        if (img.src && !img.src.startsWith("data:image")) return;

        if (stadiumCache[name]) {
            img.src = stadiumCache[name];
            return;
        }

        fetchStadiumImage(img, name);
    });
}

async function fetchStadiumImage(img, name) {
    try {
        const resp = await fetch(`/api/stadium-image?name=${encodeURIComponent(name)}`);
        const sd = await resp.json();
        if (sd.image_path) {
            stadiumCache[name] = sd.image_path;
            img.src = sd.image_path;
            img.title = sd.attribution || "";
        }
    } catch { /* ignore */ }
}

// ===== Transfer News =====
async function loadTransfers() {
    try {
        const resp = await fetch("/api/transfers");
        const data = await resp.json();
        renderTransferBoard(data);
    } catch {
        document.getElementById("list-rumor").innerHTML =
            '<p style="color:var(--text-muted);padding:20px;">Failed to load transfer news.</p>';
    }
}

function renderTransferBoard(data) {
    const cats = data.categories || {};

    Object.entries(cats).forEach(([cat, articles]) => {
        const listEl = document.getElementById(`list-${cat}`);
        const countEl = document.getElementById(`count-${cat}`);
        if (!listEl) return;
        if (countEl) countEl.textContent = articles.length;

        if (!articles.length) {
            listEl.innerHTML = '<p style="color:var(--text-muted);padding:10px;">No articles yet</p>';
            return;
        }

        listEl.innerHTML = articles.map(a => {
            const playersHtml = (a.players || []).length > 0
                ? `<div class="transfer-players">${a.players.map(p => `<span class="transfer-player-tag">${escHtml(p)}</span>`).join("")}</div>`
                : "";
            const origTitle = a.original_title
                ? `<div style="font-size:0.7rem;color:var(--text-muted);margin-top:2px;">Original: ${escHtml(a.original_title)}</div>`
                : "";
            return `
                <div class="transfer-item">
                    <a href="${escAttr(a.link)}" target="_blank" rel="noopener">${escHtml(a.title)}</a>
                    ${origTitle}
                    <div class="transfer-source">${escHtml(a.source)}</div>
                    ${playersHtml}
                </div>`;
        }).join("");
    });

    document.getElementById("transfer-updated").textContent =
        data.stale ? "Updating…" : "Last fetched: " + formatTime(new Date().toISOString());
}

async function refreshTransfers() {
    document.getElementById("transfer-updated").textContent = "Refreshing…";
    try {
        await fetch("/api/transfer-refresh", { method: "POST" });
        await loadTransfers();
    } catch {
        document.getElementById("transfer-updated").textContent = "Refresh failed";
    }
}

// ===== Charts =====
function renderCharts(data) {
    const st = data.stats || {};
    if (st.played === 0) return;
    destroyCharts();

    const wdlCtx = document.getElementById("chart-wdl");
    if (wdlCtx) {
        charts.wdl = new Chart(wdlCtx, {
            type: "doughnut",
            data: {
                labels: ["Wins", "Draws", "Losses"],
                datasets: [{
                    data: [st.wins || 0, st.draws || 0, st.losses || 0],
                    backgroundColor: ["#2ecc71", "#f39c12", "#e74c3c"],
                    borderColor: "#1a1a2e",
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: true,
                plugins: { legend: { position: "bottom", labels: { color: "#e0e0e0" } } }
            }
        });
    }

    const ptsCtx = document.getElementById("chart-points");
    if (ptsCtx && st.timeline) {
        charts.points = new Chart(ptsCtx, {
            type: "line",
            data: {
                labels: st.timeline.map(t => t.label),
                datasets: [{
                    label: "Points", data: st.timeline.map(t => t.points),
                    borderColor: "#A50044", backgroundColor: "rgba(165,0,68,0.1)",
                    fill: true, tension: 0.3, pointBackgroundColor: "#A50044",
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: true,
                scales: {
                    y: { beginAtZero: true, ticks: { color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    x: { ticks: { color: "#999" }, grid: { display: false } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    const goalsCtx = document.getElementById("chart-goals");
    if (goalsCtx && st.timeline) {
        charts.goals = new Chart(goalsCtx, {
            type: "bar",
            data: {
                labels: st.timeline.map(t => t.label),
                datasets: [{
                    label: "Goals", data: st.timeline.map(t => t.goals),
                    backgroundColor: st.timeline.map(t => t.goals > 1 ? "#2ecc71" : t.goals === 1 ? "#f39c12" : "#e74c3c"),
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: true,
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1, color: "#999" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    x: { ticks: { color: "#999" }, grid: { display: false } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

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
                responsive: true, maintainAspectRatio: true,
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
function escHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}
function escAttr(s) {
    return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function formatTime(iso) {
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
function formatDateShort(iso) {
    try { return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }); } catch { return "TBD"; }
}
function showError(msg) {
    const el = document.getElementById("error-banner");
    el.textContent = msg;
    el.classList.remove("hidden");
}
function hideError() {
    document.getElementById("error-banner").classList.add("hidden");
}
