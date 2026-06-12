import redis.asyncio as redis
from typing import Optional, Any
import json
import pickle
from core.config import settings

# [高频缓存与限流连接池单例]:
# 维护全局 Redis 客户端。专用于 API 接口防刷限流(Rate Limiting)、
# 高频意图缓存拦截，以及分布式架构下的热点会话状态(Session Context)极速存取。
class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # We'll handle encoding manually
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            # Test connection
            await self.redis.ping()
            print("✅ Redis connected successfully")
        except Exception as e:
            print(f"⚠️ Redis connection failed: {str(e)} - Running without Redis cache")
            self.redis = None
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
    
    async def set_json(self, key: str, value: Any, expire: int = None) -> bool:
        """Store JSON data in Redis"""
        if not self.redis:
            return False
        try:
            json_data = json.dumps(value, ensure_ascii=False)
            result = await self.redis.set(key, json_data, ex=expire)
            return result
        except Exception as e:
            print(f"Error setting JSON in Redis: {str(e)}")
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Retrieve JSON data from Redis"""
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data.decode('utf-8'))
            return None
        except Exception as e:
            print(f"Error getting JSON from Redis: {str(e)}")
            return None
    
    async def set_pickle(self, key: str, value: Any, expire: int = None) -> bool:
        """Store pickled data in Redis"""
        if not self.redis:
            return False
        try:
            pickled_data = pickle.dumps(value)
            result = await self.redis.set(key, pickled_data, ex=expire)
            return result
        except Exception as e:
            print(f"Error setting pickle in Redis: {str(e)}")
            return False
    
    async def get_pickle(self, key: str) -> Optional[Any]:
        """Retrieve pickled data from Redis"""
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            print(f"Error getting pickle from Redis: {str(e)}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self.redis:
            return False
        try:
            result = await self.redis.delete(key)
            return bool(result)
        except Exception as e:
            print(f"Error deleting from Redis: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self.redis:
            return False
        try:
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            print(f"Error checking existence in Redis: {str(e)}")
            return False
    
    async def set_conversation_context(self, user_id: str, conversation_id: str, context: dict, expire: int = 3600):
        """Store conversation context"""
        key = f"conversation:{user_id}:{conversation_id}"
        return await self.set_json(key, context, expire)
    
    async def get_conversation_context(self, user_id: str, conversation_id: str) -> Optional[dict]:
        """Retrieve conversation context"""
        key = f"conversation:{user_id}:{conversation_id}"
        return await self.get_json(key)
    
    async def cache_agent_response(self, agent_type: str, query_hash: str, response: dict, expire: int = 1800):
        """Cache agent response"""
        key = f"agent_cache:{agent_type}:{query_hash}"
        return await self.set_json(key, response, expire)
    
    async def get_cached_agent_response(self, agent_type: str, query_hash: str) -> Optional[dict]:
        """Retrieve cached agent response"""
        key = f"agent_cache:{agent_type}:{query_hash}"
        return await self.get_json(key)

# Global Redis client instance
redis_client = RedisClient()

async def init_redis():
    """Initialize Redis client"""
    await redis_client.connect()

async def get_redis() -> RedisClient:
    """Dependency for getting Redis client"""
    return redis_client
