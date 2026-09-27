"""
backend/ingestion/crew_adapter.py

Adapter for CREW/LOCO Rostering System.
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
        raise NotImplementedError("Live ingestion for CREW not yet configured")

def to_internal(raw):
    """Map raw system data to RailSync-AI internal schema."""
    return [r.copy() for r in raw]

def _generate_mock():
    """Generate realistic synthetic data."""
    data = []
    # 8-10 crew members
    for i in range(10):
        data.append({
            "loco_no": f"WAP-7 {30000 + random.randint(100, 999)}",
            "driver_id": f"DRV-GZB-{i:03d}",
            "driver_name": f"Driver {i}",
            "duty_start": f"{random.randint(4, 12):02d}:00",
            "duty_hours_remaining": round(random.uniform(2.0, 8.0), 1),
            "home_depot": random.choice(["GZB", "ALJN"]),
            "current_km": round(random.uniform(0.0, 150.0), 1),
            "linked_train_no": str(random.choice([20958, 12424, 12004, 14218, 64102])),
            "status": random.choice(["ON_DUTY", "RESTING", "AVAILABLE"]),
        })
    return data

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
