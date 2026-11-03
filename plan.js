/* Hunt planner UI: a goal builder (hunts wanted each year, weapons, confidence, states, quality vs.
   frequency) feeding planner-core.js, which plans applications year by year and simulates the draws.
   Relies on globals from index.html: DRAW, TROPHY, Odds, myPts, SN, DATES, pct, bagLabel. */
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

  const DEF = {
    slots: [
      { sp: { E: 1 }, every: 1, optional: false },
      { sp: { E: 1, D: 1, C: 0.5 }, every: 1, optional: false },
      { sp: { P: 1 }, every: 3, optional: true }
    ],
    weapons: { archery: true, rifle: true, muzzleloader: false },
    conf: 0.9, quality: 0.5, rest: 2, states: ALL_ST.slice(), always: ["NM"], years: 6, priv: false, otc: true, budget: 0
  };
  const clone = o => JSON.parse(JSON.stringify(o));
  let S = load();
  function load() {
    try { const v = JSON.parse(localStorage.getItem("wdp-goal") || "null"); if (v && v.slots) return Object.assign(clone(DEF), v); } catch (e) {}
    return clone(DEF);
  }
  function save() { try { localStorage.setItem("wdp-goal", JSON.stringify(S)); } catch (e) {} }
  const money = v => "$" + Math.round(v).toLocaleString();
  const startYear = () => { const d = new Date(); return d.getMonth() >= 7 ? d.getFullYear() + 1 : d.getFullYear(); };
  const esc = t => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const P100 = v => v == null ? "–" : (v >= 0.995 ? "99%+" : v < 0.005 && v > 0 ? "<1%" : Math.round(v * 100) + "%");
  const SPS = { E: "Elk", D: "Mule deer", C: "Coues", P: "Pronghorn" };
  const QUAL = [[0.15, "Hunt as often as possible"], [0.5, "Balanced"], [0.85, "Build points for top units"]];
  const EVERY = [[1, "every year"], [2, "every 2nd year"], [3, "every 3rd year"]];

  function slotText(s) {
    const sp = Object.entries(s.sp).map(([k, w]) => SPS[k] + (w < 1 ? " (sometimes)" : ""));
    return sp.join(" or ") + ", " + (EVERY.find(e => e[0] === s.every) || EVERY[0])[1] + (s.optional ? " (bonus)" : "");
  }

  // ---------- goal form ----------
  function formHTML() {
    const chk = (name, val, lab, on, extra = "") => `<label class="pchk"><input type="checkbox" name="${name}" value="${val}"${on ? " checked" : ""} ${extra}> ${lab}</label>`;
    const opt = (v, lab, cur) => `<option value="${v}"${String(v) === String(cur) ? " selected" : ""}>${lab}</option>`;
    const slotRows = S.slots.map((s, i) => `
      <div class="slot" data-i="${i}">
        <span class="sn">Hunt ${i + 1}</span>
        <span class="sps">${["E", "D", "C", "P"].map(k => `<label class="pchk"><input type="checkbox" name="s${i}sp" value="${k}"${s.sp[k] ? " checked" : ""}> ${SPS[k]}</label>`).join("")}</span>
        ${s.sp.C ? `<label class="pchk"><input type="checkbox" name="s${i}cs"${s.sp.C < 1 ? " checked" : ""}> Coues only sometimes</label>` : ""}
        <select name="s${i}ev" aria-label="How often">${EVERY.map(([v, l]) => opt(v, l, s.every)).join("")}</select>
        <label class="pchk"><input type="checkbox" name="s${i}op"${s.optional ? " checked" : ""}> Bonus (nice to have)</label>
        ${S.slots.length > 1 ? `<button type="button" class="btn ghost sm" data-del="${i}">Remove</button>` : ""}
      </div>`).join("");
    return `
    <form class="panel goal" id="goal" autocomplete="off">
      <h3>Your goal</h3>
      <p class="pnote">Each line is one hunt you want in a year. A tag for any checked species fills it. Bonus hunts are added when a decent chance exists but aren't counted toward your confidence target.</p>
      <div class="slots">${slotRows}</div>
      <button type="button" class="btn ghost sm" id="slot-add">+ Add a hunt</button>
      <div class="fgrid">
        <label>Confidence: chance your required hunts all come through by draw<select name="conf">${[[0.8, "80%"], [0.9, "90%"], [0.95, "95%"]].map(([v, l]) => opt(v, l, S.conf)).join("")}</select></label>
        <label>Strategy<select name="quality">${QUAL.map(([v, l]) => opt(v, l, S.quality)).join("")}</select></label>
        <label>After hunting a state, rest it<select name="rest">${[[0, "No rest (repeat OK)"], [1, "1 year"], [2, "2 years"]].map(([v, l]) => opt(v, l, S.rest == null ? 2 : S.rest)).join("")}</select></label>
        <label>Years to plan<select name="years">${[3, 4, 5, 6, 8, 10].map(n => opt(n, n, S.years)).join("")}</select></label>
        <label>Budget per year (optional)<input name="budget" type="number" min="0" step="100" inputmode="numeric" value="${S.budget || ""}" placeholder="no limit"></label>
      </div>
      <div class="pgroup"><span class="plbl">Weapons</span>${chk("wpn", "archery", "Archery", S.weapons.archery)}${chk("wpn", "rifle", "Rifle", S.weapons.rifle)}${chk("wpn", "muzzleloader", "Muzzleloader", S.weapons.muzzleloader)}</div>
      <div class="pgroup"><span class="plbl">States</span>${ALL_ST.map(k => chk("states", k, SN[k], S.states.includes(k))).join("")}</div>
      <div class="pgroup"><span class="plbl">Always apply (pure lottery)</span>${["NM", "ID"].map(k => chk("always", k, SN[k], S.always.includes(k))).join("")}</div>
      ${chk("otc", "1", "Show over-the-counter backups if draws fall short", S.otc)}
      ${chk("priv", "1", "Include private-land hunts", S.priv)}
      <div class="factions"><button type="submit" class="btn">Build my plan</button><button type="button" class="btn ghost" id="goal-reset">Reset to my default goal</button></div>
      <p class="pnote">Uses your points from the My Points tab.</p>
    </form>`;
  }
  function readForm() {
    const f = document.getElementById("goal"); if (!f) return;
    const q = n => f.querySelector(`[name="${n}"]`);
    S.slots = S.slots.map((s, i) => {
      const sp = {}; f.querySelectorAll(`[name="s${i}sp"]:checked`).forEach(x => { sp[x.value] = 1; });
      if (sp.C && q(`s${i}cs`) && q(`s${i}cs`).checked) sp.C = 0.5; else if (sp.C && !q(`s${i}cs`)) sp.C = 0.5;
      return { sp: Object.keys(sp).length ? sp : s.sp, every: +q(`s${i}ev`).value, optional: q(`s${i}op`).checked };
    });
    S.conf = +q("conf").value; S.quality = +q("quality").value; S.rest = +q("rest").value; S.years = +q("years").value; S.budget = Math.max(0, +q("budget").value || 0);
    S.weapons = { archery: false, rifle: false, muzzleloader: false };
    f.querySelectorAll('[name="wpn"]:checked').forEach(x => { S.weapons[x.value] = true; });
    if (!S.weapons.archery && !S.weapons.rifle && !S.weapons.muzzleloader) S.weapons.rifle = true;
    S.states = [...f.querySelectorAll('[name="states"]:checked')].map(x => x.value); if (!S.states.length) S.states = ALL_ST.slice();
    S.always = [...f.querySelectorAll('[name="always"]:checked')].map(x => x.value).filter(x => S.states.includes(x));
    S.otc = q("otc").checked; S.priv = q("priv").checked;
  }

  // ---------- run ----------
  let RES = null, RES_KEY = "", BUSY = false;
  function ptsMap() {
    const out = {};
    for (const st of ALL_ST) for (const sp of ["E", "D", "P"]) { const v = myPts(st, sp, false); if (v) out[st + sp] = v; }
    for (const sp of ["E", "D"]) { const v = myPts("MT", sp, true); if (v) out["MT" + sp + "pref"] = v; }
    { const v = myPts("UT", "D", true); if (v) out.UTDpref = v; }
    return out;
  }
  function compute(cb) {
    const pts = ptsMap(), key = JSON.stringify([S, pts]);
    if (RES && RES_KEY === key) return cb();
    BUSY = true; paint();
    setTimeout(() => {
      try {
        if (!window.__creepSet) { const by = {}; for (const st in DRAW) by[st] = DRAW[st].hunts || []; Odds.setCreepPriors(Odds.creepPriors(by)); window.__creepSet = true; }
        RES = Planner.run({ DRAW, TROPHY: TROPHY && TROPHY.units, Odds, PRICES, OTC, pts, Y0: startYear() }, S);
        RES.pts = pts; RES_KEY = key;
      } catch (e) { RES = { error: String(e && e.stack || e) }; RES_KEY = ""; }
      BUSY = false; cb();
    }, 30);
  }

  // ---------- results ----------
  const KIND = {
    burn: ["Burn points", "var(--premier)", "Spends your points here on a top hunt."],
    draw: ["Draw", "var(--easy)", "A good chance at your current points."],
    second: ["2nd choice", "var(--easy)", "Point as 1st choice, this hunt as 2nd choice: drawing it doesn't cost your points."],
    lottery: ["Lottery", "var(--mid)", "Random draw, no points."],
    combo: ["Combo draw", "var(--mid)", "Montana general license draw (preference points)."],
    early: ["Uses points early", "var(--long)", "Needed to reach your confidence target; spends points you were building."]
  };
  function appHTML(a, y) {
    const c = a.c, h = c.h, k = KIND[a.kind] || KIND.draw, pts = (y.ptsBefore[a.g] || 0);
    const swing = a.swing ? "Long shot" : null;
    const inch = window.trophyInches && c.rated ? ` (${window.trophyInches(c.sp, c.q)})` : "";
    const lowDemand = (() => { const Y = h.years[Object.keys(h.years).sort().pop()] || {}; const n = (Y.NR || {}).apps; return n == null || n >= 10 ? "" : n === 0 ? " · no nonresident applicants last draw (low demand; odds are a rough guide)" : ` · only ${n} nonresident applicant${n === 1 ? "" : "s"} last draw`; })();
    return `<div class="app">
      <div class="ah"><span class="tag" style="color:${swing ? "var(--long)" : k[1]}" title="${esc(k[2])}">${swing || k[0]}</span>
        <b>${SN[a.st]} ${SPS[a.sp].toLowerCase()}</b><span class="odds">${P100(a.p)}</span></div>
      <div class="pm">${esc(h.label || h.id)} · ${window.bagLabel ? bagLabel(h) : ""}${a.optional ? " · bonus hunt" : ""}</div>
      ${a.combo ? `<div class="pm"><b>Montana:</b> ${c.general ? "" : `apply for the ${a.sp === "E" ? "Big Game (elk)" : "Deer"} Combo with this permit (the permit only counts if the combo draws). `}${a.combo.buy ? `Buy a preference point with the application: you'll draw the combo with ${a.combo.drawWith} point${a.combo.drawWith === 1 ? "" : "s"}` : a.combo.have >= 3 ? "You're at the 3-point maximum: no point to buy" : "Don't buy a point this time: with 0 points you're in the random 25% pool"} (combo odds ${P100(a.combo.p)}).</div>` : ""}
      <div class="pm">${a.kind === "burn" || a.kind === "early" ? `Uses ${pts} pt${pts === 1 ? "" : "s"} · ` : POINT_ST(a.st) && a.kind !== "second" ? `${pts} pts · ` : a.kind === "second" ? `Point ${pts}→${pts + 1} and hunt · ` : ""}Trophy ${c.rated ? c.q + "/5" + inch : "not rated"} · tag ~${money(a.cost)}${lowDemand}</div>
      <button type="button" class="maplink" data-st="${a.st}" data-hid="${esc(h.id)}">Show on map</button>
    </div>`;
  }
  const POINT_ST = st => ["CO", "WY", "UT", "AZ", "NV", "OR", "MT"].includes(st);
  const gName = g => { const st = g.slice(0, 2), sp = g[2]; return `${SN[st]} ${sp === "D" ? "deer" : SPS[sp].toLowerCase()}${g.endsWith("pref") ? " combo" : ""}`; };

  function resultsHTML() {
    if (BUSY) return `<p class="note" role="status">Building your plan: checking every draw hunt and simulating the draws…</p>`;
    if (!RES) return "";
    if (RES.error) return `<p class="warn">The planner hit an error: ${esc(RES.error.slice(0, 300))}</p>`;
    const R = RES, st = R.stats, n = R.path.length;
    const minF = Math.min(...st.map(s => s.filled)), maxF = Math.max(...st.map(s => s.filled));
    const tags = st.reduce((a, s) => a + s.tags, 0) / n, elk = st.reduce((a, s) => a + s.elk, 0) / n;
    const cost = R.path.reduce((a, y) => a + y.cost.expected, 0) / n, up = R.path.reduce((a, y) => a + y.cost.upfront, 0) / n;
    const req = S.slots.filter(s => !s.optional);
    let html = `<h2 id="plan-top">Your plan</h2>
      <p class="lede">Goal: ${esc(S.slots.map(slotText).join("; "))}. ${S.always.length ? `Always applying in ${S.always.map(s => SN[s]).join(" and ")}. ` : ""}Based on ${R.ncands.toLocaleString()} draw hunts that fit, your points, and ${n} years of draws simulated 300 times.</p>
      <div class="kpis">
        <div><b>${P100(minF)}${maxF - minF > 0.02 ? "–" + P100(maxF) : ""}</b><span>chance each year that your ${req.length} required hunt${req.length === 1 ? "" : "s"} come${req.length === 1 ? "s" : ""} through by draw</span></div>
        <div><b>${P100(R.every)}</b><span>chance every year of the plan works out by draw alone${S.otc ? " (OTC backups cover the rest)" : ""}</span></div>
        <div><b>${tags.toFixed(1)}</b><span>tags a year on average</span></div>
        <div><b>${P100(elk)}</b><span>chance of at least one elk tag in a year</span></div>
        <div><b>${R.q4PerPlan.toFixed(1)}</b><span>hunts in units rated 4+ for trophy over ${n} years</span></div>
        <div><b>${money(cost)}</b><span>expected cost a year (${money(up)} paid when applying)</span></div>
      </div>`;
    // coming up
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const next = (typeof DATES !== "undefined" ? DATES : []).filter(d => S.states.includes(d[1])).map(d => ({ d, dt: new Date(d[0] + "T12:00:00") }))
      .filter(x => x.dt >= today && (x.dt - today) / 864e5 <= 120).sort((a, b) => a.dt - b.dt).slice(0, 6);
    if (next.length) html += `<div class="callout"><h3>Coming up</h3><ol>${next.map(x => `<li><b>${x.dt.toLocaleDateString("en-US", { month: "short", day: "numeric" })} · ${SN[x.d[1]]}.</b> ${esc(x.d[2])}${x.d[3] ? " (date estimated)" : ""}</li>`).join("")}</ol></div>`;
    // year by year
    html += `<h2>Year by year</h2><p class="note">Each year lists every application to send. The plan below follows the most likely results; if a draw goes the other way, your points carry over and next year's plan shifts. The odds already account for that.</p><div id="years">`;
    R.path.forEach((y, i) => {
      const s = st[i];
      const over = S.budget && y.cost.expected > S.budget;
      const pts = y.points.map(a => `${gName(a.g)} <span class="ptn">${y.ptsBefore[a.g] || 0}→${(y.ptsBefore[a.g] || 0) + 1}</span>`).join(" · ");
      const need = new Set(S.slots.filter(sl => !sl.optional).flatMap(sl => Object.keys(sl.sp)));
      const otcList = y.otc.filter(o => need.has(o.sp)).sort((a, b) => (a.sp === "E" ? 0 : 1) - (b.sp === "E" ? 0 : 1) || b.odds - a.odds).slice(0, 3);
      const otc = otcList.length && s.filled < 0.995 ? `<p class="pm"><b>If draws fall short (${P100(1 - s.filled)} of the time):</b> ${otcList.map(o => esc(o.label)).join("; ")}.</p>` : "";
      html += `<div class="yr"><div class="y">${y.year}</div><div class="body">
        <div class="ystat"><span><b>${P100(s.filled)}</b> required hunts filled</span><span><b>${s.tags.toFixed(1)}</b> tags expected</span><span><b>${P100(s.elk)}</b> elk</span></div>
        ${y.apps.length ? y.apps.map(a => appHTML(a, y)).join("") : `<p class="note">No draw applications needed beyond points this year.</p>`}
        ${pts ? `<p class="pbank"><span class="tag" style="color:var(--mid)">Points only</span>${pts}</p>` : ""}
        ${otc}
        <p class="pcost${over ? " over" : ""}">Paid when applying ${money(y.cost.upfront)} · expected total ${money(y.cost.expected)} · if every tag draws ${money(y.cost.allDrawn)}${over ? ` · over your ${money(S.budget)} budget` : ""}</p>
      </div></div>`;
    });
    html += `</div>`;
    // rotation table
    const groups = [...new Set(R.path.flatMap(y => y.apps.map(a => a.g).concat(y.points.map(a => a.g))))].filter(g => POINT_ST(g.slice(0, 2))).sort();
    const cell = (y, g) => {
      const a = y.apps.find(x => x.g === g), pt = y.ptsBefore[g] || 0;
      if (a) return a.kind === "second" ? `<td class="rot hunt2" title="2nd-choice hunt, point kept">2nd<small>${pt}</small></td>` : `<td class="rot hunt" title="${esc(a.c.h.label || "")}">${a.kind === "burn" || a.kind === "early" ? "★" : "●"}<small>${pt}</small></td>`;
      return y.points.find(x => x.g === g) ? `<td class="rot" title="buy a point">+<small>${pt}</small></td>` : `<td class="rot">·</td>`;
    };
    const tgt = g => { const t = (R.path[R.path.length - 1].targets || {})[g] || (R.path[0].targets || {})[g]; return t ? `${esc(t.c.h.label || t.c.h.id).slice(0, 48)} · trophy ${t.c.rated ? t.c.q + "/5" : "–"}` : "–"; };
    html += `<h2>Point rotation</h2><p class="note">★ spends points on a top hunt · ● draw at current points · 2nd hunts as a 2nd choice and keeps building · + point only. Small numbers are points going in.</p>
      <div class="tbl"><table class="rott"><thead><tr><th>State</th>${R.path.map(y => `<th>${String(y.year).slice(2)}</th>`).join("")}<th>Building toward</th></tr></thead><tbody>
      ${groups.map(g => `<tr><td>${gName(g)}</td>${R.path.map(y => cell(y, g)).join("")}<td class="note">${tgt(g)}</td></tr>`).join("")}
      </tbody></table></div>`;
    html += `<details class="dt"><summary>How the planner decides</summary><div class="note">
      <p>For every point state and species it finds the best hunt your points can reach within your strategy's horizon and the year your odds hit about 70%: that's the "building toward" hunt, and it's not spent on filler before then. Each year it starts with the hunts whose time has come (staggered so they don't all land at once) plus your always-apply lottery states, then adds the applications that most raise the chance of getting every required hunt, until it reaches your confidence target. That can mean more applications than hunts you need. Everything else buys a point.</p>
      <p>Draw odds come from each state's results replayed with you in them (with point creep); the year-by-year chances come from simulating all the draws 300 times. Only tags legal for a mature buck or bull count. Trophy ratings are by unit; a rifle either-sex tag counts a point lower because it's mostly a cow or doe hunt.</p>
      <p>Prices are 2026 nonresident fees and will change. Check each state's own numbers before applying.</p></div></details>`;
    return html;
  }

  function paint() {
    const root = document.getElementById("plan-root"); if (!root) return;
    root.innerHTML = formHTML() + `<div id="plan-out">${resultsHTML()}</div>`;
    wire();
  }
  function render() {
    const root = document.getElementById("plan-root"); if (!root) return;
    if (!ALL_ST.some(st => DRAW[st])) { root.innerHTML = formHTML() + `<p class="note">Loading draw data…</p>`; wire(); return; }
    compute(paint);
  }
  function wire() {
    const root = document.getElementById("plan-root"), f = document.getElementById("goal");
    if (!root.__mapWired) { root.__mapWired = true; root.addEventListener("click", e => { const b = e.target.closest(".maplink"); if (!b) return;
      if (b.dataset.hid && window.showHuntOnMap) window.showHuntOnMap(b.dataset.st, b.dataset.hid); }); }
    if (!f) return;
    f.addEventListener("submit", e => { e.preventDefault(); readForm(); save(); RES_KEY = ""; compute(() => { paint(); const t = document.getElementById("plan-top"); if (t) t.scrollIntoView({ behavior: "smooth", block: "start" }); }); });
    f.addEventListener("change", e => { if (/^s\d+sp$/.test(e.target.name)) { readForm(); paint(); } });   // show/hide the Coues option
    document.getElementById("slot-add").onclick = () => { readForm(); S.slots.push({ sp: { D: 1 }, every: 1, optional: true }); paint(); };
    f.querySelectorAll("[data-del]").forEach(b => b.onclick = () => { readForm(); S.slots.splice(+b.dataset.del, 1); paint(); });
    document.getElementById("goal-reset").onclick = () => { S = clone(DEF); save(); RES_KEY = ""; render(); };
  }
  window.renderPlan = render;
})();
