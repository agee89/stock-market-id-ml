import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_HOST: str
    DB_PORT: int = 5432

    # API
    YAHOO_API_KEY: str | None = None
    ALPHA_VANTAGE_KEY: str | None = None

    # Model Configuration
    MODEL_RETRAIN_INTERVAL: int = 7
    PREDICTION_CONFIDENCE_THRESHOLD: float = 0.6
    LEARNING_RATE: float = 0.001

    # Stock Configuration
    # Added ^JKSE (IHSG) and IDR=X (USDIDR) for Macro Features
    DEFAULT_STOCKS: str = "BBCA.JK,BBRI.JK,TLKM.JK,ASII.JK,UNVR.JK,^JKSE,IDR=X"
    TIMEFRAME: str = "1d"
    LOOKBACK_DAYS: int = 3650

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
