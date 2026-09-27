import os
from datetime import datetime

class IngestStore:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance
    
    def __init__(self):
        if self._initialised:
            return
        self._initialised = True
        self.demands = []
        self.trains = []
        self.freight = []
        self.scada = []
        self.crew = []
        self.asset_health = []
        self.last_refresh = None
        self._mode = os.environ.get('INGESTION_MODE', 'mock')
    
    def refresh_all(self):
        from . import bdms_adapter
        from . import tms_adapter
        from . import fois_adapter
        from . import scada_adapter
        from . import crew_adapter
        from . import asset_health_adapter
        
        # Pull live data and map to internal schema
        self.demands = bdms_adapter.to_internal(bdms_adapter.fetch_live())
        self.trains = tms_adapter.to_internal(tms_adapter.fetch_live())
        self.freight = fois_adapter.to_internal(fois_adapter.fetch_live())
        self.scada = scada_adapter.to_internal(scada_adapter.fetch_live())
        self.crew = crew_adapter.to_internal(crew_adapter.fetch_live())
        self.asset_health = asset_health_adapter.to_internal(asset_health_adapter.fetch_live())
        
        self.last_refresh = datetime.now(tz=__import__('datetime').timezone.utc)
    
    def status(self):
        return {
            "sources": {
                "bdms": len(self.demands),
                "tms": len(self.trains),
                "fois": len(self.freight),
                "scada": len(self.scada),
                "crew": len(self.crew),
                "asset_health": len(self.asset_health),
            },
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "mode": self._mode
        }
