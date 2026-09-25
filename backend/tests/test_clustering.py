"""
backend/tests/test_clustering.py

Regression tests for the Spatial Clustering & Shadowing Engine.

Test matrix
-----------
CLUS-01  CORR-01 correctly clubs CIV-01 + TRD-01 + SNT-01 (spatial overlap within 5 km)
CLUS-02  Duration_Corridor = max(D_Civil, D_TRD, D_S&T), not sum
CLUS-03  Demands outside the 5 km radius do NOT cluster together
CLUS-04  Badge composition is correct for multi-department vs single-department corridors
"""

import pytest
from clustering import cluster_demands, _overlaps_within_radius, CLUSTER_RADIUS_KM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# The canonical three demands that should always cluster into one corridor.
DEMAND_CIV_01 = {
    "demand_id": "DEM-CIV-01", "department": "CIVIL", "line": "DOWN",
    "km_start": 32.0, "km_end": 36.5, "duration_min": 180,
    "machine": "CSM-1", "fouling": True, "ohe_block_required": False,
    "tsr": True, "tsr_speed_kmh": 30, "multi_day": False,
}
DEMAND_TRD_01 = {
    "demand_id": "DEM-TRD-01", "department": "TRD", "line": "DOWN",
    "km_start": 33.0, "km_end": 35.0, "duration_min": 120,
    "machine": "TOWER-WAGON-1", "fouling": False, "ohe_block_required": True,
    "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
}
DEMAND_SNT_01 = {
    "demand_id": "DEM-SNT-01", "department": "SNT", "line": "COMMON",
    "km_start": 35.4, "km_end": 35.4, "duration_min": 90,
    "machine": None, "fouling": False, "ohe_block_required": False,
    "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
}

# Two demands that are far apart (>5 km gap) and must NOT cluster.
DEMAND_FAR_A = {
    "demand_id": "DEM-FAR-A", "department": "CIVIL", "line": "UP",
    "km_start": 10.0, "km_end": 12.0, "duration_min": 60,
    "machine": None, "fouling": False, "ohe_block_required": False,
    "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
}
DEMAND_FAR_B = {
    "demand_id": "DEM-FAR-B", "department": "TRD", "line": "UP",
    "km_start": 20.0, "km_end": 22.0, "duration_min": 60,
    "machine": None, "fouling": False, "ohe_block_required": False,
    "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
}

# A lone single-department demand.
DEMAND_SOLO = {
    "demand_id": "DEM-SOLO", "department": "SNT", "line": "DOWN",
    "km_start": 100.0, "km_end": 102.0, "duration_min": 45,
    "machine": None, "fouling": False, "ohe_block_required": False,
    "tsr": False, "tsr_speed_kmh": None, "multi_day": False,
}


# ---------------------------------------------------------------------------
# CLUS-01 — CIV-01 + TRD-01 + SNT-01 cluster into exactly one corridor
# ---------------------------------------------------------------------------

def test_corr01_clubs_civ_trd_snt():
    """CLUS-01: The three spatially-overlapping demands must form one corridor."""
    demands = [DEMAND_CIV_01, DEMAND_TRD_01, DEMAND_SNT_01]
    corridors = cluster_demands(demands)

    assert len(corridors) == 1, (
        f"Expected exactly 1 corridor for CIV-01+TRD-01+SNT-01, got {len(corridors)}"
    )
    corr = corridors[0]
    assert set(corr["member_demand_ids"]) == {"DEM-CIV-01", "DEM-TRD-01", "DEM-SNT-01"}


def test_corr01_civil_is_primary():
    """CLUS-01b: CIVIL must be the primary department when clustered with TRD/SNT."""
    demands = [DEMAND_CIV_01, DEMAND_TRD_01, DEMAND_SNT_01]
    corridors = cluster_demands(demands)
    corr = corridors[0]
    assert corr["primary_department"] == "CIVIL"
    assert corr["primary_demand"] == "DEM-CIV-01"


# ---------------------------------------------------------------------------
# CLUS-02 — Duration_Corridor = max(D_Civil, D_TRD, D_S&T), not sum
# ---------------------------------------------------------------------------

def test_duration_is_max_not_sum():
    """CLUS-02: corridor duration = max member duration, not the sum."""
    demands = [DEMAND_CIV_01, DEMAND_TRD_01, DEMAND_SNT_01]
    corridors = cluster_demands(demands)
    corr = corridors[0]

    durations = [DEMAND_CIV_01["duration_min"], DEMAND_TRD_01["duration_min"], DEMAND_SNT_01["duration_min"]]
    expected = max(durations)    # 180
    total = sum(durations)       # 390

    assert corr["duration_min"] == expected, (
        f"Duration should be max={expected}, not sum={total}. Got {corr['duration_min']}"
    )


def test_duration_equals_civil_duration():
    """CLUS-02b: Specifically the CIVIL demand has the longest duration here."""
    demands = [DEMAND_CIV_01, DEMAND_TRD_01, DEMAND_SNT_01]
    corridors = cluster_demands(demands)
    assert corridors[0]["duration_min"] == DEMAND_CIV_01["duration_min"]


# ---------------------------------------------------------------------------
# CLUS-03 — Demands outside the 5 km radius do NOT cluster together
# ---------------------------------------------------------------------------

def test_far_demands_do_not_cluster():
    """CLUS-03: DEM-FAR-A (km 10-12) and DEM-FAR-B (km 20-22) are >5 km apart and must not merge."""
    # Gap = 20.0 - 12.0 = 8 km — well beyond CLUSTER_RADIUS_KM=5.0
    demands = [DEMAND_FAR_A, DEMAND_FAR_B]
    corridors = cluster_demands(demands)
    assert len(corridors) == 2, (
        f"Far-apart demands should produce 2 corridors, got {len(corridors)}"
    )
    all_members = {mid for c in corridors for mid in c["member_demand_ids"]}
    assert all_members == {"DEM-FAR-A", "DEM-FAR-B"}


def test_radius_helper_rejects_far_pair():
    """CLUS-03b: _overlaps_within_radius returns False for the far pair directly."""
    assert not _overlaps_within_radius(DEMAND_FAR_A, DEMAND_FAR_B), (
        "Demands with an 8-km gap should not be considered within the 5-km clustering radius"
    )


def test_radius_helper_accepts_close_pair():
    """CLUS-03c: _overlaps_within_radius returns True for CIV-01/TRD-01 which overlap directly."""
    assert _overlaps_within_radius(DEMAND_CIV_01, DEMAND_TRD_01)


# ---------------------------------------------------------------------------
# CLUS-04 — Badge & department composition
# ---------------------------------------------------------------------------

def test_multi_department_badge():
    """CLUS-04a: Multi-department corridor badge lists all departments in priority order."""
    demands = [DEMAND_CIV_01, DEMAND_TRD_01, DEMAND_SNT_01]
    corridors = cluster_demands(demands)
    corr = corridors[0]

    assert corr["badge"] == "[CIVIL + TRD + SNT]"
    assert corr["departments"] == ["CIVIL", "TRD", "SNT"]


def test_single_department_badge():
    """CLUS-04b: Single-department corridor badge is just that department."""
    demands = [DEMAND_SOLO]
    corridors = cluster_demands(demands)
    corr = corridors[0]

    assert corr["badge"] == "[SNT]"
    assert corr["departments"] == ["SNT"]
    assert len(corr["member_demand_ids"]) == 1


def test_full_dataset_corr01_exists():
    """CLUS-04c: On the actual synthetic dataset, at least one corridor contains all three of
    DEM-CIV-01, DEM-TRD-01, DEM-SNT-01 — verifying the production data generator output."""
    from data_generator import load_demands
    corridors = cluster_demands(load_demands())
    trio = {"DEM-CIV-01", "DEM-TRD-01", "DEM-SNT-01"}
    matching = [c for c in corridors if trio.issubset(set(c["member_demand_ids"]))]
    assert matching, (
        "No corridor in the full dataset contains DEM-CIV-01 + DEM-TRD-01 + DEM-SNT-01"
    )
    corr = matching[0]
    assert corr["duration_min"] == 180  # max of 180, 120, 90
    assert corr["badge"] == "[CIVIL + TRD + SNT]"
