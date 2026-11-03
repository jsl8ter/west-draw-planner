# State draw rules used by the planner (nonresident, deer/elk/pronghorn) — verified Nov 2026

Each rule below is enforced in `odds.js` (draw math) or `planner-core.js` (RULES table / planning). Sources are official agency pages or administrative code.

| State | Draw math | Points | Waiting periods / limits | Source |
|---|---|---|---|---|
| CO | 100% preference (1st choice). Hybrid: hunts that took 10+ resident pts & 5+ licenses give up to 20% randomly to 5+ pt holders. **2028+:** 50/50 preference / bonus draw (bonus weighting assumed pts+1), hybrid ends, NR cap 25%. | Point when 1st choice doesn't draw (2nd-choice draw keeps points). Points void after 10 yrs inactive. 2028+: $30 NR point fee. | Qualifying license before applying. | 2 CCR 406-2-206; CPW 2026 brochure; CPW draw changes (Feb 2025) |
| WY | 75% preference, 25% random among everyone not drawn (1st choices); 2nd/3rd choices random only. | **No point for losing** — buy Jul 1–Oct 31 (counts next year). Forfeited after 2 yrs without buying. Reset only when 1st choice draws. | Special/regular one per species. | WGFD Ch. 44; wgfd.wyo.gov |
| UT | Limited entry: 50% to top bonus pts, 50% random weighted pts+1. General buck deer: strict preference (separate points), 20% youth. | Reset on drawing. | **Wait after LE draw: buck deer 5 yrs, bull elk 5, buck pronghorn 2.** Only one LE species can be drawn per year. | R657-62; DWR guidebook |
| AZ | Bonus pass up to 20% per hunt (1st/2nd choices), then random weighted by pts; NR cap 10% per hunt (≤ half in bonus pass). | Reset when any choice draws. Lost after 5 yrs not applying. Loyalty + hunter-ed points are permanent. | License required to apply. | R12-4-107, R12-4-114 |
| NM | Pure random; NR 6% unguided pool (outfitter 10% excluded). Choices 1→2→3 worked per application (planner uses 3 choices, discounted). | None. | Full fee up front, refunded if unsuccessful. | NMDGF Rules & Info; 19.31.3 NMAC |
| NV | Weighted random (pts² + 1). | Point for any unsuccessful app; reset on any tag; lost after 2 yrs not applying. | **Bull elk: 7 seasons wait; buck antelope: 3 seasons.** Deer: none. | NAC 502; eregulations.com/nevada |
| OR | 75% preference, 25% random among all 1st-choice applicants. NR cap 5% deer/elk, 3% pronghorn. | Point when 1st choice fails; reset when 1st choice draws (even if tag not bought). No expiry. | None. | OAR 635-060-0023/0030 |
| ID | Random; NR cap 10%; 2nd choice and second drawing exist. | None. | **Drawn antlered-only deer/elk or any pronghorn → no first-drawing application for that species next year.** NR general deer/elk tags are a December draw (not OTC). | IDAPA 13.01.08.257–258 |
| MT | Combos: 75% preference, 25% random only to 0-pt applicants; max 3 pts; point bought with the application counts that year. Permits: weighted random (pts² + 1), 10% NR cap; NR elk/deer permit needs the combo. | Permit bonus points count only in a year you buy one ($20); reset when 1st choice draws (in a bought year). | None for deer/elk/antelope. | fwp.mt.gov bonus points; 2026 DEA regulations p.14–17 |

Not modeled (noted): Utah youth reservation details, Oregon Premium (L/M/N) random series, Idaho second drawing, Arizona 3rd–5th choices, Wyoming 2nd/3rd random choices, Colorado secondary draw.
