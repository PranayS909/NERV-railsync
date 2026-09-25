"""
backend/tests/test_api.py

FastAPI endpoint integration tests using TestClient (via httpx).

Test matrix
-----------
API-01  Every GET/POST endpoint returns 200 with the expected top-level keys
API-02  POST /api/v1/simulate-delay with unknown train_no returns 404
API-03  POST /api/v1/arbitrate with option=4 returns 400
API-04  Regression for /optimize session-state bug:
        POST /arbitrate(option=2), then POST /optimize => corridor still absent
"""

import pytest
from fastapi.testclient import TestClient

# The TestClient import needs sys.path patched first — conftest.py handles that.
# We import main here after conftest has run.
import sys
import os

# Ensure backend dir is on path (conftest does this, but being explicit for clarity)
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from main import app


@pytest.fixture(scope="module")
def client():
    """TestClient for the FastAPI app — module-scoped to avoid repeated startup."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_between_tests(client):
    """Reset session state before every test to avoid cross-test contamination."""
    client.post("/api/v1/reset-session")
    yield
    client.post("/api/v1/reset-session")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _known_train_no(client):
    """Return the first train_no from the /trains endpoint."""
    resp = client.get("/api/v1/trains")
    assert resp.status_code == 200
    trains = resp.json()
    assert trains, "No trains returned by /api/v1/trains"
    return trains[0]["train_no"]


def _first_corridor_id(client):
    """Run /optimize and return the first corridor_id."""
    resp = client.post("/api/v1/optimize")
    assert resp.status_code == 200
    corridors = resp.json().get("corridors", [])
    assert corridors, "No corridors in /optimize result"
    return corridors[0]["corridor_id"]


# ---------------------------------------------------------------------------
# API-01 — All endpoints return 200 with expected top-level keys
# ---------------------------------------------------------------------------

def test_root_200(client):
    """API-01: GET / returns 200 with 'service' and 'status' keys."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "service" in body
    assert "status" in body


def test_network_200(client):
    """API-01: GET /api/v1/network returns 200 with 'section' and 'stations' keys."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    body = resp.json()
    assert "section" in body
    assert "stations" in body


def test_demands_200(client):
    """API-01: GET /api/v1/demands returns 200 with expected keys."""
    resp = client.get("/api/v1/demands")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("raw_demands", "clustered_corridors", "corridor_utilization_rate_pct"):
        assert key in body, f"Key '{key}' missing from /demands response"


def test_machinery_200(client):
    """API-01: GET /api/v1/machinery returns 200 with 'fleet' and 'relocation_plan' keys."""
    resp = client.get("/api/v1/machinery")
    assert resp.status_code == 200
    body = resp.json()
    assert "fleet" in body
    assert "relocation_plan" in body


def test_asset_health_200(client):
    """API-01: GET /api/v1/asset-health returns 200 with a non-empty list."""
    resp = client.get("/api/v1/asset-health")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_trains_200(client):
    """API-01: GET /api/v1/trains returns 200 with a non-empty list of trains."""
    resp = client.get("/api/v1/trains")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_optimize_200(client):
    """API-01: POST /api/v1/optimize returns 200 with 'status', 'corridors', 'kpis'."""
    resp = client.post("/api/v1/optimize")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("status", "corridors", "kpis"):
        assert key in body, f"Key '{key}' missing from /optimize response"
    assert body["status"] in ("OPTIMAL", "FEASIBLE")


def test_kpis_200(client):
    """API-01: GET /api/v1/kpis returns 200 with expected keys."""
    # Run optimize first so _LAST_SCHEDULE is populated
    client.post("/api/v1/optimize")
    resp = client.get("/api/v1/kpis")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("corridor_kpis", "dead_mileage_saved_km", "fleet_status"):
        assert key in body, f"Key '{key}' missing from /kpis response"


def test_simulate_delay_200(client):
    """API-01: POST /api/v1/simulate-delay with a known train returns 200 with expected keys."""
    train_no = _known_train_no(client)
    resp = client.post("/api/v1/simulate-delay", json={"train_no": train_no, "delay_minutes": 15})
    assert resp.status_code == 200
    body = resp.json()
    for key in ("train_no", "injected_delay_minutes", "conflicts_detected", "trade_off_matrices"):
        assert key in body, f"Key '{key}' missing from /simulate-delay response"


def test_arbitrate_200(client):
    """API-01: POST /api/v1/arbitrate with valid option returns 200."""
    corridor_id = _first_corridor_id(client)
    train_no = _known_train_no(client)
    resp = client.post("/api/v1/arbitrate", json={
        "train_no": train_no,
        "corridor_id": corridor_id,
        "option": 1,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "applied" in body


def test_reset_session_200(client):
    """API-01: POST /api/v1/reset-session returns 200."""
    resp = client.post("/api/v1/reset-session")
    assert resp.status_code == 200
    assert resp.json().get("status") == "session reset"


# ---------------------------------------------------------------------------
# API-02 — Unknown train_no returns 404
# ---------------------------------------------------------------------------

def test_simulate_delay_unknown_train_404(client):
    """API-02: POST /simulate-delay with a non-existent train_no must return HTTP 404."""
    resp = client.post("/api/v1/simulate-delay", json={
        "train_no": "TRAIN_DOES_NOT_EXIST_99999",
        "delay_minutes": 30,
    })
    assert resp.status_code == 404, (
        f"Expected 404 for unknown train, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# API-03 — option=4 returns 400
# ---------------------------------------------------------------------------

def test_arbitrate_invalid_option_400(client):
    """API-03: POST /arbitrate with option=4 must return HTTP 400."""
    corridor_id = _first_corridor_id(client)
    train_no = _known_train_no(client)
    resp = client.post("/api/v1/arbitrate", json={
        "train_no": train_no,
        "corridor_id": corridor_id,
        "option": 4,
    })
    assert resp.status_code == 400, (
        f"Expected 400 for option=4, got {resp.status_code}: {resp.text}"
    )


def test_arbitrate_option_zero_400(client):
    """API-03b: option=0 is also invalid and must return 400."""
    corridor_id = _first_corridor_id(client)
    train_no = _known_train_no(client)
    resp = client.post("/api/v1/arbitrate", json={
        "train_no": train_no,
        "corridor_id": corridor_id,
        "option": 0,
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# API-04 — /optimize session-state bug regression
# ---------------------------------------------------------------------------

def test_option2_defer_persists_through_optimize(client):
    """API-04: After POST /arbitrate(option=2), POST /optimize must NOT re-include the
    deferred corridor — regression for the session-state bug where /optimize ignored session.
    """
    # 1. Run optimize to get a corridor
    opt_resp = client.post("/api/v1/optimize")
    assert opt_resp.status_code == 200
    corridors = opt_resp.json()["corridors"]
    assert corridors, "No corridors returned"
    corridor_id = corridors[0]["corridor_id"]
    train_no = _known_train_no(client)

    # 2. Defer the corridor via Option 2 arbitration
    arb_resp = client.post("/api/v1/arbitrate", json={
        "train_no": train_no,
        "corridor_id": corridor_id,
        "option": 2,
    })
    assert arb_resp.status_code == 200

    # 3. Re-run optimize — the deferred corridor must NOT reappear
    opt_resp2 = client.post("/api/v1/optimize")
    assert opt_resp2.status_code == 200
    new_corridor_ids = {c["corridor_id"] for c in opt_resp2.json()["corridors"]}

    assert corridor_id not in new_corridor_ids, (
        f"Regression: deferred corridor {corridor_id} reappeared after POST /optimize. "
        f"The /optimize endpoint must pass session state (excluded_corridor_ids) to the solver."
    )


def test_option2_corridor_in_deferred_field_api(client):
    """API-04b: The deferred corridor appears in result['deferred_corridors'] from /optimize."""
    opt_resp = client.post("/api/v1/optimize")
    corridor_id = opt_resp.json()["corridors"][0]["corridor_id"]
    train_no = _known_train_no(client)

    client.post("/api/v1/arbitrate", json={
        "train_no": train_no,
        "corridor_id": corridor_id,
        "option": 2,
    })

    opt_resp2 = client.post("/api/v1/optimize")
    body = opt_resp2.json()
    assert "deferred_corridors" in body, "result from /optimize missing 'deferred_corridors'"
    assert corridor_id in body["deferred_corridors"], (
        f"{corridor_id} not in deferred_corridors: {body['deferred_corridors']}"
    )
