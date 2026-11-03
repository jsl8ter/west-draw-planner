/* Hunt planner engine: plans APPLICATIONS (not picks) year by year toward a goal, and simulates the
   draws to report real chances. Works in the browser (window.Planner) and in node (module.exports).

   Goal (G):
     slots:    [{ label, sp: {E:1, D:1, C:0.5}, every: 1|2|3, optional }]  hunts wanted per year; a tag of a
               listed species fills the slot (the number is a preference weight; <1 = "occasionally OK")
     weapons:  { archery, rifle, muzzleloader }
     conf:     target chance that every required slot is filled by draws (e.g. 0.9)
     quality:  0..1  0 = hunt as often as possible, 1 = wait longer for better units
     states:   states to use; always: states to apply in every year (pure lotteries like New Mexico)
     years, priv (private-land hunts ok), otc (OTC/general backups ok), budget (optional, per year)
   Context (ctx): { DRAW, TROPHY (trophy.json units), Odds, PRICES, OTC, pts: {"COE": 3, "MTEpref": 1, ...}, Y0 }

   How a year is planned:
   1. Rotation: for each point-state species (a "group", e.g. Colorado elk) the best hunt the points can reach
      within the plan ("target") and the year its odds reach BURN. Burns are capped to what the year's slots can
      use, so targets that mature together are staggered (the later one keeps gaining points).
   2. Lottery states marked "always" (New Mexico): best hunt per wanted species, every year.
   3. Fill: add the application that most raises the chance that all required slots get a tag, one per
      state+species, until the chance reaches conf. A group with 2+ banked points is never spent on a filler.
      Colorado: point as 1st choice + a leftover-type hunt as 2nd choice (draws there don't cost points).
   4. Every other point group in the goal buys a point (that's how the rotation keeps building).
   5. OTC/general tags are listed as the fallback if draws come up short (not counted in the draw odds).
   The whole policy is then replayed SIMS times with random draw results (points update each run).
*/
(function (root) {
  "use strict";
  const SYS = { CO: "pref", WY: "pref75", UT: "bonus50", AZ: "az", NM: "random", NV: "bonus_sq", OR: "pref75", ID: "random", MT: "bonus_sq" };
  const POINT_ST = new Set(["CO", "WY", "UT", "AZ", "NV", "OR", "MT"]);
  const SPECIES_IN = { CO: "EDP", WY: "EDP", UT: "EDP", AZ: "EDCP", NM: "EDCP", NV: "EDP", OR: "EDP", ID: "EDP", MT: "EDP" };
  const RESTRICTED = /\bCHAMP\b|\byouth\b|\bjunior\b|disab|mobility|\bMI\b|landowner|\bLOA\b|military|veteran|camp navajo|outfitter|\bguided\b|\bF-IM\b|apprentice|\bheritage\b|\bdepredation\b/i;
  const PRIVATE = /private[- ]land|\bprivate\b|valid on private|\bcwmu\b|ranching for wildlife|\bRFW\b|landowner/i;
  // State rules the planner enforces beyond the odds model (filled from official sources; see STATE_RULES.md)
  //   wait: { kind: years }  years you must sit out applying for that species after drawing (kind: E/D/P, "le" = limited entry)
  const RULES = {};
  const BURN = 0.7;            // odds at which a rotation target is "ready"
  const SIMS = 300;
  const grpOf = (st, sp, pref) => st + (sp === "C" ? "D" : sp) + (pref ? "pref" : "");

  function prepare(ctx, G) {
    const { DRAW, TROPHY, Odds } = ctx;
    const memo = new Map();
    const cands = [];          // eligible draw hunts
    const wantSp = new Set(G.slots.flatMap(s => Object.keys(s.sp)));
    const wOk = w => w === "archery" ? G.weapons.archery : w === "muzzleloader" ? G.weapons.muzzleloader : (w === "any" || w === "rifle") ? G.weapons.rifle : false;
    for (const st of G.states) {
      const d = DRAW[st]; if (!d) continue;
      const cur = {};
      for (const h of d.hunts) { const y = Object.keys(h.years).sort().pop(); if (!cur[h.species] || y > cur[h.species]) cur[h.species] = y; }
      for (const h of d.hunts) {
        h._st = st;
        if (!wantSp.has(h.species) || !SPECIES_IN[st].includes(h.species)) continue;
        const last = Object.keys(h.years).sort().pop();
        if (last !== cur[h.species]) continue;                                   // not offered in the latest draw
        const nr = (h.years[last] || {}).NR; if (!nr) continue;                  // no nonresident results this year
        const recent = Object.keys(h.years).sort().slice(-3).map(y => h.years[y].NR).filter(Boolean);
        if (!recent.some(b => (b.tags > 0) || (b.drawn > 0))) continue;          // nonresidents not getting tags
        const bag = h.bag || (h.sex === "female" ? "antlerless" : h.sex === "either" ? "either" : h.sex === "male" ? "antlered" : "unknown");
        if (bag !== "antlered" && bag !== "either") continue;                    // mature buck/bull legal only
        const txt = (h.label || "") + " " + (h.bag_text || "");
        if (RESTRICTED.test(txt) || RESTRICTED.test(h.kind || "") || /^[DEA]-[MFE]-\d{3}-K\d/.test(h.id)) continue;
        if (!G.priv && (PRIVATE.test(txt) || /^[DEA]-[MFE]-\d{3}-(P\d|W\d|J)/.test(h.id))) continue;
        if (!wOk(h.weapon)) continue;
        let q = null;
        for (const u of h.units || []) { const t = (((TROPHY || {})[st] || {})[h.species] || {})[String(u)]; if (t && (q == null || t.s > q)) q = t.s; }
        const general = h.kind === "general";
        // hunt-level quality: the unit's rating, less for a rifle either-sex elk/deer tag (mostly a cow/doe
        // hunt, usually late season); general/OTC-style tags rate as general hunts
        if (q != null && bag === "either" && h.weapon !== "archery" && (h.species === "E" || h.species === "D")) q = Math.max(1, q - 1);
        if (general && q != null) q = Math.min(q, 2);
        const sys = st === "MT" && general ? "mtcombo" : (st === "UT" && general) ? "pref" : SYS[st];
        const c = { st, h, sp: h.species, sys, q: q == null ? 2 : q, rated: q != null, general,
          g: grpOf(st, h.species, (st === "MT" || st === "UT") && general), cost: tagCost(ctx, st, h),
          slope: /^pref/.test(sys) ? Odds.recentSlope(Odds.creep(h.years, "NR")) : 0 };
        if (st === "CO") c.p2 = coSecond(h, last);
        cands.push(c);
      }
    }
    // odds for a hunt with `pts` points, k years from now (preference states lose ground to point creep)
    function p(c, pts, k) {
      const pe = Math.max(0, Math.round(pts - c.slope * k));
      const cache = c.cache || (c.cache = []);
      let v = cache[pe];
      if (v === undefined) {
        const s = Odds.summarize(c.sys, c.h, "NR", pe); v = s ? (s.projected != null ? s.projected : (s.historical.length ? s.historical[s.historical.length - 1][1] : s.overall)) : null;
        if (v != null) {
          // a handful of nonresident applicants is thin evidence: blend toward the whole hunt's draw rate
          const Y = c.h.years[Object.keys(c.h.years).sort().pop()] || {}, n = (Y.NR || {}).apps || 0, T = Y.T || {};
          const pool = T.apps ? Math.min(1, (T.drawn != null ? T.drawn : T.tags || 0) / T.apps) : null;
          if (n < 10 && pool != null && c.sys === "random") v = (n * v + 4 * pool) / (n + 4);
          v = Math.max(0, Math.min(1, v));
        }
        cache[pe] = v;
      }
      return v;
    }
    const byGroup = {};
    for (const c of cands) (byGroup[c.g] = byGroup[c.g] || []).push(c);
    return { cands, byGroup, p };
  }

  // Colorado 2nd choice: if the hunt still had licenses after all 1st choices, a 2nd-choice application
  // (with a point as 1st choice) likely draws, and drawing it doesn't use your points.
  function coSecond(h, y) {
    const Y = h.years[y] || {}, t = Y.T || {}, first = ((Y.R || {}).drawn || 0) + ((Y.NR || {}).drawn || 0);
    if (!t.tags) return 0;
    if (t.drawn != null && t.drawn < t.tags * 0.97) return 0.95;     // licenses left over after every choice
    if (first < t.tags * 0.9) return 0.6;                             // some left after 1st choices
    return 0;
  }

  function tagCost(ctx, st, h) {
    const P = ctx.PRICES[st]; if (!P) return 0;
    if (st === "WY" && h.kind === "special" && P.special) return P.special[h.species] || 0;
    if (st === "UT" && h.kind === "general" && P.general) return P.general[h.species] || P.tag[h.species] || 0;
    return P.tag[h.species === "C" && !P.tag.C ? "D" : h.species] || 0;
  }

  // ---- slot math: chance that every required slot can get a tag, given independent applications ----
  const SPX = ["E", "D", "C", "P"];
  function canFill(counts, slots) {
    // small exact matching: assign tags to slots (each slot takes one tag of an allowed species)
    const need = slots.map(s => Object.keys(s.sp));
    function rec(i, cnt) {
      if (i === need.length) return true;
      for (const s of need[i]) { const j = SPX.indexOf(s); if (cnt[j] > 0) { cnt[j]--; const ok = rec(i + 1, cnt); cnt[j]++; if (ok) return true; } }
      return false;
    }
    return rec(0, counts.slice());
  }
  function fillProb(apps, slots) {
    if (!slots.length) return 1;
    const cap = slots.length;
    let dist = new Map([["0,0,0,0", 1]]);
    for (const a of apps) {
      if (!a.p) continue;
      const j = SPX.indexOf(a.sp), nd = new Map();
      for (const [k, pr] of dist) {
        const v = k.split(",").map(Number);
        nd.set(k, (nd.get(k) || 0) + pr * (1 - a.p));
        const w = v.slice(); w[j] = Math.min(cap, w[j] + 1); const kk = w.join(",");
        nd.set(kk, (nd.get(kk) || 0) + pr * a.p);
      }
      dist = nd;
    }
    let tot = 0;
    for (const [k, pr] of dist) if (canFill(k.split(",").map(Number), slots)) tot += pr;
    return tot;
  }
  const expTags = apps => apps.reduce((s, a) => s + (a.p || 0), 0);

  // ---- rotation targets: best hunt each point group can reach and when ----
  function targets(P, G, pts, k0, horizon) {
    const tc = P.tcache || (P.tcache = new Map());
    // look ahead up to W years for the best hunt the points can reach (quality slider: 0 -> 2 years, 1 -> 12 years);
    // among equally good hunts the sooner one wins
    const W = Math.round(2 + G.quality * 10);
    const out = {};
    for (const g in P.byGroup) {
      const st = g.slice(0, 2); if (!POINT_ST.has(st)) continue;
      const ck = g + "|" + (pts[g] || 0) + "|" + k0;
      if (tc.has(ck)) { const v = tc.get(ck); if (v) out[g] = v; continue; }
      let best = null;
      for (const c of P.byGroup[g]) {
        if (c.general) continue;
        const base = pts[g] || 0;
        for (let t = 0; t <= W; t++) {
          const o = P.p(c, base + t, k0 + t);
          if (o != null && o >= BURN) { const sc = c.q + (c.rated ? 0 : -0.5) - 0.12 * t + 0.1 * o; if (!best || sc > best.sc) best = { c, t, sc, o }; break; }
        }
      }
      tc.set(ck, best);
      if (best) out[g] = best;
    }
    return out;
  }

  // ---- one year's applications given current points ----
  function planYear(ctx, G, P, k, pts, hist) {
    const due = G.slots.filter(s => (k % (s.every || 1)) === 0);
    const req = due.filter(s => !s.optional);
    const opt = due.filter(s => s.optional);
    const dueSp = new Set(due.flatMap(s => Object.keys(s.sp)));
    const coues = G.slots.some(s => s.sp.C) && !(hist.lastC != null && k - hist.lastC < 3);   // Coues at most every 3rd year
    const spOk = sp => dueSp.has(sp) && (sp !== "C" || coues);
    const apps = [], used = new Set();
    // variety: a state + species you hunted last year sits out a year unless it's needed for your confidence target
    // state waiting periods after drawing (can't even apply)
    const waiting = g => { const st = g.slice(0, 2), sp = g[2], w = ((RULES[st] || {}).wait || {})[sp]; return w && hist.drawnAt && hist.drawnAt[g] != null && k - hist.drawnAt[g] <= w; };
    const rest = G.rest == null ? 1 : G.rest;
    const recent = g => rest > 0 && hist.hunted && hist.hunted[g] != null && k - hist.hunted[g] <= rest;
    const add = a => { apps.push(a); used.add(a.g); };
    const T = targets(P, G, pts, k, G.years + 3);
    // 1. burns: targets ready now, best first, as many as the year's slots can use. Once the year is covered
    //    (chance >= conf and enough expected tags), extra ready targets wait a year: they keep their points.
    //    Colorado: a ready target that also draws as a 2nd choice is taken that way (points keep building).
    const burns = Object.entries(T).filter(([g, t]) => t.t === 0 && spOk(t.c.sp)).sort((a, b) => b[1].sc - a[1].sc);
    const slotsLeft = due.slice();
    for (const [g, t] of burns) {
      const i = slotsLeft.findIndex(s => s.sp[t.c.sp]);
      if (i < 0) continue;          // nothing left to fill with this species: keep the points (deferred)
      if (recent(g) || waiting(g)) continue;
      if (fillProb(apps, req) >= G.conf && expTags(apps) >= due.length + 0.3) continue;
      slotsLeft.splice(i, 1);
      const second = t.c.st === "CO" && (t.c.p2 || 0) >= 0.9;
      add({ kind: second ? "second" : ((pts[g] || 0) > 0 ? "burn" : "draw"), g, st: t.c.st, sp: t.c.sp, c: t.c,
        p: second ? t.c.p2 : P.p(t.c, pts[g] || 0, k) * mtCombo(P, t.c, pts, k), q: t.c.q, cost: t.c.cost, target: true });
    }
    // 2. always-apply lottery states: if the year still needs tags, the best chance of filling a slot;
    //    if it's already covered, a swing at the best unit (low odds, high quality)
    for (const st of G.always || []) for (const sp of ["E", "D", "C", "P"]) {
      if (!spOk(sp) || !SPECIES_IN[st].includes(sp)) continue;
      const g = grpOf(st, sp); if (used.has(g)) continue;
      const covered = fillProb(apps, req) >= G.conf;
      let best = null;
      for (const c of P.byGroup[g] || []) {
        if (c.sp !== sp) continue; const o = P.p(c, 0, k); if (!o) continue;
        // covered: the best unit you still have a real shot at (quality first, odds break ties)
        const v = covered ? (o >= 0.03 ? c.q * 10 + (c.rated ? 1 : 0) + Math.min(o, 0.25) * 4 : 0) : fillProb(apps.concat({ sp, p: o }), req) + 0.01 * o * c.q;
        if (v > 0 && (!best || v > best.v)) best = { c, p: o, v };
      }
      if (best) add({ kind: "lottery", g, st, sp: best.c.sp, c: best.c, p: best.p, q: best.c.q, cost: best.c.cost, swing: covered && best.p < 0.35 });
    }
    // 3. fill until the required slots reach the confidence target
    let pf = fillProb(apps, req);
    const pool = [];
    for (const g in P.byGroup) {
      if (used.has(g)) continue;
      const st = g.slice(0, 2);
      // a group building toward a target isn't spent on filler (only as a last resort, below)
      const protect = POINT_ST.has(st) && !g.endsWith("pref") && ((T[g] && T[g].t > 0) || (pts[g] || 0) >= 2);
      for (const sp of ["E", "D", "C", "P"]) {
        if (!spOk(sp) || grpOf(st, sp, g.endsWith("pref")) !== g) continue;
        { const b = bestNow(P, g, sp, pts, k, G, false); if (b) pool.push({ buy: b.c.st === "MT" && b.c.general ? comboOdds(P, b.c, pts[g] || 0, k).buy : undefined, kind: POINT_ST.has(st) && !g.endsWith("pref") ? (protect ? "early" : "draw") : (st === "MT" ? "combo" : "lottery"), protect, g, st, sp: b.c.sp, c: b.c, p: b.p, q: b.c.q, cost: b.c.cost }); }
        if (st === "CO") { const b2 = bestSecond(P, g, sp); if (b2) pool.push({ kind: "second", g, st, sp: b2.c.sp, c: b2.c, p: b2.c.p2, q: b2.c.q, cost: b2.c.cost }); }
      }
    }
    const takenG = new Set(apps.map(a => a.g));
    for (const pass of [false, true]) while (pf < G.conf && pool.length) {
      let best = null;
      for (const a of pool) {
        if (takenG.has(a.g) || waiting(a.g) || ((a.protect || recent(a.g)) && !pass)) continue;
        const np = fillProb(apps.concat(a), req);
        const gain = np - pf + 0.02 * a.p * (a.q - 2) * (G.slots.some(s => s.sp[a.sp] < 1) && a.sp === "C" ? 0.5 : 1);
        const score = gain / (1 + a.cost / 3000);
        if (gain > 0.004 && (!best || score > best.score)) best = { a, score, np };
      }
      if (!best) break;
      apps.push(best.a); takenG.add(best.a.g); pf = best.np;
    }
    // optional slots (e.g. pronghorn some years): best single application if it's a decent chance
    for (const s of opt) {
      if (apps.some(a => s.sp[a.sp] && a.p >= 0.5)) continue;
      const o = pool.filter(a => s.sp[a.sp] && !takenG.has(a.g)).sort((a, b) => (b.p * (1 + b.q / 5)) - (a.p * (1 + a.q / 5)))[0];
      if (o && o.p >= 0.3) { apps.push({ ...o, optional: true }); takenG.add(o.g); }
    }
    // 4. points everywhere else in the goal (keeps the rotation building)
    const points = [];
    for (const st of G.states) {
      if (!POINT_ST.has(st)) continue;
      for (const sp of ["E", "D", "P"]) {
        if (!SPECIES_IN[st].includes(sp) || !G.slots.some(s => s.sp[sp] || (sp === "D" && s.sp.C))) continue;
        const g = grpOf(st, sp); if (takenG.has(g)) continue;
        // buy a point only where it builds toward something: a target still ahead, points you already hold,
        // or (when building for top units) a state with nothing reachable yet. A target you can already
        // draw at your points doesn't need more points.
        const tg = T[g];
        if (!((tg && tg.t > 0) || (pts[g] || 0) > 0 || (!tg && G.quality >= 0.85))) continue;
        points.push({ kind: "point", g, st, sp, p: 0, cost: (ctx.PRICES[st] || {}).pt || 0, target: tg || null });
      }
      if (st === "MT") for (const sp of ["E", "D"]) { const g = grpOf(st, sp, true); const tp = T[grpOf(st, sp)];
        if (!takenG.has(g) && (pts[g] || 0) < 3 && G.slots.some(s => s.sp[sp]) && ((tp && !takenG.has(grpOf(st, sp))) || (pts[g] || 0) > 0)) points.push({ kind: "point", g, st, sp, pref: true, p: 0, cost: (ctx.PRICES.MT || {}).prefPt || 0, target: T[g] || null }); }
    }
    // Montana: every elk/deer application goes with the combo license; note whether to buy the point with it
    for (const a of apps) if (a.st === "MT") {
      const cg = grpOf("MT", a.sp, true), combo = a.c.general ? a.c : (P.byGroup[cg] || [])[0];
      if (!combo) continue;
      const have = Math.min(3, pts[cg] || 0), co = comboOdds(P, combo, have, k);
      a.combo = { p: co.p, buy: co.buy, have, drawWith: co.buy ? have + 1 : have };
      if (a.c.general) a.buy = co.buy;
    }
    // 5. OTC fallback (after draw results)
    const otc = G.otc ? (ctx.OTC || []).filter(o => G.states.includes(o.st) && dueSp.has(o.sp) && req.some(s => s.sp[o.sp]) &&
      (o.weapon === "any" ? (G.weapons.rifle || G.weapons.archery) : G.weapons[o.weapon === "rifle" ? "rifle" : o.weapon])) : [];
    return { apps, points, pf, req, opt, due, targets: T, otc };
  }

  // Montana combo license: a preference point bought with the application counts in that year's draw
  // (max 3 points), and the random 25% only goes to applicants with zero points. So with 0 points it can be
  // better NOT to buy (random pool); with 1+ points buying moves you up a level.
  function comboOdds(P, c, pts, k) {
    const have = Math.min(3, pts || 0);
    const no = P.p(c, have, k), yes = have < 3 ? P.p(c, have + 1, k) : null;
    return (yes != null && yes > (no || 0)) ? { p: yes, buy: true } : { p: no || 0, buy: false };
  }
  function mtCombo(P, c, pts, k) {
    if (c.st !== "MT" || c.general) return 1;
    const g = grpOf("MT", c.sp, true), combo = (P.byGroup[g] || [])[0];
    return combo ? comboOdds(P, combo, pts[g] || 0, k).p : 1;
  }
  function bestNow(P, g, sp, pts, k, G, lottery) {
    const bc = P.bcache || (P.bcache = new Map()), ck = g + sp + "|" + (pts[g] || 0) + "|" + k + "|" + (pts[grpOf(g.slice(0, 2), sp, true)] || 0);
    if (bc.has(ck)) return bc.get(ck);
    let best = null;
    for (const c of P.byGroup[g] || []) {
      if (c.sp !== sp) continue;
      const o = c.st === "MT" && c.general ? comboOdds(P, c, pts[g] || 0, k).p : P.p(c, pts[g] || 0, k); if (o == null || o <= 0) continue;
      const pp = o * mtCombo(P, c, pts, k);
      const v = pp * (1 + 0.15 * (c.q - 2) * (0.5 + G.quality));
      if (!best || v > best.v) best = { c, p: pp, v };
    }
    bc.set(ck, best);
    return best;
  }
  function bestSecond(P, g, sp) {
    let best = null;
    for (const c of P.byGroup[g] || []) { if (c.sp !== sp || !c.p2) continue; const v = c.p2 * (1 + 0.15 * (c.q - 2)); if (!best || v > best.v) best = { c, v }; }
    return best;
  }

  function stepPoints(pts, plan, drawn) {
    const nx = Object.assign({}, pts);
    for (const a of plan.apps) {
      if (!POINT_ST.has(a.st)) continue;
      if (a.kind === "second") { nx[a.g] = (nx[a.g] || 0) + 1; continue; }           // CO: point 1st choice, hunt 2nd choice
      if (a.st === "MT" && a.c.general) { nx[a.g] = drawn.has(a) ? 0 : Math.min(3, (nx[a.g] || 0) + (a.buy ? 1 : 0)); continue; }
      nx[a.g] = drawn.has(a) ? 0 : (nx[a.g] || 0) + 1;
      if (a.st === "MT" && !a.c.general) { const cg = grpOf("MT", a.sp, true);
        nx[cg] = drawn.has(a) ? 0 : Math.min(3, (nx[cg] || 0) + (a.combo && a.combo.buy ? 1 : 0)); }  // combo drawn with the permit
    }
    for (const a of plan.points) nx[a.g] = a.pref ? Math.min(3, (nx[a.g] || 0) + 1) : (nx[a.g] || 0) + 1;
    return nx;
  }

  function cost(ctx, plan) {
    const P = ctx.PRICES, st = new Set();
    let upfront = 0, expected = 0, allDrawn = 0;
    for (const a of plan.apps.concat(plan.points)) {
      st.add(a.st);
      const app = a.kind === "point" ? a.cost : ((P[a.st] || {}).app || 0);
      upfront += app; expected += app;
      if (a.kind !== "point") { expected += a.p * a.cost; allDrawn += a.cost; }
    }
    for (const s of st) { const l = (P[s] || {}).lic || 0; upfront += l; expected += l; }
    return { upfront, expected, allDrawn: upfront + allDrawn };
  }

  function run(ctx, G) {
    const t0 = Date.now();
    const P = prepare(ctx, G);
    const pts0 = Object.assign({}, ctx.pts);
    // the shown plan: most likely path (a draw counts as drawn when its odds are 50%+)
    const path = [];
    let pts = pts0, hist = {};
    for (let k = 0; k < G.years; k++) {
      const plan = planYear(ctx, G, P, k, pts, hist);
      plan.year = ctx.Y0 + k; plan.ptsBefore = pts; plan.cost = cost(ctx, plan);
      const drawn = new Set(plan.apps.filter(a => a.p >= 0.5));
      if ([...drawn].some(a => a.sp === "C")) hist = { ...hist, lastC: k };
      hist = { ...hist, hunted: Object.assign({}, hist.hunted, Object.fromEntries([...drawn].map(a => [a.g, k]))),
        drawnAt: Object.assign({}, hist.drawnAt, Object.fromEntries([...drawn].map(a => [a.g, k]))) };
      plan.likely = drawn;
      path.push(plan);
      pts = stepPoints(pts, plan, drawn);
    }
    // simulation: random draws, policy re-planned each year with the simulated points
    const yrs = Array.from({ length: G.years }, () => ({ filled: 0, tags: 0, elk: 0, q4: 0, hunts: [], otcNeed: 0 }));
    let goalAll = 0, q4total = 0, rnd = mulberry(12345);
    for (let s = 0; s < SIMS; s++) {
      let pts = Object.assign({}, pts0), hist = {}, allOk = true;
      for (let k = 0; k < G.years; k++) {
        const plan = planYear(ctx, G, P, k, pts, hist);
        const drawn = new Set(plan.apps.filter(a => rnd() < a.p));
        const cnt = [0, 0, 0, 0]; let best = 0;
        for (const a of drawn) { cnt[SPX.indexOf(a.sp)]++; best = Math.max(best, a.q || 0); }
        const ok = canFill(cnt.map(x => Math.min(x, plan.req.length || 1)), plan.req);
        const Y = yrs[k]; if (ok) Y.filled++; else { allOk = false; Y.otcNeed++; }
        Y.tags += drawn.size; if (cnt[0]) Y.elk++; if (best >= 4) { Y.q4++; q4total++; }
        if ([...drawn].some(a => a.sp === "C")) hist = { ...hist, lastC: k };
        hist = { ...hist, hunted: Object.assign({}, hist.hunted, Object.fromEntries([...drawn].map(a => [a.g, k]))),
          drawnAt: Object.assign({}, hist.drawnAt, Object.fromEntries([...drawn].map(a => [a.g, k]))) };
        pts = stepPoints(pts, plan, drawn);
      }
      if (allOk) goalAll++;
    }
    const stats = yrs.map(Y => ({ filled: Y.filled / SIMS, tags: Y.tags / SIMS, elk: Y.elk / SIMS, q4: Y.q4 / SIMS, otcNeed: Y.otcNeed / SIMS }));
    return { path, stats, every: goalAll / SIMS, q4PerPlan: q4total / SIMS, ncands: P.cands.length, ms: Date.now() - t0 };
  }
  function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  const api = { RULES, run, fillProb, canFill, SYS, POINT_ST, grpOf };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.Planner = api;
})(typeof window !== "undefined" ? window : globalThis);
