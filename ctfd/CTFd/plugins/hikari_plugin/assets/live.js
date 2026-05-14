(function () {
  const root = document.querySelector("[data-live-board]");
  if (!root) {
    return;
  }

  const selectors = {
    generated: root.querySelector("[data-live-generated]"),
    totalSolves: root.querySelector("[data-live-total-solves]"),
    activeTeams: root.querySelector("[data-live-active-teams]"),
    activeUsers: root.querySelector("[data-live-active-users]"),
    teams: root.querySelector("[data-live-teams]"),
    users: root.querySelector("[data-live-users]"),
    solves: root.querySelector("[data-live-solves]"),
    timeline: root.querySelector("[data-live-timeline]"),
    timelineLegend: root.querySelector("[data-live-timeline-legend]"),
  };

  const timelineColors = ["#34d399", "#d4a35a", "#5ddeff", "#a7f3d0", "#fbbf24"];

  function setText(element, value) {
    if (element) {
      element.textContent = value;
    }
  }

  function render(board) {
    setText(selectors.generated, formatDate(board.generated_at));
    setText(selectors.totalSolves, board.total_solves);
    setText(selectors.activeTeams, board.active_teams);
    setText(selectors.activeUsers, board.active_users);
    renderStandings(selectors.teams, board.team_standings);
    renderStandings(selectors.users, board.individual_standings);
    renderSolves(selectors.solves, board.recent_solves);
    renderTimeline(
      selectors.timeline,
      selectors.timelineLegend,
      board.timeline,
      board.team_standings.slice(0, 5)
    );
  }

  function renderStandings(container, standings) {
    if (!container) {
      return;
    }
    const maxScore = Math.max(1, ...standings.map((item) => item.score));
    container.replaceChildren(
      ...standings.map((item) => standingRow(item, maxScore))
    );
  }

  function standingRow(item, maxScore) {
    const row = document.createElement("div");
    row.className = "live-rank-row";

    const position = document.createElement("span");
    position.textContent = `#${item.position}`;

    const main = document.createElement("div");
    main.className = "live-rank-main";

    const title = document.createElement("div");
    title.className = "live-rank-title";
    title.append(textSpan(item.name), textSpan(`${item.score} pts`));

    const track = document.createElement("div");
    track.className = "live-track";

    const fill = document.createElement("div");
    fill.className = "live-fill";
    fill.style.setProperty("--live-width", `${Math.round((item.score / maxScore) * 100)}%`);
    track.append(fill);

    main.append(title, track);

    const meta = document.createElement("span");
    meta.className = "live-rank-meta";
    meta.textContent = `${item.solves} solves`;

    row.append(position, main, meta);
    return row;
  }

  function renderSolves(container, solves) {
    if (!container) {
      return;
    }
    if (!solves.length) {
      const empty = document.createElement("p");
      empty.className = "text-muted";
      empty.textContent = "Nenhum solve registrado.";
      container.replaceChildren(empty);
      return;
    }
    container.replaceChildren(...solves.map(solveRow));
  }

  function solveRow(solve) {
    const row = document.createElement("div");
    row.className = "live-solve";

    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = solve.challenge_name;
    const detail = document.createElement("p");
    detail.textContent = `${solve.user_name}${solve.team_name ? " · " + solve.team_name : ""} · ${formatDate(solve.occurred_at)}`;
    body.append(title, detail);

    const value = document.createElement("span");
    value.className = "live-solve-value";
    value.textContent = `+${solve.value}`;

    row.append(body, value);
    return row;
  }

  function renderTimeline(svg, legend, points, standings) {
    if (!svg) {
      return;
    }
    svg.replaceChildren();
    if (legend) {
      legend.replaceChildren();
    }
    if (points.length < 2) {
      return;
    }

    const width = 900;
    const height = 280;
    const padding = { top: 24, right: 28, bottom: 24, left: 58 };
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const maxScore = Math.max(...points.map((point) => point.score), 1);
    const times = points.map((point) => new Date(point.occurred_at).getTime());
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    const grouped = groupByTeam(points);

    renderYAxis(svg, maxScore, height, padding);

    standings.forEach((standing, index) => {
      const teamPoints = grouped.get(standing.name);
      if (!teamPoints || !teamPoints.length) {
        return;
      }
      const color = timelineColors[index % timelineColors.length];
      const pathData = teamPoints.map((point, pointIndex) => {
        const x = xForDate(point.occurred_at, minTime, maxTime, width, padding);
        const y = yForScore(point.score, maxScore, height, padding);
        return `${pointIndex === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      }).join(" ");

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", pathData);
      path.style.setProperty("--live-line", color);
      path.dataset.team = standing.name;
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${standing.name}: ${standing.score} pts, ${standing.solves} solves`;
      path.append(title);
      svg.append(path);

      const last = teamPoints[teamPoints.length - 1];
      const lastX = xForDate(last.occurred_at, minTime, maxTime, width, padding);
      const lastY = yForScore(last.score, maxScore, height, padding);
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", lastX.toFixed(1));
      circle.setAttribute("cy", lastY.toFixed(1));
      circle.setAttribute("r", "5");
      circle.style.setProperty("--live-line", color);
      svg.append(circle);

      if (legend) {
        legend.append(legendRow(standing, color));
      }
    });
  }

  function renderYAxis(svg, maxScore, height, padding) {
    const tickCount = 5;
    for (let index = 0; index < tickCount; index += 1) {
      const ratio = index / (tickCount - 1);
      const score = Math.round(maxScore * (1 - ratio));
      const y = padding.top + ratio * (height - padding.top - padding.bottom);
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.classList.add("live-axis-label");
      label.setAttribute("x", (padding.left - 12).toFixed(1));
      label.setAttribute("y", (y + 4).toFixed(1));
      label.setAttribute("text-anchor", "end");
      label.textContent = score.toLocaleString("pt-BR");
      svg.append(label);
    }
  }

  function legendRow(standing, color) {
    const row = document.createElement("div");
    row.className = "live-legend-row";
    row.style.setProperty("--live-line", color);

    const swatch = document.createElement("span");
    swatch.className = "live-legend-swatch";

    const main = document.createElement("span");
    main.className = "live-legend-main";
    const name = document.createElement("strong");
    name.textContent = `#${standing.position} ${standing.name}`;
    const solves = document.createElement("span");
    solves.textContent = `${standing.solves} solves`;
    main.append(name, solves);

    const score = document.createElement("span");
    score.className = "live-legend-score";
    score.textContent = `${standing.score} pts`;

    row.append(swatch, main, score);
    return row;
  }

  function groupByTeam(points) {
    return points.reduce((grouped, point) => {
      if (!grouped.has(point.team_name)) {
        grouped.set(point.team_name, []);
      }
      grouped.get(point.team_name).push(point);
      return grouped;
    }, new Map());
  }

  function xForDate(value, minTime, maxTime, width, padding) {
    const timestamp = new Date(value).getTime();
    const span = Math.max(maxTime - minTime, 1);
    return padding.left + ((timestamp - minTime) / span) * (width - padding.left - padding.right);
  }

  function yForScore(score, maxScore, height, padding) {
    return height - padding.bottom - (score / maxScore) * (height - padding.top - padding.bottom);
  }

  function textSpan(value) {
    const span = document.createElement("span");
    span.textContent = value;
    return span;
  }

  function formatDate(value) {
    if (!value) {
      return "-";
    }
    return new Date(value).toLocaleString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      day: "2-digit",
      month: "2-digit",
    });
  }

  async function refresh() {
    const response = await fetch("/hikari/live/data", { credentials: "same-origin" });
    if (!response.ok) {
      return;
    }
    render(await response.json());
  }

  refresh();
  window.setInterval(refresh, 5000);
})();
