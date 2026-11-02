// Backtest: predict each hunt's latest NR draw from the years before it; compare with what happened.
// node scripts/qa/backtest.js [path/to/odds.js]
const fs=require("fs"),path=require("path");
const Odds=require(path.resolve(process.argv[2]||"odds.js"));
const SYS={CO:"pref",WY:"pref75",UT:"bonus50",AZ:"az",NV:"bonus_sq",OR:"pref75",MT:"bonus_sq",NM:"random",ID:"random"};
const tot={n:0,err:0,bias:0};
// creep priors from years before each state's latest year (no peeking)
const ALL={};for(const st in SYS){ALL[st]=JSON.parse(fs.readFileSync(`data/draw/${st}.json`)).hunts;}
if(Odds.setCreepPriors&&!process.env.NOPRIOR){const pri={};for(const st in SYS){const ly=ALL[st].flatMap(h=>Object.keys(h.years)).sort().pop();Object.assign(pri,Odds.creepPriors({[st]:ALL[st]},ly))}Odds.setCreepPriors(pri)}
for(const st in SYS){const d=JSON.parse(fs.readFileSync(`data/draw/${st}.json`));let n=0,err=0,bias=0,over=0;
  for(const h0 of d.hunts){const ys=Object.keys(h0.years).filter(y=>h0.years[y].NR).sort();if(ys.length<2)continue;
    const last=ys.pop(),b=h0.years[last].NR;const sys=st==="MT"&&h0.kind==="general"?"pref75":SYS[st];
    const h={...h0,_st:st,years:{}};for(const y of ys)h.years[y]=h0.years[y];
    const levels=b.by_pts&&b.by_pts.length?b.by_pts.filter(r=>r[1]>=5).map(r=>r[0]):(sys==="random"&&b.apps>=5?[0]:[]);
    for(const p of levels){const act=Odds.historical(sys,b,p);const s=Odds.summarize(sys,h,"NR",p);if(act==null||!s)continue;
      const pr=s.projected!=null?s.projected:(s.historical.length?s.historical[s.historical.length-1][1]:null);if(pr==null)continue;
      n++;err+=Math.abs(pr-act);bias+=pr-act;if(pr-act>0.3)over++}}
  console.log(st.padEnd(3),"levels",String(n).padStart(5),"mean abs err",(err/n).toFixed(3),"bias",(bias/n>=0?"+":"")+(bias/n).toFixed(3),"overestimates >30pts",over);
  tot.n+=n;tot.err+=err;tot.bias+=bias}
console.log("ALL levels",tot.n,"mean abs err",(tot.err/tot.n).toFixed(3),"bias",(tot.bias/tot.n).toFixed(3));
