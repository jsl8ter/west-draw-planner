// What the planner can pick: current, mature-male-legal, not restricted/private, NR odds at given points.
// node scripts/qa/planner_view.js [pts=0] [minOdds=0.2] [minTrophy=3]
const fs=require("fs"),Odds=require("../../odds.js");
const T=JSON.parse(fs.readFileSync("data/trophy.json")).units;
const SYS={CO:"pref",WY:"pref75",UT:"bonus50",AZ:"az",NM:"random",NV:"bonus_sq",OR:"pref75",ID:"random",MT:"bonus_sq"};
const RESTRICTED=/\bCHAMP\b|\byouth\b|\bjunior\b|disab|mobility|\bMI\b|landowner|\bLOA\b|military|veteran|camp navajo|outfitter|\bguided\b|\bF-IM\b|apprentice|\bheritage\b|\bdepredation\b/i;
const PRIVATE=/private[- ]land|\bprivate\b|valid on private|\bcwmu\b|ranching for wildlife|\bRFW\b|landowner/i;
const [pts,minO,minT]=[+(process.argv[2]||0),+(process.argv[3]||0.2),+(process.argv[4]||3)];
const all={};for(const st in SYS)all[st]=JSON.parse(fs.readFileSync(`data/draw/${st}.json`)).hunts;
Odds.setCreepPriors(Odds.creepPriors(all));
for(const st in SYS){const hs=all[st];const cur={};for(const h of hs){const y=Object.keys(h.years).sort().pop();if(!cur[h.species]||y>cur[h.species])cur[h.species]=y}
  const rows=[];
  for(const h of hs){h._st=st;if(!h.years[cur[h.species]])continue;if(!["antlered","either"].includes(h.bag))continue;
    const txt=(h.label||"")+" "+(h.bag_text||"");if(RESTRICTED.test(txt)||PRIVATE.test(txt)||/^[DEA]-[MFE]-\d{3}-(P\d|W\d|J|K)/.test(h.id))continue;
    let tr=null;for(const u of h.units||[]){const t=((T[st]||{})[h.species]||{})[String(u)];if(t&&(tr==null||t.s>tr))tr=t.s}
    if((tr||0)<minT)continue;const sys=st==="MT"&&h.kind==="general"?"pref75":SYS[st];
    const s=Odds.summarize(sys,h,"NR",pts);if(!s||s.projected==null||s.projected<minO)continue;
    const y=Odds.latestYear(h,"NR"),b=h.years[y].NR;if(y!==Object.keys(h.years).sort().pop())continue;
    rows.push(`  ${h.id.padEnd(16)} ${h.species} tr${tr} ${(s.projected*100).toFixed(0).padStart(3)}%  NR ${y}: ${b.drawn??"?"}/${b.apps} drew, need ${Odds.ptsNeeded(b)??"-"} | ${h.bag_text||h.bag} | ${(h.label||"").slice(0,60)}`)}
  console.log(`${st}: ${rows.length}`);rows.slice(0,+(process.env.N||6)).forEach(r=>console.log(r))}
