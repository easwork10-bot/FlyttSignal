from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://flyttsignal:flyttsignal@localhost:5432/flyttsignal"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    uppsala_bostadsformedling_live_enabled: bool = False
    uppsala_bostadsformedling_graphql_url: str = "https://www.bostad.uppsala.se/mypages/api"
    uppsala_bostadsformedling_user_agent: str = "FlyttSignal/0.4 UBF-public-listings"
    uppsala_bostadsformedling_max_items: int = 500
    uppsala_bostadsformedling_timeout_seconds: float = 30
    uppsala_bostadsformedling_detail_enabled: bool = False
    uppsala_bostadsformedling_detail_concurrency: int = 4
    uppsala_bostadsformedling_listing_lifecycle_enabled: bool = False
    uppsala_bostadsformedling_listing_lifecycle_grace_runs: int = 2
    heimstaden_live_enabled: bool = False
    heimstaden_uppsala_url: str = "https://heimstaden.com/se/sok-lagenhet/?text=Uppsala"
    heimstaden_user_agent: str = "FlyttSignal/0.3 Heimstaden-Uppsala-listings"
    heimstaden_max_items: int = 25
    homeq_public_live_enabled: bool = False
    homeq_public_search_api_url: str = "https://www.homeq.se/api/v3/search"
    homeq_public_user_agent: str = "FlyttSignal/0.5 HomeQ-Uppsala-public-listings"
    homeq_public_max_items: int = 100
    homeq_public_page_size: int = 10
    homeq_public_concurrency: int = 4
    homeq_public_timeout_seconds: float = 30
    homeq_uppsala_min_lat: float = 59.77578261859438
    homeq_uppsala_max_lat: float = 59.9081353161649
    homeq_uppsala_min_lng: float = 17.452387788735052
    homeq_uppsala_max_lng: float = 17.829660243898616
    homeq_uppsala_zoom: float = 11.17
    hsb_public_live_enabled: bool = False
    hsb_public_uppsala_url: str = "https://www.hsb.se/sok-bostad/sok-hyresratter/uppsala/"
    hsb_public_user_agent: str = "FlyttSignal/0.5 HSB-Uppsala-public-listings"
    hsb_public_max_items: int = 50
    hsb_public_timeout_seconds: float = 30
    worker_poll_seconds: int = 30
    worker_stale_run_minutes: int = 30
    rental_listing_revisions_enabled: bool = False
    rental_signal_shadow_enabled: bool = False
    rental_signal_inference_enabled: bool = False
    scb_live_enabled: bool = False
    scb_api_base_url: str = "https://api.scb.se/OV0104/v2beta/api/v2"
    scb_user_agent: str = "FlyttSignal/0.2 SCB-benchmark-adapter"
    lantmateriet_live_enabled: bool = False
    lantmateriet_api_base_url: str = (
        "https://api-ver.lantmateriet.se/distribution/produkter/belagenhetsadress/v4.2"
    )
    lantmateriet_token_url: str = "https://apimanager-ver.lantmateriet.se/oauth2/token"
    lantmateriet_client_id: str | None = None
    lantmateriet_client_secret: str | None = None
    lantmateriet_user_agent: str = "FlyttSignal/0.2 Lantmateriet-address-enrichment"
    uppsala_open_data_live_enabled: bool = False
    uppsala_open_data_api_base_url: str = (
        "https://kartportal.uppsala.se/mapping/rest/services/"
        "iOpenData/OpenData_Byggnader/MapServer/1"
    )
    uppsala_open_data_user_agent: str = "FlyttSignal/0.2 Uppsala-open-data-buildings"
    uppsala_open_data_max_features: int = 100
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
