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
    scada_units = [
        {"equipment_id": "OHE-GZB-TSS01", "km": 0.0, "type": "breaker", "voltage_kv": 25.2, "current_a": 320, "temp_c": 38, "temperature_c": 38, "fault_flag": False, "fault_description": None, "last_inspected": "2026-09-24", "line": "DOWN"},
        {"equipment_id": "OHE-DER-SP01", "km": 26.2, "type": "insulator", "voltage_kv": 24.8, "current_a": 290, "temp_c": 42, "temperature_c": 42, "fault_flag": False, "fault_description": None, "last_inspected": "2026-09-22", "line": "UP"},
        {"equipment_id": "OHE-AJR-SS02", "km": 35.4, "type": "dropper", "voltage_kv": 23.9, "current_a": 410, "temp_c": 64, "temperature_c": 64, "fault_flag": True, "fault_description": "Contact wire jumper hotspot (35.4 km)", "last_inspected": "2026-09-27", "line": "DOWN"},
        {"equipment_id": "OHE-DKDE-SP02", "km": 43.5, "type": "mast", "voltage_kv": 25.0, "current_a": 310, "temp_c": 40, "temperature_c": 40, "fault_flag": False, "fault_description": None, "last_inspected": "2026-09-21", "line": "COMMON"},
        {"equipment_id": "OHE-KRJ-TSS02", "km": 83.1, "type": "breaker", "voltage_kv": 24.6, "current_a": 380, "temp_c": 45, "temperature_c": 45, "fault_flag": False, "fault_description": None, "last_inspected": "2026-09-25", "line": "UP"},
        {"equipment_id": "OHE-KRJ-SS03", "km": 86.5, "type": "insulator", "voltage_kv": 23.7, "current_a": 430, "temp_c": 68, "temperature_c": 68, "fault_flag": True, "fault_description": "Overhead cantilever insulator arc warning (86.5 km)", "last_inspected": "2026-09-27", "line": "UP"},
        {"equipment_id": "OHE-SOM-SP03", "km": 110.2, "type": "mast", "voltage_kv": 25.1, "current_a": 305, "temp_c": 39, "temperature_c": 39, "fault_flag": False, "fault_description": None, "last_inspected": "2026-09-20", "line": "UP"},
        {"equipment_id": "OHE-ALJN-TSS03", "km": 150.0, "type": "breaker", "voltage_kv": 25.3, "current_a": 340, "temp_c": 41, "temperature_c": 41, "fault_flag": False, "fault_description": None, "last_inspected": "2026-09-26", "line": "DOWN"}
    ]
    return scada_units

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
