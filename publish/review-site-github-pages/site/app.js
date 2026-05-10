const gameSelect = document.querySelector("#game-select");
const reviewFilter = document.querySelector("#review-filter");
const reviewFilterHelp = document.querySelector("#review-filter-help");
const gameMeta = document.querySelector("#game-meta");
const positionList = document.querySelector("#position-list");
const timelineCount = document.querySelector("#timeline-count");
const summaryTitle = document.querySelector("#summary-title");
const summarySubtitle = document.querySelector("#summary-subtitle");
const summaryStats = document.querySelector("#summary-stats");
const rankComparisonSection = document.querySelector("#rank-comparison-section");
const rankModelSelect = document.querySelector("#rank-model-select");
const rankOverview = document.querySelector("#rank-overview");
const rankNote = document.querySelector("#rank-note");
const rankBucketTable = document.querySelector("#rank-bucket-table");
const timeBudgetSection = document.querySelector("#time-budget-section");
const timeBudgetOverview = document.querySelector("#time-budget-overview");
const timeBudgetNote = document.querySelector("#time-budget-note");
const timeBudgetPositionSummary = document.querySelector("#time-budget-position-summary");
const timeBudgetBudgetTable = document.querySelector("#time-budget-budget-table");
const realizabilitySection = document.querySelector("#realizability-section");
const realizabilityOverview = document.querySelector("#realizability-overview");
const realizabilityNote = document.querySelector("#realizability-note");
const realizabilityBucketTable = document.querySelector("#realizability-bucket-table");
const positionTitle = document.querySelector("#position-title");
const positionBadges = document.querySelector("#position-badges");
const boardImage = document.querySelector("#board-image");
const positionMeta = document.querySelector("#position-meta");
const complexityScoreCard = document.querySelector("#complexity-score-card");
const depthBreakdown = document.querySelector("#depth-breakdown");
const humanMoveCard = document.querySelector("#human-move-card");
const realizabilityPositionSummary = document.querySelector("#realizability-position-summary");
const realizabilityCandidateList = document.querySelector("#realizability-candidate-list");
const realizabilityPositionNote = document.querySelector("#realizability-position-note");
const modelMoves = document.querySelector("#model-moves");
const engineMoves = document.querySelector("#engine-moves");
const continuationList = document.querySelector("#continuation-list");
const moveText = document.querySelector("#move-text");
const treeView = document.querySelector("#tree-view");
const maiaEngineConflictSummary = document.querySelector("#maia-engine-conflict-summary");
const maiaEngineConflictList = document.querySelector("#maia-engine-conflict-list");
const engineBestReluctanceSummary = document.querySelector("#engine-best-reluctance-summary");

const FILTERS = {
  all: {
    label: "All eligible positions",
    help: "Show every saved middlegame position for the selected game.",
  },
  high: {
    label: "High-complexity only",
    help: "Keep only positions that passed the current complexity threshold.",
  },
  maia_engine_bad: {
    label: "Maia high / Engine bad",
    help: "Show positions where Maia gives at least one human-like move >=10%, but Stockfish values that move at least 300 centipawns below its own best move.",
  },
  engine_best_reluctant: {
    label: "Engine best / Maia reluctant",
    help: "Show positions where Stockfish's best move scores at least +3.00, but Maia assigns that move less than 10% probability.",
  },
};

let bundle = null;
let selectedGameId = null;
let selectedPositionId = null;
let splitDataMode = false;
const gameCache = new Map();

const RANK_MODEL_OPTIONS = {
  maia: "Maia",
  stockfish: "Stockfish",
};

function moveSan(move) {
  return move?.san || move?.uci || "n/a";
}

function actualMoveLabel(actualMove) {
  if (!actualMove?.available || !actualMove.detail) {
    return "No following move available";
  }
  return `${actualMove.detail.san} (${actualMove.detail.uci})`;
}

function formatPercentage(value) {
  if (value == null || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatCp(scoreCp) {
  if (scoreCp == null || Number.isNaN(scoreCp)) {
    return "n/a";
  }
  return `${scoreCp >= 0 ? "+" : ""}${(scoreCp / 100).toFixed(2)}`;
}

function buildSummary() {
  const summary = bundle.summary;
  summaryTitle.textContent = `${summary.games_with_high_complexity} games, ${summary.high_complexity_count} flagged positions`;
  summarySubtitle.textContent = `Threshold ${summary.high_complexity_threshold} | model move cutoff ${summary.min_probability} | 3-ply expansion ${summary.expansion_plies}`;

  const cards = [
    ["Eligible", summary.eligible_middlegame_count],
    ["High complexity", summary.high_complexity_count],
    ["Maia high / engine bad", summary.maia_high_engine_bad_position_count ?? "n/a"],
    ["Engine best / Maia reluctant", summary.engine_best_maia_reluctant_position_count ?? "n/a"],
    ["Maia avg rank", summary.maia_actual_move_rank_mean ?? "n/a"],
    ["SF avg rank", summary.stockfish_actual_move_rank_mean ?? "n/a"],
  ];
  summaryStats.innerHTML = "";
  for (const [label, value] of cards) {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    summaryStats.appendChild(card);
  }
}

function formatNumber(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(2);
}

function formatRealizability(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(2);
}

function rankExperiment() {
  return bundle.experiments?.rank_bucket_comparison || null;
}

function timeBudgetExperiment() {
  return bundle.experiments?.time_budget_sweep || null;
}

function realizabilityExperiment() {
  return bundle.experiments?.realizability_probe || null;
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}: ${response.status}`);
  }
  return response.json();
}

async function loadBundle() {
  try {
    const fullBundle = await fetchJson("./data/site_bundle.json");
    splitDataMode = false;
    return fullBundle;
  } catch (error) {
    const [summaryPayload, manifestPayload, experimentsPayload] = await Promise.all([
      fetchJson("./data/summary.json"),
      fetchJson("./data/games_manifest.json"),
      fetchJson("./data/experiments.json"),
    ]);
    splitDataMode = true;
    return {
      generated_at: summaryPayload.generated_at,
      summary: summaryPayload.summary,
      games: manifestPayload.games,
      experiments: experimentsPayload,
    };
  }
}

async function ensureGameLoaded(gameId) {
  const game = bundle.games.find((candidate) => candidate.game_id === gameId);
  if (!game) return null;
  if (!splitDataMode || Array.isArray(game.positions)) {
    return game;
  }
  if (gameCache.has(gameId)) {
    const cached = gameCache.get(gameId);
    Object.assign(game, cached);
    return game;
  }
  const dataPath = game.data_path || `data/games/${gameId}.json`;
  const loadedGame = await fetchJson(`./${dataPath}`);
  gameCache.set(gameId, loadedGame);
  Object.assign(game, loadedGame);
  return game;
}

function renderRankModelOptions() {
  const experiment = rankExperiment();
  if (!experiment) return;
  rankModelSelect.innerHTML = "";
  Object.entries(RANK_MODEL_OPTIONS).forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    rankModelSelect.appendChild(option);
  });
  if (!rankModelSelect.value) {
    rankModelSelect.value = "maia";
  }
}

function rankMetricValue(scopeSummary, modelKey) {
  if (!scopeSummary) return null;
  return modelKey === "stockfish" ? scopeSummary.mean_rank_topk_clipped : scopeSummary.mean_rank;
}

function renderRankOverview() {
  const experiment = rankExperiment();
  if (!experiment) {
    rankComparisonSection.style.display = "none";
    return;
  }
  rankComparisonSection.style.display = "";

  const modelKey = rankModelSelect.value || "maia";
  const slices = experiment.summary?.slices || {};
  const allScope = slices.all_eligible?.[modelKey] || {};
  const complexScope = slices.high_complexity?.[modelKey] || {};
  const allMean = rankMetricValue(allScope, modelKey);
  const complexMean = rankMetricValue(complexScope, modelKey);
  const delta = allMean != null && complexMean != null ? complexMean - allMean : null;

  const cards = [
    ["All mean rank", formatNumber(allMean)],
    ["Complex mean rank", formatNumber(complexMean)],
    ["Delta", delta == null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`],
    ["All hit@1", formatPercentage(allScope.hit_at_1)],
    ["Complex hit@1", formatPercentage(complexScope.hit_at_1)],
    ["Complex coverage", formatPercentage(complexScope.coverage)],
  ];

  rankOverview.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    rankOverview.appendChild(card);
  });

  if (modelKey === "stockfish") {
    const topk = Number(experiment.summary?.stockfish?.multipv ?? 20);
    rankNote.textContent = `Stockfish mean rank uses a top-${topk}-clipped rank: if the human move is outside the engine top-${topk}, it is recorded as ${topk + 1}. Coverage shows how often the human move actually entered the top-${topk}.`;
  } else {
    rankNote.textContent = "Maia mean rank uses the exact root policy rank for the human move from Maia's stored move distribution.";
  }
}

function deltaClass(delta) {
  if (delta == null) return "";
  if (delta > 0) return "delta-up";
  if (delta < 0) return "delta-down";
  return "";
}

function renderRankBucketTable() {
  const experiment = rankExperiment();
  if (!experiment) {
    rankBucketTable.innerHTML = "";
    return;
  }

  const modelKey = rankModelSelect.value || "maia";
  const rows = experiment.bucket_rows || [];
  const scopedRows = rows.filter((row) => row.model === modelKey);
  const byBucket = new Map();
  scopedRows.forEach((row) => {
    const bucket = row.elo_bucket_label;
    const current = byBucket.get(bucket) || {};
    current[row.scope] = row;
    byBucket.set(bucket, current);
  });

  const entries = Array.from(byBucket.entries()).sort((left, right) => {
    const leftStart = Number(left[1].all_eligible?.elo_bucket_start ?? left[1].high_complexity?.elo_bucket_start ?? 0);
    const rightStart = Number(right[1].all_eligible?.elo_bucket_start ?? right[1].high_complexity?.elo_bucket_start ?? 0);
    return leftStart - rightStart;
  });

  const meanField = modelKey === "stockfish" ? "mean_rank_topk_clipped" : "mean_rank";
  rankBucketTable.innerHTML = `
    <thead>
      <tr>
        <th>Bucket</th>
        <th>All count</th>
        <th>All mean</th>
        <th>Complex count</th>
        <th>Complex mean</th>
        <th>Delta</th>
        <th>All hit@1</th>
        <th>Complex hit@1</th>
        <th>All coverage</th>
        <th>Complex coverage</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const body = rankBucketTable.querySelector("tbody");

  entries.forEach(([bucketLabel, bucketScopes]) => {
    const allScope = bucketScopes.all_eligible || null;
    const complexScope = bucketScopes.high_complexity || null;
    const allMean = allScope?.[meanField] != null ? Number(allScope[meanField]) : null;
    const complexMean = complexScope?.[meanField] != null ? Number(complexScope[meanField]) : null;
    const delta = allMean != null && complexMean != null ? complexMean - allMean : null;
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${bucketLabel}</strong></td>
      <td>${allScope?.position_count ?? "—"}</td>
      <td>${formatNumber(allMean)}</td>
      <td>${complexScope?.position_count ?? "—"}</td>
      <td>${formatNumber(complexMean)}</td>
      <td class="${deltaClass(delta)}">${delta == null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`}</td>
      <td>${formatPercentage(allScope?.hit_at_1)}</td>
      <td>${formatPercentage(complexScope?.hit_at_1)}</td>
      <td>${formatPercentage(allScope?.coverage)}</td>
      <td>${formatPercentage(complexScope?.coverage)}</td>
    `;
    body.appendChild(row);
  });
}

function renderTimeBudgetOverview() {
  const experiment = timeBudgetExperiment();
  if (!experiment) {
    timeBudgetSection.style.display = "none";
    return;
  }
  timeBudgetSection.style.display = "";

  const summary = experiment.summary || {};
  const cards = [
    ["Positions", summary.selected_position_count ?? "—"],
    ["Budgets", Array.isArray(summary.budgets_ms) ? summary.budgets_ms.length : "—"],
    ["Best move switches", formatNumber(summary.best_move_switch_stats?.mean)],
    ["Score range (cp)", formatNumber(summary.best_score_range_stats?.mean)],
    ["Actual-rank range", formatNumber(summary.actual_move_rank_range_stats?.mean)],
    ["Workers", summary.parallel?.max_workers ?? "—"],
  ];

  timeBudgetOverview.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    timeBudgetOverview.appendChild(card);
  });

  const budgets = Array.isArray(summary.budgets_ms) ? summary.budgets_ms.join(" / ") : "n/a";
  timeBudgetNote.textContent = `This sweep runs Stockfish on the top ${summary.selected_position_count ?? "n/a"} high-complexity positions with budgets ${budgets} ms. The key question is whether the engine's own preferred move stays stable when it gets more time.`;
}

function renderTimeBudgetPosition(position) {
  const payload = position.experiments?.time_budget;
  if (!payload?.available) {
    timeBudgetPositionSummary.innerHTML = `<div class="empty-state">This position was not included in the overnight time-budget sweep subset.</div>`;
    timeBudgetBudgetTable.innerHTML = "";
    return;
  }

  const summary = payload.summary || {};
  const rows = payload.budget_rows || [];
  timeBudgetPositionSummary.innerHTML = `
    <strong>How unstable is this position for Stockfish?</strong>
    <div class="muted-line">Best-move switches: ${summary.best_move_switch_count ?? "—"} • unique best moves: ${summary.unique_best_move_count ?? "—"} • best-score range: ${summary.best_score_range_cp ?? "—"} cp • actual-rank range: ${summary.actual_move_rank_range ?? "—"}</div>
    <div class="muted-line">Best-move path: ${summary.best_move_path || "n/a"}</div>
    <div class="muted-line">Actual-move rank path: ${summary.actual_move_rank_path || "n/a"}</div>
  `;

  timeBudgetBudgetTable.innerHTML = `
    <thead>
      <tr>
        <th>Budget</th>
        <th>Best move</th>
        <th>Best score</th>
        <th>Depth</th>
        <th>Actual rank</th>
        <th>Actual score</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const body = timeBudgetBudgetTable.querySelector("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const actualClass = row.actual_move_in_topk ? "" : "delta-up";
    tr.innerHTML = `
      <td><strong>${row.budget_ms} ms</strong></td>
      <td>${row.best_move_san || row.best_move_uci || "—"}<br /><span class="muted-line">${row.best_move_uci || ""}</span></td>
      <td>${row.best_move_score_text || "—"}</td>
      <td>${row.best_move_depth ?? "—"}</td>
      <td class="${actualClass}">${row.actual_move_rank_label || "—"}</td>
      <td>${row.actual_move_score_text || "—"}</td>
    `;
    body.appendChild(tr);
  });
}

function renderRealizabilityOverview() {
  const experiment = realizabilityExperiment();
  if (!experiment) {
    realizabilitySection.style.display = "none";
    return;
  }
  realizabilitySection.style.display = "";

  const summary = experiment.summary || {};
  const cards = [
    ["Candidate rows", summary.candidate_count ?? "—"],
    ["Mean actual", formatRealizability(summary.mean_actual_realizability)],
    ["Mean engine best", formatRealizability(summary.mean_engine_best_realizability)],
    ["Actual - engine", summary.mean_actual_minus_engine_best == null ? "—" : `${Number(summary.mean_actual_minus_engine_best) >= 0 ? "+" : ""}${formatRealizability(summary.mean_actual_minus_engine_best)}`],
    ["Actual > engine", formatPercentage(summary.actual_beats_engine_best_rate)],
    ["Maia corr", formatNumber(summary.candidate_level_maia_probability_realizability_corr)],
  ];

  realizabilityOverview.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    realizabilityOverview.appendChild(card);
  });

  const population = summary.population || {};
  const engine = summary.engine || {};
  realizabilityNote.textContent = `Current v0 run is scoped to ${
    population.complex_only ? "high-complexity positions only" : "all eligible positions"
  }, with Stockfish root ${engine.root_movetime_ms ?? "—"} ms / node ${
    engine.node_movetime_ms ?? "—"
  } ms. The current implementation follows best resistance after one acceptable player continuation, so treat the score as a practical first approximation rather than a final definition.`;
}

function renderRealizabilityBucketTable() {
  const experiment = realizabilityExperiment();
  if (!experiment) {
    realizabilityBucketTable.innerHTML = "";
    return;
  }

  const rows = experiment.bucket_rows || [];
  realizabilityBucketTable.innerHTML = `
    <thead>
      <tr>
        <th>Bucket</th>
        <th>Positions</th>
        <th>Actual mean</th>
        <th>Engine mean</th>
        <th>Delta</th>
        <th>Actual &gt; engine</th>
        <th>Actual = top real.</th>
        <th>Maia corr</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const body = realizabilityBucketTable.querySelector("tbody");

  rows
    .slice()
    .sort((left, right) => Number(left.elo_bucket_start) - Number(right.elo_bucket_start))
    .forEach((row) => {
      const delta = row.mean_actual_minus_engine_best == null ? null : Number(row.mean_actual_minus_engine_best);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${row.elo_bucket_label}</strong></td>
        <td>${row.position_count ?? "—"}</td>
        <td>${formatRealizability(row.mean_actual_realizability)}</td>
        <td>${formatRealizability(row.mean_engine_best_realizability)}</td>
        <td class="${deltaClass(delta)}">${delta == null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`}</td>
        <td>${formatPercentage(row.actual_beats_engine_best_rate)}</td>
        <td>${formatPercentage(row.actual_matches_top_realizability_rate)}</td>
        <td>${formatNumber(row.candidate_level_maia_probability_realizability_corr)}</td>
      `;
      body.appendChild(tr);
    });
}

function currentGame() {
  return bundle.games.find((game) => game.game_id === selectedGameId) || bundle.games[0];
}

function positionMatchesFilter(position, filterMode) {
  if (filterMode === "all") return true;
  if (filterMode === "high") return position.complexity.high;
  if (filterMode === "maia_engine_bad") return position.conflicts.maia_high_engine_bad.flagged;
  if (filterMode === "engine_best_reluctant") return position.conflicts.engine_best_maia_reluctant.flagged;
  return true;
}

function filteredPositions(game) {
  const positions = Array.isArray(game?.positions) ? game.positions : [];
  return positions.filter((position) => positionMatchesFilter(position, reviewFilter.value));
}

function renderGameOptions() {
  gameSelect.innerHTML = "";
  bundle.games.forEach((game) => {
    const option = document.createElement("option");
    option.value = game.game_id;
    option.textContent = `${game.white} vs ${game.black} (${game.game_id})`;
    gameSelect.appendChild(option);
  });
}

function renderFilterOptions() {
  reviewFilter.innerHTML = "";
  Object.entries(FILTERS).forEach(([value, meta]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = meta.label;
    reviewFilter.appendChild(option);
  });
  reviewFilter.value = "all";
  reviewFilterHelp.textContent = FILTERS[reviewFilter.value].help;
}

function renderGameMeta(game) {
  gameMeta.innerHTML = `
    <div><strong>${game.white}</strong> (${game.white_elo}) vs <strong>${game.black}</strong> (${game.black_elo})</div>
    <div>${game.event} • ${game.time_control}</div>
    <div>${game.opening} (${game.eco})</div>
    <div>Eligible ${game.stats.eligible_positions} • High ${game.stats.high_complexity_positions} • Maia high / engine bad ${game.stats.maia_high_engine_bad_positions} • Engine best / Maia reluctant ${game.stats.engine_best_maia_reluctant_positions}</div>
  `;
  moveText.textContent = game.move_text;
}

function renderPositionList(game) {
  const positions = filteredPositions(game);
  timelineCount.textContent = `${positions.length} steps`;
  positionList.innerHTML = "";

  if (!positions.length) {
    positionList.innerHTML = `<div class="empty-state">No positions match the current filter.</div>`;
    return;
  }

  positions.forEach((position) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "position-item";
    if (position.complexity.high) button.classList.add("high");
    if (position.complexity.inference_status !== "success") button.classList.add("fail");
    if (position.conflicts.maia_high_engine_bad.flagged) button.classList.add("conflict-a");
    if (position.conflicts.engine_best_maia_reluctant.flagged) button.classList.add("conflict-b");
    if (position.position_id === selectedPositionId) button.classList.add("active");
    button.innerHTML = `
      <div class="position-item-head">
        <span>${position.label}</span>
        <span>${position.complexity.score ?? "—"}</span>
      </div>
      <div class="position-sub">
        <span>${position.previous_move.san}</span>
        <span>${position.side_to_move} to move</span>
      </div>
    `;
    button.addEventListener("click", () => {
      selectedPositionId = position.position_id;
      render();
    });
    positionList.appendChild(button);
  });
}

function currentPosition(game) {
  const positions = filteredPositions(game);
  return positions.find((position) => position.position_id === selectedPositionId) || positions[0];
}

function renderBadges(position) {
  positionBadges.innerHTML = "";
  const badges = [];
  if (position.complexity.high) badges.push(["high", "High complexity"]);
  else badges.push(["ok", "Not flagged"]);

  if (position.conflicts.maia_high_engine_bad.flagged) badges.push(["conflict-a", "Maia high / engine bad"]);
  if (position.conflicts.engine_best_maia_reluctant.flagged) badges.push(["conflict-b", "Engine best / Maia reluctant"]);

  if (position.actual_move.model_qualifies_threshold) badges.push(["ok", "Human move in model >=10%"]);
  else badges.push(["warn", "Human move below model threshold"]);

  if (position.engine.available && position.actual_move.engine_rank) badges.push(["ok", `Engine rank #${position.actual_move.engine_rank}`]);
  else if (position.engine.available) badges.push(["warn", "Human move not in engine top set"]);

  if (position.complexity.inference_status !== "success") badges.push(["warn", "Model inference failed"]);

  badges.forEach(([klass, text]) => {
    const span = document.createElement("span");
    span.className = `badge ${klass}`;
    span.textContent = text;
    positionBadges.appendChild(span);
  });
}

function renderPositionMeta(position) {
  positionMeta.innerHTML = `
    <div><strong>Position</strong><br />${position.position_id}</div>
    <div><strong>Fullmove</strong><br />${position.fullmove_number}</div>
    <div><strong>Previous move</strong><br />${position.previous_move.san} (${position.previous_move.uci})</div>
    <div><strong>Actual next move</strong><br />${actualMoveLabel(position.actual_move)}</div>
    <div><strong>Side to move</strong><br />${position.side_to_move}</div>
    <div><strong>FEN</strong><br />${position.fen}</div>
  `;
}

function renderScore(position) {
  const score = position.complexity.score ?? "—";
  complexityScoreCard.innerHTML = `
    <strong>${score}</strong>
    <div>
      <div>Queried nodes: ${position.complexity.queried_node_count}</div>
      <div>Status: ${position.complexity.inference_status}</div>
    </div>
  `;

  const depthItems = [
    ["Depth 0", position.complexity.depth_breakdown.depth_0 ?? 0],
    ["Depth 1", position.complexity.depth_breakdown.depth_1 ?? 0],
    ["Depth 2", position.complexity.depth_breakdown.depth_2 ?? 0],
  ];
  const maxDepth = Math.max(...depthItems.map(([, value]) => value), 1);
  depthBreakdown.innerHTML = "";
  depthItems.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "depth-row";
    row.innerHTML = `
      <span>${label}</span>
      <div class="depth-bar"><span style="width:${(value / maxDepth) * 100}%"></span></div>
      <strong>${value}</strong>
    `;
    depthBreakdown.appendChild(row);
  });

  const actualMove = position.actual_move;
  if (!actualMove.available) {
    humanMoveCard.innerHTML = "No human continuation recorded after this position.";
    return;
  }
  humanMoveCard.innerHTML = `
    <strong>Actual human move</strong><br />
    ${actualMove.detail.san} (${actualMove.detail.uci})<br />
    Model rank: ${actualMove.model_rank ?? "not found"} •
    Model probability: ${actualMove.model_probability != null ? formatPercentage(actualMove.model_probability) : "n/a"} •
    Engine rank: ${actualMove.engine_rank ?? "not in top set"}
  `;
}

function renderMoveCards(container, moves, kind, position, extraMetaBuilder) {
  container.innerHTML = "";
  if (!moves.length) {
    container.innerHTML = `<div class="empty-state">No ${kind} moves available for this position.</div>`;
    return;
  }
  moves.forEach((move) => {
    const card = document.createElement("div");
    card.className = `move-card ${kind}`;
    if (kind === "model" && move.qualifies) card.classList.add("qualifying");
    if (position.actual_move?.detail?.uci === move.uci) card.classList.add("actual");
    const width = kind === "model"
      ? Math.max(move.probability * 100, 2)
      : Math.max((move.rank === 1 ? 100 : Math.max(20, 100 - move.rank * 12)), 12);
    card.innerHTML = `
      <div class="move-card-head">
        <span class="move-rank">#${move.rank}</span>
        <span class="move-san">${move.san ?? move.uci}</span>
      </div>
      <div class="move-card-body">
        <div class="prob-bar"><span style="width:${width}%"></span></div>
        <div class="move-meta">${extraMetaBuilder(move)}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderModelMoves(position) {
  renderMoveCards(
    modelMoves,
    position.model.top_moves,
    "model",
    position,
    (move) => [
      `<span>${move.uci}</span>`,
      `<span>${formatPercentage(move.probability)}</span>`,
      `<span>${move.qualifies ? ">=10%" : "<10%"}</span>`,
      position.actual_move?.detail?.uci === move.uci ? "<span>Actual move</span>" : "",
    ].filter(Boolean).join(""),
  );
}

function renderEngineMoves(position) {
  const engineTop = position.engine.moves.map((move) => ({
    ...move,
    rank: move.rank,
    san: move.san,
  }));
  renderMoveCards(
    engineMoves,
    engineTop,
    "engine",
    position,
    (move) => [
      `<span>${move.uci}</span>`,
      `<span>${move.score_text}</span>`,
      `<span>${move.pv_san}</span>`,
      position.actual_move?.detail?.uci === move.uci ? "<span>Actual move</span>" : "",
    ].join(""),
  );
}

function renderContinuation(position) {
  continuationList.innerHTML = "";
  if (!position.actual_continuation.length) {
    continuationList.innerHTML = `<div class="empty-state">No continuation available.</div>`;
    return;
  }
  position.actual_continuation.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "continuation-item";
    div.innerHTML = `
      <span>${index + 1}. ${item.san}</span>
      <span>${item.fullmove_number} • after move side ${item.side_to_move_after}</span>
    `;
    continuationList.appendChild(div);
  });
}

function renderTree(position) {
  treeView.innerHTML = "";
  const groups = position.model.tree_nodes_by_depth;
  const labels = {
    "0": "Depth 0: root move choices",
    "1": "Depth 1: reply branches",
    "2": "Depth 2: third-ply follow-ups",
  };

  Object.entries(groups).forEach(([depth, nodes]) => {
    const section = document.createElement("div");
    section.className = "tree-depth";
    section.innerHTML = `<h4>${labels[depth]}</h4>`;

    if (!nodes.length) {
      section.innerHTML += `<div class="empty-state">No nodes available at this depth.</div>`;
      treeView.appendChild(section);
      return;
    }

    nodes.forEach((node) => {
      const item = document.createElement("div");
      item.className = "tree-node";
      const pathLabel = node.path_uci.length ? node.path_uci.join(" → ") : "root";
      item.innerHTML = `
        <div class="node-path">${pathLabel}</div>
        <div>Path probability ${formatPercentage(node.path_probability)} • qualifying moves ${node.qualifying_move_count} • win prob ${formatPercentage(node.win_prob)}</div>
      `;
      const chips = document.createElement("div");
      chips.className = "node-moves";
      node.qualifying_moves.forEach((move) => {
        const chip = document.createElement("span");
        chip.className = "node-chip";
        chip.textContent = `${move.uci} ${formatPercentage(move.probability)}`;
        chips.appendChild(chip);
      });
      item.appendChild(chips);
      section.appendChild(item);
    });
    treeView.appendChild(section);
  });
}

function renderMaiaEngineConflict(position) {
  const conflict = position.conflicts.maia_high_engine_bad;
  if (!conflict.flagged) {
    maiaEngineConflictSummary.innerHTML = `
      <strong>No flagged Maia-high / engine-bad move here.</strong>
      <div class="muted-line">Threshold: Stockfish best minus candidate at least ${conflict.gap_threshold_cp} cp, while Maia still gives that move at least 10% probability. Shallow missing moves in this position: ${conflict.shallow_missing_count}.</div>
    `;
    maiaEngineConflictList.innerHTML = `<div class="empty-state">This position does not currently trigger the Maia-high / engine-bad filter.</div>`;
    return;
  }

  const actualConflict = conflict.moves.find((move) => move.is_actual_move);
  maiaEngineConflictSummary.innerHTML = `
    <strong>${conflict.move_count} flagged move${conflict.move_count === 1 ? "" : "s"} in this position.</strong>
    <div class="muted-line">These are Maia moves with probability >=10% that trail Stockfish's best move by at least ${conflict.gap_threshold_cp} centipawns.${actualConflict ? ` The human actually played ${actualConflict.san}.` : ""}</div>
  `;
  maiaEngineConflictList.innerHTML = "";
  conflict.moves.forEach((move) => {
    const card = document.createElement("div");
    card.className = "move-card model";
    if (move.is_actual_move) card.classList.add("actual");
    const width = Math.max(move.probability * 100, 2);
    card.innerHTML = `
      <div class="move-card-head">
        <span class="move-rank">#${move.maia_rank}</span>
        <span class="move-san">${move.san}</span>
      </div>
      <div class="move-card-body">
        <div class="prob-bar"><span style="width:${width}%"></span></div>
        <div class="move-meta">
          <span>${move.uci}</span>
          <span>${formatPercentage(move.probability)}</span>
          <span>Engine rank #${move.engine_rank}</span>
          <span>${move.engine_score_text}</span>
          <span>Gap ${formatCp(move.gap_cp)}</span>
          ${move.is_actual_move ? "<span>Actual move</span>" : ""}
        </div>
      </div>
    `;
    maiaEngineConflictList.appendChild(card);
  });
}

function renderEngineBestReluctance(position) {
  const conflict = position.conflicts.engine_best_maia_reluctant;
  const best = conflict.engine_best;
  if (!best) {
    engineBestReluctanceSummary.innerHTML = `<div class="empty-state">No engine-best / Maia-reluctant data available for this position.</div>`;
    return;
  }

  if (!conflict.flagged) {
    engineBestReluctanceSummary.innerHTML = `
      <strong>Engine best move is not currently flagged as Maia-reluctant.</strong>
      <div class="muted-line">Engine best: ${best.san} (${best.uci}) • score ${best.score_text} • Maia rank ${best.maia_rank ?? "n/a"} • Maia probability ${formatPercentage(best.maia_probability)}.</div>
      <div class="muted-line">This filter only triggers when the engine best move scores at least ${formatCp(conflict.strong_threshold_cp)} and Maia keeps it below ${formatPercentage(conflict.reluctant_probability)}.</div>
    `;
    return;
  }

  engineBestReluctanceSummary.innerHTML = `
    <strong>Stockfish strongly prefers ${best.san} (${best.uci}), but Maia discounts it.</strong>
    <div class="muted-line">Engine score ${best.score_text} • Maia rank ${best.maia_rank ?? "n/a"} • Maia probability ${formatPercentage(best.maia_probability)} • Human ${best.actual_matches ? "did" : "did not"} play the engine best move.</div>
    <div class="muted-line">PV: ${best.pv_san || "n/a"}</div>
  `;
}

function renderRealizabilityPosition(position) {
  const payload = position.experiments?.realizability;
  if (!payload?.available) {
    realizabilityPositionSummary.innerHTML = `<div class="empty-state">This position has no realizability analysis yet. The current v0 run only covers the scoped experiment subset.</div>`;
    realizabilityCandidateList.innerHTML = `<div class="empty-state">No realizability candidates available for this position.</div>`;
    realizabilityPositionNote.innerHTML = `Realizability asks whether an engine-valued idea is easy to cash in as a human: wide acceptable follow-ups, low refutation density, low unique-move burden, and small deviation penalties all push the score up.`;
    return;
  }

  const summary = payload.summary || {};
  const candidates = payload.candidates || [];
  realizabilityPositionSummary.innerHTML = `
    <strong>Actual vs engine-best realizability</strong>
    <div class="muted-line">Actual move: ${position.actual_move?.detail?.san || "n/a"} • actual score ${formatRealizability(summary.actual_realizability_score_v0)} • engine-best score ${formatRealizability(summary.engine_best_realizability_score_v0)} • delta ${summary.actual_minus_engine_best_realizability == null ? "—" : `${Number(summary.actual_minus_engine_best_realizability) >= 0 ? "+" : ""}${formatRealizability(summary.actual_minus_engine_best_realizability)}`}</div>
    <div class="muted-line">Top realizability candidate: ${summary.top_realizability_san || "n/a"} (${summary.top_realizability_uci || "n/a"}) • score ${formatRealizability(summary.top_realizability_score_v0)} • human ${summary.actual_matches_top_realizability ? "did" : "did not"} choose it.</div>
  `;

  realizabilityCandidateList.innerHTML = "";
  candidates.forEach((candidate, index) => {
    const card = document.createElement("div");
    card.className = "move-card engine";
    if (candidate.is_actual_move) card.classList.add("actual");
    if (candidate.is_engine_best) card.classList.add("qualifying");
    const width = Math.max(Number(candidate.realizability_score_v0 || 0), 6);
    const labels = [];
    if (candidate.is_actual_move) labels.push("Actual move");
    if (candidate.is_engine_best) labels.push("Engine best");
    if (candidate.forced_include_actual) labels.push("Forced include");
    card.innerHTML = `
      <div class="move-card-head">
        <span class="move-rank">#${index + 1}</span>
        <span class="move-san">${candidate.candidate_san || candidate.candidate_uci}</span>
      </div>
      <div class="move-card-body">
        <div class="prob-bar"><span style="width:${width}%"></span></div>
        <div class="move-meta">
          <span>${candidate.candidate_uci}</span>
          <span>R=${formatRealizability(candidate.realizability_score_v0)}</span>
          <span>Maia ${formatPercentage(candidate.maia_probability)}</span>
          <span>d1 width ${formatNumber(candidate.acceptable_width_player_d1)}</span>
          <span>survival ${formatPercentage(candidate.survival_rate_after_opponent)}</span>
          <span>burden ${candidate.unique_burden_plies ?? "—"}</span>
          ${labels.map((label) => `<span>${label}</span>`).join("")}
        </div>
      </div>
    `;
    realizabilityCandidateList.appendChild(card);
  });

  realizabilityPositionNote.innerHTML = `
    <strong>How to read this panel</strong>
    <div class="muted-line">Higher realizability means the move keeps more acceptable follow-ups, survives more opponent replies, and asks for fewer narrow or brittle continuations. The current v0 implementation follows the strongest opponent reply after one best acceptable player continuation, so this is a practical proxy, not the final theoretical metric.</div>
  `;
}

function clearSelectedPosition() {
  positionTitle.textContent = "No position selected";
  positionBadges.innerHTML = "";
  boardImage.removeAttribute("src");
  positionMeta.innerHTML = `<div class="empty-state">No positions match the current filter for this game.</div>`;
  complexityScoreCard.innerHTML = `<div class="empty-state">Pick another review focus or switch to a different game.</div>`;
  depthBreakdown.innerHTML = "";
  humanMoveCard.innerHTML = `<div class="empty-state">No human move details available.</div>`;
  modelMoves.innerHTML = `<div class="empty-state">No model moves to show.</div>`;
  engineMoves.innerHTML = `<div class="empty-state">No engine moves to show.</div>`;
  continuationList.innerHTML = `<div class="empty-state">No continuation available.</div>`;
  treeView.innerHTML = `<div class="empty-state">No tree data available.</div>`;
  maiaEngineConflictSummary.innerHTML = `<div class="empty-state">No conflict details available.</div>`;
  maiaEngineConflictList.innerHTML = "";
  engineBestReluctanceSummary.innerHTML = `<div class="empty-state">No conflict details available.</div>`;
  timeBudgetPositionSummary.innerHTML = `<div class="empty-state">No time-budget details available.</div>`;
  timeBudgetBudgetTable.innerHTML = "";
  realizabilityPositionSummary.innerHTML = `<div class="empty-state">No realizability details available.</div>`;
  realizabilityCandidateList.innerHTML = `<div class="empty-state">No realizability candidates available.</div>`;
  realizabilityPositionNote.innerHTML = `Realizability asks whether an engine-valued idea is easy to cash in as a human.`;
}

function renderLoadingState(message = "Loading game data…") {
  positionTitle.textContent = message;
  positionBadges.innerHTML = "";
  boardImage.removeAttribute("src");
  positionMeta.innerHTML = `<div class="empty-state">${message}</div>`;
  complexityScoreCard.innerHTML = `<div class="empty-state">${message}</div>`;
  depthBreakdown.innerHTML = "";
  humanMoveCard.innerHTML = `<div class="empty-state">${message}</div>`;
  modelMoves.innerHTML = `<div class="empty-state">${message}</div>`;
  engineMoves.innerHTML = `<div class="empty-state">${message}</div>`;
  continuationList.innerHTML = `<div class="empty-state">${message}</div>`;
  treeView.innerHTML = `<div class="empty-state">${message}</div>`;
  maiaEngineConflictSummary.innerHTML = `<div class="empty-state">${message}</div>`;
  maiaEngineConflictList.innerHTML = "";
  engineBestReluctanceSummary.innerHTML = `<div class="empty-state">${message}</div>`;
  timeBudgetPositionSummary.innerHTML = `<div class="empty-state">${message}</div>`;
  timeBudgetBudgetTable.innerHTML = "";
  realizabilityPositionSummary.innerHTML = `<div class="empty-state">${message}</div>`;
  realizabilityCandidateList.innerHTML = `<div class="empty-state">${message}</div>`;
  realizabilityPositionNote.innerHTML = message;
}

function renderSelectedPosition(game) {
  const position = currentPosition(game);
  if (!position) {
    clearSelectedPosition();
    return;
  }
  selectedPositionId = position.position_id;
  positionTitle.textContent = `${position.position_id} • ${position.label}`;
  boardImage.src = position.board_image;
  renderBadges(position);
  renderPositionMeta(position);
  renderScore(position);
  renderModelMoves(position);
  renderEngineMoves(position);
  renderContinuation(position);
  renderTree(position);
  renderMaiaEngineConflict(position);
  renderEngineBestReluctance(position);
  renderTimeBudgetPosition(position);
  renderRealizabilityPosition(position);
}

function ensureSelectedPosition(game) {
  const positions = filteredPositions(game);
  if (!positions.length) {
    selectedPositionId = null;
    return;
  }
  const stillVisible = positions.find((position) => position.position_id === selectedPositionId);
  if (stillVisible) {
    return;
  }
  selectedPositionId = positions[0].position_id;
}

async function render() {
  const game = currentGame();
  renderFilterHelp();
  renderRankOverview();
  renderRankBucketTable();
  renderTimeBudgetOverview();
  renderRealizabilityOverview();
  renderRealizabilityBucketTable();
  if (!game) {
    clearSelectedPosition();
    return;
  }
  renderGameMeta(game);
  if (splitDataMode && !Array.isArray(game.positions)) {
    timelineCount.textContent = `${game.position_count ?? game.stats?.eligible_positions ?? 0} steps`;
    positionList.innerHTML = `<div class="empty-state">Loading positions for ${game.white} vs ${game.black}…</div>`;
    renderLoadingState(`Loading ${game.game_id} positions…`);
    await ensureGameLoaded(game.game_id);
  }
  ensureSelectedPosition(game);
  renderPositionList(game);
  renderSelectedPosition(game);
}

function renderFilterHelp() {
  reviewFilterHelp.textContent = FILTERS[reviewFilter.value].help;
}

async function init() {
  bundle = await loadBundle();
  buildSummary();
  renderGameOptions();
  renderFilterOptions();
  renderRankModelOptions();

  selectedGameId = bundle.games[0]?.game_id ?? null;
  gameSelect.value = selectedGameId;
  selectedPositionId = null;

  gameSelect.addEventListener("change", async () => {
    selectedGameId = gameSelect.value;
    selectedPositionId = null;
    await render();
  });

  reviewFilter.addEventListener("change", async () => {
    selectedPositionId = null;
    await render();
  });

  rankModelSelect.addEventListener("change", async () => {
    await render();
  });

  await render();
}

init();
