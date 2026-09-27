"""
backend/data_generator.py

Synthetic data generator for RailSync-AI.
Generates a mathematically consistent mock dataset representing the
Ghaziabad Jn (GZB) - Aligarh Jn (ALJN) 150km double-electrified BG
trunk route, per the RailSync-AI MVP spec.

On import, load_* functions will auto-instantiate the JSON files under
data/ if they do not already exist, then load and return them.
"""

import json
import os
import random

random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

NETWORK_FILE = os.path.join(DATA_DIR, "network_topology.json")
TRAINS_FILE = os.path.join(DATA_DIR, "trains.json")
DEMANDS_FILE = os.path.join(DATA_DIR, "bdms_demands.json")
MACHINERY_FILE = os.path.join(DATA_DIR, "machinery_assets.json")
ASSET_HEALTH_FILE = os.path.join(DATA_DIR, "asset_health.json")


# ---------------------------------------------------------------------------
# 3.1 Network Topology
# ---------------------------------------------------------------------------
def _build_network_topology():
    stations = [
        {"code": "GZB", "name": "Ghaziabad Jn", "km": 0.0, "platforms": 6, "loops": 4,
         "siding_base": "Siding Base A", "main_lines": 2},
        {"code": "MIU", "name": "Maripat", "km": 19.5, "platforms": None, "loops": 2, "main_lines": 2},
        {"code": "DER", "name": "Dadri", "km": 26.2, "platforms": None, "loops": 3, "main_lines": 2,
         "freight_interchange": True},
        {"code": "BRKY", "name": "Boraki", "km": 30.8, "platforms": None, "loops": 0, "main_lines": 2},
        {"code": "AJR", "name": "Ajaibpur", "km": 35.4, "platforms": None, "loops": 1, "main_lines": 2},
        {"code": "DKDE", "name": "Dankaur", "km": 43.5, "platforms": None, "loops": 2, "main_lines": 2},
        {"code": "WAIR", "name": "Wair", "km": 52.8, "platforms": None, "loops": 0, "main_lines": 2},
        {"code": "CHL", "name": "Chandausi / Chola", "km": 58.2, "platforms": None, "loops": 2, "main_lines": 2},
        {"code": "KRJ", "name": "Khurja Jn", "km": 83.1, "platforms": None, "loops": 5,
         "siding_base": "Siding Base B", "main_lines": 4},
        {"code": "DAR", "name": "Danwar", "km": 94.6, "platforms": None, "loops": 0, "main_lines": 2},
        {"code": "SOM", "name": "Somna", "km": 110.2, "platforms": None, "loops": 2, "main_lines": 2},
        {"code": "KLA", "name": "Kulwa", "km": 125.8, "platforms": None, "loops": 0, "main_lines": 2},
        {"code": "ALJN", "name": "Aligarh Jn", "km": 150.0, "platforms": 7, "loops": 6,
         "siding_base": "Siding Base C", "main_lines": 2},
    ]
    topology = {
        "section": "GZB-ALJN",
        "description": "Ghaziabad Jn to Aligarh Jn, 150km Double Electrified BG trunk route",
        "total_km": 150.0,
        "lines": ["UP", "DOWN"],
        "stations": stations,
    }
    return topology


# ---------------------------------------------------------------------------
# 3.2 Train Timetables & Telemetry
# ---------------------------------------------------------------------------
def _hhmm_to_min(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(m):
    m = int(round(m)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


STATION_KMS = {
    "GZB": 0.0, "MIU": 19.5, "DER": 26.2, "BRKY": 30.8, "AJR": 35.4, "DKDE": 43.5,
    "WAIR": 52.8, "CHL": 58.2, "KRJ": 83.1, "DAR": 94.6, "SOM": 110.2, "KLA": 125.8,
    "ALJN": 150.0,
}
STATION_ORDER = ["GZB", "MIU", "DER", "BRKY", "AJR", "DKDE", "WAIR", "CHL", "KRJ", "DAR", "SOM", "KLA", "ALJN"]


def _make_schedule(stops, start_time_min, max_speed_kmh, direction, dwell_default=2):
    """stops: list of station codes in travel order (already correctly directed)."""
    schedule = []
    t = start_time_min
    prev_km = STATION_KMS[stops[0]]
    for i, st in enumerate(stops):
        km = STATION_KMS[st]
        if i > 0:
            dist = abs(km - prev_km)
            # effective speed derated to ~70% of max to account for accel/decel + block sections
            travel_min = (dist / (max_speed_kmh * 0.7)) * 60
            t += travel_min
        arr = t
        dwell = dwell_default if st not in ("GZB", "ALJN") else 2
        dep = arr + dwell
        schedule.append({"station": st, "arr": _min_to_hhmm(arr), "dep": _min_to_hhmm(dep), "km": km})
        t = dep
        prev_km = km
    return schedule


def _build_trains():
    trains = []

    def stops_down(*included):
        return [s for s in STATION_ORDER if s in included or s in ("GZB", "ALJN")]

    def stops_up(*included):
        return list(reversed(stops_down(*included)))

    # --- Premier trains (Priority 1, weight 100) ---
    trains.append({
        "train_no": "20958", "name": "Vande Bharat Express", "type": "PREMIER", "priority": 1,
        "weight": 100, "direction": "DOWN", "max_speed_kmh": 130,
        "schedule": _make_schedule(["GZB", "MIU", "DER", "AJR", "DKDE", "CHL", "KRJ", "SOM", "ALJN"],
                                    _hhmm_to_min("06:00"), 130, "DOWN"),
    })
    trains.append({
        "train_no": "12424", "name": "Rajdhani Express", "type": "PREMIER", "priority": 1,
        "weight": 100, "direction": "DOWN", "max_speed_kmh": 130,
        "schedule": _make_schedule(["GZB", "ALJN"], _hhmm_to_min("07:00"), 130, "DOWN"),
    })
    trains.append({
        "train_no": "12004", "name": "Shatabdi Express", "type": "PREMIER", "priority": 1,
        "weight": 100, "direction": "UP", "max_speed_kmh": 120,
        "schedule": _make_schedule(["ALJN", "KRJ", "GZB"], _hhmm_to_min("08:00"), 120, "UP"),
    })

    # --- Mail/Express/MEMU (Priority 2, weight 40) ---
    trains.append({
        "train_no": "14218", "name": "Unchahar Express", "type": "EXPRESS", "priority": 2,
        "weight": 40, "direction": "DOWN", "max_speed_kmh": 100,
        "schedule": _make_schedule(["GZB", "DER", "DKDE", "KRJ", "ALJN"], _hhmm_to_min("09:00"), 100, "DOWN"),
    })
    trains.append({
        "train_no": "64102", "name": "Aligarh - Delhi MEMU", "type": "MEMU", "priority": 2,
        "weight": 40, "direction": "UP", "max_speed_kmh": 90,
        "schedule": _make_schedule(list(reversed(STATION_ORDER)), _hhmm_to_min("06:30"), 90, "UP", dwell_default=1.5),
    })
    regional_defs = [
        ("15484", "Ananya Express", "DOWN", ["GZB", "DER", "AJR", "CHL", "KRJ", "ALJN"], "10:15"),
        ("15069", "Doon Express", "UP", ["ALJN", "SOM", "KRJ", "DKDE", "GZB"], "11:30"),
        ("12554", "Vaishali Express", "DOWN", ["GZB", "DKDE", "KRJ", "DAR", "ALJN"], "13:00"),
    ]
    for no, name, direction, stops, start in regional_defs:
        trains.append({
            "train_no": no, "name": name, "type": "EXPRESS", "priority": 2, "weight": 40,
            "direction": direction, "max_speed_kmh": 100,
            "schedule": _make_schedule(stops, _hhmm_to_min(start), 100, direction),
        })

    # --- Non-timetabled freight (Priority 3, weight 10) with FOIS forecast uncertainty ---
    freight_defs = [
        ("BOXN_COAL_UP", "UP", ["ALJN", "KRJ", "DER", "GZB"], "07:15", 55),
        ("BCN_FOOD_DN", "DOWN", ["GZB", "DER", "KRJ", "ALJN"], "09:30", 50),
        ("CONTAINER_CONCOR", "DOWN", ["DER", "KRJ", "ALJN"], "11:00", 65),
    ]
    for no, direction, stops, start, speed in freight_defs:
        trains.append({
            "train_no": no, "name": no.replace("_", " ").title(), "type": "FREIGHT", "priority": 3,
            "weight": 10, "direction": direction, "max_speed_kmh": speed,
            "forecast_uncertainty_min": 0,
            "schedule": _make_schedule(stops, _hhmm_to_min(start), speed, direction, dwell_default=5),
        })
    extra_freight = [
        ("BTPN_OIL_UP", "UP", ["ALJN", "SOM", "KRJ", "GZB"], "12:20", 50, 20),
        ("BOBRN_STEEL_DN", "DOWN", ["GZB", "DKDE", "KRJ", "DAR", "ALJN"], "14:45", 55, -15),
        ("BCNA_CEMENT_UP", "UP", ["ALJN", "KLA", "KRJ", "CHL", "GZB"], "16:10", 45, 20),
    ]
    for no, direction, stops, start, speed, uncertainty in extra_freight:
        trains.append({
            "train_no": no, "name": no.replace("_", " ").title(), "type": "FREIGHT", "priority": 3,
            "weight": 10, "direction": direction, "max_speed_kmh": speed,
            "forecast_uncertainty_min": uncertainty,
            "schedule": _make_schedule(stops, _hhmm_to_min(start), speed, direction, dwell_default=5),
        })

    return trains


# ---------------------------------------------------------------------------
# 3.3 BDMS Maintenance Demands
# ---------------------------------------------------------------------------
def _build_demands():
    demands = [
        {
            "demand_id": "DEM-CIV-01", "department": "CIVIL", "line": "DOWN",
            "km_start": 32.0, "km_end": 36.5, "work_nature": "Track Tamping",
            "duration_min": 180, "machine": "CSM-1", "fouling": True,
            "ohe_block_required": False, "tsr": True, "tsr_speed_kmh": 30,
            "multi_day": False,
        },
        {
            "demand_id": "DEM-CIV-02", "department": "CIVIL", "line": "UP",
            "km_start": 85.0, "km_end": 88.0, "work_nature": "Ballast Deep Screening",
            "duration_min": 240, "machine": "BCM-2", "fouling": True,
            "ohe_block_required": True, "tsr": False, "tsr_speed_kmh": None,
            "multi_day": False,
        },
        {
            "demand_id": "DEM-CIV-03", "department": "CIVIL", "line": "COMMON",
            "station": "DKDE", "km_start": 43.5, "km_end": 43.5, "work_nature": "Turnout Renewal",
            "duration_min": 150, "machine": None, "fouling": True,
            "ohe_block_required": False, "tsr": False, "tsr_speed_kmh": None,
            "multi_day": True, "multi_day_total": 3, "multi_day_index": 1,
        },
        {
            "demand_id": "DEM-TRD-01", "department": "TRD", "line": "DOWN",
            "km_start": 33.0, "km_end": 35.0, "work_nature": "Cantilever & Insulator Replacement",
            "duration_min": 120, "machine": "TOWER-WAGON-1", "fouling": False,
            "ohe_block_required": True, "diesel_through_allowed": True, "tsr": False,
            "tsr_speed_kmh": None, "multi_day": False,
            "overlaps_with": "DEM-CIV-01",
        },
        {
            "demand_id": "DEM-TRD-02", "department": "TRD", "line": "UP",
            "km_start": 86.0, "km_end": 87.5, "work_nature": "Contact Wire Dropper Adjustment",
            "duration_min": 90, "machine": None, "fouling": False,
            "ohe_block_required": True, "diesel_through_allowed": True, "tsr": False,
            "tsr_speed_kmh": None, "multi_day": False,
            "overlaps_with": "DEM-CIV-02",
        },
        {
            "demand_id": "DEM-SNT-01", "department": "SNT", "station": "AJR",
            "line": "COMMON", "km_start": 35.4, "km_end": 35.4,
            "work_nature": "Point Machine Overhaul & Track Circuit Tuning",
            "duration_min": 90, "machine": None, "fouling": False,
            "ohe_block_required": False, "disconnection_required": True, "tsr": False,
            "tsr_speed_kmh": None, "multi_day": False,
            "adjacent_to": "DEM-CIV-01",
        },
        {
            "demand_id": "DEM-SNT-02", "department": "SNT", "line": "UP",
            "km_start": 110.0, "km_end": 112.0, "work_nature": "Axle Counter Sensor Calibration",
            "duration_min": 60, "machine": None, "fouling": False,
            "ohe_block_required": False, "tsr": False, "tsr_speed_kmh": None,
            "multi_day": False,
        },
    ]
    # 3 additional synthetic demands to reach the "10 realistic demands" target
    extra = [
        {
            "demand_id": "DEM-CIV-04", "department": "CIVIL", "line": "UP",
            "km_start": 120.0, "km_end": 123.0, "work_nature": "Rail Renewal",
            "duration_min": 200, "machine": "UNIMAT-3", "fouling": True,
            "ohe_block_required": False, "tsr": True, "tsr_speed_kmh": 30, "multi_day": False,
        },
        {
            "demand_id": "DEM-TRD-03", "department": "TRD", "line": "DOWN",
            "km_start": 5.0, "km_end": 7.0, "work_nature": "OHE Mast Painting",
            "duration_min": 100, "machine": None, "fouling": False,
            "ohe_block_required": True, "diesel_through_allowed": True, "tsr": False,
            "tsr_speed_kmh": None, "multi_day": False,
        },
        {
            "demand_id": "DEM-SNT-03", "department": "SNT", "station": "CHL",
            "line": "COMMON", "km_start": 58.2, "km_end": 58.2,
            "work_nature": "Signal Cable Route Relay",
            "duration_min": 75, "machine": None, "fouling": False,
            "ohe_block_required": False, "tsr": False, "tsr_speed_kmh": None,
            "multi_day": False,
        },
    ]
    demands.extend(extra)
    return demands


# ---------------------------------------------------------------------------
# 3.4 Track Assets & Machinery Registry
# ---------------------------------------------------------------------------
def _build_machinery():
    return [
        {"asset_id": "CSM-1", "type": "Plasser Continuous Tamping Machine",
         "base_siding": "KRJ", "status": "IDLE", "max_transit_speed_kmh": 40, "current_km": 83.1},
        {"asset_id": "BCM-2", "type": "Ballast Cleaning Machine",
         "base_siding": "GZB", "status": "IDLE", "max_transit_speed_kmh": 35, "current_km": 0.0},
        {"asset_id": "TOWER-WAGON-1", "type": "8-Wheeler TRD Inspection Car",
         "base_siding": "DER", "status": "IDLE", "max_transit_speed_kmh": 45, "current_km": 26.2},
        {"asset_id": "UNIMAT-3", "type": "Turnout Tamping Machine",
         "base_siding": "ALJN", "status": "IDLE", "max_transit_speed_kmh": 40, "current_km": 150.0},
    ]


# ---------------------------------------------------------------------------
# 3.5 Asset Health & Diagnostic Data
# ---------------------------------------------------------------------------
def _build_asset_health():
    health = []
    km = 0.0
    while km < 150.0:
        seg_end = min(km + 5.0, 150.0)
        tgi = random.randint(40, 100)
        oms_vert = round(random.uniform(0.05, 0.32), 2)
        oms_lat = round(random.uniform(0.05, 0.28), 2)
        overdue_days = random.choice([0, 0, 0, 3, 7, 14, 21, 30])
        criticality = min(10, round(overdue_days / 3) + (2 if tgi < 60 else 0) +
                           (2 if max(oms_vert, oms_lat) > 0.20 else 0))
        health.append({
            "segment_km_start": round(km, 1),
            "segment_km_end": round(seg_end, 1),
            "track_geometry_index": tgi,
            "oms_vertical_g": oms_vert,
            "oms_lateral_g": oms_lat,
            "oms_flag_urgent": max(oms_vert, oms_lat) > 0.20,
            "overdue_maintenance_days": overdue_days,
            "criticality_score": criticality,
        })
        km = seg_end
    return health


# ---------------------------------------------------------------------------
# Public load_* API — auto-instantiate on first call
# ---------------------------------------------------------------------------
def _load_or_create(path, builder_fn):
    if not os.path.exists(path):
        data = builder_fn()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return data
    with open(path, "r") as f:
        return json.load(f)


def load_network():
    return _load_or_create(NETWORK_FILE, _build_network_topology)


def load_trains():
    return _load_or_create(TRAINS_FILE, _build_trains)


def load_demands():
    return _load_or_create(DEMANDS_FILE, _build_demands)


def load_machinery():
    return _load_or_create(MACHINERY_FILE, _build_machinery)


def load_asset_health():
    return _load_or_create(ASSET_HEALTH_FILE, _build_asset_health)


def regenerate_all():
    """Force-regenerate every synthetic dataset, overwriting existing files."""
    for path, builder in [
        (NETWORK_FILE, _build_network_topology),
        (TRAINS_FILE, _build_trains),
        (DEMANDS_FILE, _build_demands),
        (MACHINERY_FILE, _build_machinery),
        (ASSET_HEALTH_FILE, _build_asset_health),
    ]:
        data = builder()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    return {
        "network": load_network(), "trains": load_trains(), "demands": load_demands(),
        "machinery": load_machinery(), "asset_health": load_asset_health(),
    }


if __name__ == "__main__":
    regenerate_all()
    print(f"Synthetic data generated in {DATA_DIR}")
