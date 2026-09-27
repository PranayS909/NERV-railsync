"""
backend/ingestion/bdms_adapter.py

Adapter for BDMS.
Mock mode: generates realistic synthetic data matching the real system's schema.
Live mode: would call the real API endpoint (placeholder for production).
"""
import os
import json
from datetime import datetime, timezone

MODE = os.environ.get('INGESTION_MODE', 'mock')

def fetch_live():
    """Return raw data in the source system's native schema."""
    if MODE == 'mock':
        return _generate_mock()
    else:
        raise NotImplementedError("Live ingestion for BDMS not yet configured")

def to_internal(raw):
    """Map raw system data to RailSync-AI internal schema."""
    internal_demands = []
    for d in raw:
        # Strip BDMS-specific fields
        internal = d.copy()
        for key in ["submitted_by", "approved_by", "submitted_at", "status", "priority_score"]:
            internal.pop(key, None)
        internal_demands.append(internal)
    return internal_demands

def _generate_mock():
    """Generate realistic synthetic data."""
    # Start with the core overlap trio required by clustering.py tests
    demands = [
        {
            "demand_id": "DEM-CIV-01",
            "department": "CIVIL",
            "line": "DOWN",
            "km_start": 32.0,
            "km_end": 36.5,
            "work_nature": "Track Tamping",
            "duration_min": 180,
            "machine": "CSM-1",
            "fouling": True,
            "ohe_block_required": False,
            "tsr": True,
            "tsr_speed_kmh": 30,
            "multi_day": False,
            "submitted_by": "SSE/P-Way/GZB",
            "approved_by": "Sr.DEN/Coord/GZB",
            "submitted_at": "2026-09-25T08:30:00+05:30",
            "status": "APPROVED",
            "priority_score": 8.5,
        },
        {
            "demand_id": "DEM-TRD-01",
            "department": "TRD",
            "line": "DOWN",
            "km_start": 33.0,
            "km_end": 35.0,
            "work_nature": "Cantilever & Insulator Replacement",
            "duration_min": 120,
            "machine": "TOWER-WAGON-1",
            "fouling": False,
            "ohe_block_required": True,
            "diesel_through_allowed": True,
            "tsr": False,
            "tsr_speed_kmh": None,
            "multi_day": False,
            "overlaps_with": "DEM-CIV-01",
            "submitted_by": "SSE/TRD/GZB",
            "approved_by": "Sr.DEE/TRD/GZB",
            "submitted_at": "2026-09-25T09:00:00+05:30",
            "status": "APPROVED",
            "priority_score": 7.0,
        },
        {
            "demand_id": "DEM-SNT-01",
            "department": "SNT",
            "station": "AJR",
            "line": "COMMON",
            "km_start": 35.4,
            "km_end": 35.4,
            "work_nature": "Point Machine Overhaul & Track Circuit Tuning",
            "duration_min": 90,
            "machine": None,
            "fouling": False,
            "ohe_block_required": False,
            "disconnection_required": True,
            "tsr": False,
            "tsr_speed_kmh": None,
            "multi_day": False,
            "adjacent_to": "DEM-CIV-01",
            "submitted_by": "SSE/SIG/AJR",
            "approved_by": "Sr.DSTE/GZB",
            "submitted_at": "2026-09-25T10:15:00+05:30",
            "status": "APPROVED",
            "priority_score": 6.5,
        }
    ]
    
    # Generate ~7 more mock demands to meet the 10-15 requirement
    for i in range(2, 9):
        demands.append({
            "demand_id": f"BDMS-CIV-00{i}",
            "department": "CIVIL",
            "line": "UP",
            "km_start": 80.0 + i,
            "km_end": 82.0 + i,
            "work_nature": "Track Maintenance",
            "duration_min": None if i % 3 == 0 else 180,
            "machine": f"BCM-{i}",
            "fouling": True,
            "ohe_block_required": False,
            "tsr": False,
            "tsr_speed_kmh": None,
            "multi_day": False,
            "submitted_by": "SSE/P-Way",
            "approved_by": "Sr.DEN",
            "submitted_at": "2026-09-25T08:30:00+05:30",
            "status": "APPROVED",
            "priority_score": 8.0,
        })
    return demands

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
