"""
backend/ingestion/tms_adapter.py

Adapter for Train Management System / NTES.
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
        raise NotImplementedError("Live ingestion for TMS not yet configured")

def to_internal(raw):
    """Map raw system data to RailSync-AI internal schema."""
    # The internal schema for trains needs the schedule from the base timetable (data_generator.py).
    # Since this is an ingestion mock, we'll pull the base timetable and merge.
    from data_generator import load_trains
    base_trains = load_trains()
    train_map = {t["train_no"]: t for t in base_trains}
    
    internal_trains = []
    for r in raw:
        t_no = r["train_no"]
        if t_no in train_map:
            # Copy base schedule and metadata
            internal = train_map[t_no].copy()
            # Overlay live data
            internal["current_km"] = r["current_km"]
            internal["current_delay_min"] = r["current_delay_min"]
            internal["speed_kmh"] = r["speed_kmh"]
            internal_trains.append(internal)
    
    # Also include base trains not in TMS just in case, or only TMS trains.
    # We will just return the ones in TMS to simulate live tracked trains.
    return internal_trains

def _generate_mock():
    """Generate realistic synthetic data."""
    # We'll pull from data_generator.py just to have valid train_nos.
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data_generator import load_trains
    base_trains = load_trains()
    
    mock_data = []
    # Take up to 14 trains
    for t in base_trains[:14]:
        mock_data.append({
            "train_no": t["train_no"],
            "train_name": t.get("name", "Unknown Express"),
            "current_km": random.uniform(10.0, 140.0),
            "current_delay_min": random.randint(0, 30),
            "last_station": "DKDE",
            "next_station": "WAIR",
            "eta_next_station": "08:45",
            "speed_kmh": random.randint(60, 120),
            "timestamp": "2026-09-25T08:32:00+05:30",
            "direction": t.get("direction", "DOWN"),
            "type": t.get("type", "EXPRESS"),
            "priority": t.get("priority", 2),
            "weight": t.get("weight", 40),
        })
    return mock_data

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
