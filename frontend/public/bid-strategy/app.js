let rules = [];
let ruleFiles = [];
let activeRunId = 0;
const DEFAULT_SIGMA_RATIO = 0.05;
let sigmaAutoMode = true;
let lastBacktestResult = null;

const els = {
  ceiling: document.getElementById("ceilingInput"),
  floor: document.getElementById("floorInput"),
  minProfitRate: document.getElementById("minProfitRateInput"),
  step: document.getElementById("stepInput"),
  precision: document.getElementById("precisionInput"),
  marketMean: document.getElementById("marketMeanInput"),
  sigma: document.getElementById("sigmaInput"),
  bidderMode: document.getElementById("bidderModeInput"),
  bidderCount: document.getElementById("bidderCountInput"),
  bidderMin: document.getElementById("bidderMinInput"),
  bidderMax: document.getElementById("bidderMaxInput"),
  simulationCount: document.getElementById("simulationCountInput"),
  ruleSelect: document.getElementById("ruleSelect"),
  runButton: document.getElementById("runButton"),
  sampleButton: document.getElementById("sampleButton"),
  autoSigmaButton: document.getElementById("autoSigmaButton"),
  statusText: document.getElementById("statusText"),
  bestBid: document.getElementById("bestBid"),
  bestScore: document.getElementById("bestScore"),
  benchmark: document.getElementById("benchmark"),
  scoreGap: document.getElementById("scoreGap"),
  bestBidNote: document.getElementById("bestBidNote"),
  scoreNote: document.getElementById("scoreNote"),
  benchmarkNote: document.getElementById("benchmarkNote"),
  gapNote: document.getElementById("gapNote"),
  chart: document.getElementById("scoreChart"),
  chartTooltip: document.getElementById("chartTooltip"),
  chartCaption: document.getElementById("chartCaption"),
  message: document.getElementById("messageBox"),
  rankingBody: document.getElementById("rankingBody"),
  ruleCards: document.getElementById("ruleCards"),
  refreshFilesButton: document.getElementById("refreshFilesButton"),
  parseRuleButton: document.getElementById("parseRuleButton"),
  saveParsedRuleButton: document.getElementById("saveParsedRuleButton"),
  ruleFileSelect: document.getElementById("ruleFileSelect"),
  extractedText: document.getElementById("extractedText"),
  draftRuleJson: document.getElementById("draftRuleJson"),
  backendStatus: document.getElementById("backendStatus"),
  sigmaAutoNote: document.getElementById("sigmaAutoNote"),
  actualBids: document.getElementById("actualBidsInput"),
  backtestButton: document.getElementById("backtestButton"),
  calibrateButton: document.getElementById("calibrateButton"),
  exportBacktestButton: document.getElementById("exportBacktestButton")
};

const currency = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });

function formatMoney(value) {
  return Number.isFinite(value) ? currency.format(value) : "-";
}

function formatNumber(value, precision = 3) {
  return Number.isFinite(value) ? value.toFixed(precision) : "-";
}

function formatPct(value, precision = 3) {
  return Number.isFinite(value) ? `${(value * 100).toFixed(precision)}%` : "-";
}

function defaultSigmaFromCeiling(ceiling) {
  if (!Number.isFinite(ceiling) || ceiling <= 0) return 0;
  return Math.round((ceiling * DEFAULT_SIGMA_RATIO) / 1000) * 1000;
}

function updateSigmaNote() {
  if (!els.sigmaAutoNote) return;
  const ceiling = Number(els.ceiling.value);
  const autoValue = defaultSigmaFromCeiling(ceiling);
  els.sigmaAutoNote.textContent = sigmaAutoMode
    ? `自动：最高限价 × 5% = ${formatMoney(autoValue)}。可手动调整。`
    : `手动：当前 σ=${formatMoney(Number(els.sigma.value))}。点击“σ按最高限价自动”可恢复自动。`;
}

function applyAutoSigma() {
  const value = defaultSigmaFromCeiling(Number(els.ceiling.value));
  if (value > 0) els.sigma.value = String(value);
  updateSigmaNote();
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.detail || "请求失败");
  return data;
}

async function loadRules(selectedId) {
  rules = await api("/api/bid-strategy/rules");
  renderRuleOptions(selectedId);
  renderRuleCards();
}

async function loadRuleFiles() {
  ruleFiles = await api("/api/bid-strategy/rule-files");
  els.ruleFileSelect.replaceChildren(...ruleFiles.map(file => {
    const option = document.createElement("option");
    option.value = file.path;
    option.textContent = `${file.name} (${file.extension})`;
    return option;
  }));
  if (!ruleFiles.length) {
    const option = document.createElement("option");
    option.textContent = "未发现规则文件";
    option.value = "";
    els.ruleFileSelect.appendChild(option);
  }
}

async function loadHealth() {
  try {
    const health = await api("/api/bid-strategy/health");
    const mineru = health.mineruAvailable ? `MinerU 可用：${health.mineruPath || "PATH"}` : "MinerU 未检测到";
    const rapidocr = health.rapidocrAvailable ? "RapidOCR 可用" : "RapidOCR 未安装";
    const ollama = health.ollamaAvailable ? `Ollama 可用：${health.ollamaModel}` : `Ollama 未连接：${health.ollamaModel}`;
    els.backendStatus.textContent = `${rapidocr}；${mineru}；${ollama}。图片优先使用 RapidOCR，复杂 PDF 使用 MinerU。`;
  } catch {
    els.backendStatus.textContent = "后端状态检测失败，请使用 python server.py 启动系统。";
  }
}

function renderRuleOptions(selectedId) {
  const confirmedRules = rules.filter(rule => rule.status !== "draft");
  els.ruleSelect.replaceChildren(...confirmedRules.map(rule => {
    const option = document.createElement("option");
    option.value = rule.id;
    option.textContent = rule.name;
    option.selected = rule.id === selectedId;
    return option;
  }));
}

function renderRuleCards() {
  els.ruleCards.replaceChildren(...rules.map(rule => {
    const card = document.createElement("article");
    card.className = "rule-card";
    const title = document.createElement("h3");
    title.textContent = rule.name;
    const meta = document.createElement("p");
    meta.textContent = `${rule.source || "未知来源"} · ${rule.status === "draft" ? "草稿" : "已确认"}`;
    const detail = document.createElement("p");
    const correction = rule.benchmark?.correction;
    const correctionText = correction?.enabled ? `${correction.mode} ${correction.lowerFactor ?? "-"}~${correction.upperFactor ?? "-"}` : "无修正";
    const weightText = Number.isFinite(rule.scoreWeight) ? `；权重：${formatPct(rule.scoreWeight, 0)}` : "";
    detail.textContent = `基准价：${rule.benchmark?.factor ?? 1} × 平均价；去值：${rule.benchmark?.trimMode || "none"}；修正：${correctionText}；评分：${rule.score?.type || "unknown"}；满分：${rule.maxScore}${weightText}`;
    card.append(title, meta, detail);
    return card;
  }));
}

function trimValues(values, trimMode, originalCount = values.length) {
  const sorted = values.slice().sort((a, b) => a - b);
  if (trimMode === "drop_high" && sorted.length > 1) return sorted.slice(0, -1);
  if (trimMode === "drop_low" && sorted.length > 1) return sorted.slice(1);
  if (trimMode === "drop_high_low" && sorted.length > 2) return sorted.slice(1, -1);
  if (trimMode === "over5_drop_high_low" && sorted.length > 5) return sorted.slice(1, -1);
  if (trimMode === "rule2_correction" && originalCount > 5 && sorted.length > 1) return sorted.slice(1);
  if (trimMode === "rule4_count") {
    if (sorted.length <= 5) return sorted;
    if (sorted.length <= 7) return sorted.slice(0, -1);
    return sorted.slice(1, -1);
  }
  if (trimMode === "rule13_count") {
    if (sorted.length <= 1) return sorted.slice(0, 1);
    if (sorted.length < 3) return sorted;
    if (sorted.length <= 5) return sorted.slice(0, -1);
    return sorted.slice(1, -2);
  }
  if (trimMode === "rule14_count") {
    let n = 0;
    if (sorted.length > 20) n = 3;
    else if (sorted.length > 10) n = 2;
    else if (sorted.length > 5) n = 1;
    return n > 0 && sorted.length > n * 2 ? sorted.slice(n, -n) : sorted;
  }
  if (trimMode === "rule15_count") {
    if (sorted.length >= 15) return sorted.slice(2, -2);
    if (sorted.length >= 10) return sorted.slice(1, -1);
    return sorted;
  }
  if (trimMode === "rule16_count") {
    return sorted.length > 5 ? sorted.slice(1, -1) : sorted;
  }
  if (trimMode === "rule18_count") {
    return sorted.length >= 5 ? sorted.slice(1, -1) : sorted;
  }
  if (trimMode === "rule20_count") {
    if (sorted.length <= 3) return sorted;
    if (sorted.length <= 6) return sorted.slice(0, -1);
    return sorted.slice(1, -1);
  }
  if (trimMode === "rule22_count") {
    return sorted.length >= 5 ? sorted.slice(1, -1) : sorted;
  }
  return sorted;
}

function calculateBenchmark(rule, quotes) {
  const benchmarkRule = rule.benchmark || {};
  const correction = benchmarkRule.correction || {};
  const roundBenchmark = value => Number.isFinite(benchmarkRule.roundPrecision)
    ? Number(value.toFixed(Number(benchmarkRule.roundPrecision)))
    : value;
  if (benchmarkRule.trimMode === "rule19_control") {
    const initialAverage = mean(quotes);
    const lower = initialAverage * 0.8;
    const upper = initialAverage * 1.15;
    let basis = quotes.slice();
    if (quotes.length > 3) {
      const inRange = quotes.filter(value => value >= lower && value <= upper);
      if (inRange.length >= 3) {
        basis = inRange;
      } else {
        basis = quotes.slice();
        while (basis.length > 3 && basis.some(value => value < lower || value > upper)) {
          let removeIndex = 0;
          let maxDistance = -Infinity;
          basis.forEach((value, index) => {
            const distance = Math.abs(value - initialAverage);
            if (distance > maxDistance) {
              maxDistance = distance;
              removeIndex = index;
            }
          });
          basis.splice(removeIndex, 1);
        }
      }
    }
    return roundBenchmark(mean(basis) * (benchmarkRule.factor ?? 1));
  }
  if (benchmarkRule.trimMode === "rule22_count") {
    const base = mean(trimValues(quotes, "rule22_count", quotes.length));
    const floatRate = Number.isFinite(benchmarkRule.floatRate) ? Number(benchmarkRule.floatRate) : 0;
    return roundBenchmark(base * (benchmarkRule.factor ?? 1) * (1 + floatRate));
  }
  if (benchmarkRule.trimMode === "rule13_count" && quotes.length <= 1) {
    return roundBenchmark(Math.min(...quotes));
  }
  if (benchmarkRule.trimMode === "rule16_count" || benchmarkRule.trimMode === "rule18_count") {
    const base = trimValues(quotes, benchmarkRule.trimMode, quotes.length);
    const baseAverage = mean(base);
    const filtered = base.filter(value => Math.abs((value - baseAverage) / baseAverage) < 0.3);
    const averagePart = mean(filtered.length ? filtered : base);
    const minPart = Math.min(...base);
    return roundBenchmark(minPart * 0.5 + averagePart * 0.5);
  }
  let benchmark = mean(trimValues(quotes, benchmarkRule.trimMode, quotes.length)) * (benchmarkRule.factor ?? 1);
  if (!correction.enabled) return roundBenchmark(benchmark);
  if (Array.isArray(correction.skipCounts) && correction.skipCounts.includes(quotes.length)) return roundBenchmark(benchmark);

  const rounds = Math.max(1, Number(correction.rounds || 1));
  for (let round = 0; round < rounds; round += 1) {
    const lower = Number.isFinite(correction.lowerFactor) ? benchmark * correction.lowerFactor : -Infinity;
    const upper = Number.isFinite(correction.upperFactor) ? benchmark * correction.upperFactor : Infinity;
    const hasOutside = quotes.some(value => value < lower || value >= upper);
    if (!hasOutside) break;
    let adjusted;
    if (correction.mode === "remove_outside") {
      adjusted = quotes.filter(value => value >= lower && value < upper);
      if (!adjusted.length) adjusted = quotes.slice();
    } else {
      adjusted = quotes.map(value => Math.min(upper, Math.max(lower, value)));
    }
    const correctionTrimMode = correction.trimMode || benchmarkRule.trimMode;
    const next = mean(trimValues(adjusted, correctionTrimMode, quotes.length)) * (benchmarkRule.factor ?? 1);
    if (Math.abs(next - benchmark) < 0.000001) break;
    benchmark = next;
  }
  return roundBenchmark(benchmark);
}

function scoreQuote(rule, quote, benchmark) {
  const scoreRule = rule.score || {};
  const maxScore = Number(rule.maxScore || 100);
  const deviation = (quote - benchmark) / benchmark;
  const deviationPct = deviation * 100;
  let score;

  if (scoreRule.type === "target_price") {
    const target = benchmark * Number(scoreRule.targetFactor || 1);
    if (quote < target && Number.isFinite(scoreRule.belowTargetScore)) {
      score = Number(scoreRule.belowTargetScore);
    } else if (quote < target) {
      score = maxScore - ((target - quote) / target) * 100 * Number(scoreRule.lowPenaltyPerPct || 0);
    } else {
      score = maxScore - ((quote - target) / target) * 100 * Number(scoreRule.highPenaltyPerPct || 0);
    }
  } else if (scoreRule.type === "band") {
    const fullLow = Number(scoreRule.fullLowPct || 0);
    const fullHigh = Number(scoreRule.fullHighPct || 0);
    if (deviationPct > fullLow && deviationPct <= fullHigh) {
      score = maxScore;
    } else if (deviationPct <= fullLow) {
      score = maxScore - (fullLow - deviationPct) * Number(scoreRule.lowPenaltyPerPct || 0);
    } else {
      score = maxScore - (deviationPct - fullHigh) * Number(scoreRule.highPenaltyPerPct || 0);
    }
  } else if (scoreRule.type === "rule15_band") {
    if (deviationPct > 5) {
      score = maxScore - 2.5 - (deviationPct - 5) * 1;
    } else if (deviationPct > 0) {
      score = maxScore - deviationPct * 0.5;
    } else if (deviationPct > -3) {
      score = maxScore;
    } else if (deviationPct > -10) {
      score = maxScore - (-3 - deviationPct) * 0.5;
    } else {
      score = maxScore - 3.5 - (-10 - deviationPct) * 1;
    }
  } else if (scoreRule.type === "rule16_tier") {
    if (deviationPct > 10) {
      score = maxScore - 10 - (deviationPct - 10) * 1.2;
    } else if (deviationPct > 0) {
      score = maxScore - deviationPct * 1;
    } else if (deviationPct >= -5) {
      score = maxScore;
    } else if (deviationPct >= -10) {
      score = maxScore - (-5 - deviationPct) * 0.2;
    } else {
      score = maxScore - 1 - (-10 - deviationPct) * 0.5;
    }
  } else if (scoreRule.type === "rule17_table") {
    if (deviationPct <= -19 || deviationPct >= 5) {
      score = 56;
    } else if (deviationPct >= -7 && deviationPct <= -3) {
      score = 100;
    } else {
      const points = [
        [-19, 56],
        [-16, 68],
        [-13, 80],
        [-10, 90],
        [-7, 100],
        [-3, 100],
        [-1, 90],
        [1, 80],
        [3, 68],
        [5, 56]
      ];
      let lowerPoint = points[0];
      let upperPoint = points[points.length - 1];
      for (let i = 0; i < points.length - 1; i += 1) {
        if (deviationPct >= points[i][0] && deviationPct <= points[i + 1][0]) {
          lowerPoint = points[i];
          upperPoint = points[i + 1];
          break;
        }
      }
      const ratio = (deviationPct - lowerPoint[0]) / (upperPoint[0] - lowerPoint[0]);
      score = lowerPoint[1] + (upperPoint[1] - lowerPoint[1]) * ratio;
    }
  } else if (scoreRule.type === "rule19_score") {
    const baseScore = Number.isFinite(scoreRule.baseScore) ? Number(scoreRule.baseScore) : maxScore;
    if (deviationPct > 5) {
      score = baseScore - 5 - (deviationPct - 5) * 1.5;
    } else if (deviationPct > 0) {
      score = baseScore - deviationPct * 1;
    } else if (deviationPct === 0) {
      score = baseScore;
    } else {
      score = baseScore + Math.abs(deviationPct) * 0.5;
    }
  } else if (scoreRule.type === "rule20_score") {
    const baseScore = Number.isFinite(scoreRule.baseScore) ? Number(scoreRule.baseScore) : 95;
    if (deviationPct > 0) {
      score = Math.max(60, baseScore - deviationPct);
    } else if (deviationPct === 0) {
      score = baseScore;
    } else {
      const belowPct = Math.abs(deviationPct);
      if (belowPct <= 5) {
        score = Math.min(maxScore, baseScore + belowPct);
      } else if (belowPct < 20) {
        score = maxScore - (belowPct - 5);
      } else {
        score = 85;
      }
    }
  } else if (scoreRule.type === "rule21_score") {
    const baseScore = Number.isFinite(scoreRule.baseScore) ? Number(scoreRule.baseScore) : 80;
    const rationalityScore = Number.isFinite(scoreRule.rationalityScore) ? Number(scoreRule.rationalityScore) : 15;
    let priceScore;
    if (deviationPct > 0) {
      priceScore = Math.max(60, baseScore - deviationPct);
    } else if (deviationPct === 0) {
      priceScore = baseScore;
    } else {
      const belowPct = Math.abs(deviationPct);
      if (belowPct <= 5) {
        priceScore = Math.min(85, baseScore + belowPct);
      } else if (belowPct < 20) {
        priceScore = 85 - (belowPct - 5);
      } else {
        priceScore = 70;
      }
    }
    score = priceScore + rationalityScore;
  } else if (scoreRule.type === "rule22_score") {
    if (deviationPct > 0) {
      score = maxScore - deviationPct * 2;
    } else {
      score = maxScore;
    }
  } else if (scoreRule.type === "distance") {
    score = maxScore - Math.abs(deviationPct) * Number(scoreRule.highPenaltyPerPct || 1);
  } else {
    score = deviationPct > 0
      ? maxScore - deviationPct * Number(scoreRule.highPenaltyPerPct || 0)
      : maxScore - Math.abs(deviationPct) * Number(scoreRule.lowPenaltyPerPct || 0);
  }

  const minScore = Number.isFinite(scoreRule.minScore) ? Number(scoreRule.minScore) : 0;
  if (scoreRule.type === "target_price" && quote >= benchmark * Number(scoreRule.targetFactor || 1)) {
    score = Math.max(minScore, score);
  }
  const finalScoreRaw = Math.min(maxScore, Math.max(minScore, score));
  const finalScore = Number.isFinite(scoreRule.roundPrecision)
    ? Number(finalScoreRaw.toFixed(Number(scoreRule.roundPrecision)))
    : finalScoreRaw;
  const weightedScore = Number.isFinite(rule.scoreWeight) ? finalScore * Number(rule.scoreWeight) : finalScore;
  return { score: finalScore, weightedScore, deviation };
}

function evaluateBid(rule, competitors, myBid) {
  const allQuotes = competitors.map(item => item.amount).concat(myBid);
  const benchmark = calculateBenchmark(rule, allQuotes);
  const scoredCompetitors = competitors.map(item => ({ ...item, ...scoreQuote(rule, item.amount, benchmark) }));
  const myScore = scoreQuote(rule, myBid, benchmark);
  const topCompetitor = scoredCompetitors.reduce((best, item) => {
    if (!best || item.score > best.score) return item;
    if (item.score === best.score && item.amount < best.amount) return item;
    return best;
  }, null);
  return {
    bid: myBid,
    benchmark,
    myScore: myScore.score,
    myDeviation: myScore.deviation,
    scoredCompetitors,
    topCompetitor,
    wins: !topCompetitor || myScore.score >= topCompetitor.score
  };
}

function searchBestBid(rule, competitors, floor, ceiling, step) {
  const points = [];
  let bestWinning = null;
  let bestScoring = null;
  for (let bid = floor; bid <= ceiling + 0.0001; bid += step) {
    const result = evaluateBid(rule, competitors, bid);
    points.push(result);
    if (!bestScoring || result.myScore > bestScoring.myScore || (result.myScore === bestScoring.myScore && result.bid < bestScoring.bid)) {
      bestScoring = result;
    }
    if (result.wins && (!bestWinning || result.myScore > bestWinning.myScore || (result.myScore === bestWinning.myScore && result.bid > bestWinning.bid))) {
      bestWinning = result;
    }
  }
  return { points, best: bestWinning || bestScoring, bestScoring, hasWinningBid: Boolean(bestWinning) };
}

function seededRandom(seed = 20260714) {
  let state = seed >>> 0;
  return function rand() {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function normalRandom(rand, meanValue, sigmaValue) {
  const u1 = Math.max(rand(), 1e-12);
  const u2 = Math.max(rand(), 1e-12);
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return meanValue + z * sigmaValue;
}

function generateCompetitors(rand, count, meanValue, sigmaValue, ceiling) {
  const competitors = [];
  for (let i = 0; i < count; i += 1) {
    let amount = normalRandom(rand, meanValue, sigmaValue);
    let guard = 0;
    while ((amount <= 0 || amount > ceiling) && guard < 20) {
      amount = normalRandom(rand, meanValue, sigmaValue);
      guard += 1;
    }
    amount = Math.min(ceiling, Math.max(1, amount));
    competitors.push({ name: `模拟对手${i + 1}`, amount });
  }
  return competitors;
}

function drawBidderCount(rand, bidderMode, bidderCount, bidderMin, bidderMax) {
  if (bidderMode === "fixed") return Math.max(2, Math.round(bidderCount));
  const minCount = Math.max(2, Math.round(Math.min(bidderMin, bidderMax)));
  const maxCount = Math.max(minCount, Math.round(Math.max(bidderMin, bidderMax)));
  return minCount + Math.floor(rand() * (maxCount - minCount + 1));
}

function buildMarketScenarios(ceiling, marketMean) {
  if (Number.isFinite(marketMean) && marketMean > 0) {
    return [{ label: "手动 μ", mean: marketMean, weight: 1 }];
  }
  return [0.85, 0.9, 0.95].map(factor => ({
    label: `H×${factor}`,
    mean: ceiling * factor,
    weight: 1
  }));
}

function scenarioText(scenarios) {
  return scenarios.map(item => `${item.label}=${formatMoney(item.mean)}`).join("，");
}

function buildFloatRateScenarios(rule) {
  const configured = rule?.benchmark?.floatRateScenarios;
  if (Array.isArray(configured) && configured.length) {
    return configured.map(Number).filter(Number.isFinite);
  }
  if (rule?.id === "rule22") return [-0.1, -0.075, -0.05, -0.025, 0];
  const fixed = Number(rule?.benchmark?.floatRate);
  return Number.isFinite(fixed) && fixed !== 0 ? [fixed] : [0];
}

function floatRateScenarioText(rates) {
  const nonZero = rates.filter(rate => Math.abs(rate) > 1e-12);
  if (!nonZero.length) return "浮动率=0%";
  return `浮动率场景：${rates.map(rate => `${(rate * 100).toFixed(1)}%`).join("，")}`;
}

function ruleWithFloatRate(rule, floatRate) {
  if (!Number.isFinite(floatRate) || Math.abs(floatRate - Number(rule?.benchmark?.floatRate || 0)) < 1e-12) return rule;
  return {
    ...rule,
    benchmark: {
      ...(rule.benchmark || {}),
      floatRate
    }
  };
}

function monteCarloSearch(rule, floor, ceiling, step, marketScenarios, sigma, bidderMode, bidderCount, bidderMin, bidderMax, simulationCount) {
  const points = [];
  let best = null;
  const maxScore = Number(rule.maxScore || 100);
  const floatRateScenarios = buildFloatRateScenarios(rule);

  for (let bid = floor; bid <= ceiling + 0.0001; bid += step) {
    const rand = seededRandom(20260714 + Math.round(bid));
    let totalScore = 0;
    let totalBenchmark = 0;
    let wins = 0;
    let fullScores = 0;
    let totalBidderCount = 0;

    for (let i = 0; i < simulationCount; i += 1) {
      const scenario = marketScenarios[i % marketScenarios.length];
      const scenarioRule = ruleWithFloatRate(rule, floatRateScenarios[i % floatRateScenarios.length]);
      const sampledBidderCount = drawBidderCount(rand, bidderMode, bidderCount, bidderMin, bidderMax);
      const opponentCount = Math.max(1, sampledBidderCount - 1);
      const competitors = generateCompetitors(rand, opponentCount, scenario.mean, sigma, ceiling);
      const result = evaluateBid(scenarioRule, competitors, bid);
      totalScore += result.myScore;
      totalBenchmark += result.benchmark;
      totalBidderCount += sampledBidderCount;
      if (result.wins) wins += 1;
      if (result.myScore >= maxScore - 1e-9) fullScores += 1;
    }

    const point = {
      bid,
      myScore: totalScore / simulationCount,
      benchmark: totalBenchmark / simulationCount,
      averageBidderCount: totalBidderCount / simulationCount,
      winProbability: wins / simulationCount,
      fullScoreProbability: fullScores / simulationCount,
      expectedProfit: bid - floor,
      wins: wins / simulationCount >= 0.5,
      scoredCompetitors: [],
      topCompetitor: null,
      myDeviation: 0
    };
    points.push(point);
    if (!best || point.myScore > best.myScore || (point.myScore === best.myScore && point.bid > best.bid)) {
      best = point;
    }
  }
  return { points, best };
}

function waitForBrowser() {
  return new Promise(resolve => setTimeout(resolve, 0));
}

async function monteCarloSearchAsync(rule, floor, ceiling, step, marketScenarios, sigma, bidderMode, bidderCount, bidderMin, bidderMax, simulationCount, onProgress, runId) {
  const points = [];
  let best = null;
  const maxScore = Number(rule.maxScore || 100);
  const floatRateScenarios = buildFloatRateScenarios(rule);
  const candidates = [];
  for (let bid = floor; bid <= ceiling + 0.0001; bid += step) {
    candidates.push(bid);
  }

  let lastYield = performance.now();
  for (let candidateIndex = 0; candidateIndex < candidates.length; candidateIndex += 1) {
    if (runId !== activeRunId) throw new Error("本次计算已取消。");

    const bid = candidates[candidateIndex];
    const rand = seededRandom(20260714 + Math.round(bid));
    let totalScore = 0;
    let totalBenchmark = 0;
    let wins = 0;
    let fullScores = 0;
    let totalBidderCount = 0;

    for (let i = 0; i < simulationCount; i += 1) {
      const scenario = marketScenarios[i % marketScenarios.length];
      const scenarioRule = ruleWithFloatRate(rule, floatRateScenarios[i % floatRateScenarios.length]);
      const sampledBidderCount = drawBidderCount(rand, bidderMode, bidderCount, bidderMin, bidderMax);
      const opponentCount = Math.max(1, sampledBidderCount - 1);
      const competitors = generateCompetitors(rand, opponentCount, scenario.mean, sigma, ceiling);
      const result = evaluateBid(scenarioRule, competitors, bid);
      totalScore += result.myScore;
      totalBenchmark += result.benchmark;
      totalBidderCount += sampledBidderCount;
      if (result.wins) wins += 1;
      if (result.myScore >= maxScore - 1e-9) fullScores += 1;
    }

    const point = {
      bid,
      myScore: totalScore / simulationCount,
      benchmark: totalBenchmark / simulationCount,
      averageBidderCount: totalBidderCount / simulationCount,
      winProbability: wins / simulationCount,
      fullScoreProbability: fullScores / simulationCount,
      expectedProfit: bid - floor,
      wins: wins / simulationCount >= 0.5,
      scoredCompetitors: [],
      topCompetitor: null,
      myDeviation: 0
    };
    points.push(point);
    if (!best || point.myScore > best.myScore || (point.myScore === best.myScore && point.bid > best.bid)) {
      best = point;
    }

    const now = performance.now();
    if (now - lastYield > 50 || candidateIndex === candidates.length - 1) {
      onProgress?.(candidateIndex + 1, candidates.length, best);
      lastYield = now;
      await waitForBrowser();
    }
  }
  return { points, best };
}

function validateInputs() {
  const ceiling = Number(els.ceiling.value);
  const floor = Number(els.floor.value);
  const minProfitRate = Number(els.minProfitRate.value || 0);
  const step = Number(els.step.value);
  const precision = Number(els.precision.value);
  const marketMeanRaw = els.marketMean.value.trim();
  const marketMean = marketMeanRaw ? Number(marketMeanRaw) : null;
  const sigma = Number(els.sigma.value);
  const bidderMode = els.bidderMode.value;
  const bidderCount = Number(els.bidderCount.value);
  const bidderMin = Number(els.bidderMin.value);
  const bidderMax = Number(els.bidderMax.value);
  const simulationCount = Number(els.simulationCount.value);
  const numericValues = marketMean === null
    ? [ceiling, floor, minProfitRate, step, precision, sigma, bidderCount, bidderMin, bidderMax, simulationCount]
    : [ceiling, floor, minProfitRate, step, precision, marketMean, sigma, bidderCount, bidderMin, bidderMax, simulationCount];
  if (!numericValues.every(Number.isFinite)) throw new Error("所有模拟参数都必须是数字。");
  if (ceiling <= 0 || floor <= 0 || step <= 0 || sigma < 0) throw new Error("最高限价、成本、步长必须大于 0，σ 不能为负。");
  if (minProfitRate <= -100) throw new Error("成本搜索调整不能小于或等于 -100%；例如 -5 表示从成本的 95% 开始搜索。");
  if (marketMean !== null && marketMean <= 0) throw new Error("市场合理均价 μ 如果填写，必须大于 0；不知道时可以留空。");
  if (floor > ceiling) throw new Error("我的成本/保本线不能高于最高报价限制。");
  const searchFloor = floor * (1 + minProfitRate / 100);
  if (searchFloor <= 0) throw new Error("成本搜索调整过低，导致搜索下限小于等于 0。");
  if (searchFloor > ceiling) throw new Error(`成本搜索调整过高，搜索下限 ${formatMoney(searchFloor)} 已超过最高报价限制。`);
  if (bidderCount < 2) throw new Error("投标人总数至少为 2。");
  if (bidderMin < 2 || bidderMax < 2 || bidderMin > bidderMax) throw new Error("投标人数范围必须满足 2 ≤ n_min ≤ n_max。");
  if (simulationCount < 100) throw new Error("模拟次数建议至少 100 次。");
  const candidateCount = Math.floor((ceiling - searchFloor) / step) + 1;
  if (candidateCount > 2000) throw new Error("候选报价点过多，请调大搜索步长。");
  if (candidateCount * simulationCount > 20000000) throw new Error("模拟规模过大，请调大搜索步长或降低模拟次数。");
  const rule = rules.find(item => item.id === els.ruleSelect.value);
  if (!rule) throw new Error("请先选择一条已确认规则。");
  const marketScenarios = buildMarketScenarios(ceiling, marketMean);
  return { ceiling, floor, searchFloor, minProfitRate, step, precision, marketMean, marketScenarios, sigma, bidderMode, bidderCount, bidderMin, bidderMax, simulationCount, rule };
}

function setError(message) {
  els.message.textContent = message;
  els.message.className = "message error";
  els.statusText.textContent = "需修正";
}

function setMessage(message) {
  els.message.textContent = message;
  els.message.className = "message";
}

function clearBacktestExport() {
  lastBacktestResult = null;
  if (els.exportBacktestButton) els.exportBacktestButton.disabled = true;
}

function markNeedsRun() {
  activeRunId += 1;
  els.runButton.disabled = false;
  els.statusText.textContent = "待计算";
  setMessage("参数已变更，请点击“重新计算”运行模拟。");
  if (els.chartTooltip) els.chartTooltip.hidden = true;
  clearBacktestExport();
}

function drawChart(points, best, competitors, precision) {
  const svg = els.chart;
  const ns = "http://www.w3.org/2000/svg";
  const width = 920;
  const height = 360;
  const margin = { top: 26, right: 28, bottom: 50, left: 70 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  svg.replaceChildren();

  function make(tag, attrs, parent = svg) {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    parent.appendChild(node);
    return node;
  }

  make("title", { id: "chartTitle" }).textContent = "投标报价得分模拟曲线";
  make("desc", { id: "chartDesc" }).textContent = "展示不同报价下的价格分以及可中标范围。";

  const minBid = Math.min(...points.map(point => point.bid));
  const maxBid = Math.max(...points.map(point => point.bid));
  const maxScore = Math.max(1, ...points.map(point => point.myScore), ...competitors.map(item => item.score || 0));
  const yMax = Math.ceil(maxScore / 10) * 10 || 10;
  const x = value => margin.left + ((value - minBid) / Math.max(1, maxBid - minBid)) * plotW;
  const y = value => margin.top + plotH - (value / yMax) * plotH;

  for (let i = 0; i <= 5; i += 1) {
    const score = yMax * i / 5;
    const yy = y(score);
    make("line", { x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line" });
    make("text", { x: 18, y: yy + 4, class: "chart-label" }).textContent = `${Math.round(score)}分`;
  }

  let bandStart = null;
  points.forEach((point, index) => {
    if (point.wins && bandStart === null) bandStart = point.bid;
    if ((!point.wins || index === points.length - 1) && bandStart !== null) {
      const bandEnd = point.wins && index === points.length - 1 ? point.bid : points[index - 1].bid;
      make("rect", { x: x(bandStart), y: margin.top, width: Math.max(2, x(bandEnd) - x(bandStart)), height: plotH, class: "win-band" });
      bandStart = null;
    }
  });

  make("line", { x1: margin.left, y1: margin.top + plotH, x2: width - margin.right, y2: margin.top + plotH, class: "axis" });
  make("line", { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, class: "axis" });
  make("path", { d: points.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.bid).toFixed(1)},${y(point.myScore).toFixed(1)}`).join(" "), class: "score-line" });
  make("circle", { cx: x(best.bid), cy: y(best.myScore), r: 6, class: "best-dot" });
  make("text", { x: Math.min(width - 130, x(best.bid) + 10), y: Math.max(18, y(best.myScore) - 12), class: "chart-strong" }).textContent = `推荐 ${formatNumber(best.myScore, precision)}分`;
  make("text", { x: margin.left, y: height - 14, class: "chart-label" }).textContent = formatMoney(minBid);
  make("text", { x: width - margin.right - 92, y: height - 14, class: "chart-label" }).textContent = formatMoney(maxBid);

  svg.onmousemove = event => {
    const rect = svg.getBoundingClientRect();
    const viewX = (event.clientX - rect.left) / rect.width * width;
    const bidAtPointer = minBid + ((viewX - margin.left) / plotW) * (maxBid - minBid);
    const nearest = points.reduce((bestPoint, point) => {
      return Math.abs(point.bid - bidAtPointer) < Math.abs(bestPoint.bid - bidAtPointer) ? point : bestPoint;
    }, points[0]);
    if (!nearest || !els.chartTooltip) return;
    els.chartTooltip.hidden = false;
    els.chartTooltip.innerHTML = `
      <strong>${formatMoney(nearest.bid)}</strong>
      <span><em>平均得分</em><b>${formatNumber(nearest.myScore, precision)}</b></span>
      <span><em>中标概率</em><b>${formatPct(nearest.winProbability || 0, precision)}</b></span>
      <span><em>满分概率</em><b>${formatPct(nearest.fullScoreProbability || 0, precision)}</b></span>
      <span><em>平均基准价</em><b>${formatMoney(nearest.benchmark)}</b></span>
      <span><em>平均投标人数</em><b>${formatNumber(nearest.averageBidderCount || 0, 2)}</b></span>
    `;
    const panelRect = svg.parentElement.getBoundingClientRect();
    const left = Math.min(panelRect.width - 270, Math.max(8, event.clientX - panelRect.left + 14));
    const top = Math.max(8, event.clientY - panelRect.top - 28);
    els.chartTooltip.style.left = `${left}px`;
    els.chartTooltip.style.top = `${top}px`;
  };
  svg.onmouseleave = () => {
    if (els.chartTooltip) els.chartTooltip.hidden = true;
  };
}

function pickNearestPoint(points, targetBid) {
  return points.reduce((nearest, point) => {
    return Math.abs(point.bid - targetBid) < Math.abs(nearest.bid - targetBid) ? point : nearest;
  }, points[0]);
}

function analyzeBidInterval(points, best) {
  const scoreFloor = best.myScore * 0.98;
  const winFloor = Math.max(0, best.winProbability * 0.75);
  const eligible = points.map(point => ({
    ...point,
    robust: point.myScore >= scoreFloor && point.winProbability >= winFloor
  }));
  const bestIndex = eligible.findIndex(point => point.bid === best.bid);
  let startIndex = bestIndex;
  let endIndex = bestIndex;
  while (startIndex > 0 && eligible[startIndex - 1].robust) startIndex -= 1;
  while (endIndex < eligible.length - 1 && eligible[endIndex + 1].robust) endIndex += 1;

  const segment = eligible.slice(startIndex, endIndex + 1);
  const low = segment[0] || best;
  const high = segment[segment.length - 1] || best;
  const balanced = pickNearestPoint(segment.length ? segment : [best], (low.bid + high.bid) / 2);
  const recommended = high;
  return {
    low,
    balanced,
    high,
    recommended,
    scoreFloor,
    winFloor,
    count: segment.length,
    isSinglePoint: low.bid === high.bid
  };
}

function formatBidRange(interval) {
  if (!interval || interval.isSinglePoint) return formatMoney(interval?.recommended?.bid);
  return `${formatMoney(interval.low.bid)} ~ ${formatMoney(interval.high.bid)}`;
}

function renderRanking(best, precision, interval) {
  const recommendation = interval?.recommended || best;
  const rows = [
    { name: "稳健区间", amount: formatBidRange(interval), score: interval?.scoreFloor, deviation: interval?.count, winner: true, amountText: true },
    { name: "保守报价", amount: interval?.low?.bid ?? best.bid, score: interval?.low?.myScore ?? best.myScore, deviation: interval?.low?.winProbability ?? best.winProbability, winner: false },
    { name: "均衡报价", amount: interval?.balanced?.bid ?? best.bid, score: interval?.balanced?.myScore ?? best.myScore, deviation: interval?.balanced?.winProbability ?? best.winProbability, winner: false },
    { name: "利润优先报价", amount: recommendation.bid, score: recommendation.myScore, deviation: recommendation.winProbability, winner: true },
    { name: "平均基准价", amount: best.benchmark, score: best.myScore, deviation: 0, winner: false },
    { name: "平均投标人数", amount: best.averageBidderCount, score: best.winProbability * 100, deviation: 0, winner: false }
  ];
  els.rankingBody.replaceChildren(...rows.map(row => {
    const tr = document.createElement("tr");
    const amountText = row.amountText ? row.amount : row.name === "平均投标人数" ? formatNumber(row.amount, 2) : formatMoney(row.amount);
    const supplement = row.name === "稳健区间"
      ? `${row.deviation} 个报价点`
      : ["利润优先报价", "保守报价", "均衡报价"].includes(row.name)
        ? formatPct(row.deviation, precision)
        : "-";
    const resultText = row.name === "稳健区间" ? "高分区间" : row.name === "利润优先报价" ? "区间上沿" : "";
    [row.name, amountText, "-", formatNumber(row.score, precision), supplement, resultText].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 5 && row.winner) td.className = "winner";
      tr.appendChild(td);
    });
    return tr;
  }));
}

function isLowerBoundarySolution(best, floor, step) {
  return best && Math.abs(best.bid - floor) <= Math.max(1, step * 0.001);
}

function boundarySolutionMessage(best, floor, marketMean, marketScenarios) {
  const marketText = marketMean === null ? scenarioText(marketScenarios) : formatMoney(marketMean);
  return `当前最优点落在搜索下限 ${formatMoney(floor)}，这是边界解：在 ${formatMoney(floor)} 以上继续加价会降低规则价格分。请不要把它理解成“唯一理想报价正好等于下限”，而是说明按当前 μ/σ/n 和规则，理论高分区间大概率低于或贴近该下限。当前 μ 场景：${marketText}。`;
}

function parseBidLine(line, index) {
  const numericTextPattern = /^\d[\d,，]*(?:\.\d+)?$/;
  const separatorPattern = /[-–—,，:：\t]/g;
  for (const separator of line.matchAll(separatorPattern)) {
    const namePart = line.slice(0, separator.index).trim();
    const amountPart = line.slice(separator.index + separator[0].length).trim();
    if (/[^\d\s,，.]/.test(namePart) && numericTextPattern.test(amountPart)) {
      const amount = Number(amountPart.replace(/[,，]/g, ""));
      if (!Number.isFinite(amount) || amount <= 0) throw new Error(`第 ${index + 1} 行报价必须大于 0。`);
      return {
        name: namePart.replace(/[\s,，:：;；\-–—]+$/g, "").trim() || `投标人${index + 1}`,
        amount,
        rawLine: line
      };
    }
  }
  const matches = Array.from(line.matchAll(/\d[\d,，]*(?:\.\d+)?/g));
  if (!matches.length) throw new Error(`第 ${index + 1} 行没有识别到报价。`);
  const amountMatch = matches[matches.length - 1];
  const amountText = amountMatch[0].replace(/[,，]/g, "");
  const amount = Number(amountText);
  if (!Number.isFinite(amount) || amount <= 0) throw new Error(`第 ${index + 1} 行报价必须大于 0。`);
  const name = line
    .slice(0, amountMatch.index)
    .replace(/[\s,，:：;；\-–—]+$/g, "")
    .trim();
  return {
    name: name || `投标人${index + 1}`,
    amount,
    rawLine: line
  };
}

function parseActualBids() {
  const values = els.actualBids.value
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map(parseBidLine);
  if (values.length < 2) throw new Error("至少需要输入 2 个已开标报价。");
  return values;
}

function standardDeviation(values) {
  if (values.length <= 1) return 0;
  const avg = mean(values);
  const variance = values.reduce((sum, value) => sum + (value - avg) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function calibrationSampleForRule(rule, amounts) {
  const sorted = amounts.slice().sort((a, b) => a - b);
  if (rule?.id === "rule2" && sorted.length > 5) {
    return sorted.slice(1, -1);
  }
  return sorted;
}

function renderBacktestRows(rows, precision) {
  els.rankingBody.replaceChildren(...rows.map(row => {
    const tr = document.createElement("tr");
    const scoreGapText = row.rank === 1
      ? "第一名"
      : `距上一名 ${formatNumber(row.gapToPreviousScore, precision)} 分 / 报价差 ${formatMoney(row.gapToPreviousAmount)}`;
    const supplement = Math.abs((row.weightedScore ?? row.score) - row.score) > 1e-9
      ? `偏差 ${formatPct(row.deviation, precision)} / 加权 ${formatNumber(row.weightedScore, precision)}`
      : `偏差 ${formatPct(row.deviation, precision)} / ${scoreGapText}`;
    [
      row.name,
      formatMoney(row.amount),
      formatMoney(row.benchmark),
      formatNumber(row.rankScore ?? row.score, precision),
      supplement,
      row.rank
    ].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 5 && row.rank === 1) td.className = "winner";
      tr.appendChild(td);
    });
    return tr;
  }));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function excelCell(value, options = {}) {
  const attrs = options.text ? ' style="mso-number-format:\\@"' : "";
  return `<td${attrs}>${escapeHtml(value)}</td>`;
}

function excelRow(values, options = {}) {
  return `<tr>${values.map(value => excelCell(value, options)).join("")}</tr>`;
}

function downloadBlob(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportBacktestExcel() {
  try {
    if (!lastBacktestResult) throw new Error("请先点击“按当前规则复算开标结果”，生成回测结果后再导出。");
    const { rule, benchmark, rows, precision, exportedAt } = lastBacktestResult;
    const ruleJson = JSON.stringify(rule, null, 2);
    const resultRows = rows.map(row => excelRow([
      row.rank,
      row.name,
      row.rawLine || "",
      row.amount,
      row.benchmark,
      row.deviation,
      row.score,
      Number.isFinite(row.weightedScore) ? row.weightedScore : "",
      row.rankScore,
      row.gapToPreviousScore,
      row.gapToPreviousAmount,
      row.gapToFirstScore,
      row.gapToFirstAmount
    ]));
    const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    table { border-collapse: collapse; }
    td, th { border: 1px solid #999; padding: 6px; }
    th { background: #e8f0ec; font-weight: bold; }
  </style>
</head>
<body>
  <h2>开标后回测结果</h2>
  <table>
    ${excelRow(["导出时间", exportedAt], { text: true })}
    ${excelRow(["规则ID", rule.id], { text: true })}
    ${excelRow(["规则名称", rule.name], { text: true })}
    ${excelRow(["复算评标基准价", benchmark])}
    ${excelRow(["小数精度", precision])}
  </table>
  <br>
  <table>
    <tr>
      <th>排名</th>
      <th>投标对象</th>
      <th>原始输入</th>
      <th>投标金额</th>
      <th>基准价</th>
      <th>偏差率</th>
      <th>原始得分</th>
      <th>加权得分</th>
      <th>排名得分</th>
      <th>距上一名分差</th>
      <th>距上一名报价差</th>
      <th>距第一名分差</th>
      <th>距第一名报价差</th>
    </tr>
    ${resultRows.join("\n")}
  </table>
  <br>
  <h2>对应规则JSON</h2>
  <table>
    <tr><th>规则JSON</th></tr>
    <tr><td style="mso-number-format:\\@"><pre>${escapeHtml(ruleJson)}</pre></td></tr>
  </table>
</body>
</html>`;
    const safeRuleName = String(rule.name || rule.id || "rule").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 40);
    const timestamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
    downloadBlob(`开标后回测_${safeRuleName}_${timestamp}.xls`, html, "application/vnd.ms-excel;charset=utf-8");
    setMessage(`已导出开标后回测 Excel，包含当前规则「${rule.name}」和复算排名结果。`);
  } catch (error) {
    setError(error.message);
  }
}

function runBacktest() {
  try {
    activeRunId += 1;
    const rule = rules.find(item => item.id === els.ruleSelect.value);
    if (!rule) throw new Error("请先选择一条已确认规则。");
    const precision = Number(els.precision.value);
    const bidders = parseActualBids();
    const benchmark = calculateBenchmark(rule, bidders.map(item => item.amount));
    const scored = bidders.map(item => {
      const scoredItem = { ...item, ...scoreQuote(rule, item.amount, benchmark) };
      return {
        ...scoredItem,
        rankScore: Number.isFinite(scoredItem.weightedScore) ? scoredItem.weightedScore : scoredItem.score
      };
    });
    const ranked = scored
      .slice()
      .sort((a, b) => b.rankScore - a.rankScore || a.amount - b.amount)
      .map((item, index, list) => {
        const previous = index > 0 ? list[index - 1] : null;
        const first = list[0];
        return {
          ...item,
          benchmark,
          rank: index + 1,
          gapToPreviousScore: previous ? previous.rankScore - item.rankScore : 0,
          gapToPreviousAmount: previous ? Math.abs(item.amount - previous.amount) : 0,
          gapToFirstScore: first ? first.rankScore - item.rankScore : 0,
          gapToFirstAmount: first ? Math.abs(item.amount - first.amount) : 0
        };
      });
    const winner = ranked[0];
    lastBacktestResult = {
      rule: JSON.parse(JSON.stringify(rule)),
      benchmark,
      rows: ranked.map(row => ({ ...row })),
      precision,
      exportedAt: new Date().toLocaleString("zh-CN")
    };
    if (els.exportBacktestButton) els.exportBacktestButton.disabled = false;

    els.bestBid.textContent = formatMoney(winner.amount);
    els.bestScore.textContent = formatNumber(winner.rankScore, precision);
    els.benchmark.textContent = formatMoney(benchmark);
    els.scoreGap.textContent = formatPct(winner.deviation, precision);
    els.bestBidNote.textContent = "开标后复算排名第 1";
    els.scoreNote.textContent = rule.name;
    els.benchmarkNote.textContent = "由全部已开标报价按当前规则复算";
    els.gapNote.textContent = "第一名偏差率";
    els.statusText.textContent = "已回测";
    els.chartCaption.textContent = `开标后回测：当前使用规则「${rule.name}」，共 ${bidders.length} 家，复算评标基准价 ${formatMoney(benchmark)}。`;
    setMessage(`已按当前选择的评分规则「${rule.name}」复算开标结果。第一名报价 ${formatMoney(winner.amount)}，最终得分 ${formatNumber(winner.rankScore, precision)}。`);
    renderBacktestRows(ranked, precision);
  } catch (error) {
    clearBacktestExport();
    setError(error.message);
  }
}

function calibrateFromActualBids() {
  try {
    const bidders = parseActualBids();
    const amounts = bidders.map(item => item.amount);
    const rule = rules.find(item => item.id === els.ruleSelect.value);
    const sample = calibrationSampleForRule(rule, amounts);
    els.marketMean.value = Math.round(mean(sample));
    els.sigma.value = Math.round(standardDeviation(sample));
    sigmaAutoMode = false;
    updateSigmaNote();
    els.bidderMode.value = "fixed";
    els.bidderCount.value = String(bidders.length);
    els.bidderMin.value = String(bidders.length);
    els.bidderMax.value = String(bidders.length);
    markNeedsRun();
    const sampleText = sample.length === bidders.length ? `${bidders.length} 家` : `${bidders.length} 家中去掉 1 个最高价和 1 个最低价后的 ${sample.length} 家`;
    setMessage(`已用 ${sampleText} 开标报价校准：μ=${formatMoney(Number(els.marketMean.value))}，σ=${formatMoney(Number(els.sigma.value))}，n=${bidders.length}。最高限价和成本请仍按当前项目手动确认；如果推荐价卡在保本线，说明当前成本约束高于模型的理想高分区间。`);
  } catch (error) {
    setError(error.message);
  }
}

async function run() {
  const runId = activeRunId + 1;
  activeRunId = runId;
  try {
    const { ceiling, floor, searchFloor, minProfitRate, step, precision, marketMean, marketScenarios, sigma, bidderMode, bidderCount, bidderMin, bidderMax, simulationCount, rule } = validateInputs();
    const candidateCount = Math.floor((ceiling - searchFloor) / step) + 1;
    els.runButton.disabled = true;
    els.statusText.textContent = "计算中";
    setMessage(`正在模拟：${candidateCount} 个候选报价 × ${simulationCount} 次。请稍等，页面可继续响应。`);
    await waitForBrowser();
    const { points, best } = await monteCarloSearchAsync(
      rule,
      searchFloor,
      ceiling,
      step,
      marketScenarios,
      sigma,
      bidderMode,
      bidderCount,
      bidderMin,
      bidderMax,
      simulationCount,
      (done, total, currentBest) => {
        const pct = Math.round((done / total) * 100);
        els.statusText.textContent = `计算中 ${pct}%`;
        els.bestBid.textContent = currentBest ? formatMoney(currentBest.bid) : "-";
        els.bestScore.textContent = currentBest ? formatNumber(currentBest.myScore, precision) : "-";
        setMessage(`正在模拟：已完成 ${done}/${total} 个候选报价，当前最优报价 ${currentBest ? formatMoney(currentBest.bid) : "-"}。`);
      },
      runId
    );
    if (runId !== activeRunId) return;

    const interval = analyzeBidInterval(points, best);
    const recommendation = interval.recommended;
    els.bestBid.textContent = formatBidRange(interval);
    els.bestScore.textContent = formatNumber(recommendation.myScore, precision);
    els.benchmark.textContent = formatMoney(recommendation.benchmark);
    els.scoreGap.textContent = formatPct(recommendation.winProbability, precision);
    const lowerBoundary = isLowerBoundarySolution(best, searchFloor, step);
    els.bestBidNote.textContent = lowerBoundary
      ? `边界高分区间，利润优先 ${formatMoney(recommendation.bid)}`
      : `利润优先 ${formatMoney(recommendation.bid)}，按 ${simulationCount} 次模拟`;
    els.scoreNote.textContent = rule.name;
    els.benchmarkNote.textContent = `模拟平均基准价，来源：${rule.source || "规则库"}`;
    els.gapNote.textContent = "模拟中标概率";
    els.statusText.textContent = "已模拟";
    const bidderText = bidderMode === "fixed" ? `总投标人数固定为 ${bidderCount}` : `总投标人数在 ${bidderMin}-${bidderMax} 间随机`;
    const marketText = marketMean === null ? `μ自动场景：${scenarioText(marketScenarios)}` : `μ=${formatMoney(marketMean)}`;
    const costAdjustText = minProfitRate < 0
      ? `向成本以下下探 ${formatNumber(Math.abs(minProfitRate), 1)}%`
      : minProfitRate > 0
        ? `成本以上保留 ${formatNumber(minProfitRate, 1)}%`
        : "从成本线开始";
    const floatRates = buildFloatRateScenarios(rule);
    const floatText = rule.id === "rule22" ? `，${floatRateScenarioText(floatRates)}` : "";
    els.chartCaption.textContent = `对手报价按 ${marketText}、σ=${formatMoney(sigma)} 生成${floatText}，${bidderText}，已在搜索下限 ${formatMoney(searchFloor)} 至 ${formatMoney(ceiling)} 区间按 ${formatMoney(step)} 步长搜索；成本 ${formatMoney(floor)}，${costAdjustText}。`;

    if (lowerBoundary) {
      setMessage(`${boundarySolutionMessage(best, searchFloor, marketMean, marketScenarios)} 当前成本为 ${formatMoney(floor)}，成本搜索调整为 ${formatNumber(minProfitRate, 1)}%，用于观察成本线附近或成本线以下的更大报价区间。`);
    } else {
      setMessage(marketMean === null
        ? "当前为自动 μ 场景模拟：系统同时考虑最高限价 85%、90%、95% 三种市场均价，并输出最高分附近 98% 内的稳健报价区间。"
        : rule.id === "rule22"
          ? "当前为规则22稳健模拟：浮动率不是投标人可控参数，系统按 -10% 到 0% 多个场景共同评估，并输出稳健报价区间。"
          : "当前为蒙特卡洛模拟优化：系统随机生成对手报价，按所选规则计算每个候选报价，并输出最高分附近 98% 内的稳健报价区间。");
    }
    drawChart(points, best, [], precision);
    renderRanking(best, precision, interval);
  } catch (error) {
    if (error.message !== "本次计算已取消。") setError(error.message);
  } finally {
    if (runId === activeRunId) els.runButton.disabled = false;
  }
}

async function parseSelectedRuleFile() {
  try {
    const path = els.ruleFileSelect.value;
    if (!path) throw new Error("请先选择规则文件。");
    els.statusText.textContent = "解析中";
    els.extractedText.value = "正在提取文本并生成规则草稿...";
    els.draftRuleJson.value = "";
    const result = await api("/api/bid-strategy/parse-rule", {
      method: "POST",
      body: JSON.stringify({ path })
    });
    els.extractedText.value = result.text || `未提取到文本。提取器：${result.extractor}`;
    els.draftRuleJson.value = JSON.stringify(result.rule, null, 2);
    setMessage(result.modelMessage ? `已生成保守草稿。${result.modelMessage}` : "已生成规则草稿，请复核后保存。");
    els.statusText.textContent = "待确认";
  } catch (error) {
    setError(error.message);
  }
}

async function saveParsedRule() {
  try {
    const rule = JSON.parse(els.draftRuleJson.value);
    const saved = await api("/api/bid-strategy/rules", {
      method: "POST",
      body: JSON.stringify({ rule })
    });
    await loadRules(saved.id);
    setMessage("规则已保存到规则库，并已加入报价计算下拉框。请点击“重新计算”运行模拟。");
    els.statusText.textContent = "已保存";
  } catch (error) {
    setError(`保存失败：${error.message}`);
  }
}

function fillSample() {
  els.ceiling.value = "12000000";
  els.floor.value = "6000000";
  els.step.value = "10000";
  els.marketMean.value = "6840000";
  sigmaAutoMode = true;
  applyAutoSigma();
  els.bidderMode.value = "range";
  els.bidderCount.value = "8";
  els.bidderMin.value = "5";
  els.bidderMax.value = "12";
  els.simulationCount.value = "5000";
  markNeedsRun();
}

async function init() {
  try {
    await Promise.all([loadRules("rule2"), loadRuleFiles(), loadHealth()]);
    applyAutoSigma();
    els.runButton.addEventListener("click", run);
    els.sampleButton.addEventListener("click", fillSample);
    els.autoSigmaButton.addEventListener("click", () => {
      sigmaAutoMode = true;
      applyAutoSigma();
      markNeedsRun();
    });
    els.refreshFilesButton.addEventListener("click", loadRuleFiles);
    els.parseRuleButton.addEventListener("click", parseSelectedRuleFile);
    els.saveParsedRuleButton.addEventListener("click", saveParsedRule);
    els.backtestButton.addEventListener("click", runBacktest);
    els.calibrateButton.addEventListener("click", calibrateFromActualBids);
    els.exportBacktestButton.addEventListener("click", exportBacktestExcel);
    els.actualBids.addEventListener("input", clearBacktestExport);
    els.ceiling.addEventListener("input", () => {
      if (sigmaAutoMode) applyAutoSigma();
      markNeedsRun();
    });
    els.ceiling.addEventListener("change", () => {
      if (sigmaAutoMode) applyAutoSigma();
      markNeedsRun();
    });
    els.sigma.addEventListener("input", () => {
      sigmaAutoMode = false;
      updateSigmaNote();
      markNeedsRun();
    });
    els.sigma.addEventListener("change", () => {
      sigmaAutoMode = false;
      updateSigmaNote();
      markNeedsRun();
    });
    [els.floor, els.minProfitRate, els.step, els.precision, els.marketMean, els.bidderMode, els.bidderCount, els.bidderMin, els.bidderMax, els.simulationCount, els.ruleSelect].forEach(input => {
      input.addEventListener("input", markNeedsRun);
      input.addEventListener("change", markNeedsRun);
    });
    markNeedsRun();
  } catch (error) {
    setError(error.message);
  }
}

init();
