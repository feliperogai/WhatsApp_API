from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # LLM
    ollama_urls: List[str] = ["http://localhost:11434"]
    ollama_models: List[str] = ["llama3:latest"]
    llm_pool_size: int = 2
    llm_timeout: int = 30
    
    # Queue
    max_queue_size: int = 1000
    max_workers: int = 3
    max_retries: int = 3
    retry_delays: List[int] = [5, 10, 30]
    
    # Rate Limiting
    global_rate_limit: float = 10  # per minute
    global_burst: int = 5
    user_rate_limit: float = 3     # per minute
    user_burst: int = 2
    
    # Cache
    cache_ttl: int = 3600
    max_cache_size: int = 1000
    
    # Application
    environment: str = "production"
    log_level: str = "INFO"
    port: int = 8000

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="allow"
    )

    @field_validator('retry_delays', mode='before')
    def parse_retry_delays(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                # fallback para split por vírgula
                return [int(x) for x in v.split(',') if x.strip().isdigit()]
        return v

settings = Settings()