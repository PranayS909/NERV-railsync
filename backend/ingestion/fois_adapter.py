"""
backend/ingestion/fois_adapter.py

Adapter for FOIS (Freight Operations Information System).
Mock mode: generates realistic synthetic data matching the real system's schema.
Live mode: would call the real API endpoint (placeholder for production).
"""
import os
import json

MODE = os.environ.get('INGESTION_MODE', 'mock')

def fetch_live():
    """Return raw data in the source system's native schema."""
    if MODE == 'mock':
        return _generate_mock()
    else:
        raise NotImplementedError("Live ingestion for FOIS not yet configured")

def to_internal(raw):
    """Map raw system data to RailSync-AI internal schema."""
    # For now, just pass through the mapped fields.
    return [r.copy() for r in raw]

def _generate_mock():
    """Generate realistic synthetic data."""
    return [
        {
            "rake_id": "BOXN_COAL_UP",
            "commodity": "Coal",
            "origin": "ALJN",
            "destination": "GZB",
            "scheduled_departure": "07:15",
            "forecast_uncertainty_min": 20,
            "wagons": 58,
            "gross_tonnes": 4200,
            "current_status": "RUNNING",
            "last_interchange": "KRJ",
        },
        {
            "rake_id": "BCN_FOOD_DN",
            "commodity": "Food Grains",
            "origin": "GZB",
            "destination": "ALJN",
            "scheduled_departure": "09:30",
            "forecast_uncertainty_min": 15,
            "wagons": 42,
            "gross_tonnes": 3100,
            "current_status": "SCHEDULED",
            "last_interchange": "GZB",
        },
        {
            "rake_id": "CONTAINER_CONCOR",
            "commodity": "Containers",
            "origin": "DER",
            "destination": "ALJN",
            "scheduled_departure": "11:00",
            "forecast_uncertainty_min": 10,
            "wagons": 45,
            "gross_tonnes": 2800,
            "current_status": "ARRIVED",
            "last_interchange": "ALJN",
        },
        {
            "rake_id": "BTPN_OIL_UP",
            "commodity": "Oil",
            "origin": "ALJN",
            "destination": "GZB",
            "scheduled_departure": "12:20",
            "forecast_uncertainty_min": 25,
            "wagons": 50,
            "gross_tonnes": 3800,
            "current_status": "RUNNING",
            "last_interchange": "SOM",
        },
        {
            "rake_id": "BOBRN_STEEL_DN",
            "commodity": "Steel",
            "origin": "GZB",
            "destination": "ALJN",
            "scheduled_departure": "14:45",
            "forecast_uncertainty_min": -15,
            "wagons": 55,
            "gross_tonnes": 4100,
            "current_status": "SCHEDULED",
            "last_interchange": "GZB",
        }
    ]

if __name__ == '__main__':
    print(json.dumps(fetch_live(), indent=2)[:3000])
