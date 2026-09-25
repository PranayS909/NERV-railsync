"""
backend/tests/test_arbitration.py

Regression tests for the Dynamic Marey Chart & Conflict Resolver (arbitration.py).

Test matrix
-----------
ARB-01  inject_delay() accumulates correctly across multiple calls for the same train_no
ARB-02  trade_off_matrix() option 3 is marked infeasible when fouling_active=True
ARB-03  Regression: apply_arbitration(option=2) adds corridor to deferred_corridors, and a
        subsequent optimize_schedule() using get_session_state() does NOT re-include it
ARB-04  reset_session() clears injected_delays, deferred_corridors, and applied_arbitrations
"""

import pytest
import arbitration
from arbitration import (
    inject_delay,
    reset_session,
    get_session_state,
    trade_off_matrix,
    apply_arbitration,
)
from optimizer import optimize_schedule
from data_generator import load_trains, load_demands
from clustering import cluster_demands


# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_session():
    """Ensure every test starts with a fresh session and always cleans up after."""
    reset_session()
    yield
    reset_session()


def _first_premier_train_no():
    return next(t["train_no"] for t in load_trains() if t["priority"] == 1)


def _any_corridor_id():
    """Return the corridor_id of the first corridor from the default solve."""
    result = optimize_schedule()
    return result["corridors"][0]["corridor_id"]


# ---------------------------------------------------------------------------
# ARB-01 — inject_delay() accumulates across multiple calls
# ---------------------------------------------------------------------------

def test_inject_delay_single_call():
    """ARB-01a: A single inject_delay call sets the exact amount."""
    train_no = _first_premier_train_no()
    inject_delay(train_no, 15)
    state = get_session_state()
    assert state["injected_delays"].get(train_no) == 15


def test_inject_delay_accumulates():
    """ARB-01b: Multiple inject_delay calls for the same train accumulate (not overwrite)."""
    train_no = _first_premier_train_no()
    inject_delay(train_no, 20)
    inject_delay(train_no, 10)
    inject_delay(train_no, 5)
    state = get_session_state()
    assert state["injected_delays"][train_no] == 35, (
        f"Expected cumulative delay 35, got {state['injected_delays'][train_no]}"
    )


def test_inject_delay_different_trains_independent():
    """ARB-01c: Delays injected for different trains do not affect each other."""
    trains = [t["train_no"] for t in load_trains() if t["priority"] == 1]
    if len(trains) < 2:
        pytest.skip("Need at least 2 premier trains for this test")
    t1, t2 = trains[0], trains[1]
    inject_delay(t1, 30)
    inject_delay(t2, 10)
    state = get_session_state()
    assert state["injected_delays"][t1] == 30
    assert state["injected_delays"][t2] == 10


# ---------------------------------------------------------------------------
# ARB-02 — trade_off_matrix() option 3 infeasible when fouling_active=True
# ---------------------------------------------------------------------------

def test_option3_infeasible_when_fouling():
    """ARB-02: When the corridor has fouling_active=True, option 3 must be marked infeasible."""
    # Find a corridor with fouling_active=True in the scheduled result
    schedule = optimize_schedule()
    fouling_corridors = [c for c in schedule["corridors"] if c["fouling_active"]]
    if not fouling_corridors:
        pytest.skip("No fouling corridors in the default dataset — check data_generator")

    train_no = _first_premier_train_no()
    corridor_id = fouling_corridors[0]["corridor_id"]

    matrix = trade_off_matrix(train_no, corridor_id, schedule_result=schedule)
    assert "options" in matrix, "trade_off_matrix returned error or malformed result"

    option_3 = next((o for o in matrix["options"] if o["option"] == 3), None)
    assert option_3 is not None, "Option 3 missing from trade_off_matrix"
    assert option_3.get("feasible") is False, (
        f"Option 3 should be infeasible for a fouling corridor, got feasible={option_3.get('feasible')}"
    )


def test_option3_feasible_when_no_fouling():
    """ARB-02b: When fouling_active=False, option 3 must NOT be infeasible."""
    schedule = optimize_schedule()
    non_fouling = [c for c in schedule["corridors"] if not c["fouling_active"]]
    if not non_fouling:
        pytest.skip("All corridors are fouling — cannot test option 3 feasibility")

    train_no = _first_premier_train_no()
    corridor_id = non_fouling[0]["corridor_id"]

    matrix = trade_off_matrix(train_no, corridor_id, schedule_result=schedule)
    option_3 = next((o for o in matrix["options"] if o["option"] == 3), None)
    assert option_3 is not None
    assert option_3.get("feasible", True) is True


# ---------------------------------------------------------------------------
# ARB-03 — Option 2 regression: defer corridor persists across optimize calls
# ---------------------------------------------------------------------------

def test_option2_adds_to_deferred_corridors():
    """ARB-03a: apply_arbitration(option=2) must add the corridor to deferred_corridors in session."""
    schedule = optimize_schedule()
    corridor_id = schedule["corridors"][0]["corridor_id"]
    train_no = _first_premier_train_no()

    apply_arbitration(train_no, corridor_id, option=2)

    state = get_session_state()
    assert corridor_id in state["excluded_corridor_ids"], (
        f"Corridor {corridor_id} not in excluded_corridor_ids after Option 2 arbitration. "
        f"State: {state}"
    )


def test_option2_corridor_absent_from_subsequent_optimize():
    """ARB-03b: After apply_arbitration(option=2), a call to optimize_schedule() using
    get_session_state() must NOT include the deferred corridor in the result."""
    schedule = optimize_schedule()
    corridor_id = schedule["corridors"][0]["corridor_id"]
    train_no = _first_premier_train_no()

    apply_arbitration(train_no, corridor_id, option=2)

    # Simulate what the /optimize endpoint does: read session state, pass to optimizer
    state = get_session_state()
    new_result = optimize_schedule(
        injected_delays=state["injected_delays"],
        excluded_corridor_ids=state["excluded_corridor_ids"],
    )

    present_ids = {c["corridor_id"] for c in new_result["corridors"]}
    assert corridor_id not in present_ids, (
        f"Deferred corridor {corridor_id} still appears in optimize result after Option 2 apply"
    )


def test_option2_corridor_in_deferred_field():
    """ARB-03c: The deferred corridor must appear in result['deferred_corridors']."""
    schedule = optimize_schedule()
    corridor_id = schedule["corridors"][0]["corridor_id"]
    train_no = _first_premier_train_no()

    apply_arbitration(train_no, corridor_id, option=2)

    state = get_session_state()
    new_result = optimize_schedule(
        injected_delays=state["injected_delays"],
        excluded_corridor_ids=state["excluded_corridor_ids"],
    )

    assert corridor_id in new_result.get("deferred_corridors", []), (
        f"Expected {corridor_id} in result['deferred_corridors']: {new_result.get('deferred_corridors')}"
    )


# ---------------------------------------------------------------------------
# ARB-04 — reset_session() clears all state
# ---------------------------------------------------------------------------

def test_reset_clears_injected_delays():
    """ARB-04a: reset_session() must clear injected_delays."""
    train_no = _first_premier_train_no()
    inject_delay(train_no, 45)
    reset_session()
    state = get_session_state()
    assert state["injected_delays"] == {}, (
        f"injected_delays not cleared: {state['injected_delays']}"
    )


def test_reset_clears_deferred_corridors():
    """ARB-04b: reset_session() must clear deferred_corridors."""
    schedule = optimize_schedule()
    corridor_id = schedule["corridors"][0]["corridor_id"]
    train_no = _first_premier_train_no()
    apply_arbitration(train_no, corridor_id, option=2)

    reset_session()
    state = get_session_state()
    assert state["excluded_corridor_ids"] == [], (
        f"excluded_corridor_ids not cleared after reset: {state['excluded_corridor_ids']}"
    )


def test_reset_clears_applied_arbitrations():
    """ARB-04c: reset_session() must clear the applied_arbitrations log."""
    schedule = optimize_schedule()
    corridor_id = schedule["corridors"][0]["corridor_id"]
    train_no = _first_premier_train_no()
    apply_arbitration(train_no, corridor_id, option=1)

    reset_session()
    # Verify by checking that _SESSION is clean (access via module internal for this test)
    assert arbitration._SESSION["applied_arbitrations"] == []


def test_reset_followed_by_optimize_includes_all_corridors():
    """ARB-04d: After reset, all corridors return (no longer excluded)."""
    schedule_before = optimize_schedule()
    corridor_id = schedule_before["corridors"][0]["corridor_id"]
    total_before = len(schedule_before["corridors"])

    train_no = _first_premier_train_no()
    apply_arbitration(train_no, corridor_id, option=2)
    reset_session()

    state = get_session_state()
    schedule_after = optimize_schedule(
        injected_delays=state["injected_delays"],
        excluded_corridor_ids=state["excluded_corridor_ids"],
    )
    total_after = len(schedule_after["corridors"])
    assert total_after == total_before, (
        f"After reset, expected {total_before} corridors but got {total_after}"
    )
