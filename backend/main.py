"""
backend/main.py

RailSync-AI REST API (FastAPI).
Run with:  uvicorn backend.main:app --reload --port 8000
"""

# ---------------------------------------------------------------------------
# Path bootstrap — ensures flat imports (from data_generator import ...) work
# whether this module is loaded as a package (uvicorn backend.main:app from
# the project root) or run directly (python main.py from inside backend/).
# ---------------------------------------------------------------------------
import sys
import os
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
# ---------------------------------------------------------------------------

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_generator import load_network, load_trains, load_demands, load_machinery, load_asset_health
from clustering import cluster_demands, utilization_rate
from optimizer import optimize_schedule
from arbitration import inject_delay, detect_conflicts, trade_off_matrix, apply_arbitration, reset_session, get_session_state
from relocation import plan_relocations

app = FastAPI(
    title="RailSync-AI",
    description="AI-Powered Automatic Block Planning System for Indian Railways",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# cache the last optimizer run so /simulate-delay and /arbitrate can reference it
_LAST_SCHEDULE = {"result": None}


class SimulateDelayRequest(BaseModel):
    train_no: str
    delay_minutes: int


class ArbitrateRequest(BaseModel):
    train_no: str
    corridor_id: str
    option: int


@app.get("/")
def root():
    return {
        "service": "RailSync-AI",
        "status": "running",
        "endpoints": [
            "/api/v1/network", "/api/v1/demands", "/api/v1/machinery",
            "POST /api/v1/optimize", "POST /api/v1/simulate-delay", "POST /api/v1/arbitrate",
        ],
    }


@app.get("/api/v1/network")
def get_network():
    return load_network()


@app.get("/api/v1/demands")
def get_demands():
    corridors = cluster_demands(load_demands())
    return {
        "raw_demands": load_demands(),
        "clustered_corridors": corridors,
        "corridor_utilization_rate_pct": utilization_rate(corridors),
    }


@app.get("/api/v1/machinery")
def get_machinery():
    relocation_plan = plan_relocations()
    return {
        "fleet": load_machinery(),
        "relocation_plan": relocation_plan,
    }


@app.get("/api/v1/asset-health")
def get_asset_health():
    return load_asset_health()


@app.get("/api/v1/trains")
def get_trains():
    return load_trains()


@app.post("/api/v1/optimize")
def post_optimize():
    state = get_session_state()
    result = optimize_schedule(
        injected_delays=state["injected_delays"],
        excluded_corridor_ids=state["excluded_corridor_ids"],
    )
    _LAST_SCHEDULE["result"] = result
    return result


@app.post("/api/v1/simulate-delay")
def post_simulate_delay(req: SimulateDelayRequest):
    known_trains = {t["train_no"] for t in load_trains()}
    if req.train_no not in known_trains:
        raise HTTPException(status_code=404, detail=f"Unknown train_no '{req.train_no}'")

    conflict_report = inject_delay(req.train_no, req.delay_minutes)
    _LAST_SCHEDULE["result"] = conflict_report["schedule"]

    # attach a full trade-off matrix for every detected conflict involving this train
    matrices = []
    for conflict in conflict_report["conflicts"]:
        if conflict["train_no"] == req.train_no:
            matrices.append(trade_off_matrix(req.train_no, conflict["corridor_id"], conflict_report["schedule"]))

    return {
        "train_no": req.train_no,
        "injected_delay_minutes": req.delay_minutes,
        "total_injected_delay_minutes": conflict_report["injected_delays"].get(req.train_no, 0),
        "conflicts_detected": conflict_report["conflicts"],
        "trade_off_matrices": matrices,
    }


@app.post("/api/v1/arbitrate")
def post_arbitrate(req: ArbitrateRequest):
    if req.option not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="option must be 1, 2, or 3")
    result = apply_arbitration(req.train_no, req.corridor_id, req.option)
    _LAST_SCHEDULE["result"] = result["updated_conflicts"]["schedule"]
    return result


@app.post("/api/v1/reset-session")
def post_reset_session():
    reset_session()
    return {"status": "session reset"}


@app.get("/api/v1/kpis")
def get_kpis():
    schedule = _LAST_SCHEDULE["result"] or optimize_schedule()
    relocation_plan = plan_relocations()
    return {
        "corridor_kpis": schedule.get("kpis", {}),
        "dead_mileage_saved_km": relocation_plan["total_dead_mileage_saved_km"],
        "fleet_status": relocation_plan["fleet_status"],
    }