"""
backend/arbitration.py

Dynamic Marey Chart & Conflict Resolver.
Detects collisions between live/delayed train trajectories and sanctioned
block boxes in time-distance space, then computes the 3-option
Trade-Off Arbitration Matrix used by the Section Controller.
"""

from backend.data_generator import load_trains
from backend.clustering import cluster_demands, load_demands
from backend.optimizer import optimize_schedule, _train_time_at_km, _min_to_hhmm

# in-memory session state for injected delays / applied arbitrations (MVP: single session)
_SESSION = {
    "injected_delays": {},   # train_no -> minutes
    "applied_arbitrations": [],  # log of {train_no, corridor_id, option, applied_at}
}


def inject_delay(train_no, delay_minutes):
    _SESSION["injected_delays"][train_no] = _SESSION["injected_delays"].get(train_no, 0) + delay_minutes
    return detect_conflicts()


def reset_session():
    _SESSION["injected_delays"] = {}
    _SESSION["applied_arbitrations"] = []


def detect_conflicts(schedule_result=None):
    """Re-solve (or reuse) the schedule with current injected delays and report
    any train/corridor collisions in time-distance space."""
    schedule_result = schedule_result or optimize_schedule(injected_delays=_SESSION["injected_delays"])
    trains = {t["train_no"]: t for t in load_trains()}

    conflicts = []
    for corridor in schedule_result["corridors"]:
        for conflict in corridor["conflicts"]:
            train = trains.get(conflict["train_no"])
            if not train:
                continue
            conflicts.append({
                "corridor_id": corridor["corridor_id"],
                "train_no": conflict["train_no"],
                "train_name": train["name"],
                "train_priority": train["priority"],
                "reason": conflict["reason"],
                "penalty_min": conflict["penalty_min"],
                "corridor_window": [corridor["sanctioned_start"], corridor["sanctioned_end"]],
                "km_range": [corridor["km_start"], corridor["km_end"]],
            })
    return {
        "injected_delays": dict(_SESSION["injected_delays"]),
        "conflicts": conflicts,
        "schedule": schedule_result,
    }


def _find_corridor(schedule_result, corridor_id):
    for c in schedule_result["corridors"]:
        if c["corridor_id"] == corridor_id:
            return c
    return None


def trade_off_matrix(train_no, corridor_id, schedule_result=None):
    """Compute the 3-option arbitration matrix for a specific train/corridor conflict."""
    schedule_result = schedule_result or optimize_schedule(injected_delays=_SESSION["injected_delays"])
    trains = {t["train_no"]: t for t in load_trains()}
    train = trains.get(train_no)
    corridor = _find_corridor(schedule_result, corridor_id)
    if not train or not corridor:
        return {"error": "train or corridor not found"}

    weight = train["weight"]
    duration = corridor["duration_min"]

    # Option 1: Regulate/detain the train in an upstream loop -> prioritize maintenance
    option_1 = {
        "option": 1,
        "label": "Regulate Train / Prioritize Maintenance",
        "action": f"Detain {train_no} at nearest upstream loop station",
        "secondary_delay_min": 12,
        "penalty_score": round(weight * 12, 1),
        "notes": "Block proceeds as sanctioned; train absorbs delay at a loop line.",
    }

    # Option 2: Compress/defer the block -> prioritize train traffic
    machine_idle_cost = 8 * len(corridor["machines_required"]) if corridor["machines_required"] else 5
    option_2 = {
        "option": 2,
        "label": "Prioritize Train / Defer Maintenance",
        "action": f"Defer or compress corridor {corridor_id} to let {train_no} pass on schedule",
        "machine_idle_cost_min": machine_idle_cost,
        "deferred_maintenance_penalty": round(0.5 * duration, 1),
        "penalty_score": round(machine_idle_cost + 0.5 * duration, 1),
        "notes": "Maintenance work is rescheduled to next available window; machine incurs idle cost at siding.",
    }

    # Option 3: Compress block + apply TSR, allow train through at caution speed
    caution_delay = 6 if corridor["tsr_active"] else 8
    option_3 = {
        "option": 3,
        "label": "Compress Block + Apply TSR",
        "action": f"Shorten corridor {corridor_id} by 30 min, allow {train_no} through at 30 km/h caution order",
        "transit_delay_min": caution_delay,
        "block_compressed_by_min": 30,
        "penalty_score": round(weight * caution_delay / 10 + duration * 0.15, 1),
        "notes": "Feasible only if the corridor's fouling status permits restricted-speed passage.",
        "feasible": not corridor["fouling_active"],
    }

    options = [option_1, option_2, option_3]
    recommended = min((o for o in options if o.get("feasible", True)), key=lambda o: o["penalty_score"])

    return {
        "train_no": train_no,
        "train_name": train["name"],
        "train_priority": train["priority"],
        "corridor_id": corridor_id,
        "corridor_window": corridor["sanctioned_start"] + " - " + corridor["sanctioned_end"],
        "options": options,
        "recommended_option": recommended["option"],
    }


def apply_arbitration(train_no, corridor_id, option):
    """Apply the chosen option, logging it and returning the updated schedule view."""
    entry = {"train_no": train_no, "corridor_id": corridor_id, "option": option}
    _SESSION["applied_arbitrations"].append(entry)

    if option == 1:
        # detain train: model as an injected delay absorbed at a loop (does not shift corridor)
        inject_delay(train_no, 12)
    elif option == 2:
        # defer maintenance: crude MVP handling -- flag corridor for reschedule note
        pass
    elif option == 3:
        # compress + TSR: small residual delay to train, corridor unaffected in this MVP model
        inject_delay(train_no, 6)

    return {
        "applied": entry,
        "session_log": list(_SESSION["applied_arbitrations"]),
        "updated_conflicts": detect_conflicts(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(detect_conflicts(), indent=2)[:2000])
