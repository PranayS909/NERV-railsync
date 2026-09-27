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
            "/api/v1/ingest/bdms", "/api/v1/ingest/tms", "/api/v1/ingest/fois",
            "/api/v1/ingest/scada", "/api/v1/ingest/crew", "/api/v1/ingest/asset-health",
            "POST /api/v1/ingest/refresh-all", "/api/v1/ingest/status"
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


def _detect_raw_conflicts(train_no: str, delay_minutes: int, schedule_result: dict) -> list:
    """
    Check the *current* schedule for corridors that the given delayed train
    would collide with — BEFORE the optimizer re-routes them.

    Returns a list of corridor_id strings that conflict with the delayed train.
    This preserves the "problem state" so trade-off matrices can be built even
    when the optimizer would silently fix the conflict in its next run.
    """
    from optimizer import _train_time_at_km, _min_to_hhmm
    trains = {t["train_no"]: t for t in load_trains()}
    train = trains.get(train_no)
    if not train:
        return []

    conflicting_ids = []
    for corridor in schedule_result.get("corridors", []):
        c_start_min = int(corridor["sanctioned_start"].split(":")[0]) * 60 + \
                      int(corridor["sanctioned_start"].split(":")[1])
        c_end_min   = int(corridor["sanctioned_end"].split(":")[0]) * 60 + \
                      int(corridor["sanctioned_end"].split(":")[1])
        km_start = corridor["km_start"]
        km_end   = corridor["km_end"]

        # Find the time the (delayed) train passes through the corridor's km band
        try:
            t_enter = _train_time_at_km(train, km_start) + delay_minutes
            t_exit  = _train_time_at_km(train, km_end)   + delay_minutes
            if t_enter > t_exit:
                t_enter, t_exit = t_exit, t_enter
        except Exception:
            continue

        # Overlap check: train window vs corridor window
        if t_enter <= c_end_min and t_exit >= c_start_min:
            conflicting_ids.append(corridor["corridor_id"])

    return conflicting_ids


@app.post("/api/v1/simulate-delay")
def post_simulate_delay(req: SimulateDelayRequest):
    known_trains = {t["train_no"] for t in load_trains()}
    if req.train_no not in known_trains:
        raise HTTPException(status_code=404, detail=f"Unknown train_no '{req.train_no}'")

    # Step 1: detect collisions against the CURRENT (pre-delay) schedule
    # so we can build trade-off matrices before the optimizer moves corridors away.
    pre_schedule = _LAST_SCHEDULE.get("result") or optimize_schedule()
    raw_conflicts = _detect_raw_conflicts(req.train_no, req.delay_minutes, pre_schedule)

    # Step 2: register the delay and re-optimize (optimizer may resolve some conflicts)
    conflict_report = inject_delay(req.train_no, req.delay_minutes)
    _LAST_SCHEDULE["result"] = conflict_report["schedule"]

    # Step 3: build trade-off matrix for every raw collision found in Step 1
    matrices = []
    seen = set()
    for corridor_id in raw_conflicts:
        if corridor_id not in seen:
            seen.add(corridor_id)
            m = trade_off_matrix(req.train_no, corridor_id, pre_schedule)
            if "error" not in m:
                matrices.append(m)

    # Fall back: if optimizer left residual conflicts, include those too
    for conflict in conflict_report["conflicts"]:
        if conflict["train_no"] == req.train_no and conflict["corridor_id"] not in seen:
            seen.add(conflict["corridor_id"])
            m = trade_off_matrix(req.train_no, conflict["corridor_id"], conflict_report["schedule"])
            if "error" not in m:
                matrices.append(m)

    return {
        "train_no": req.train_no,
        "injected_delay_minutes": req.delay_minutes,
        "total_injected_delay_minutes": conflict_report["injected_delays"].get(req.train_no, 0),
        "conflicts_detected": raw_conflicts if raw_conflicts else conflict_report["conflicts"],
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


# --- Ingestion endpoints ---
from ingestion.ingest_store import IngestStore
from ingestion import bdms_adapter, tms_adapter, fois_adapter, scada_adapter, crew_adapter, asset_health_adapter

_store = IngestStore()

@app.get("/api/v1/ingest/bdms")
def get_ingest_bdms():
    return bdms_adapter.fetch_live()

@app.get("/api/v1/ingest/tms")
def get_ingest_tms():
    return tms_adapter.fetch_live()

@app.get("/api/v1/ingest/fois")
def get_ingest_fois():
    return fois_adapter.fetch_live()

@app.get("/api/v1/ingest/scada")
def get_ingest_scada():
    return scada_adapter.fetch_live()

@app.get("/api/v1/ingest/crew")
def get_ingest_crew():
    return crew_adapter.fetch_live()

@app.get("/api/v1/ingest/asset-health")
def get_ingest_asset_health_adapter():
    return asset_health_adapter.fetch_live()

@app.post("/api/v1/ingest/refresh-all")
def post_ingest_refresh_all():
    _store.refresh_all()
    # Re-run optimizer with fresh ingested data
    state = get_session_state()
    result = optimize_schedule(
        injected_delays=state["injected_delays"],
        excluded_corridor_ids=state["excluded_corridor_ids"],
    )
    _LAST_SCHEDULE["result"] = result
    return {
        "status": "refreshed",
        "ingestion_status": _store.status(),
        "schedule": result,
    }

@app.get("/api/v1/ingest/status")
def get_ingest_status():
    return _store.status()