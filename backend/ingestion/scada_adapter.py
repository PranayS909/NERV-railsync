"""
backend/ingestion/scada_adapter.py

Adapter for SCADA / OHE Health Telemetry.
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
        raise NotImplementedError("Live ingestion for SCADA not yet configured")

def to_internal(raw):
    """Map raw system data to RailSync-AI internal schema."""
    return [r.copy() for r in raw]

def _generate_mock():
    """Generate realistic synthetic data."""
    data = []
    # ~30 items across 150km
    for i in range(30):
        km = round(random.uniform(0.0, 150.0), 1)
        data.append({
            "equipment_id": f"OHE-MAST-{km}",
            "km": km,
            "type": random.choice(["mast", "dropper", "breaker", "insulator"]),
            "voltage_kv": round(random.uniform(24.5, 27.5), 1),
            "current_a": random.randint(200, 450),
            "temp_c": random.randint(30, 60),
            "fault_flag": random.random() < 0.05,
            "fault_description": "High temperature" if random.random() < 0.05 else None,
            "last_inspected": "2026-09-20",
            "line": random.choice(["UP", "DOWN"]),
        })
    return data

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
