session_manager_py = ""
import json
import redis.asyncio as redis
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from app.models.session import UserSession
from app.config.settings import settings

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.session_timeout = timedelta(hours=24)  # Sessões expiram em 24h
        
    async def initialize(self):
        try:
            self.redis_client = redis.from_url(settings.redis_url)
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory storage.")
            self._sessions_memory = {}  # Fallback para memória
    
    async def get_or_create_session(self, phone_number: str) -> UserSession:
        session = await self.get_session(phone_number)
        
        if not session:
            session = UserSession(
                session_id=f"session_{phone_number}_{int(datetime.now().timestamp())}",
                phone_number=phone_number,
                current_agent=None,
                conversation_context={},
                message_history=[]
            )
            await self.save_session(session)
            logger.info(f"New session created for {phone_number}")
        
        return session
    
    async def get_session(self, phone_number: str) -> Optional[UserSession]:
        session_key = f"session:{phone_number}"
        
        try:
            if self.redis_client:
                session_data = await self.redis_client.get(session_key)
                if session_data:
                    data = json.loads(session_data)
                    session = UserSession(**data)
                    
                    # Verifica se sessão não expirou
                    if session.expires_at > datetime.now():
                        return session
                    else:
                        await self.delete_session(phone_number)
                        return None
            else:
                # Fallback para memória
                if hasattr(self, '_sessions_memory') and phone_number in self._sessions_memory:
                    return self._sessions_memory[phone_number]
                    
        except Exception as e:
            logger.error(f"Error retrieving session for {phone_number}: {e}")
        
        return None
    
    async def save_session(self, session: UserSession):
        session_key = f"session:{session.phone_number}"
        session.updated_at = datetime.now()
        
        try:
            if self.redis_client:
                session_data = session.model_dump_json()
                await self.redis_client.setex(
                    session_key,
                    int(self.session_timeout.total_seconds()),
                    session_data
                )
            else:
                # Fallback para memória
                if not hasattr(self, '_sessions_memory'):
                    self._sessions_memory = {}
                self._sessions_memory[session.phone_number] = session
                
        except Exception as e:
            logger.error(f"Error saving session for {session.phone_number}: {e}")
    
    async def delete_session(self, phone_number: str):
        session_key = f"session:{phone_number}"
        
        try:
            if self.redis_client:
                await self.redis_client.delete(session_key)
            else:
                if hasattr(self, '_sessions_memory') and phone_number in self._sessions_memory:
                    del self._sessions_memory[phone_number]
            
            logger.info(f"Session deleted for {phone_number}")
        except Exception as e:
            logger.error(f"Error deleting session for {phone_number}: {e}")
    
    async def get_active_sessions_count(self) -> int:
        try:
            if self.redis_client:
                keys = await self.redis_client.keys("session:*")
                return len(keys)
            else:
                return len(getattr(self, '_sessions_memory', {}))
        except Exception as e:
            logger.error(f"Error counting sessions: {e}")
            return 0
    
    async def cleanup_expired_sessions(self):
        try:
            if not self.redis_client and hasattr(self, '_sessions_memory'):
                # Cleanup para memória
                current_time = datetime.now()
                expired_sessions = [
                    phone for phone, session in self._sessions_memory.items()
                    if session.expires_at <= current_time
                ]
                for phone in expired_sessions:
                    del self._sessions_memory[phone]
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                    
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
