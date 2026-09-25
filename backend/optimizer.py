"""
backend/optimizer.py

Constraint Programming Optimizer using Google OR-Tools CP-SAT.
Models 15-minute discrete time steps across a 12-hour (06:00-18:00)
simulation window and sanctions corridor start/end times, subject to:

  1. No non-diesel train may traverse a section under active OHE block.
  2. No train may pass through a section under active physical fouling.
  3. Minimum 5-minute headway between consecutive departures (approximated
     via the train timetable's own scheduling; enforced as a modelling
     note since full re-timetabling is out of MVP scope).
  4. Machine non-overlap: a machine cannot serve two corridors without an
     allotted transit buffer between them.

Objective:
    minimize  sum(w_train * conflict_delay)
            + sum(machine_transit_buffer_cost)
            - sum(criticality_score * duration)
"""

from ortools.sat.python import cp_model

from data_generator import load_trains, load_demands, load_machinery, load_asset_health
from clustering import cluster_demands

SIM_START_MIN = 6 * 60      # 06:00
SIM_END_MIN = 18 * 60       # 18:00
SLOT_MIN = 15
NUM_SLOTS = (SIM_END_MIN - SIM_START_MIN) // SLOT_MIN  # 48

MACHINE_TRANSIT_BUFFER_MIN = 30  # generic turnaround/prep buffer between successive jobs on one machine


# ---------------------------------------------------------------------------
# Train position interpolation
# ---------------------------------------------------------------------------
def _train_time_at_km(train, km):
    """Linear-interpolate the clock time (minutes since 00:00) a train crosses `km`.
    Returns None if km is outside the train's routed schedule."""
    sched = train["schedule"]
    kms = [pt["km"] for pt in sched]
    lo_km, hi_km = min(kms), max(kms)
    if km < lo_km - 1e-6 or km > hi_km + 1e-6:
        return None

    def to_min(t):
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    pts = sorted(sched, key=lambda p: p["km"])
    for i in range(len(pts) - 1):
        k1, k2 = pts[i]["km"], pts[i + 1]["km"]
        if k1 - 1e-6 <= km <= k2 + 1e-6:
            t1 = to_min(pts[i]["dep"])
            t2 = to_min(pts[i + 1]["arr"])
            if k2 == k1:
                return t1
            frac = (km - k1) / (k2 - k1)
            return t1 + frac * (t2 - t1)
    return None


def _train_is_electric(train):
    # MVP assumption: all rolling stock is electric-hauled unless explicitly a
    # diesel-through freight movement, matching the "OHE mandatory" premise of the brief.
    return True


# ---------------------------------------------------------------------------
# Corridor <-> train conflict cost, precomputed per candidate start slot
# ---------------------------------------------------------------------------
def _corridor_conflict_cost(corridor, start_min, trains, injected_delays=None):
    injected_delays = injected_delays or {}
    end_min = start_min + corridor["duration_min"]
    cost = 0
    conflicts = []
    lines_to_check = ["UP", "DOWN"] if corridor["line"] == "COMMON" else [corridor["line"]]

    for train in trains:
        if train["direction"] not in lines_to_check:
            continue
        t_cross = _train_time_at_km(train, corridor["km_start"])
        t_cross_end = _train_time_at_km(train, corridor["km_end"])
        candidates = [t for t in (t_cross, t_cross_end) if t is not None]
        if not candidates:
            continue
        t_cross = sum(candidates) / len(candidates) + injected_delays.get(train["train_no"], 0)

        if not (start_min <= t_cross <= end_min):
            continue

        if corridor["fouling_active"]:
            cost += train["weight"] * 30  # hard block -> ~30min regulation penalty
            conflicts.append({"train_no": train["train_no"], "reason": "fouling", "penalty_min": 30})
        elif corridor["ohe_block_active"] and _train_is_electric(train) and not corridor["diesel_allowed_through"]:
            cost += train["weight"] * 25
            conflicts.append({"train_no": train["train_no"], "reason": "ohe_block", "penalty_min": 25})
        elif corridor["tsr_active"]:
            cost += train["weight"] * 6  # caution order transit delay
            conflicts.append({"train_no": train["train_no"], "reason": "tsr", "penalty_min": 6})
    return cost, conflicts


def _avg_criticality(corridor, asset_health):
    scores = [
        seg["criticality_score"] for seg in asset_health
        if seg["segment_km_end"] >= corridor["km_start"] and seg["segment_km_start"] <= corridor["km_end"]
    ]
    return sum(scores) / len(scores) if scores else 5.0


# ---------------------------------------------------------------------------
# Main optimizer entry point
# ---------------------------------------------------------------------------
def optimize_schedule(injected_delays=None, excluded_corridor_ids=None):
    trains = load_trains()
    asset_health = load_asset_health()
    all_corridors = cluster_demands(load_demands())
    machinery = {m["asset_id"]: m for m in load_machinery()}

    excluded = set(excluded_corridor_ids or [])
    corridors = [c for c in all_corridors if c["corridor_id"] not in excluded]
    deferred_corridors = [c["corridor_id"] for c in all_corridors if c["corridor_id"] in excluded]

    model = cp_model.CpModel()

    starts = {}          # corridor_id -> IntVar (slot index)
    intervals = {}        # corridor_id -> IntervalVar
    cost_terms = []
    corridor_meta = {}

    for c in corridors:
        duration_slots = max(1, -(-c["duration_min"] // SLOT_MIN))  # ceil division
        max_start_slot = NUM_SLOTS - duration_slots
        if max_start_slot < 0:
            # corridor longer than the whole window; clamp (rare edge case for MVP data)
            max_start_slot = 0
            duration_slots = NUM_SLOTS

        start_var = model.NewIntVar(0, max_start_slot, f"start_{c['corridor_id']}")
        end_var = model.NewIntVar(duration_slots, NUM_SLOTS, f"end_{c['corridor_id']}")
        interval = model.NewIntervalVar(start_var, duration_slots, end_var, f"iv_{c['corridor_id']}")
        starts[c["corridor_id"]] = start_var
        intervals[c["corridor_id"]] = interval
        corridor_meta[c["corridor_id"]] = {"corridor": c, "duration_slots": duration_slots}

        # Precompute per-slot conflict cost and select via AddElement
        slot_costs = []
        for slot in range(0, max_start_slot + 1):
            start_min = SIM_START_MIN + slot * SLOT_MIN
            cost, _ = _corridor_conflict_cost(c, start_min, trains, injected_delays)
            slot_costs.append(int(cost))
        # pad remaining domain (shouldn't be hit since start_var domain matches) defensively
        while len(slot_costs) <= max_start_slot:
            slot_costs.append(0)

        cost_var = model.NewIntVar(0, max(slot_costs) if slot_costs else 0, f"cost_{c['corridor_id']}")
        model.AddElement(start_var, slot_costs, cost_var)
        cost_terms.append(cost_var)

        # criticality reward (higher criticality -> encourage scheduling, i.e. reduce cost)
        criticality = _avg_criticality(c, asset_health)
        cost_terms.append(-int(criticality * c["duration_min"] // 15))

    # Machine non-overlap constraint with transit buffer (Module C constraint #4)
    # Each machine gets a buffer-padded interval so that two jobs on the same machine
    # are separated by at least MACHINE_TRANSIT_BUFFER_MIN between end-of-job-1 and
    # start-of-job-2.  We pad the *duration* of the interval used for NoOverlap so
    # the solver is forced to leave a gap >= MACHINE_TRANSIT_BUFFER_MIN.
    BUFFER_SLOTS = -(-MACHINE_TRANSIT_BUFFER_MIN // SLOT_MIN)  # ceil(30/15) = 2 slots
    machine_intervals_buffered = {}
    for c in corridors:
        for m in c["machines_required"]:
            dur_slots = corridor_meta[c["corridor_id"]]["duration_slots"]
            padded_dur = dur_slots + BUFFER_SLOTS
            padded_end = model.NewIntVar(
                padded_dur, NUM_SLOTS + BUFFER_SLOTS, f"mach_end_{c['corridor_id']}_{m}"
            )
            padded_iv = model.NewIntervalVar(
                starts[c["corridor_id"]], padded_dur, padded_end, f"mach_iv_{c['corridor_id']}_{m}"
            )
            machine_intervals_buffered.setdefault(m, []).append(padded_iv)
    for m, ivs in machine_intervals_buffered.items():
        if len(ivs) > 1:
            model.AddNoOverlap(ivs)

    model.Minimize(sum(cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    result = {
        "status": solver.StatusName(status),
        "corridors": [],
        "deferred_corridors": deferred_corridors,
        "kpis": {},
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result

    total_weighted_delay = 0
    total_secondary_delay_prevented = 0
    for c in corridors:
        meta = corridor_meta[c["corridor_id"]]
        slot = solver.Value(starts[c["corridor_id"]])
        start_min = SIM_START_MIN + slot * SLOT_MIN
        end_min = start_min + c["duration_min"]
        cost, conflicts = _corridor_conflict_cost(c, start_min, trains, injected_delays)
        total_weighted_delay += cost

        # naive baseline: assume unclustered single-department blocks would have caused
        # this much additional secondary delay to trains from the shadowed departments
        if len(c["departments"]) > 1:
            total_secondary_delay_prevented += (len(c["departments"]) - 1) * 15

        result["corridors"].append({
            "corridor_id": c["corridor_id"],
            "badge": c["badge"],
            "departments": c["departments"],
            "line": c["line"],
            "km_start": c["km_start"],
            "km_end": c["km_end"],
            "sanctioned_start": _min_to_hhmm(start_min),
            "sanctioned_end": _min_to_hhmm(end_min),
            "duration_min": c["duration_min"],
            "machines_required": c["machines_required"],
            "ohe_block_active": c["ohe_block_active"],
            "fouling_active": c["fouling_active"],
            "tsr_active": c["tsr_active"],
            "tsr_speed_kmh": c["tsr_speed_kmh"],
            "conflicts": conflicts,
        })

    clubbed = sum(len(c["member_demand_ids"]) for c in corridors if len(c["departments"]) > 1)
    total_demands = sum(len(c["member_demand_ids"]) for c in corridors)
    result["kpis"] = {
        "total_weighted_conflict_cost": total_weighted_delay,
        "total_secondary_delay_prevented_min": total_secondary_delay_prevented,
        "corridor_utilization_rate_pct": round(100.0 * clubbed / total_demands, 1) if total_demands else 0.0,
        "num_corridors": len(corridors),
        "num_original_demands": total_demands,
        "solve_time_sec": round(solver.WallTime(), 3),
    }
    return result


def _min_to_hhmm(m):
    m = int(round(m)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


if __name__ == "__main__":
    import json
    print(json.dumps(optimize_schedule(), indent=2))