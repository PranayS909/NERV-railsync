"""
backend/relocation.py

Post-Maintenance Heavy Asset Relocation.
Tracks machine state (IDLE / WORKING / TRANSIT), and, once a corridor
block completes, computes dead-mileage cost to the next scheduled
maintenance zone over a 7- to 30-day lookahead horizon, pairing machine
movements with available freight path slots where possible to avoid
extra non-revenue light-engine movements.
"""

import random

from data_generator import load_machinery, load_trains
from clustering import cluster_demands, load_demands
from optimizer import optimize_schedule

random.seed(7)

STATION_KMS = {
    "GZB": 0.0, "MIU": 19.5, "DER": 26.2, "BRKY": 30.8, "AJR": 35.4, "DKDE": 43.5,
    "WAIR": 52.8, "CHL": 58.2, "KRJ": 83.1, "DAR": 94.6, "SOM": 110.2, "KLA": 125.8,
    "ALJN": 150.0,
}


def _nearest_freight_path(km, direction_hint=None):
    """Find a freight train whose route passes near `km`, to piggyback the
    machine's light-engine movement on an existing non-revenue-friendly path."""
    freights = [t for t in load_trains() if t["type"] == "FREIGHT"]
    best = None
    best_dist = float("inf")
    for f in freights:
        for pt in f["schedule"]:
            d = abs(pt["km"] - km)
            if d < best_dist:
                best_dist = d
                best = f
    return best


def plan_relocations(lookahead_days=7):
    machinery = {m["asset_id"]: dict(m) for m in load_machinery()}
    schedule = optimize_schedule()
    corridors_by_machine = {}
    for c in schedule["corridors"]:
        for m in c["machines_required"]:
            corridors_by_machine.setdefault(m, []).append(c)

    plans = []
    total_dead_mileage_saved = 0.0

    for asset_id, machine in machinery.items():
        jobs = sorted(corridors_by_machine.get(asset_id, []), key=lambda c: c["sanctioned_start"])
        cur_km = machine["current_km"]
        cur_state = "IDLE"
        timeline = []

        for job in jobs:
            dead_km = abs(job["km_start"] - cur_km)
            transit_min = (dead_km / machine["max_transit_speed_kmh"]) * 60 if dead_km > 0 else 0
            piggyback = _nearest_freight_path(job["km_start"])
            # naive saving estimate: piggybacking on an existing freight path saves ~40% of
            # the light-engine dead mileage that would otherwise require a dedicated path
            saved = round(dead_km * 0.4, 2) if piggyback else 0.0
            total_dead_mileage_saved += saved

            timeline.append({
                "event": "TRANSIT",
                "from_km": round(cur_km, 1),
                "to_km": job["km_start"],
                "dead_mileage_km": round(dead_km, 2),
                "transit_min": round(transit_min, 1),
                "piggyback_freight": piggyback["train_no"] if piggyback else None,
                "dead_mileage_saved_km": saved,
            })
            timeline.append({
                "event": "WORKING",
                "corridor_id": job["corridor_id"],
                "km_start": job["km_start"],
                "km_end": job["km_end"],
                "window": [job["sanctioned_start"], job["sanctioned_end"]],
            })
            cur_km = job["km_end"]
            cur_state = "WORKING"

        # post-job relocation back toward base siding within lookahead horizon
        base_km = STATION_KMS.get(machine["base_siding"], cur_km)
        if jobs:
            dead_km_home = abs(base_km - cur_km)
            piggyback_home = _nearest_freight_path(base_km)
            saved_home = round(dead_km_home * 0.4, 2) if piggyback_home else 0.0
            total_dead_mileage_saved += saved_home
            timeline.append({
                "event": "RELOCATE_TO_BASE",
                "from_km": round(cur_km, 1),
                "to_km": base_km,
                "dead_mileage_km": round(dead_km_home, 2),
                "piggyback_freight": piggyback_home["train_no"] if piggyback_home else None,
                "dead_mileage_saved_km": saved_home,
                "lookahead_days": lookahead_days,
            })
            cur_state = "TRANSIT"
        else:
            cur_state = "IDLE"

        plans.append({
            "asset_id": asset_id,
            "asset_type": machine["type"],
            "base_siding": machine["base_siding"],
            "final_state": cur_state,
            "jobs_assigned": len(jobs),
            "timeline": timeline,
        })

    return {
        "lookahead_days": lookahead_days,
        "plans": plans,
        "total_dead_mileage_saved_km": round(total_dead_mileage_saved, 2),
        "fleet_status": {
            asset_id: (p["final_state"])
            for asset_id, p in zip(machinery.keys(), plans)
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(plan_relocations(), indent=2))
