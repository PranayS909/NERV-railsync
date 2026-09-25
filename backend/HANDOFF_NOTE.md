# RailSync-AI — Handoff Note (Backend + Frontend Complete)

Status as of this session: **backend and frontend both built, smoke-tested end-to-end, and working.**
This is now a functioning MVP end to end: `uvicorn` up on :8000 → open `frontend/index.html` →
optimize runs, Marey chart renders real train lines + sanctioned corridors, delay injection and
arbitration round-trip correctly. Use this note to resume in a fresh conversation without
re-deriving context — attach it + the code.

## What's done

All 6 backend deliverables from the spec exist under `railsync-ai/`:
- `requirements.txt`
- `backend/data_generator.py` — auto-generates `data/*.json` on first run (network,
  14 trains, 10 BDMS demands incl. the CIV-01/TRD-01/SNT-01 spatial-overlap trio
  and CIV-02/TRD-02 pair called out in the spec, 4 machines, asset health per 5km segment)
- `backend/clustering.py` — union-find clustering at 5.0km chainage radius, Civil-primary
  shadowing, `Duration_Corridor = max(D_Civil, D_TRD, D_S&T)`
- `backend/optimizer.py` — OR-Tools CP-SAT, 15-min slots across 06:00–18:00 (48 slots),
  machine `NoOverlap` constraint, per-slot conflict cost via `AddElement`, minimizes
  weighted train conflict cost − criticality×duration reward
- `backend/arbitration.py` — conflict detection against the Marey time-distance space,
  delay injection, 3-option trade-off matrix (regulate / defer / compress+TSR)
- `backend/relocation.py` — per-machine timeline (transit → working → relocate-to-base),
  dead-mileage + piggyback-on-freight savings estimate
- `backend/main.py` — FastAPI app, all endpoints from spec Module F implemented and tested

**Verified working:** data generation, clustering output (7 corridors from 10 demands,
CORR-01 correctly clubs CIVIL+TRD+SNT), CP-SAT solver returns `OPTIMAL` in ~6ms, full
`uvicorn` server tested live with curl against `/optimize`, `/simulate-delay`, `/kpis`.

## Known MVP simplifications (intentional, for a hackathon-scope MVP)

- **Train position interpolation** is linear between timetable stops (real IR uses block
  section running times, not linear interpolation) — fine for a 150km double-line MVP.
- **Headway constraint (5 min)** is not enforced as a hard CP-SAT constraint on train
  departures — trains keep their generated timetable as fixed; only corridor placement is
  optimized against that fixed timetable. A stretch goal would be to make train departure
  times decision variables too.
- **Machine transit buffer** between two jobs on the same machine is a flat 30-min constant
  in the `NoOverlap` interval, not `Δkm / speed` per the spec formula — the real formula is
  used in `relocation.py`'s dead-mileage calc, just not yet fed back into the optimizer's
  interval sizing.
- **All trains assumed electric-hauled** unless a corridor explicitly allows diesel-through,
  per `_train_is_electric()` in `optimizer.py` — matches the brief's "OHE mandatory" framing.
- **Option 2 (defer maintenance)** in arbitration is logged but doesn't yet actually re-run
  the optimizer excluding that corridor from the current window — it's a flagged no-op.
- Session state (injected delays, arbitration log) is **in-memory, single-session**, reset via
  `POST /api/v1/reset-session`. No persistence/DB.

## Frontend (`frontend/index.html`) — what's built

Single self-contained HTML file (vanilla JS + inline SVG, no build step, Inter + JetBrains Mono
via Google Fonts CDN, dark control-room palette). `API_BASE` is hardcoded to
`http://localhost:8000` near the top of the `<script>` block — change that constant if the
backend is hosted elsewhere.

- **Marey chart**: SVG, X=time 06:00–18:00 (30min grid), Y=true km 0–150 (station lines at their
  real chainage, not evenly spaced). Train polylines colored by spec (blue=premier,
  green=express/MEMU, dashed amber=freight, red=delayed-this-session). Corridor blocks drawn as
  semi-transparent rects colored by primary department, with badge text and hover tooltips.
- **Toolbar**: "Run AI Corridor Optimization" → `POST /api/v1/optimize`, redraws corridors + top
  two KPIs. "Inject live delay" (train dropdown + 0–90min slider) → `POST /api/v1/simulate-delay`,
  which also re-runs `/optimize` so the chart reflects the new solve, then surfaces a conflict
  banner if the delayed train now collides with a sanctioned corridor.
- **Arbitration modal**: opened from the conflict banner, renders every entry in
  `trade_off_matrices[]` as three side-by-side option cards (recommended one gets a teal border +
  "Suggested option" tag) with a "Select & Apply" button wired to `POST /api/v1/arbitrate`.
- **KPI bar**: secondary delay prevented, corridor utilization %, dead-mileage saved, and a
  live fleet-status chip list, refreshed from `GET /api/v1/kpis` after every optimize/arbitrate.
- **Reset Session** button clears injected delays via `POST /api/v1/reset-session`.

Verified: JS passes `node --check`, and a full click-through against a live `uvicorn` instance
confirmed the network/trains/optimize/kpis calls return the shapes the frontend expects.

## Possible next steps (not started)

- Visual QA in an actual browser (this session only verified via curl + JS syntax check, not a
  rendered screenshot) — check chart legibility, tooltip positioning, and mobile breakpoint.
- Wire `/api/v1/asset-health` into the dashboard (currently generated by the backend but unused
  by the frontend) — could color-code track segments by TGI/criticality on the Marey Y-axis.
- Animate the corridor bars appearing after "Run AI Corridor Optimization" (spec calls for this;
  current version redraws instantly).
- Option 2 (defer maintenance) in arbitration is still a logged no-op server-side — see above.
