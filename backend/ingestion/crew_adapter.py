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
    sample_crew = [
        {"driver_id": "DRV-GZB-101", "driver_name": "R. K. Sharma (Loco Pilot)", "loco_no": "WAP-7 30214", "home_depot": "GZB", "linked_train_no": "20958 (Vande Bharat)", "duty_hours_remaining": 6.5, "status": "ON_DUTY"},
        {"driver_id": "DRV-GZB-104", "driver_name": "Amitabh Verma (Loco Pilot)", "loco_no": "WAP-7 30488", "home_depot": "GZB", "linked_train_no": "12424 (Rajdhani Exp)", "duty_hours_remaining": 7.2, "status": "ON_DUTY"},
        {"driver_id": "DRV-ALJN-201", "driver_name": "S. P. Singh (Sr. Loco Pilot)", "loco_no": "WAP-5 30012", "home_depot": "ALJN", "linked_train_no": "12004 (Shatabdi Exp)", "duty_hours_remaining": 5.5, "status": "ON_DUTY"},
        {"driver_id": "DRV-GZB-112", "driver_name": "V. K. Yadav (Loco Pilot)", "loco_no": "WAP-4 22560", "home_depot": "GZB", "linked_train_no": "14218 (Unchahar Exp)", "duty_hours_remaining": 4.8, "status": "ON_DUTY"},
        {"driver_id": "DRV-GZB-118", "driver_name": "Harpreet Singh (MEMU Pilot)", "loco_no": "MEMU-3011", "home_depot": "GZB", "linked_train_no": "64102 (MEMU)", "duty_hours_remaining": 3.2, "status": "ON_DUTY"},
        {"driver_id": "DRV-KRJ-301", "driver_name": "D. K. Yadav (Tamper Operator)", "loco_no": "CSM-301", "home_depot": "KRJ", "linked_train_no": "CSM-1 (Plasser Tamper)", "duty_hours_remaining": 4.0, "status": "ON_DUTY"},
        {"driver_id": "DRV-GZB-305", "driver_name": "Rajesh Kumar (BCM Operator)", "loco_no": "BCM-502", "home_depot": "GZB", "linked_train_no": "BCM-2 (Ballast Cleaner)", "duty_hours_remaining": 1.8, "status": "ON_DUTY"},
        {"driver_id": "DRV-DER-309", "driver_name": "M. K. Gupta (TRD Tower Car Op)", "loco_no": "TW-4001", "home_depot": "DER", "linked_train_no": "TOWER-WAGON-1 (TRD)", "duty_hours_remaining": 8.0, "status": "ON_DUTY"},
        {"driver_id": "DRV-ALJN-312", "driver_name": "S. K. Mishra (Turnout Tamper Op)", "loco_no": "UNM-903", "home_depot": "ALJN", "linked_train_no": "UNIMAT-3 (Turnout)", "duty_hours_remaining": 1.2, "status": "ON_DUTY"}
    ]
    return sample_crew

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
