"""
backend/clustering.py

Spatial Clustering & Shadowing Engine.
Groups BDMS demands that lie on the same physical corridor within a
5.0 km chainage distance into a single "Integrated Corridor Block",
with Civil as the primary block and TRD/S&T shadowed as secondary
blocks nested inside it.
"""

from backend.data_generator import load_demands

CLUSTER_RADIUS_KM = 5.0
DEPARTMENT_PRIORITY = {"CIVIL": 0, "TRD": 1, "SNT": 2}


def _midpoint(d):
    return (d["km_start"] + d["km_end"]) / 2.0


def _overlaps_within_radius(d1, d2, radius=CLUSTER_RADIUS_KM):
    # Two demands cluster if their km ranges are within `radius` km of each other,
    # regardless of exact line, since corridor shadowing spans the possession envelope.
    lo1, hi1 = d1["km_start"] - radius, d1["km_end"] + radius
    return not (hi1 < d2["km_start"] or lo1 > d2["km_end"])


def cluster_demands(demands=None):
    """Union-find style clustering of demands within CLUSTER_RADIUS_KM chainage."""
    if demands is None:
        demands = load_demands()

    n = len(demands)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if _overlaps_within_radius(demands[i], demands[j]):
                union(i, j)

    groups = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(demands[i])

    corridors = []
    for idx, (root, members) in enumerate(groups.items(), start=1):
        corridors.append(_build_corridor(f"CORR-{idx:02d}", members))

    corridors.sort(key=lambda c: c["km_start"])
    return corridors


def _build_corridor(corridor_id, members):
    members_sorted = sorted(members, key=lambda d: DEPARTMENT_PRIORITY.get(d["department"], 9))
    primary = next((d for d in members_sorted if d["department"] == "CIVIL"), members_sorted[0])
    secondary = [d for d in members_sorted if d["demand_id"] != primary["demand_id"]]

    km_start = min(d["km_start"] for d in members)
    km_end = max(d["km_end"] for d in members)
    duration = max(d["duration_min"] for d in members)  # Duration_Corridor = max(D_Civil, D_TRD, D_S&T)

    departments = sorted({d["department"] for d in members}, key=lambda x: DEPARTMENT_PRIORITY.get(x, 9))
    badge = "[" + " + ".join(departments) + "]"

    ohe_block_active = any(d.get("ohe_block_required") for d in members)
    fouling_active = any(d.get("fouling") for d in members)
    # Diesel movement is permitted through an OHE-blocked corridor only if nothing
    # in the corridor physically fouls the line.
    diesel_allowed_through = ohe_block_active and not fouling_active
    tsr_members = [d for d in members if d.get("tsr")]
    tsr_active = len(tsr_members) > 0
    tsr_speed = min((d["tsr_speed_kmh"] for d in tsr_members if d.get("tsr_speed_kmh")), default=None)

    machines = sorted({d["machine"] for d in members if d.get("machine")})
    line = primary.get("line", "COMMON")

    return {
        "corridor_id": corridor_id,
        "primary_demand": primary["demand_id"],
        "primary_department": primary["department"],
        "member_demand_ids": [d["demand_id"] for d in members],
        "departments": departments,
        "badge": badge,
        "line": line,
        "km_start": round(km_start, 2),
        "km_end": round(km_end, 2),
        "duration_min": duration,
        "ohe_block_active": ohe_block_active,
        "fouling_active": fouling_active,
        "diesel_allowed_through": diesel_allowed_through,
        "tsr_active": tsr_active,
        "tsr_speed_kmh": tsr_speed,
        "machines_required": machines,
        "multi_day": any(d.get("multi_day") for d in members),
        "members": members,
    }


def utilization_rate(corridors=None, demands=None):
    """% of demands whose work got clubbed into a multi-department corridor."""
    demands = demands or load_demands()
    corridors = corridors or cluster_demands(demands)
    clubbed = sum(len(c["member_demand_ids"]) for c in corridors if len(c["departments"]) > 1)
    total = len(demands)
    return round(100.0 * clubbed / total, 1) if total else 0.0


if __name__ == "__main__":
    for c in cluster_demands():
        print(c["corridor_id"], c["badge"], c["line"], c["km_start"], "-", c["km_end"],
              f"{c['duration_min']}min", "OHE" if c["ohe_block_active"] else "", "TSR" if c["tsr_active"] else "")
