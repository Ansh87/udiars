"""UDIARS Data Ingestion Layer — live API clients with synthetic fallbacks."""
from .usgs_nwis import USGSNWISClient
from .noaa_mrms import NOAAMRMSClient
from .nasa_firms import NASAFIRMSClient
from .usgs_earthquake import USGSEarthquakeClient
from .open_meteo import OpenMeteoClient
from .facilities import get_facilities

__all__ = [
    "USGSNWISClient",
    "NOAAMRMSClient",
    "NASAFIRMSClient",
    "USGSEarthquakeClient",
    "OpenMeteoClient",
    "get_facilities",
]
