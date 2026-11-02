// Planner's view of each hunt for QA: node scripts/qa/candidates.js [minTrophy] > out.tsv
const fs=require("fs"),Odds=require("../../odds.js");
const T=JSON.parse(fs.readFileSync("data/trophy.json")).units;
const SYS={CO:"pref",WY:"pref75",UT:"bonus50",AZ:"az",NM:"random",NV:"bonus_sq",OR:"pref75",ID:"random",MT:"bonus_sq"};
const minT=+(process.argv[2]||3);
const rows=[["st","id","sp","sex","bag","weapon","label","units","trophy","year","NR_tags","NR_apps","NR_drawn","NR_min","T_tags","odds0","odds_hist0"].join("\t")];
for(const st in SYS){const d=JSON.parse(fs.readFileSync(`data/draw/${st}.json`));
  for(const h of d.hunts){const sys=st==="MT"&&h.kind==="general"?"pref75":SYS[st];
    let tr=null;for(const u of h.units||[]){const t=((T[st]||{})[h.species]||{})[String(u)];if(t&&(tr==null||t.s>tr))tr=t.s}
    if((tr||0)<minT)continue;
    const y=Odds.latestYear(h,"NR");if(!y)continue;const b=h.years[y].NR,t=h.years[y].T||{};
    const s=Odds.summarize(sys,h,"NR",0);const o=s?(s.projected!=null?s.projected:(s.historical.length?s.historical[s.historical.length-1][1]:s.overall)):null;
    if(o==null||o<0.2)continue;
    rows.push([st,h.id,h.species,h.sex||"",h.bag||"",h.weapon,(h.label||"").slice(0,90),(h.units||[]).slice(0,5).join(","),tr,y,b.tags??"",b.apps??"",b.drawn??"",b.min_pts??"",t.tags??"",o.toFixed(2),s.historical.length?s.historical[s.historical.length-1][1].toFixed(2):""].join("\t"))}}
console.log(rows.join("\n"));
