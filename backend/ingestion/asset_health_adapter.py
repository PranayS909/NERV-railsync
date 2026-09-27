"""
backend/ingestion/asset_health_adapter.py

Adapter for Track Geometry Car / OMS asset health data.
Mock mode: generates realistic synthetic data matching the real system's schema.
Live mode: would call the real API endpoint (placeholder for production).
"""
import os
import json
import random

MODE = os.environ.get('INGESTION_MODE', 'mock')

def fetch_live():
    """Return raw data in the source system's native schema."""
    if MODE == 'mock':
        return _generate_mock()
    else:
        raise NotImplementedError("Live ingestion for Asset Health not yet configured")

def to_internal(raw):
    """Map raw system data to RailSync-AI internal schema."""
    return [r.copy() for r in raw]

def _generate_mock():
    """Generate realistic synthetic data."""
    data = []
    # per-5km-segment readings across 150km route
    for i in range(30):
        start = float(i * 5)
        end = start + 5.0
        data.append({
            "segment_km_start": start,
            "segment_km_end": end,
            "track_geometry_index": random.randint(60, 100),
            "unevenness_mm": round(random.uniform(1.0, 5.0), 1),
            "twist_mm_per_m": round(random.uniform(0.5, 2.0), 1),
            "gauge_mm": round(random.uniform(1675.0, 1678.0), 1),
            "oms_vertical_g": round(random.uniform(0.05, 0.20), 2),
            "oms_lateral_g": round(random.uniform(0.05, 0.15), 2),
            "oms_flag_urgent": random.random() < 0.05,
            "overdue_maintenance_days": random.randint(0, 10) if random.random() < 0.2 else 0,
            "criticality_score": random.randint(1, 5),
            "last_tgc_run": "2026-09-15",
        })
    return data

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
