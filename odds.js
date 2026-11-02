/* Draw odds engine: historical odds at your point level, plus a next-year projection that
   follows each state's draw rules. Systems:
     pref      100% to highest points (Colorado)
     pref75    75% by points, 25% random among the rest (Wyoming, Oregon, Montana combos)
     bonus     weighted random, chances = points + 1
     bonus_sq  weighted random, chances = points^2 + 1 (Nevada, Montana permits)
     bonus50   half of tags to top points, half weighted points + 1 (Utah limited entry)
     az        20% of tags to top points, rest weighted points + 1 (Arizona)
     random    equal chances, no points (New Mexico, Idaho)
   by_pts rows are [points, applicants, drawn]. */
(function (root) {
  "use strict";

  function sortRows(rows) { return rows.map(r => [r[0], r[1], r[2] || 0]).filter(r => r[1] > 0).sort((a, b) => b[0] - a[0]); }

  // Weighted sampling without replacement ~ exponential race: find t with sum n_k(1-e^{-w_k t}) = tags.
  function weightedOdds(groups, tags) {
    const total = groups.reduce((s, g) => s + g.n, 0);
    if (tags <= 0) return groups.map(() => 0);
    if (tags >= total) return groups.map(() => 1);
    const filled = t => groups.reduce((s, g) => s + g.n * (1 - Math.exp(-g.w * t)), 0);
    let lo = 0, hi = 1;
    while (filled(hi) < tags && hi < 1e12) hi *= 2;
    for (let i = 0; i < 80; i++) { const m = (lo + hi) / 2; if (filled(m) < tags) lo = m; else hi = m; }
    return groups.map(g => 1 - Math.exp(-g.w * hi));
  }

  // Top-points pass: give `k` tags to the highest point holders; returns {taken: Map(points->count), left}
  function topPass(groups, k) {
    const taken = new Map(); let left = k;
    for (const g of groups.slice().sort((a, b) => b.p - a.p)) {
      if (left <= 0) break;
      const t = Math.min(g.n, left); taken.set(g.p, t); left -= t;
    }
    return { taken, left };
  }

  // Probability for one applicant holding `pts` in a pool `groups` [{p,n}] with `tags` tags.
  function drawProb(system, groups, tags, pts) {
    groups = groups.filter(g => g.n > 0);
    if (!groups.some(g => g.p === pts)) groups.push({ p: pts, n: 1 });
    const total = groups.reduce((s, g) => s + g.n, 0);
    if (!tags || !total) return 0;
    if (system === "random") return Math.min(1, tags / total);
    const prefShare = system === "pref" ? 1 : system === "pref75" ? 0.75 : system === "bonus50" ? 0.5 : system === "az" ? 0.2 : 0;
    const k = Math.round(tags * prefShare);
    const { taken } = topPass(groups, k);
    const mine = groups.find(g => g.p === pts);
    const pTop = (taken.get(pts) || 0) / mine.n;
    const rest = tags - Array.from(taken.values()).reduce((a, b) => a + b, 0);
    if (rest <= 0) return pTop;
    const remaining = groups.map(g => ({ p: g.p, n: g.n - (taken.get(g.p) || 0) })).filter(g => g.n > 0);
    if (!remaining.some(g => g.p === pts)) return pTop;
    const weight = p => system === "bonus_sq" ? p * p + 1 : (system === "bonus" || system === "bonus50" || system === "az") ? p + 1 : 1;
    const odds = weightedOdds(remaining.map(g => ({ n: g.n, w: weight(g.p) })), rest);
    const pRest = odds[remaining.findIndex(g => g.p === pts)];
    return pTop + (1 - pTop) * pRest;
  }

  // Historical odds at `pts` for one year's residency block {apps,drawn,tags,min_pts,by_pts}
  // pref75 reports often count only the points phase in by_pts; the random phase shows up
  // only in the hunt's total drawn. Returns P(random | missed points phase) or 0.
  function randomShare(blk) {
    if (!blk || !blk.by_pts || blk.drawn == null || !blk.apps) return 0;
    const prefDrawn = blk.by_pts.reduce((s, r) => s + (r[2] || 0), 0);
    const extra = blk.drawn - prefDrawn, pool = blk.apps - prefDrawn;
    return extra > 0 && pool > 0 ? Math.min(1, extra / pool) : 0;
  }

  function historical(system, blk, pts) { const v = historicalRaw(system, blk, pts); return v == null ? null : Math.max(0, Math.min(1, v)); }
  function historicalRaw(system, blk, pts) {
    if (!blk) return null;
    if (blk.apps && blk.drawn != null && blk.drawn >= blk.apps) return 1; // undersubscribed
    if (blk.by_pts && blk.by_pts.length && sortRows(blk.by_pts).length) {
      const rows = sortRows(blk.by_pts);
      const rs = system === "pref75" ? randomShare(blk) : 0;
      const row = rows.find(r => r[0] === pts);
      if (row && rs) { const pp = row[2] / row[1]; return pp + (1 - pp) * rs; }
      if (!row && rs && pts <= rows[0][0]) { const lower = rows.find(r => r[0] < pts); const pp = lower ? lower[2] / lower[1] : 0; return pp + (1 - pp) * rs; }
      if (row) return row[2] / row[1];
      const maxP = rows[0][0];
      if (pts > maxP) return 1;
      if (system === "pref" && blk.min_pts != null) return pts > blk.min_pts ? 1 : 0;
      // nearest lower level for weighted systems
      const lower = rows.find(r => r[0] < pts);
      return lower ? lower[2] / lower[1] : null;
    }
    if (blk.apps && (blk.drawn != null || blk.tags != null)) {
      const d = blk.drawn != null ? blk.drawn : blk.tags;
      if (system === "random" || blk.min_pts == null) return Math.min(1, d / blk.apps);
      return pts > blk.min_pts ? 1 : pts === blk.min_pts ? 0.5 : 0;
    }
    return null;
  }

  // Next-year projection: applicants who didn't draw gain a point, last year's 0-point
  // applicants are replaced by a new 0-point cohort of the same size, tags held constant.
  // tags available to this residency: if fewer drew than the listed quota while others missed,
  // the listed number is a total quota, so use what this residency actually drew
  function resTags(blk) {
    let t = blk.tags != null ? blk.tags : blk.drawn;
    if (blk.drawn != null && blk.apps != null && t != null && blk.drawn < t && blk.apps > blk.drawn) t = blk.drawn;
    return t;
  }
  function project(system, blk, pts) {
    if (!blk) return null;
    const tags = resTags(blk);
    if (system === "random") return blk.apps ? Math.min(1, (tags || 0) / blk.apps) : null;
    if (!blk.by_pts || !blk.by_pts.length || !tags) return null;
    const rows = sortRows(blk.by_pts);
    if (!rows.length) return null;
    const m = new Map();
    for (const [p, a, d] of rows) { const stay = Math.max(0, a - d); m.set(p + 1, (m.get(p + 1) || 0) + stay); }
    // new 0-point cohort: last year's 0-point applicants, plus last year's winners who
    // come back at 0 points (keeps the applicant pool about the same size year to year)
    const zero = rows.find(r => r[0] === 0);
    const winners = rows.reduce((s, r) => s + (r[2] || 0), 0);
    const listed = rows.reduce((s, r) => s + r[1], 0);
    const unlisted = blk.apps != null ? Math.max(0, blk.apps - listed) : 0; // applicants not in point rows
    m.set(0, (m.get(0) || 0) + (zero ? zero[1] : 0) + winners + unlisted);
    const groups = Array.from(m, ([p, n]) => ({ p, n }));
    return drawProb(system, groups, tags, pts);
  }

  // Point creep: min points drawn per year and linear trend (points per year)
  function creep(years, res) {
    const pts = Object.keys(years).sort().map(y => [+y, years[y][res] && years[y][res].min_pts]).filter(x => x[1] != null);
    if (pts.length < 2) return { series: pts, slope: null };
    const n = pts.length, mx = pts.reduce((s, x) => s + x[0], 0) / n, my = pts.reduce((s, x) => s + x[1], 0) / n;
    const num = pts.reduce((s, x) => s + (x[0] - mx) * (x[1] - my), 0), den = pts.reduce((s, x) => s + (x[0] - mx) ** 2, 0);
    return { series: pts, slope: den ? num / den : 0 };
  }

  // Years needed to reach a projected cutoff (preference systems)
  function yearsToDraw(system, hunt, res, pts) {
    if (!/^pref/.test(system)) return null;
    const c = creep(hunt.years, res);
    if (!c.series.length) return null;
    const last = c.series[c.series.length - 1];
    const slope = c.slope != null ? Math.max(0, c.slope) : 0;
    for (let y = 1; y <= 30; y++) {
      const need = last[1] + slope * y;
      if (pts + y - 1 >= need) return y; // you gain a point each year you apply
    }
    return 31;
  }

  function latestYear(hunt, res) {
    const ys = Object.keys(hunt.years || {}).filter(y => hunt.years[y][res]).sort();
    return ys.length ? ys[ys.length - 1] : null;
  }

  // States where nonresidents draw from the same pool as residents (under a cap), not from their own quota.
  // With only a handful of nonresident applicants their own row can read 100% (one person with 15 points drew);
  // there the whole pool's odds are the better estimate, so the projection is capped at the pooled projection.
  const POOLED = new Set(["CO", "OR", "AZ", "ID", "MT"]);
  const THIN = 10;
  function poolBlock(Y) {
    if (Y.T && Y.T.by_pts && Y.T.by_pts.length) return Y.T;
    const r = Y.R, n = Y.NR; if (!r || !n || r.apps == null || n.apps == null) return null;
    const m = new Map();
    for (const b of [r, n]) for (const [p, a, d] of (b.by_pts || [])) { const q = m.get(p) || [0, 0]; q[0] += a; q[1] += d || 0; m.set(p, q); }
    const drawn = (r.drawn || 0) + (n.drawn || 0);
    return { apps: r.apps + n.apps, drawn, tags: drawn, by_pts: m.size ? Array.from(m, ([p, q]) => [p, q[0], q[1]]) : null };
  }
  function summarize(system, hunt, res, pts) {
    const y = latestYear(hunt, res);
    if (!y) return null;
    const blk = hunt.years[y][res];
    const hist = Object.keys(hunt.years).sort().map(yy => [yy, historical(system, hunt.years[yy][res], pts)]).filter(x => x[1] != null);
    let projected = project(system, blk, pts), pooled = false;
    if (res === "NR" && POOLED.has(hunt._st) && blk.apps != null && blk.apps < THIN) {
      const all = poolBlock(hunt.years[y]);
      if (all && all.apps) {
        const pa = system === "random" || !all.by_pts ? Math.min(1, (all.drawn != null ? all.drawn : all.tags || 0) / all.apps) : project(system, all, pts);
        if (pa != null && (projected == null || pa < projected)) { projected = pa; pooled = true; }
      }
    }
    return {
      year: y, blk, pooled,
      historical: hist,
      projected,
      minPts: blk.min_pts != null ? blk.min_pts : null,
      creep: creep(hunt.years, res),
      years: yearsToDraw(system, hunt, res, pts),
      overall: blk.apps ? Math.min(1, (blk.drawn != null ? blk.drawn : blk.tags || 0) / blk.apps) : null
    };
  }

  // Lowest point level giving at least `target` chance next year (weighted systems)
  function pointsFor(system, blk, target) {
    if (!blk || !blk.by_pts || !sortRows(blk.by_pts).length) return null;
    for (let p = 0; p <= 30; p++) { const v = project(system, blk, p); if (v != null && v >= target) return p; }
    return 31;
  }

  const api = { pointsFor, drawProb, historical, project, creep, yearsToDraw, summarize, latestYear, weightedOdds };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.Odds = api;
})(typeof window !== "undefined" ? window : globalThis);
