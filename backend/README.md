# RailSync-AI — Backend (MVP)

AI-Powered Automatic Block Planning System for Indian Railways.
This is the **backend** portion of the RailSync-AI MVP: synthetic data
generation, corridor clustering/shadowing, a CP-SAT block scheduler,
conflict arbitration, and asset relocation planning, exposed via FastAPI.

Route modeled: **Ghaziabad Jn (GZB) → Aligarh Jn (ALJN)**, 150km double-electrified
BG trunk, 13 stations, 14 trains (3 premier / 5 mail-express-MEMU / 6 freight),
10 BDMS demands, 4 heavy track machines.

## 1. Setup

```bash
cd railsync-ai
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The synthetic dataset auto-generates into `data/*.json` on first run — no manual
seeding step required. API docs (Swagger UI) at: `http://localhost:8000/docs`

## 3. Endpoints

| Method | Path                          | Purpose                                                        |
|--------|-------------------------------|------------------------------------------------------------------|
| GET    | `/api/v1/network`             | Stations, km posts, track layout                                |
| GET    | `/api/v1/trains`               | Full train timetable (14 trains)                                 |
| GET    | `/api/v1/demands`              | Raw BDMS demands + clustered corridors + utilization rate         |
| GET    | `/api/v1/machinery`            | Machine fleet + relocation/dead-mileage plan                      |
| GET    | `/api/v1/asset-health`         | TGI/OMS/criticality per 5km segment                                |
| POST   | `/api/v1/optimize`             | Runs the CP-SAT solver, returns sanctioned schedule + KPIs         |
| POST   | `/api/v1/simulate-delay`       | `{"train_no": "12424", "delay_minutes": 45}` → conflicts + trade-off matrices |
| POST   | `/api/v1/arbitrate`            | `{"train_no": "...", "corridor_id": "CORR-01", "option": 1|2|3}` → applies choice |
| POST   | `/api/v1/reset-session`        | Clears injected delays / arbitration log                          |
| GET    | `/api/v1/kpis`                 | Rolled-up dashboard KPIs                                          |

## 4. Quick smoke test

```bash
curl -X POST http://localhost:8000/api/v1/optimize | python3 -m json.tool
curl -X POST http://localhost:8000/api/v1/simulate-delay \
  -H "Content-Type: application/json" \
  -d '{"train_no": "12424", "delay_minutes": 45}'
```

## 5. Module map

- `backend/data_generator.py` — synthetic dataset (network, trains, BDMS demands, machinery, asset health)
- `backend/clustering.py` — 5km chainage clustering + Civil-primary corridor shadowing
- `backend/optimizer.py` — OR-Tools CP-SAT solver, 15-min slots over 06:00–18:00
- `backend/arbitration.py` — Marey-chart conflict detection, delay injection, 3-option matrix
- `backend/relocation.py` — post-block machine relocation & dead-mileage estimate
- `backend/main.py` — FastAPI app wiring it all together
- `frontend/index.html` — self-contained dashboard: Marey chart, optimize/delay controls, arbitration modal, KPI bar

## 6. Running the frontend

The backend must be running on `http://localhost:8000` first (CORS is already open).
Then just open the file directly:

```bash
open frontend/index.html        # macOS
xdg-open frontend/index.html    # Linux
# or: python3 -m http.server 5500 --directory frontend, then visit localhost:5500
```

It calls `POST /api/v1/optimize` on load, lets you inject a delay on any of the 14 trains
and pulls the 3-option trade-off matrix straight into the arbitration modal.

See `HANDOFF_NOTE.md` for what's simplified in this MVP and current project status.
