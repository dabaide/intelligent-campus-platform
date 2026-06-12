"""
System Monitoring and Logging API Endpoints
Provides system health, logs, and performance metrics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from models.user import User
from api.deps import get_current_admin_user
from services.logging_service import MonitoringService, LogLevel
from services.cache_service import get_cache_service, get_performance_monitor

router = APIRouter()


@router.get("/health")
async def get_system_health(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get overall system health status (admin only)
    
    Returns:
        System health status with metrics
    """
    try:
        monitoring_service = MonitoringService(db, redis)
        health = monitoring_service.get_system_health()
        return health
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    component: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get system logs with optional filtering (admin only)
    
    Args:
        level: Optional log level filter
        component: Optional component filter
        limit: Maximum number of logs to return
    """
    try:
        monitoring_service = MonitoringService(db, redis)
        logs = monitoring_service.get_logs(
            level=level,
            component=component,
            limit=limit
        )
        return {
            "total": len(logs),
            "logs": logs
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/metrics")
async def get_performance_metrics(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get performance metrics (admin only)
    
    Returns:
        Performance metrics including API requests, agent interactions, etc.
    """
    try:
        monitoring_service = MonitoringService(db, redis)
        metrics = monitoring_service.get_performance_metrics()
        return metrics
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/cache-stats")
async def get_cache_statistics(
    current_user: User = Depends(get_current_admin_user),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get cache statistics (admin only)
    
    Returns:
        Cache size, hit rates, and other cache metrics
    """
    try:
        cache_service = get_cache_service(redis)
        stats = await cache_service.get_cache_stats()
        return stats
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.get("/performance-stats")
async def get_performance_statistics(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get detailed performance statistics (admin only)
    
    Returns:
        Performance metrics including latency percentiles
    """
    try:
        perf_monitor = get_performance_monitor()
        stats = perf_monitor.get_all_metrics()
        return {
            "metrics": stats,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance stats: {str(e)}")


@router.post("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    redis: RedisClient = Depends(get_redis)
):
    """
    Clear cache (admin only)
    
    Args:
        pattern: Optional pattern to match cache keys
    """
    try:
        cache_service = get_cache_service(redis)
        
        if pattern:
            deleted = await cache_service.clear_pattern(pattern)
            return {
                "status": "success",
                "message": f"Cleared {deleted} cache entries matching pattern: {pattern}"
            }
        else:
            success = await cache_service.clear_all_cache()
            return {
                "status": "success" if success else "failed",
                "message": "All cache cleared" if success else "Failed to clear cache"
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.post("/metrics/reset")
async def reset_metrics(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Reset performance metrics (admin only)
    """
    try:
        monitoring_service = MonitoringService(db, redis)
        monitoring_service.reset_metrics()
        
        perf_monitor = get_performance_monitor()
        perf_monitor.reset_metrics()
        
        return {
            "status": "success",
            "message": "Metrics reset successfully"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")


@router.get("/error-summary")
async def get_error_summary(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get error summary for the specified period (admin only)
    
    Args:
        days: Number of days to look back
    """
    try:
        monitoring_service = MonitoringService(db, redis)
        error_logs = monitoring_service.system_log.get_recent_errors(limit=1000)
        
        # Filter by date
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered_errors = [
            log for log in error_logs
            if datetime.fromisoformat(log["timestamp"]) > cutoff
        ]
        
        # Group by component
        errors_by_component = {}
        for error in filtered_errors:
            component = error.get("component", "unknown")
            if component not in errors_by_component:
                errors_by_component[component] = []
            errors_by_component[component].append(error)
        
        return {
            "period_days": days,
            "total_errors": len(filtered_errors),
            "errors_by_component": {
                comp: {
                    "count": len(errors),
                    "recent": errors[:5]
                }
                for comp, errors in errors_by_component.items()
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get error summary: {str(e)}")
