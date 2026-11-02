/* Strategy builder: turns the hunter's settings (or a typed focus command) into a multi-year
   plan using the draw data, My Points, trophy ratings and nonresident costs. Relies on globals
   from index.html: DRAW, TROPHY, Odds, myPts, huntSys, usesPref, nrOpen, trophyOf, isAntlerless,
   isEither, SN, SPECIES, DATES, oddsVal, pct. */
(function () {
  "use strict";
  const ALL_ST = ["CO", "WY", "UT", "AZ", "NM", "NV", "OR", "ID", "MT"];
  const SPN = { E: "Elk", D: "Mule deer", C: "Coues deer", P: "Pronghorn" };
  // Nonresident costs (2026 prices; Wyoming points at 2027 price). lic = yearly license needed to apply.
  const PRICES = {
    CO: { lic: 117.62, app: 11.49, pt: 0, tag: { E: 845, D: 507, P: 507 } },
    WY: { lic: 0, app: 15, pt: 75, tag: { E: 707, D: 389, P: 341 }, special: { E: 1965, D: 1215, P: 1215 } },
    UT: { lic: 144, app: 21, pt: 21, tag: { E: 1950, D: 1070, P: 571 }, general: { E: 849, D: 599 } },
    AZ: { lic: 160, app: 15, pt: 15, tag: { E: 665, D: 315, C: 315, P: 565 } },
    NM: { lic: 104, app: 13, pt: null, tag: { E: 773, D: 398, C: 398, P: 423 } },
    NV: { lic: 155, app: 14, appE: 19, pt: 11, tag: { E: 1200, D: 240, P: 300 } },
    OR: { lic: 193, app: 10, pt: 10, tag: { E: 660, D: 500, P: 443 } },
    ID: { lic: 205, app: 18, pt: null, tag: { E: 651.75, D: 351.75, P: 342.75 } },
    MT: { lic: 0, app: 5, pt: 20, ptP: 15, tag: { E: 1112, D: 760, P: 200 }, prefPt: 100 }
  };
  const SPECIES_IN = { CO: "EDP", WY: "EDP", UT: "EDP", AZ: "EDCP", NM: "EDCP", NV: "EDP", OR: "EDP", ID: "EDP", MT: "EDP" };
  // Over-the-counter / general options that aren't in the draw reports
  const OTC = [
    { st: "CO", sp: "E", label: "Colorado over-the-counter bull elk, 2nd or 3rd rifle", weapon: "rifle", tag: "antlered", cost: 845 + 117.62, trophy: 2, odds: 1, note: "Sold over the counter in many western units, like the Flat Tops (12/23/24)." },
    { st: "UT", sp: "E", label: "Utah general-season archery elk (over the counter)", weapon: "archery", tag: "either", cost: 849 + 144, trophy: 2, odds: 1, note: "Unlimited; goes on sale in early July." },
    { st: "ID", sp: "E", label: "Idaho general elk tag, uncapped zone (McCall, Weiser River, Panhandle)", weapon: "any", tag: "antlered", cost: 651.75 + 205 + 18, trophy: 2, odds: 0.9, note: "Nonresident general tag draw in December; leftovers sell over the counter in late March." },
    { st: "ID", sp: "D", label: "Idaho general deer tag", weapon: "any", tag: "antlered", cost: 351.75 + 205 + 18, trophy: 2, odds: 0.9, note: "Nonresident general tag draw in December." },
    { st: "AZ", sp: "D", label: "Arizona over-the-counter archery deer (mule deer or Coues)", weapon: "archery", tag: "antlered", cost: 300 + 160, trophy: 2, odds: 0.95, note: "On sale in early November; sells out." },
    { st: "AZ", sp: "C", label: "Arizona over-the-counter archery deer (Coues or mule deer)", weapon: "archery", tag: "antlered", cost: 300 + 160, trophy: 2, odds: 0.95, note: "On sale in early November; sells out." },
    { st: "OR", sp: "E", label: "Oregon general archery elk (over the counter)", weapon: "archery", tag: "either", cost: 660 + 193, trophy: 1, odds: 1, note: "Sold over the counter." },
    { st: "OR", sp: "D", label: "Oregon general archery deer (over the counter)", weapon: "archery", tag: "antlered", cost: 500 + 193, trophy: 1, odds: 1, note: "Sold over the counter." }
  ];
  const DEF = { species: ["E", "D", "C", "P"], states: ALL_ST.slice(), hpy: 2, minOdds: 0.5, trophyEvery: 2, trophyMin: 4,
    maxWait: 8, weapon: "any", tag: "antlered", budget: 4000, otc: true, priv: false, years: 5, focus: "" };
  let S = load();

  function load() { try { return Object.assign({}, DEF, JSON.parse(localStorage.getItem("wdp-plan") || "{}")); } catch (e) { return Object.assign({}, DEF); } }
  function save() { try { localStorage.setItem("wdp-plan", JSON.stringify(S)); } catch (e) {} }
  const money = v => "$" + Math.round(v).toLocaleString();
  const startYear = () => { const d = new Date(); return d.getMonth() >= 7 ? d.getFullYear() + 1 : d.getFullYear(); };

  // ---------- typed focus command ----------
  const ST_NAMES = { colorado: "CO", wyoming: "WY", utah: "UT", arizona: "AZ", "new mexico": "NM", nevada: "NV", oregon: "OR", idaho: "ID", montana: "MT" };
  function parseCommand(text) {
    const t = " " + text.toLowerCase().replace(/(\d),(\d{3})/g, "$1$2").replace(/[,;]/g, " ") + " ";
    const out = {}, said = [];
    // species
    const sp = [];
    if (/\belk\b/.test(t)) sp.push("E");
    if (/\bmule ?deer\b|\bmulies?\b/.test(t) || (/\bdeer\b/.test(t) && !/coues/.test(t))) sp.push("D");
    if (/\bcoues\b/.test(t)) sp.push("C");
    if (/\bpronghorn\b|\bantelope\b|\blopes?\b/.test(t)) sp.push("P");
    if (sp.length) { out.species = sp; said.push("Species: " + sp.map(k => SPN[k]).join(", ")); }
    // states: "skip/no/not/except/avoid X" excludes; "only/just/focus on X" restricts
    const named = [], skipped = [];
    for (const [name, code] of Object.entries(ST_NAMES)) {
      const re = new RegExp("(skip|no|not|except|avoid|without|drop)\\s+(?:\\w+\\s+){0,2}?" + name + "\\b");
      if (re.test(t)) skipped.push(code); else if (new RegExp("\\b" + name + "\\b").test(t)) named.push(code);
    }
    if (/\b(only|just|focus on|stick to)\b/.test(t) && named.length) { out.states = named; said.push("Only " + named.map(c => SN[c]).join(", ")); }
    else if (skipped.length) { out.states = ALL_ST.filter(c => !skipped.includes(c)); said.push("Skip " + skipped.map(c => SN[c]).join(", ")); }
    // hunts per year
    let m = t.match(/(\d|one|two|three|four)\s+hunts?\s*(a|per|each)\s*year/);
    if (m) { const n = { one: 1, two: 2, three: 3, four: 4 }[m[1]] || +m[1]; out.hpy = Math.max(1, Math.min(4, n)); said.push(out.hpy + " hunt" + (out.hpy > 1 ? "s" : "") + " a year"); }
    // trophy cadence and quality
    m = t.match(/trophy[^.]*?every\s+(\d|other|two|three|four|five)\s*(years?)?/);
    if (m) { const n = { other: 2, two: 2, three: 3, four: 4, five: 5 }[m[1]] || +m[1]; out.trophyEvery = n; said.push("Trophy hunt every " + n + " years"); }
    if (/\bno trophy\b|\bdon'?t care about trophy\b|\bjust (want to )?hunt\b/.test(t)) { out.trophyEvery = 0; said.push("No trophy goal"); }
    m = t.match(/trophy\s*(?:score|rating|level)?\s*(\d)\s*\+?/) || t.match(/\b([345])\s*\+?\s*trophy/);
    if (m && +m[1] >= 2 && +m[1] <= 5) { out.trophyMin = +m[1]; said.push("Trophy " + m[1] + "+"); }
    if (/top[- ]tier|giant|once in a lifetime/.test(t)) { out.trophyMin = 5; said.push("Top-tier trophy"); }
    m = t.match(/(?:within|in|wait(?:ing)?(?: up to)?|max(?:imum)?(?: of)?)\s+(\d+)\s+years?/);
    if (m) { out.maxWait = Math.max(1, Math.min(20, +m[1])); said.push("Wait at most " + out.maxWait + " years"); }
    // weapon and tag
    if (/\barchery\b|\bbow\b/.test(t)) { out.weapon = "archery"; said.push("Archery"); }
    else if (/\bmuzzle ?loader\b|\bml\b/.test(t)) { out.weapon = "muzzleloader"; said.push("Muzzleloader"); }
    else if (/\brifle\b|\bany weapon\b/.test(t)) { out.weapon = "rifle"; said.push("Rifle"); }
    if (/\bcows?\b|\bdoes?\b|\bantlerless\b|\bmeat\b/.test(t)) { out.tag = /\bmeat\b/.test(t) ? "any" : "antlerless"; said.push(out.tag === "any" ? "Any tag (meat hunts OK)" : "Antlerless tags"); }
    else if (/\bbulls?\b|\bbucks?\b|\bantlered\b/.test(t)) { out.tag = "antlered"; said.push("Antlered tags"); }
    // odds
    m = t.match(/(\d{2})\s*%/);
    if (m) { out.minOdds = Math.max(0.05, Math.min(0.95, +m[1] / 100)); said.push("At least " + m[1] + "% odds"); }
    else if (/\bsure thing|\bguaranteed|\bcertain\b/.test(t)) { out.minOdds = 0.9; said.push("Near-sure draws"); }
    // budget
    m = t.match(/\$\s*([\d.,]+)\s*(k)?/) || t.match(/([\d.,]+)\s*(k)?\s*(?:dollars|budget|a year|per year)/);
    if (m) { let v = parseFloat(m[1].replace(/,/g, "")); if (m[2]) v *= 1000; if (v >= 100) { out.budget = Math.round(v); said.push("Budget " + money(v) + " a year"); } }
    // OTC
    if (/\bprivate|\branch(es)?\b|\bcwmu\b/.test(t)) { out.priv = !/\bno private|\bpublic (land )?only\b/.test(t); said.push(out.priv ? "Private-land hunts OK" : "Public land only"); }
    if (/\bno (otc|over the counter|general)\b|\bdraw only\b/.test(t)) { out.otc = false; said.push("Draw tags only"); }
    else if (/\b(otc|over the counter|general tags?)\b/.test(t)) { out.otc = true; said.push("Include over-the-counter tags"); }
    return { out, said };
  }

  // ---------- candidates ----------
  // bag from the official hunt code / bag-limit text; spike-only, whitetail-only and unconfirmed tags are never "antlered"
  function tagOk(h) {
    const b = bagOf(h);
    if (S.tag === "any") return b !== "other";
    return S.tag === "antlerless" ? (b === "antlerless" || b === "either") : (b === "antlered" || b === "either");
  }
  function weaponOk(w) { return S.weapon === "any" || w === S.weapon || (S.weapon === "rifle" && w === "any"); }
  function huntTrophy(st, h) {
    if (!trophyOk(h)) return null;   // spike-only / antlerless / unconfirmed: the unit's trophy rating doesn't apply
    let best = null;
    for (const u of h.units || []) { const t = trophyOf(st, h.species, String(u)); if (t && (best == null || t.s > best)) best = t.s; }
    return best;
  }
  function huntCost(st, h) {
    const P = PRICES[st]; if (!P) return 0;
    if (st === "WY" && h.kind === "special" && P.special) return P.special[h.species] || 0;
    if (st === "UT" && h.kind === "general" && P.general) return P.general[h.species] || P.tag[h.species] || 0;
    return (P.tag[h.species === "C" && !P.tag.C ? "D" : h.species]) || 0;
  }
  const hasPts = st => PRICES[st] && PRICES[st].pt != null;
  function candidates() {
    const out = [];
    for (const st of S.states) {
      const d = DRAW[st]; if (!d) continue;
      for (const h of d.hunts) {
        if (!S.species.includes(h.species) || !weaponOk(h.weapon) || !tagOk(h) || restricted(h) || (!S.priv && privateLand(h))) continue;
        if (!nrOpen(h) || !isCurrent(h)) continue;   // no NR tags lately, or not offered in the latest draw
        const y = Odds.latestYear(h, "NR"); if (!y) continue;
        // nonresident results must be from the hunt's latest draw, not an older year
        if (y !== Object.keys(h.years).sort().pop()) continue;
        // need at least two years of nonresident history, and enough applicants to mean something
        const ys = Object.keys(h.years).filter(yy => h.years[yy].NR && h.years[yy].NR.apps != null);
        if (ys.length < 2) continue;
        out.push({ st, h, sp: h.species, trophy: huntTrophy(st, h), cost: huntCost(st, h), sys: huntSys(st, h), pref: usesPref(st, h),
          label: (h.label || h.id), units: (h.units || []).slice(0, 4).join(", ") });
      }
    }
    return out;
  }
  // odds for a hunt in plan year k with `pts` points; preference states shift by historical point creep
  function oddsAt(c, pts, k) {
    const sys = c.sys;
    let p = pts;
    if (/^pref/.test(sys) && k > 0) { const slope = Odds.recentSlope(Odds.creep(c.h.years, "NR")); p = Math.max(0, Math.round(pts - slope * k)); }
    const s = Odds.summarize(sys, c.h, "NR", p);
    let v = oddsVal(s);
    // Montana elk/deer permits also need the nonresident combo license draw
    if (v != null && c.st === "MT" && c.h.kind !== "general" && (c.sp === "E" || c.sp === "D") && window.mtCombo) { const cb = window.mtCombo(c.sp); if (cb != null) v *= cb; }
    return v;
  }
  const ptKeyOf = c => c.st + (c.sp === "C" ? "D" : c.sp) + (c.pref ? "pref" : "");

  // ---------- the plan ----------
  function build() {
    const Y0 = startYear(), cands = candidates();
    const pts = {};   // current points per state+species(+pref)
    const banking = new Set();
    for (const st of S.states) for (const sp of S.species) {
      if (!SPECIES_IN[st].includes(sp) || !hasPts(st)) continue;
      const k = st + (sp === "C" ? "D" : sp); banking.add(k); pts[k] = myPts(st, sp, false);
      if (st === "MT" && sp !== "P") { banking.add(k + "pref"); pts[k + "pref"] = myPts(st, sp, true); }
    }
    const P = c => pts[ptKeyOf(c)] || 0;
    const years = [];
    let lastTrophy = -99;
    const usedHunts = new Set();
    for (let k = 0; k < S.years; k++) {
      const year = Y0 + k, picks = [], usedSS = new Set();
      const scored = cands.filter(c => !usedHunts.has(c.st + c.h.id)).map(c => ({ c, pts: P(c), o: oddsAt(c, P(c), k) })).filter(x => x.o != null);
      // trophy slot
      const trophyDue = S.trophyEvery > 0 && (k - lastTrophy) >= S.trophyEvery;
      if (trophyDue) {
        const t = scored.filter(x => (x.c.trophy || 0) >= S.trophyMin && x.o >= S.minOdds)
          .sort((a, b) => (b.c.trophy - a.c.trophy) || (b.o - a.o) || (a.c.cost - b.c.cost))[0];
        if (t) { picks.push({ ...t, kind: "trophy" }); usedSS.add(t.c.st + t.c.sp); lastTrophy = k; }
      }
      // fill remaining hunts: best trophy you can draw, cheaper and fewer points spent first on ties
      const fill = scored.filter(x => x.o >= S.minOdds && !usedSS.has(x.c.st + x.c.sp))
        .map(x => ({ ...x, score: (x.c.trophy || 1.5) * 10 + x.o * 4 - (/^pref/.test(x.c.sys) ? P(x.c) * 0.8 : 0) - x.c.cost / 800 }))
        .sort((a, b) => b.score - a.score);
      for (const x of fill) { if (picks.length >= S.hpy) break; if (usedSS.has(x.c.st + x.c.sp)) continue; picks.push({ ...x, kind: "hunt" }); usedSS.add(x.c.st + x.c.sp); }
      if (picks.length < S.hpy && S.otc) {
        for (const o of OTC) {
          if (picks.length >= S.hpy) break;
          if (!S.states.includes(o.st) || !S.species.includes(o.sp) || usedSS.has(o.st + o.sp) || !weaponOk(o.weapon)) continue;
          if (S.tag === "antlerless" && o.tag === "antlered") continue;
          picks.push({ otc: o, o: o.odds, kind: "otc" }); usedSS.add(o.st + o.sp);
        }
      }
      // costs
      let fixed = 0; const apply = [];
      const licStates = new Set();
      for (const key of banking) {
        const st = key.slice(0, 2), sp = key[2], pref = key.endsWith("pref"), Pr = PRICES[st];
        let c = pref ? Pr.prefPt : (sp === "P" && Pr.ptP ? Pr.ptP : (sp === "E" && Pr.appE ? Pr.appE : (Pr.pt || Pr.app)));
        if (st === "WY" && k === 0 && new Date() < new Date(year - 1 + "-11-03")) c = { E: 52, D: 41, P: 31 }[sp] || c;
        fixed += c; licStates.add(st);
        apply.push({ st, sp, pref, pts: pts[key], cost: c });
      }
      for (const st of S.states) if (!hasPts(st) && S.species.some(sp => SPECIES_IN[st].includes(sp))) {
        const Pr = PRICES[st]; const n = S.species.filter(sp => SPECIES_IN[st].includes(sp)).length;
        fixed += Pr.app * n; licStates.add(st); apply.push({ st, sp: "lottery", pts: null, cost: Pr.app * n, n });
      }
      for (const st of licStates) fixed += PRICES[st].lic || 0;
      const tagCost = picks.reduce((s, p) => s + (p.otc ? p.otc.cost : p.c.cost * (p.o || 1)), 0);
      years.push({ year, picks, apply, fixed, tagCost, ptsBefore: Object.assign({}, pts) });
      // advance points: drawn hunts reset, everything else +1
      const drawn = new Set(picks.filter(p => p.c).map(p => ptKeyOf(p.c)));
      for (const key of banking) pts[key] = drawn.has(key) ? 0 : (pts[key] || 0) + 1;
      picks.filter(p => p.c).forEach(p => usedHunts.add(p.c.st + p.c.h.id));
    }
    // trophy track: best trophy hunts and when you'd likely draw them
    const track = [];
    const tc = cands.filter(c => (c.trophy || 0) >= S.trophyMin);
    for (const c of tc) {
      let when = null, o0 = null;
      for (let k = 0; k <= S.maxWait; k++) { const o = oddsAt(c, (myPts(c.st, c.sp, c.pref)) + k, k); if (k === 0) o0 = o; if (o != null && o >= S.minOdds) { when = k; break; } }
      track.push({ c, when, o0 });
    }
    track.sort((a, b) => ((a.when ?? 99) - (b.when ?? 99)) || (b.c.trophy - a.c.trophy) || ((b.o0 || 0) - (a.o0 || 0)));
    const seen = new Set(), trackTop = [];
    for (const t of track) { const k = t.c.st + "|" + t.c.units + "|" + t.c.sp; if (seen.has(k)) continue; seen.add(k); trackTop.push(t); if (trackTop.length >= 10) break; }
    return { Y0, years, trackTop, ncands: cands.length };
  }

  // ---------- render ----------
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function settingsHTML() {
    const chk = (name, val, lab, on) => `<label class="pchk"><input type="checkbox" name="${name}" value="${val}"${on ? " checked" : ""}> ${lab}</label>`;
    const opt = (v, lab, cur) => `<option value="${v}"${String(v) === String(cur) ? " selected" : ""}>${lab}</option>`;
    return `
    <form class="panel" id="plan-cmd" autocomplete="off">
      <label for="plan-text" class="plbl">Tell the planner what to focus on</label>
      <textarea id="plan-text" rows="2" placeholder="Example: elk and Coues, 2 hunts a year, trophy elk every 3 years within 6 years, archery, skip Oregon, $3,000 a year">${esc(S.focus || "")}</textarea>
      <div class="factions"><button type="submit" class="btn">Update plan</button><button type="button" class="btn ghost" id="plan-reset">Reset to defaults</button></div>
      <div id="plan-said" class="said"></div>
    </form>
    <details class="panel" id="plan-settings"><summary>All settings</summary>
      <div class="pgroup"><span class="plbl">Species</span>${["E", "D", "C", "P"].map(k => chk("species", k, SPN[k], S.species.includes(k))).join("")}</div>
      <div class="pgroup"><span class="plbl">States</span>${ALL_ST.map(k => chk("states", k, SN[k], S.states.includes(k))).join("")}</div>
      <div class="fgrid">
        <label>Hunts per year<select name="hpy">${[1, 2, 3, 4].map(n => opt(n, n, S.hpy)).join("")}</select></label>
        <label>Draw odds I'll count on<select name="minOdds">${[[.25, "25%+"], [.5, "50%+"], [.75, "75%+"], [.9, "90%+"]].map(([v, l]) => opt(v, l, S.minOdds)).join("")}</select></label>
        <label>Trophy hunt<select name="trophyEvery">${[[0, "No trophy goal"], [2, "Every 2 years"], [3, "Every 3 years"], [4, "Every 4 years"], [5, "Every 5 years"]].map(([v, l]) => opt(v, l, S.trophyEvery)).join("")}</select></label>
        <label>Trophy means<select name="trophyMin">${[3, 4, 5].map(v => opt(v, `${v}+ · elk ${window.trophyInches ? window.trophyInches("E", v).replace(/–.*/, "\"+") : ""}, deer ${window.trophyInches ? window.trophyInches("D", v).replace(/–.*/, "\"+") : ""}`, S.trophyMin)).join("")}</select></label>
        <label>Longest wait for a trophy<select name="maxWait">${[3, 5, 8, 10, 15].map(n => opt(n, n + " years", S.maxWait)).join("")}</select></label>
        <label>Weapon<select name="weapon">${[["any", "Any"], ["rifle", "Rifle"], ["archery", "Archery"], ["muzzleloader", "Muzzleloader"]].map(([v, l]) => opt(v, l, S.weapon)).join("")}</select></label>
        <label>Tags<select name="tag">${[["antlered", "Antlered (incl. either-sex)"], ["antlerless", "Antlerless"], ["any", "Any tag"]].map(([v, l]) => opt(v, l, S.tag)).join("")}</select></label>
        <label>Yearly budget<input name="budget" type="number" min="0" step="100" inputmode="numeric" value="${S.budget}"></label>
        <label>Years to plan<select name="years">${[3, 5, 7].map(n => opt(n, n, S.years)).join("")}</select></label>
      </div>
      <label class="pchk"><input type="checkbox" name="otc"${S.otc ? " checked" : ""}> Include over-the-counter and general tags</label>
      <label class="pchk"><input type="checkbox" name="priv"${S.priv ? " checked" : ""}> Include private-land and ranch hunts</label>
      <div class="factions"><button type="button" class="btn" id="plan-apply">Apply settings</button></div>
      ${FLASH ? `<p class="said" role="status">${esc(FLASH)}</p>` : ""}
    </details>`;
  }
  function pickHTML(p) {
    if (p.otc) return `<div class="pick"><div class="ph"><span class="tag" style="color:var(--otc)">OTC</span><b>${esc(p.otc.label)}</b></div><div class="pm">${SN[p.otc.st]} · ${SPN[p.otc.sp]} · ~${money(p.otc.cost)} incl. license</div><p class="note">${esc(p.otc.note)}</p><button type="button" class="maplink" data-st="${p.otc.st}" data-sp="${p.otc.sp}">Show ${SN[p.otc.st]} on map</button></div>`;
    const c = p.c, t = c.trophy;
    return `<div class="pick"><div class="ph"><span class="tag" style="color:${p.kind === "trophy" ? "var(--premier)" : "var(--easy)"}">${p.kind === "trophy" ? "Trophy" : "Hunt"}</span><b>${SN[c.st]} ${SPN[c.sp].toLowerCase()} · ${esc(c.units)}</b></div>
      <div class="pm">${esc(c.label)} · <b>${bagLabel(c.h)}</b>${c.h.bag_text ? ` (${esc(c.h.bag_text)})` : ""}</div>
      <div class="pm">Odds ${pct(p.o)}${/^bonus|^az|^pref/.test(c.sys) ? ` with ${p.pts ?? "your"} pts` : ""}${t ? ` · trophy ${t}/5 (${window.trophyInches ? window.trophyInches(c.sp, t) : ""})` : ""} · tag ~${money(c.cost)}</div>${(() => { const y = Odds.latestYear(c.h, "NR"), a = y ? c.h.years[y].NR.apps : null; return a != null && a < 10 ? `<div class="pm small-n">Only ${a} nonresident applicant${a === 1 ? "" : "s"} in ${y}, so these odds could swing.</div>` : ""; })()}<button type="button" class="maplink" data-st="${c.st}" data-hid="${esc(c.h.id)}">Show unit${(c.h.units || []).length > 1 ? "s" : ""} on map</button></div>`;
  }
  function render() {
    const root = document.getElementById("plan-root"); if (!root) return;
    const loaded = ALL_ST.some(st => DRAW[st]);
    let html = settingsHTML();
    if (!loaded) { root.innerHTML = html + `<p class="note">Loading draw data…</p>`; wire(); return; }
    const R = build();
    const sum = [`${S.species.map(k => SPN[k]).join(", ")}`, `${S.hpy} hunt${S.hpy > 1 ? "s" : ""} a year`,
      S.trophyEvery ? `trophy ${S.trophyMin}+ every ${S.trophyEvery} years` : "no trophy goal", S.weapon !== "any" ? S.weapon : "any weapon",
      `odds ${Math.round(S.minOdds * 100)}%+`, `${money(S.budget)} a year`, S.states.length === 9 ? "all 9 states" : S.states.map(c => SN[c]).join(", ")].join(" · ");
    // next steps from the deadline list
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const next = DATES.filter(d => S.states.includes(d[1])).map(d => ({ d, dt: new Date(d[0] + "T12:00:00") }))
      .filter(x => x.dt >= today && (x.dt - today) / 864e5 <= 120).sort((a, b) => a.dt - b.dt).slice(0, 7);
    html += `<h2 id="plan-top">Your plan</h2>${FLASH ? `<p class="said updated" role="status">${esc(FLASH)}</p>` : ""}<p class="lede">${esc(sum)}. Built from ${R.ncands.toLocaleString()} draw hunts that fit, your points on the My Points tab, trophy ratings and nonresident prices. Points are assumed to grow one a year where you apply and reset when you draw; preference cutoffs keep creeping at their past rate.</p>`;
    if (next.length) html += `<div class="callout"><h3>Coming up</h3><ol>${next.map(x => `<li><b>${x.dt.toLocaleDateString("en-US", { month: "short", day: "numeric" })} · ${SN[x.d[1]]}.</b> ${esc(x.d[2])}${x.d[3] ? " (date estimated)" : ""}</li>`).join("")}</ol></div>`;
    html += `<h2>Year by year</h2><div id="years">` + R.years.map(y => {
      const over = y.fixed + y.tagCost > S.budget;
      const bank = y.apply.filter(a => a.sp !== "lottery");
      const lot = y.apply.filter(a => a.sp === "lottery");
      return `<div class="yr"><div class="y">${y.year}</div><div class="body">
        ${y.picks.length ? y.picks.map(p => pickHTML(p)).join("") : `<p class="note">No hunt clears ${Math.round(S.minOdds * 100)}% odds this year with these settings. Lower the odds, add states or allow over-the-counter tags.</p>`}
        ${y.picks.length < S.hpy && y.picks.length ? `<p class="note">Only ${y.picks.length} of ${S.hpy} hunts found at ${Math.round(S.minOdds * 100)}%+ odds.</p>` : ""}
        <p class="pbank"><span class="tag" style="color:var(--mid)">Apply / points</span>${bank.map(a => `${a.st} ${a.pref ? (a.sp === "E" ? "elk" : "deer") + " combo (pref.)" : (a.sp === "D" ? "deer" : SPN[a.sp].toLowerCase())}${a.pts != null ? ` <span class="ptn">${a.pts}→${a.pts + 1}</span>` : ""}`).join(" · ")}${lot.length ? ` · lottery: ${lot.map(a => a.st).join(", ")}` : ""}</p>
        <p class="pcost${over ? " over" : ""}">Applications, points & licenses ${money(y.fixed)} + expected tags ${money(y.tagCost)} = <b>${money(y.fixed + y.tagCost)}</b>${over ? ` · over your ${money(S.budget)} budget` : ""}</p>
      </div></div>`;
    }).join("") + `</div>`;
    html += `<h2>Trophy targets</h2><p class="lede">Hunts rated ${S.trophyMin}+ for trophy, soonest first. "Year" is when your odds reach ${Math.round(S.minOdds * 100)}% if you keep applying.</p><div class="tbl"><table><thead><tr><th>Hunt</th><th>Trophy</th><th>Odds next draw</th><th>Reach ${Math.round(S.minOdds * 100)}%</th><th>Tag</th></tr></thead><tbody>` +
      (R.trackTop.length ? R.trackTop.map(t => `<tr><td><b>${SN[t.c.st]} ${SPN[t.c.sp].toLowerCase()} ${esc(t.c.units)}</b><br><span class="note">${esc(t.c.label.slice(0, 70))}</span><br><button type="button" class="maplink" data-st="${t.c.st}" data-hid="${esc(t.c.h.id)}">Show on map</button></td><td class="num">${t.c.trophy}/5<br><span class="note">${window.trophyInches ? window.trophyInches(t.c.sp, t.c.trophy) : ""}</span></td><td class="num">${pct(t.o0)}</td><td class="num">${t.when == null ? `beyond ${S.maxWait} yrs` : t.when === 0 ? R.Y0 : R.Y0 + t.when}</td><td class="num">${money(t.c.cost)}</td></tr>`).join("") : `<tr><td colspan="5">No trophy-rated hunts match these settings.</td></tr>`) + `</tbody></table></div>`;
    html += `<p class="note" style="margin-top:8px">Prices are 2026 nonresident fees (Wyoming points at the 2027 price) and will change. Expected tag cost is tag price × draw odds. Odds come from each state's draw reports; check the state's own numbers before you apply.</p>`;
    root.innerHTML = html; wire();
  }
  let FLASH = "";
  // apply the settings form: rebuild, confirm, and (from the button) jump to the new plan
  function applySettings(jump) {
    readForm(); save();
    const set = document.getElementById("plan-settings"), open = set && set.open;
    FLASH = "Plan updated: " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + ".";
    render();
    const s2 = document.getElementById("plan-settings"); if (s2) s2.open = jump ? false : open;
    if (jump) { const t = document.getElementById("plan-top"); if (t) t.scrollIntoView({ behavior: "smooth", block: "start" }); }
  }
  function readForm() {
    const f = document.getElementById("plan-settings"); if (!f) return;
    const q = n => f.querySelector(`[name="${n}"]`);
    S.species = [...f.querySelectorAll('[name="species"]:checked')].map(i => i.value);
    S.states = [...f.querySelectorAll('[name="states"]:checked')].map(i => i.value);
    S.hpy = +q("hpy").value; S.minOdds = +q("minOdds").value; S.trophyEvery = +q("trophyEvery").value; S.trophyMin = +q("trophyMin").value;
    S.maxWait = +q("maxWait").value; S.weapon = q("weapon").value; S.tag = q("tag").value; S.budget = Math.max(0, +q("budget").value || 0);
    S.years = +q("years").value; S.otc = q("otc").checked; S.priv = q("priv").checked;
    if (!S.species.length) S.species = DEF.species.slice(); if (!S.states.length) S.states = ALL_ST.slice();
  }
  function wire() {
    const cmd = document.getElementById("plan-cmd"), set = document.getElementById("plan-settings");
    const root = document.getElementById("plan-root");
    if (!root.__mapWired) { root.__mapWired = true; root.addEventListener("click", e => { const b = e.target.closest(".maplink"); if (!b) return;
      if (b.dataset.hid && window.showHuntOnMap) window.showHuntOnMap(b.dataset.st, b.dataset.hid); else if (window.showStateOnMap) window.showStateOnMap(b.dataset.st, b.dataset.sp); }); }
    cmd.addEventListener("submit", e => {
      e.preventDefault();
      const text = document.getElementById("plan-text").value.trim();
      const { out, said } = parseCommand(text);
      Object.assign(S, out); S.focus = text; save(); render();
      const el = document.getElementById("plan-said");
      el.innerHTML = said.length ? "Got it: " + said.map(x => `<span class="chip sm">${esc(x)}</span>`).join(" ") : "I didn't catch any settings in that. Try naming species, states, hunts a year, a budget or a weapon.";
      document.getElementById("plan-root").scrollIntoView({ behavior: "smooth" });
    });
    document.getElementById("plan-reset").onclick = () => { S = Object.assign({}, DEF); save(); render(); };
    set.addEventListener("change", () => applySettings(false));
    document.getElementById("plan-apply").onclick = () => applySettings(true);
    // the budget box applies as you type (after a short pause), not only when you leave it
    const bud = set.querySelector('[name="budget"]'); let tm;
    if (bud) bud.addEventListener("input", () => { clearTimeout(tm); tm = setTimeout(() => { const pos = bud.selectionStart; applySettings(false); const nb = document.querySelector('#plan-settings [name="budget"]'); if (nb) { nb.focus(); try { nb.setSelectionRange(pos, pos); } catch (e) {} } }, 900); });
  }
  window.renderPlan = render;
  window.__planParse = parseCommand;
  window.__planBuild = () => build();
  window.__planSet = o => { Object.assign(S, o); };
})();
