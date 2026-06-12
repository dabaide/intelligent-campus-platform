"""
Cache Service
Provides caching strategies and performance optimization
"""

from typing import Any, Optional, Dict, List
import json
from datetime import datetime, timedelta
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis_client import RedisClient


class CacheService:
    """Service for managing cache operations"""
    
    # Cache expiration times (in seconds)
    CACHE_EXPIRY = {
        "search_results": 300,  # 5 minutes
        "user_profile": 900,  # 15 minutes
        "faq_list": 3600,  # 1 hour
        "document_list": 3600,  # 1 hour
        "agent_stats": 600,  # 10 minutes
        "system_health": 60,  # 1 minute
        "conversation": 1800,  # 30 minutes
    }
    
    def __init__(self, redis: RedisClient = None):
        self.redis = redis
        self.local_cache: Dict[str, Any] = {}
        self.local_cache_expiry: Dict[str, datetime] = {}
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and arguments"""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (str, int, float)):
                key_parts.append(str(arg))
            elif isinstance(arg, dict):
                key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest()[:8])
        
        # Add keyword arguments
        if kwargs:
            kwargs_str = json.dumps(kwargs, sort_keys=True)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])
        
        return ":".join(key_parts)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            # Check local cache first
            if key in self.local_cache:
                expiry = self.local_cache_expiry.get(key)
                if expiry and datetime.now() < expiry:
                    return self.local_cache[key]
                else:
                    del self.local_cache[key]
                    if key in self.local_cache_expiry:
                        del self.local_cache_expiry[key]
            
            # Check Redis cache
            if self.redis:
                value = await self.redis.get(key)
                if value:
                    return json.loads(value) if isinstance(value, str) else value
            
            return None
        
        except Exception as e:
            print(f"❌ Cache get error: {str(e)}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expiry_type: str = "default",
        custom_expiry: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        try:
            # Determine expiry time
            expiry_seconds = custom_expiry or self.CACHE_EXPIRY.get(expiry_type, 300)
            
            # Set in local cache
            self.local_cache[key] = value
            self.local_cache_expiry[key] = datetime.now() + timedelta(seconds=expiry_seconds)
            
            # Set in Redis cache
            if self.redis:
                await self.redis.set(
                    key,
                    json.dumps(value, default=str) if not isinstance(value, str) else value,
                    ex=expiry_seconds
                )
            
            return True
        
        except Exception as e:
            print(f"❌ Cache set error: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            # Delete from local cache
            if key in self.local_cache:
                del self.local_cache[key]
            if key in self.local_cache_expiry:
                del self.local_cache_expiry[key]
            
            # Delete from Redis cache
            if self.redis:
                await self.redis.delete(key)
            
            return True
        
        except Exception as e:
            print(f"❌ Cache delete error: {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all cache keys matching a pattern"""
        try:
            deleted_count = 0
            
            # Clear from local cache
            keys_to_delete = [k for k in self.local_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.local_cache[key]
                if key in self.local_cache_expiry:
                    del self.local_cache_expiry[key]
                deleted_count += 1
            
            # Clear from Redis cache
            if self.redis:
                redis_deleted = await self.redis.delete_pattern(f"*{pattern}*")
                deleted_count += redis_deleted
            
            return deleted_count
        
        except Exception as e:
            print(f"❌ Cache clear pattern error: {str(e)}")
            return 0
    
    async def get_search_results(
        self,
        query: str,
        category: Optional[str] = None,
        search_type: str = "hybrid"
    ) -> Optional[Dict[str, Any]]:
        """Get cached search results"""
        cache_key = self._generate_cache_key(
            "search",
            query,
            category=category,
            search_type=search_type
        )
        return await self.get(cache_key)
    
    async def set_search_results(
        self,
        query: str,
        results: Dict[str, Any],
        category: Optional[str] = None,
        search_type: str = "hybrid"
    ) -> bool:
        """Cache search results"""
        cache_key = self._generate_cache_key(
            "search",
            query,
            category=category,
            search_type=search_type
        )
        return await self.set(cache_key, results, expiry_type="search_results")
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user profile"""
        cache_key = self._generate_cache_key("user_profile", user_id)
        return await self.get(cache_key)
    
    async def set_user_profile(self, user_id: str, profile: Dict[str, Any]) -> bool:
        """Cache user profile"""
        cache_key = self._generate_cache_key("user_profile", user_id)
        return await self.set(cache_key, profile, expiry_type="user_profile")
    
    async def get_faq_list(self, category: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Get cached FAQ list"""
        cache_key = self._generate_cache_key("faq_list", category=category)
        return await self.get(cache_key)
    
    async def set_faq_list(self, faqs: List[Dict[str, Any]], category: Optional[str] = None) -> bool:
        """Cache FAQ list"""
        cache_key = self._generate_cache_key("faq_list", category=category)
        return await self.set(cache_key, faqs, expiry_type="faq_list")
    
    async def get_agent_stats(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """Get cached agent statistics"""
        cache_key = self._generate_cache_key("agent_stats", agent_type)
        return await self.get(cache_key)
    
    async def set_agent_stats(self, agent_type: str, stats: Dict[str, Any]) -> bool:
        """Cache agent statistics"""
        cache_key = self._generate_cache_key("agent_stats", agent_type)
        return await self.set(cache_key, stats, expiry_type="agent_stats")
    
    async def get_system_health(self) -> Optional[Dict[str, Any]]:
        """Get cached system health"""
        cache_key = "system_health"
        return await self.get(cache_key)
    
    async def set_system_health(self, health: Dict[str, Any]) -> bool:
        """Cache system health"""
        cache_key = "system_health"
        return await self.set(cache_key, health, expiry_type="system_health")
    
    async def invalidate_search_cache(self):
        """Invalidate all search cache"""
        return await self.clear_pattern("search:")
    
    async def invalidate_faq_cache(self):
        """Invalidate all FAQ cache"""
        return await self.clear_pattern("faq_list:")
    
    async def invalidate_user_cache(self, user_id: str):
        """Invalidate cache for a specific user"""
        return await self.clear_pattern(f"user_profile:{user_id}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        local_cache_size = len(self.local_cache)
        
        stats = {
            "local_cache_size": local_cache_size,
            "local_cache_keys": list(self.local_cache.keys())[:10],  # Show first 10 keys
            "timestamp": datetime.now().isoformat()
        }
        
        if self.redis:
            try:
                redis_info = await self.redis.redis.info()
                stats["redis_memory_used"] = redis_info.get("used_memory_human", "N/A")
                stats["redis_connected_clients"] = redis_info.get("connected_clients", 0)
            except Exception as e:
                stats["redis_error"] = str(e)
        
        return stats
    
    async def clear_all_cache(self) -> bool:
        """Clear all cache"""
        try:
            # Clear local cache
            self.local_cache.clear()
            self.local_cache_expiry.clear()
            
            # Clear Redis cache
            if self.redis:
                await self.redis.flushdb()
            
            return True
        
        except Exception as e:
            print(f"❌ Failed to clear all cache: {str(e)}")
            return False


class PerformanceMonitor:
    """Monitor performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.max_samples = 1000
    
    def record_metric(self, metric_name: str, value: float):
        """Record a performance metric"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        
        self.metrics[metric_name].append(value)
        
        # Keep only recent samples
        if len(self.metrics[metric_name]) > self.max_samples:
            self.metrics[metric_name] = self.metrics[metric_name][-self.max_samples:]
    
    def get_metric_stats(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get statistics for a metric"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return None
        
        values = self.metrics[metric_name]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": sorted(values)[len(values) // 2],
            "p95": sorted(values)[int(len(values) * 0.95)],
            "p99": sorted(values)[int(len(values) * 0.99)]
        }
    
    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get all metric statistics"""
        return {
            metric_name: self.get_metric_stats(metric_name)
            for metric_name in self.metrics
            if self.get_metric_stats(metric_name)
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics.clear()


# Global instances
_cache_service: Optional[CacheService] = None
_performance_monitor: Optional[PerformanceMonitor] = None


def get_cache_service(redis: RedisClient = None) -> CacheService:
    """Get or create cache service"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(redis)
    return _cache_service


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
