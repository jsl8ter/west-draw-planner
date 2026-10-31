# Draw-statistics parsers

Each state gets `scripts/draw/parse_<st>.py` (lowercase) exposing `parse() -> dict` and an optional
module-level `LOG = []` list of strings (written to `data/draw/<ST>.log.txt`). `parse_all.py` writes the
result to `data/draw/<ST>.json`. Parsers run on GitHub Actions (open internet, Python 3.12,
`pdfplumber`, `openpyxl`, `xlrd`, `requests` installed). Download report files inside `parse()`.

## Output format

```json
{
  "state": "UT",
  "system": "pref | pref75 | bonus | bonus_sq | bonus50 | az | random",
  "point_label": "bonus points",            // what the state calls them
  "sources": [{"year": 2026, "species": "E", "url": "...", "title": "..."}],
  "hunts": [
    {
      "id": "EB1001",                       // state's hunt code
      "species": "E",                       // E elk, D mule deer, C Coues deer, P pronghorn
      "units": ["Beaver, East"],            // unit numbers/names exactly as the state writes them
      "label": "Beaver, East - Any legal weapon bull",
      "weapon": "any|rifle|archery|muzzleloader|other",
      "sex": "male|female|either",
      "kind": "limited|general|special|random|other",
      "years": {
        "2026": {
          "NR": {"tags": 5, "apps": 812, "drawn": 5, "min_pts": 20,
                 "by_pts": [[20, 3, 3], [19, 40, 2], [0, 300, 0]]},
          "R":  {"tags": 40, "apps": 5120, "drawn": 40, "min_pts": 18, "by_pts": [[...]]},
          "T":  {"tags": 45, "apps": 5932, "drawn": 45}
        }
      }
    }
  ]
}
```

Rules:
- `apps` = first-choice applicants for that hunt (state that in LOG if the state counts differently).
- `by_pts` rows are `[points, applicants, drawn]` at that point level, first choice, sorted high to low.
  Omit when the state doesn't publish it.
- `min_pts` = lowest point level that drew in the point-based pass (preference states). Omit for pure random states.
- `tags` = licenses/permits available to that residency in the draw. If only a total quota is published,
  put it in `T.tags` and leave NR/R tags out.
- Any field the source does not have is omitted, never guessed. Numbers must be integers.
- Species codes only E, D, C, P. Skip other species, youth-only, landowner, and auction/raffle hunts.
- Years: at least the last 3 available, up to 5.
- `LOG`: append one line per source file parsed (url, rows parsed, hunts found) and every row you
  could not parse (first 50), so failures are visible.

## Running

- Probe a file's layout: dispatch the workflow with `step=probe states=ST urls="<url> <url>"`.
  Output lands in `data/draw/probe/ST/NN.txt` (pull after the run).
- Run a parser: `step=parse states=ST`. Output: `data/draw/ST.json` and `data/draw/ST.log.txt`.
- Dispatch: `gh api -X POST repos/jsl8ter/west-draw-planner/actions/workflows/draw.yml/dispatches -f ref=main -f "inputs[step]=parse" -f "inputs[states]=UT"`
- Find the run: `gh api repos/jsl8ter/west-draw-planner/actions/runs --jq '[.workflow_runs[]|select(.name=="Draw statistics")][0:5][]|{id,status,conclusion,display_title,created_at}'`
- Logs of a failed run: `gh api repos/jsl8ter/west-draw-planner/actions/runs/<id>/jobs --jq '.jobs[0].id'` then
  `gh api repos/jsl8ter/west-draw-planner/actions/jobs/<job_id>/logs`.
- Always `git pull --rebase origin main` before committing and before reading outputs; other parsers
  push to the same repo concurrently. Commit only your own `scripts/draw/parse_<st>.py` (and probe lists).
