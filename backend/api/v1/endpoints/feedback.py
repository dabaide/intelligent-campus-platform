"""
Feedback API Endpoints
Handles user feedback submission and analysis
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from models.user import User
from api.deps import get_current_user, get_current_admin_user
from services.feedback_service import FeedbackService

router = APIRouter()


@router.post("/submit")
async def submit_feedback(
    agent_type: str,
    rating: int,
    feedback_text: Optional[str] = None,
    tags: Optional[list] = None,
    message_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Submit user feedback for an agent response
    
    Args:
        agent_type: Type of agent (navigation, academic, life, admin)
        rating: Rating from 1-5
        feedback_text: Optional feedback text
        tags: Optional tags for categorization
        message_id: Optional ID of the message being rated
    """
    try:
        if not 1 <= rating <= 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        feedback_service = FeedbackService(db, redis)
        
        message_uuid = None
        if message_id:
            try:
                message_uuid = uuid.UUID(message_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid message ID format")
        
        result = await feedback_service.submit_feedback(
            user_id=current_user.id,
            agent_type=agent_type,
            message_id=message_uuid,
            rating=rating,
            feedback_text=feedback_text,
            tags=tags
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.get("/history")
async def get_feedback_history(
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Get user's feedback history"""
    try:
        feedback_service = FeedbackService(db, redis)
        history = await feedback_service.get_user_feedback_history(
            user_id=current_user.id,
            limit=limit
        )
        return {"feedback_history": history}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get feedback history: {str(e)}")


@router.get("/agent/{agent_type}")
async def get_agent_feedback(
    agent_type: str,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get feedback statistics for an agent (admin only)
    
    Args:
        agent_type: Type of agent
        days: Number of days to look back
    """
    try:
        feedback_service = FeedbackService(db, redis)
        stats = await feedback_service.get_agent_feedback(
            agent_type=agent_type,
            days=days
        )
        return stats
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent feedback: {str(e)}")


@router.get("/system-summary")
async def get_system_feedback_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get overall system feedback summary (admin only)
    
    Args:
        days: Number of days to look back
    """
    try:
        feedback_service = FeedbackService(db, redis)
        summary = await feedback_service.get_system_feedback_summary(days=days)
        return summary
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get feedback summary: {str(e)}")


@router.get("/problematic-agents")
async def get_problematic_agents(
    days: int = Query(30, ge=1, le=365),
    rating_threshold: float = Query(3.0, ge=1.0, le=5.0),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get agents with low average ratings (admin only)
    
    Args:
        days: Number of days to look back
        rating_threshold: Threshold for "problematic" rating
    """
    try:
        feedback_service = FeedbackService(db, redis)
        problematic = await feedback_service.get_problematic_agents(
            days=days,
            rating_threshold=rating_threshold
        )
        return {"problematic_agents": problematic}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get problematic agents: {str(e)}")
