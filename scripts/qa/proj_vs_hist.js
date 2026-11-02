// For every current NR hunt and point level 0..max: projected vs latest-year actual outcome at that level.
const fs=require("fs"),Odds=require("../../odds.js");
const SYS={CO:"pref",WY:"pref75",UT:"bonus50",AZ:"az",NM:"random",NV:"bonus_sq",OR:"pref75",ID:"random",MT:"bonus_sq"};
const out={};
for(const st in SYS){const d=JSON.parse(fs.readFileSync(`data/draw/${st}.json`));const cur={};
  for(const h of d.hunts){const y=Object.keys(h.years).sort().pop();if(!cur[h.species]||y>cur[h.species])cur[h.species]=y}
  let n=0,big=0,ex=[],abs=0;
  for(const h of d.hunts){h._st=st;if(!h.years[cur[h.species]])continue;const sys=st==="MT"&&h.kind==="general"?"pref75":SYS[st];
    const y=Odds.latestYear(h,"NR");if(!y)continue;const b=h.years[y].NR;if(!b.by_pts)continue;
    for(const [p,a,dd] of b.by_pts){if(a<5)continue;const hist=Odds.historical(sys,b,p);const s=Odds.summarize(sys,h,"NR",p);if(!s||hist==null||s.projected==null)continue;
      n++;const dlt=s.projected-hist;abs+=Math.abs(dlt);if(Math.abs(dlt)>0.3){big++;if(ex.length<6)ex.push(`${h.id}@${p}: proj ${s.projected.toFixed(2)} vs ${y} actual ${hist.toFixed(2)} (${a} apps)`)}}}
  out[st]={levels:n,meanAbsDiff:(abs/Math.max(1,n)).toFixed(3),over30pts:big,ex};}
console.log(JSON.stringify(out,null,1));
