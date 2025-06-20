from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

class LLMSettings(BaseSettings):
    # Ollama Configuration
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://192.168.15.31:11435")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    # OpenAI Configuration (fallback)
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # LLM General Settings
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "500"))
    timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))
    
    # Agent Settings
    agent_memory_size: int = int(os.getenv("AGENT_MEMORY_SIZE", "10"))
    context_window: int = int(os.getenv("CONTEXT_WINDOW", "4000"))
    
    # Available Models
    available_models: List[str] = [
        "llama3.1:8b",
        "llama3.1:70b", 
        "qwen2.5:7b",
        "mistral:7b",
        "codellama:7b"
    ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # IMPORTANTE: Ignora campos extras do .env
        env_prefix = ""   # Não usa prefixo

# Cria instância com valores já carregados
llm_settings = LLMSettings(
    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://192.168.15.31:11435"),
    ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
    openai_api_key=os.getenv("OPENAI_API_KEY", None),
    openai_model=os.getenv("OPENAI_MODEL", "gpt-4"),
    temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
    max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
    timeout=int(os.getenv("LLM_TIMEOUT", "30")),
    agent_memory_size=int(os.getenv("AGENT_MEMORY_SIZE", "10")),
    context_window=int(os.getenv("CONTEXT_WINDOW", "4000"))
)