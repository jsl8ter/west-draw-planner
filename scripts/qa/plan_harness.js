// node scripts/qa/plan_harness.js  -> runs the planner engine on real data with the user's stated goal
const fs=require("fs"),Odds=require("../../odds.js"),Planner=require("../../planner-core.js");
const src=fs.readFileSync("plan.js","utf8");
const PRICES=eval("("+src.match(/const PRICES = (\{[\s\S]*?\n  \});/)[1]+")");
const OTC=eval(src.match(/const OTC = (\[[\s\S]*?\n  \]);/)[1]);
const DRAW={};for(const st of ["CO","WY","UT","AZ","NM","NV","OR","ID","MT"])DRAW[st]=JSON.parse(fs.readFileSync(`data/draw/${st}.json`));
const TROPHY=JSON.parse(fs.readFileSync("data/trophy.json")).units;
const by={};for(const st in DRAW){for(const h of DRAW[st].hunts)h._st=st;by[st]=DRAW[st].hunts}Odds.setCreepPriors(Odds.creepPriors(by));
const G={slots:[{label:"Elk",sp:{E:1},every:1},{label:"Elk or mule deer",sp:{E:1,D:1,C:0.5},every:1},{label:"Pronghorn",sp:{P:1},every:3,optional:true}],
  weapons:{archery:true,rifle:true,muzzleloader:false},conf:0.9,quality:0.5,states:["CO","WY","UT","AZ","NM","NV","OR","ID","MT"],always:["NM"],years:6,priv:false,otc:true};
const pts=JSON.parse(process.env.PTS||"{}");
const R=Planner.run({DRAW,TROPHY,Odds,PRICES,OTC,pts,Y0:2027},G);
console.log("cands",R.ncands,"ms",R.ms,"| all years goal met",(R.every*100).toFixed(0)+"%","| 4+ trophy hunts per plan",R.q4PerPlan.toFixed(2));
for(const [i,y] of R.path.entries()){const s=R.stats[i];
 console.log(`\n${y.year}: P(slots by draw) plan ${(y.pf*100).toFixed(0)}% sim ${(s.filled*100).toFixed(0)}% | tags ${s.tags.toFixed(2)} | elk ${(s.elk*100).toFixed(0)}% | 4+ ${(s.q4*100).toFixed(0)}% | cost upfront $${Math.round(y.cost.upfront)} expected $${Math.round(y.cost.expected)}`);
 for(const a of y.apps)console.log(`   ${a.kind.padEnd(7)} ${a.st} ${a.sp} ${(a.p*100).toFixed(0).padStart(3)}% q${a.q} ${a.c.h.id} ${(a.c.h.label||"").slice(0,55)} [${a.g}:${y.ptsBefore[a.g]||0}pts]`);
 console.log("   points:",y.points.map(a=>a.g+"("+(y.ptsBefore[a.g]||0)+(a.target?"→"+a.target.c.h.id+" in "+a.target.t+"y":"")+")").join(" "));}
