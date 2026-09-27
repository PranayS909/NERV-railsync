import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion import (
    IngestStore,
    bdms_adapter,
    tms_adapter,
    fois_adapter,
    scada_adapter,
    crew_adapter,
    asset_health_adapter,
)

def test_bdms_adapter():
    raw = bdms_adapter.fetch_live()
    assert len(raw) >= 10
    internal = bdms_adapter.to_internal(raw)
    assert len(internal) == len(raw)
    # Check stripped fields and existing key fields
    for d in internal:
        assert "demand_id" in d
        assert "department" in d
        assert "submitted_by" not in d

def test_tms_adapter():
    raw = tms_adapter.fetch_live()
    assert len(raw) > 0
    internal = tms_adapter.to_internal(raw)
    assert len(internal) == len(raw)
    for t in internal:
        assert "train_no" in t
        assert "current_km" in t
        assert "schedule" in t  # Merged from base schedule

def test_fois_adapter():
    raw = fois_adapter.fetch_live()
    assert len(raw) >= 5
    internal = fois_adapter.to_internal(raw)
    assert len(internal) == len(raw)
    for f in internal:
        assert "rake_id" in f
        assert "commodity" in f

def test_scada_adapter():
    raw = scada_adapter.fetch_live()
    assert len(raw) > 0
    internal = scada_adapter.to_internal(raw)
    assert len(internal) == len(raw)
    for s in internal:
        assert "equipment_id" in s
        assert "voltage_kv" in s

def test_crew_adapter():
    raw = crew_adapter.fetch_live()
    assert len(raw) > 0
    internal = crew_adapter.to_internal(raw)
    assert len(internal) == len(raw)
    for c in internal:
        assert "driver_id" in c
        assert "loco_no" in c

def test_asset_health_adapter():
    raw = asset_health_adapter.fetch_live()
    assert len(raw) > 0
    internal = asset_health_adapter.to_internal(raw)
    assert len(internal) == len(raw)
    for a in internal:
        assert "segment_km_start" in a
        assert "track_geometry_index" in a

def test_ingest_store():
    store = IngestStore()
    store.refresh_all()
    
    status = store.status()
    assert status["sources"]["bdms"] > 0
    assert status["sources"]["tms"] > 0
    assert status["sources"]["fois"] > 0
    assert status["sources"]["scada"] > 0
    assert status["sources"]["crew"] > 0
    assert status["sources"]["asset_health"] > 0
    assert status["last_refresh"] is not None
