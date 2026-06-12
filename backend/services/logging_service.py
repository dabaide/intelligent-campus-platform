"""
System Logging and Monitoring Service
Handles detailed logging, monitoring, and system health tracking
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta
from enum import Enum
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
import logging

from core.redis_client import RedisClient


class LogLevel(str, Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemLog:
    """In-memory system log storage"""
    
    def __init__(self, max_logs: int = 10000):
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = max_logs
        self.logger = logging.getLogger("intelligent_campus")
    
    def log(
        self,
        level: LogLevel,
        message: str,
        component: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Add a log entry
        
        Args:
            level: Log level
            message: Log message
            component: Component name
            details: Additional details
            user_id: Associated user ID
        
        Returns:
            Log entry
        """
        log_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
            "component": component,
            "details": details or {},
            "user_id": str(user_id) if user_id else None
        }
        
        self.logs.append(log_entry)
        
        # Keep only recent logs in memory
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        # Also log to Python logger
        log_func = getattr(self.logger, level.value.lower())
        log_func(f"[{component}] {message}")
        
        return log_entry
    
    def get_logs(
        self,
        level: Optional[LogLevel] = None,
        component: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get logs with optional filtering"""
        filtered_logs = self.logs
        
        if level:
            filtered_logs = [log for log in filtered_logs if log["level"] == level.value]
        
        if component:
            filtered_logs = [log for log in filtered_logs if log["component"] == component]
        
        # Return in reverse chronological order
        filtered_logs = sorted(filtered_logs, key=lambda x: x["timestamp"], reverse=True)
        
        return filtered_logs[offset:offset + limit]
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error logs"""
        error_logs = [
            log for log in self.logs
            if log["level"] in ["ERROR", "CRITICAL"]
        ]
        error_logs = sorted(error_logs, key=lambda x: x["timestamp"], reverse=True)
        return error_logs[:limit]
    
    def clear_old_logs(self, days: int = 7):
        """Clear logs older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)
        self.logs = [
            log for log in self.logs
            if datetime.fromisoformat(log["timestamp"]) > cutoff
        ]


class MonitoringService:
    """Service for system monitoring and health checks"""
    
    def __init__(self, db: AsyncSession, redis: RedisClient = None):
        self.db = db
        self.redis = redis
        self.system_log = SystemLog()
        self.metrics = {
            "api_requests": 0,
            "api_errors": 0,
            "agent_interactions": 0,
            "successful_interactions": 0,
            "avg_response_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    def log_event(
        self,
        level: LogLevel,
        message: str,
        component: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Log an event"""
        return self.system_log.log(level, message, component, details, user_id)
    
    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time_ms: float,
        user_id: Optional[uuid.UUID] = None
    ):
        """Log API request"""
        self.metrics["api_requests"] += 1
        
        if status_code >= 400:
            self.metrics["api_errors"] += 1
        
        self.log_event(
            level=LogLevel.INFO if status_code < 400 else LogLevel.WARNING,
            message=f"API Request: {method} {path}",
            component="API",
            details={
                "method": method,
                "path": path,
                "status_code": status_code,
                "response_time_ms": response_time_ms
            },
            user_id=user_id
        )
    
    def log_agent_interaction(
        self,
        agent_type: str,
        task_type: str,
        success: bool,
        execution_time_ms: float,
        user_id: Optional[uuid.UUID] = None,
        error_message: Optional[str] = None
    ):
        """Log agent interaction"""
        self.metrics["agent_interactions"] += 1
        if success:
            self.metrics["successful_interactions"] += 1
        
        self.log_event(
            level=LogLevel.INFO if success else LogLevel.ERROR,
            message=f"Agent Interaction: {agent_type} - {task_type}",
            component="Agent",
            details={
                "agent_type": agent_type,
                "task_type": task_type,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "error": error_message
            },
            user_id=user_id
        )
    
    def log_cache_operation(
        self,
        operation: str,
        key: str,
        hit: bool,
        execution_time_ms: float
    ):
        """Log cache operation"""
        if hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        self.log_event(
            level=LogLevel.DEBUG,
            message=f"Cache {operation}: {key}",
            component="Cache",
            details={
                "operation": operation,
                "key": key,
                "hit": hit,
                "execution_time_ms": execution_time_ms
            }
        )
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        total_requests = self.metrics["api_requests"]
        error_rate = (
            (self.metrics["api_errors"] / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        interaction_success_rate = (
            (self.metrics["successful_interactions"] / self.metrics["agent_interactions"] * 100)
            if self.metrics["agent_interactions"] > 0 else 0
        )
        
        cache_hit_rate = (
            (self.metrics["cache_hits"] / (self.metrics["cache_hits"] + self.metrics["cache_misses"]) * 100)
            if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0 else 0
        )
        
        # Determine overall health status
        if error_rate > 10 or interaction_success_rate < 80:
            health_status = "degraded"
        elif error_rate > 5 or interaction_success_rate < 90:
            health_status = "warning"
        else:
            health_status = "healthy"
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "total_api_requests": self.metrics["api_requests"],
                "api_error_rate": round(error_rate, 2),
                "agent_interaction_success_rate": round(interaction_success_rate, 2),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "total_agent_interactions": self.metrics["agent_interactions"]
            },
            "recent_errors": len(self.system_log.get_recent_errors())
        }
    
    def get_logs(
        self,
        level: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get system logs"""
        log_level = LogLevel[level.upper()] if level else None
        return self.system_log.get_logs(level=log_level, component=component, limit=limit)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics.copy()
        }
    
    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = {
            "api_requests": 0,
            "api_errors": 0,
            "agent_interactions": 0,
            "successful_interactions": 0,
            "avg_response_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }


# Global monitoring service instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service(db: AsyncSession, redis: RedisClient = None) -> MonitoringService:
    """Get or create monitoring service"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService(db, redis)
    return _monitoring_service
