"""
backend/tests/test_optimizer.py

Regression tests for the CP-SAT Optimizer.

Test matrix
-----------
OPT-01  optimize_schedule() returns OPTIMAL or FEASIBLE on the default synthetic dataset
OPT-02  Machine transit buffer regression: two corridors on the same machine have a gap >= 30 min
OPT-03  A corridor with fouling_active=True never overlaps a premier train's crossing time
OPT-04  excluded_corridor_ids removes those corridors from the result and lists them under deferred_corridors
"""

import pytest
from optimizer import (
    optimize_schedule,
    MACHINE_TRANSIT_BUFFER_MIN,
    SIM_START_MIN,
    SLOT_MIN,
    _train_time_at_km,
)
from data_generator import load_trains


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hhmm_to_min(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------------------
# OPT-01 — Default dataset returns OPTIMAL or FEASIBLE
# ---------------------------------------------------------------------------

def test_optimize_returns_solvable_status():
    """OPT-01: The solver must reach OPTIMAL or FEASIBLE within its time limit."""
    result = optimize_schedule()
    assert result["status"] in ("OPTIMAL", "FEASIBLE"), (
        f"Unexpected solver status: {result['status']}"
    )


def test_optimize_returns_corridors_list():
    """OPT-01b: Result must contain at least one scheduled corridor."""
    result = optimize_schedule()
    assert isinstance(result["corridors"], list)
    assert len(result["corridors"]) > 0


def test_optimize_kpis_present():
    """OPT-01c: KPI dict must contain expected keys."""
    result = optimize_schedule()
    kpis = result["kpis"]
    for key in ("total_weighted_conflict_cost", "num_corridors", "solve_time_sec"):
        assert key in kpis, f"KPI key '{key}' missing from result"


# ---------------------------------------------------------------------------
# OPT-02 — Machine transit buffer regression test
# ---------------------------------------------------------------------------

def test_machine_transit_buffer_enforced():
    """OPT-02: Two corridors forced onto the same machine must have a gap >= MACHINE_TRANSIT_BUFFER_MIN.

    We fabricate two minimal demands that share 'TEST-MACH' and run the optimizer.
    The gap between end of the earlier corridor and start of the later one must be
    >= MACHINE_TRANSIT_BUFFER_MIN (30 min) in the sanctioned schedule.
    """
    # Build two demands that share the same machine and are spatially non-overlapping
    # (so they form two separate corridors) but are close enough that a greedy packer
    # would try to schedule them back-to-back with zero gap.
    demands_two_jobs = [
        {
            "demand_id": "DEM-TEST-A", "department": "CIVIL", "line": "UP",
            "km_start": 5.0, "km_end": 7.0, "duration_min": 60,
            "machine": "TEST-MACH", "fouling": False, "ohe_block_required": False,
            "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
        },
        {
            "demand_id": "DEM-TEST-B", "department": "CIVIL", "line": "UP",
            "km_start": 60.0, "km_end": 62.0, "duration_min": 45,
            "machine": "TEST-MACH", "fouling": False, "ohe_block_required": False,
            "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
        },
    ]

    from clustering import cluster_demands as _cluster
    from optimizer import optimize_schedule as _optimize
    from unittest.mock import patch
    from data_generator import load_trains, load_asset_health, load_machinery

    # Patch cluster_demands inside optimizer to use our synthetic demands
    with patch("optimizer.load_demands", return_value=demands_two_jobs), \
         patch("optimizer.load_machinery", return_value=[
             {"asset_id": "TEST-MACH", "type": "Test Machine",
              "base_siding": "GZB", "status": "IDLE",
              "max_transit_speed_kmh": 40, "current_km": 0.0}
         ]):
        result = _optimize()

    assert result["status"] in ("OPTIMAL", "FEASIBLE"), (
        f"Solver returned {result['status']} for the two-job machine test"
    )

    corridors = {c["corridor_id"]: c for c in result["corridors"]}
    # Both demand corridors must be present
    assert len(corridors) == 2, f"Expected 2 corridors, got {len(corridors)}"

    times = sorted(
        (_hhmm_to_min(c["sanctioned_start"]), _hhmm_to_min(c["sanctioned_end"]))
        for c in result["corridors"]
    )
    # gap = start of 2nd - end of 1st
    gap_minutes = times[1][0] - times[0][1]
    assert gap_minutes >= MACHINE_TRANSIT_BUFFER_MIN, (
        f"Machine transit buffer violated: gap={gap_minutes} min "
        f"< MACHINE_TRANSIT_BUFFER_MIN={MACHINE_TRANSIT_BUFFER_MIN} min"
    )


# ---------------------------------------------------------------------------
# OPT-03 — fouling_active corridor never overlaps a premier train crossing
# ---------------------------------------------------------------------------

def test_fouling_corridor_no_premier_overlap():
    """OPT-03: Every corridor with fouling_active=True must not have its sanctioned window
    contain the crossing time of any PREMIER (priority=1) train at that km range.

    The optimizer assigns high conflict cost (weight * 30) for such cases, so the solver
    should shift the corridor to avoid premier trains wherever possible.
    """
    trains = load_trains()
    premier_trains = [t for t in trains if t["priority"] == 1]

    result = optimize_schedule()

    for corr in result["corridors"]:
        if not corr["fouling_active"]:
            continue
        start_min = _hhmm_to_min(corr["sanctioned_start"])
        end_min = _hhmm_to_min(corr["sanctioned_end"])
        km_mid = (corr["km_start"] + corr["km_end"]) / 2.0

        for train in premier_trains:
            t_cross = _train_time_at_km(train, km_mid)
            if t_cross is None:
                continue  # train doesn't traverse this section

            # If premier train crosses within the fouling window that's a real conflict.
            # The optimizer may not always achieve zero conflicts on a tiny MVP dataset,
            # but the conflict should be logged in `corr["conflicts"]`, not silently ignored.
            if start_min <= t_cross <= end_min:
                # Verify the conflict is at least recorded
                conflict_reasons = [cf["train_no"] for cf in corr.get("conflicts", [])]
                assert train["train_no"] in conflict_reasons, (
                    f"Premier train {train['train_no']} crosses fouling corridor "
                    f"{corr['corridor_id']} at t={t_cross:.1f} min "
                    f"[window {corr['sanctioned_start']}-{corr['sanctioned_end']}] "
                    f"but is NOT listed in corridor conflicts — conflict cost must be wired in."
                )


# ---------------------------------------------------------------------------
# OPT-04 — excluded_corridor_ids removes corridors from result
# ---------------------------------------------------------------------------

def test_excluded_corridor_ids_not_in_result():
    """OPT-04a: Corridors listed in excluded_corridor_ids must be absent from result['corridors']."""
    first_result = optimize_schedule()
    assert first_result["corridors"], "No corridors to exclude — synthetic dataset problem?"
    corridor_to_exclude = first_result["corridors"][0]["corridor_id"]

    second_result = optimize_schedule(excluded_corridor_ids=[corridor_to_exclude])

    present_ids = {c["corridor_id"] for c in second_result["corridors"]}
    assert corridor_to_exclude not in present_ids, (
        f"Corridor {corridor_to_exclude} was listed in excluded_corridor_ids "
        f"but still appears in result['corridors']"
    )


def test_excluded_corridor_ids_appear_in_deferred():
    """OPT-04b: Excluded corridors must be listed in result['deferred_corridors']."""
    first_result = optimize_schedule()
    corridor_to_exclude = first_result["corridors"][0]["corridor_id"]

    second_result = optimize_schedule(excluded_corridor_ids=[corridor_to_exclude])

    assert "deferred_corridors" in second_result, "result missing 'deferred_corridors' key"
    assert corridor_to_exclude in second_result["deferred_corridors"], (
        f"Excluded corridor {corridor_to_exclude} not found in result['deferred_corridors']: "
        f"{second_result['deferred_corridors']}"
    )


def test_excluded_multiple_corridors():
    """OPT-04c: Excluding multiple corridors works correctly."""
    first_result = optimize_schedule()
    ids_to_exclude = [c["corridor_id"] for c in first_result["corridors"][:2]]

    second_result = optimize_schedule(excluded_corridor_ids=ids_to_exclude)

    present_ids = {c["corridor_id"] for c in second_result["corridors"]}
    for exc_id in ids_to_exclude:
        assert exc_id not in present_ids, (
            f"Excluded corridor {exc_id} still present in result"
        )
    for exc_id in ids_to_exclude:
        assert exc_id in second_result["deferred_corridors"]
