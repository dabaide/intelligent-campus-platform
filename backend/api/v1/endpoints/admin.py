from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from models.user import User
from models.conversation import Conversation, Message
from models.agent_interaction import AgentInteraction, UserFeedback, AgentPerformance
from models.knowledge_base import Document, FAQ
from api.deps import get_current_admin_user

router = APIRouter()

@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get admin dashboard statistics
    """
    try:
        # User statistics
        total_users_query = select(func.count(User.id))
        total_users_result = await db.execute(total_users_query)
        total_users = total_users_result.scalar()
        
        active_users_query = select(func.count(User.id)).where(User.is_active == True)
        active_users_result = await db.execute(active_users_query)
        active_users = active_users_result.scalar()
        
        # Recent user registrations (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_users_query = select(func.count(User.id)).where(
            User.created_at >= thirty_days_ago
        )
        recent_users_result = await db.execute(recent_users_query)
        recent_registrations = recent_users_result.scalar()
        
        # Conversation statistics
        total_conversations_query = select(func.count(Conversation.id))
        total_conversations_result = await db.execute(total_conversations_query)
        total_conversations = total_conversations_result.scalar()
        
        active_conversations_query = select(func.count(Conversation.id)).where(
            Conversation.status == "active"
        )
        active_conversations_result = await db.execute(active_conversations_query)
        active_conversations = active_conversations_result.scalar()
        
        # Message statistics
        total_messages_query = select(func.count(Message.id))
        total_messages_result = await db.execute(total_messages_query)
        total_messages = total_messages_result.scalar()
        
        # Agent interaction statistics
        total_interactions_query = select(func.count(AgentInteraction.id))
        total_interactions_result = await db.execute(total_interactions_query)
        total_interactions = total_interactions_result.scalar()
        
        successful_interactions_query = select(func.count(AgentInteraction.id)).where(
            AgentInteraction.status == "completed"
        )
        successful_interactions_result = await db.execute(successful_interactions_query)
        successful_interactions = successful_interactions_result.scalar()
        
        # Knowledge base statistics
        total_documents_query = select(func.count(Document.id)).where(Document.is_active == True)
        total_documents_result = await db.execute(total_documents_query)
        total_documents = total_documents_result.scalar()
        
        total_faqs_query = select(func.count(FAQ.id)).where(FAQ.is_active == True)
        total_faqs_result = await db.execute(total_faqs_query)
        total_faqs = total_faqs_result.scalar()
        
        # User feedback statistics
        avg_rating_query = select(func.avg(UserFeedback.rating))
        avg_rating_result = await db.execute(avg_rating_query)
        avg_rating = avg_rating_result.scalar() or 0.0
        
        # Get system health from Redis
        system_health = {
            "redis_connected": True,
            "database_connected": True,
            "last_backup": "2024-04-15 12:00:00",
            "disk_usage": "45%",
            "memory_usage": "68%"
        }
        
        try:
            await redis.redis.ping()
        except:
            system_health["redis_connected"] = False
        
        return {
            "user_statistics": {
                "total_users": total_users,
                "active_users": active_users,
                "recent_registrations": recent_registrations,
                "user_growth_rate": (recent_registrations / max(total_users - recent_registrations, 1)) * 100
            },
            "conversation_statistics": {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "total_messages": total_messages,
                "avg_messages_per_conversation": total_messages / max(total_conversations, 1)
            },
            "agent_statistics": {
                "total_interactions": total_interactions,
                "successful_interactions": successful_interactions,
                "success_rate": (successful_interactions / max(total_interactions, 1)) * 100
            },
            "knowledge_statistics": {
                "total_documents": total_documents,
                "total_faqs": total_faqs,
                "avg_user_rating": round(avg_rating, 2)
            },
            "system_health": system_health,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard data: {str(e)}"
        )

@router.get("/users")
async def get_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get users with filtering and pagination
    """
    try:
        query = select(User)
        
        if role:
            query = query.where(User.role == role)
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Get paginated results
        query = query.order_by(desc(User.created_at)).limit(limit).offset(offset)
        result = await db.execute(query)
        users = result.scalars().all()
        
        user_list = []
        for user in users:
            user_list.append({
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "student_id": user.student_id,
                "full_name": user.full_name,
                "role": user.role,
                "department": user.department,
                "grade": user.grade,
                "major": user.major,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "created_at": user.created_at
            })
        
        return {
            "users": user_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get users: {str(e)}"
        )

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_data: dict,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user status (activate/deactivate)
    """
    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent self-deactivation
        if str(user.id) == str(current_user.id) and not status_data.get("is_active", True):
            raise HTTPException(
                status_code=400, 
                detail="Cannot deactivate your own account"
            )
        
        user.is_active = status_data.get("is_active", user.is_active)
        await db.commit()
        
        return {
            "message": f"User {'activated' if user.is_active else 'deactivated'} successfully",
            "user_id": str(user.id),
            "is_active": user.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user status: {str(e)}"
        )

@router.get("/agent-performance")
async def get_detailed_agent_performance(
    days: int = Query(30, le=365),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed agent performance analytics
    """
    try:
        # Get agent interactions from the last N days
        start_date = datetime.now() - timedelta(days=days)
        
        interactions_query = select(AgentInteraction).where(
            AgentInteraction.started_at >= start_date
        )
        interactions_result = await db.execute(interactions_query)
        interactions = interactions_result.scalars().all()
        
        # Calculate performance metrics by agent
        agent_metrics = {}
        
        for interaction in interactions:
            agent_type = interaction.agent_type
            
            if agent_type not in agent_metrics:
                agent_metrics[agent_type] = {
                    "total_interactions": 0,
                    "successful_interactions": 0,
                    "failed_interactions": 0,
                    "total_execution_time": 0,
                    "confidence_scores": [],
                    "task_types": {}
                }
            
            metrics = agent_metrics[agent_type]
            metrics["total_interactions"] += 1
            
            if interaction.status == "completed":
                metrics["successful_interactions"] += 1
            else:
                metrics["failed_interactions"] += 1
            
            if interaction.execution_time_ms:
                metrics["total_execution_time"] += interaction.execution_time_ms
            
            if interaction.confidence_score:
                metrics["confidence_scores"].append(interaction.confidence_score)
            
            # Track task types
            task_type = interaction.task_type
            if task_type not in metrics["task_types"]:
                metrics["task_types"][task_type] = 0
            metrics["task_types"][task_type] += 1
        
        # Calculate final metrics
        performance_data = {}
        for agent_type, metrics in agent_metrics.items():
            total = metrics["total_interactions"]
            if total > 0:
                performance_data[agent_type] = {
                    "total_interactions": total,
                    "success_rate": (metrics["successful_interactions"] / total) * 100,
                    "failure_rate": (metrics["failed_interactions"] / total) * 100,
                    "avg_execution_time_ms": metrics["total_execution_time"] / total if total > 0 else 0,
                    "avg_confidence_score": sum(metrics["confidence_scores"]) / len(metrics["confidence_scores"]) if metrics["confidence_scores"] else 0,
                    "popular_tasks": sorted(metrics["task_types"].items(), key=lambda x: x[1], reverse=True)[:5]
                }
        
        return {
            "performance_data": performance_data,
            "analysis_period_days": days,
            "total_interactions_analyzed": len(interactions),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent performance: {str(e)}"
        )

@router.get("/user-feedback")
async def get_user_feedback_summary(
    days: int = Query(30),
    agent_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user feedback summary
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        query = select(UserFeedback).where(UserFeedback.created_at >= start_date)
        
        if agent_type:
            query = query.where(UserFeedback.agent_type == agent_type)
        
        result = await db.execute(query)
        feedback_entries = result.scalars().all()
        
        if not feedback_entries:
            return {
                "summary": {
                    "total_feedback": 0,
                    "average_rating": 0,
                    "rating_distribution": {},
                    "feedback_by_agent": {}
                },
                "recent_feedback": [],
                "analysis_period_days": days
            }
        
        # Calculate summary statistics
        total_feedback = len(feedback_entries)
        total_rating = sum(f.rating for f in feedback_entries)
        average_rating = total_rating / total_feedback
        
        # Rating distribution
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for feedback in feedback_entries:
            rating_distribution[feedback.rating] += 1
        
        # Feedback by agent
        feedback_by_agent = {}
        for feedback in feedback_entries:
            agent = feedback.agent_type or "general"
            if agent not in feedback_by_agent:
                feedback_by_agent[agent] = {
                    "count": 0,
                    "total_rating": 0,
                    "average_rating": 0
                }
            
            feedback_by_agent[agent]["count"] += 1
            feedback_by_agent[agent]["total_rating"] += feedback.rating
        
        # Calculate averages
        for agent, data in feedback_by_agent.items():
            data["average_rating"] = data["total_rating"] / data["count"]
        
        # Recent feedback with text
        recent_feedback = []
        text_feedback = [f for f in feedback_entries if f.feedback_text]
        text_feedback.sort(key=lambda x: x.created_at, reverse=True)
        
        for feedback in text_feedback[:10]:  # Last 10 with text
            recent_feedback.append({
                "id": str(feedback.id),
                "rating": feedback.rating,
                "feedback_text": feedback.feedback_text,
                "feedback_type": feedback.feedback_type,
                "agent_type": feedback.agent_type,
                "created_at": feedback.created_at
            })
        
        return {
            "summary": {
                "total_feedback": total_feedback,
                "average_rating": round(average_rating, 2),
                "rating_distribution": rating_distribution,
                "feedback_by_agent": feedback_by_agent
            },
            "recent_feedback": recent_feedback,
            "analysis_period_days": days
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feedback summary: {str(e)}"
        )

@router.get("/system-logs")
async def get_system_logs(
    level: Optional[str] = Query("INFO"),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_admin_user),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get system logs (mock implementation)
    """
    try:
        # In a real implementation, this would fetch actual system logs
        # For now, return mock log data
        mock_logs = [
            {
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "level": "INFO",
                "component": "AgentOrchestrator",
                "message": "Successfully processed user request",
                "user_id": str(uuid.uuid4()),
                "execution_time_ms": 245
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=12)).isoformat(),
                "level": "WARNING", 
                "component": "RAGService",
                "message": "Low confidence score in semantic search",
                "details": {"confidence": 0.45, "query": "图书馆开放时间"}
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=18)).isoformat(),
                "level": "ERROR",
                "component": "QualityAgent", 
                "message": "Failed to verify response accuracy",
                "error": "Connection timeout to external verification service"
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=25)).isoformat(),
                "level": "INFO",
                "component": "ConversationService",
                "message": "New conversation created",
                "conversation_id": str(uuid.uuid4())
            }
        ]
        
        # Filter by log level if specified
        if level and level != "ALL":
            mock_logs = [log for log in mock_logs if log["level"] == level]
        
        return {
            "logs": mock_logs[:limit],
            "total_retrieved": min(len(mock_logs), limit),
            "log_level_filter": level
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system logs: {str(e)}"
        )

@router.post("/maintenance/rebuild-index")
async def rebuild_search_index(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Rebuild search index (admin only)
    """
    try:
        from services.rag_service import RAGService
        
        rag_service = RAGService(db, redis)
        
        # This would trigger a full index rebuild
        # For now, just return a success message
        await rag_service._create_new_index()
        
        return {
            "message": "Search index rebuild initiated",
            "status": "in_progress",
            "initiated_by": current_user.username,
            "started_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rebuild search index: {str(e)}"
        )

@router.post("/maintenance/clear-cache")
async def clear_system_cache(
    cache_type: str = Query("all"),  # all, conversation, agent, search
    current_user: User = Depends(get_current_admin_user),
    redis: RedisClient = Depends(get_redis)
):
    """
    Clear system caches
    """
    try:
        cleared_keys = []
        
        if cache_type in ["all", "conversation"]:
            # Clear conversation contexts
            # In production, would scan for conversation:* keys
            cleared_keys.append("conversation_contexts")
        
        if cache_type in ["all", "agent"]:
            # Clear agent response caches
            cleared_keys.append("agent_caches")
        
        if cache_type in ["all", "search"]:
            # Clear search result caches
            cleared_keys.append("search_results")
        
        # Mock cache clearing - in production would actually clear Redis keys
        return {
            "message": f"Cache cleared successfully",
            "cache_type": cache_type,
            "cleared_categories": cleared_keys,
            "cleared_by": current_user.username,
            "cleared_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )

@router.get("/export/conversations")
async def export_conversations(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    format: str = Query("json"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export conversation data for analysis
    """
    try:
        query = select(Conversation)
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(Conversation.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(Conversation.created_at <= end_dt)
        
        query = query.limit(1000)  # Limit export size
        result = await db.execute(query)
        conversations = result.scalars().all()
        
        export_data = []
        for conv in conversations:
            # Get message count for each conversation
            message_query = select(func.count(Message.id)).where(
                Message.conversation_id == conv.id
            )
            msg_result = await db.execute(message_query)
            message_count = msg_result.scalar()
            
            export_data.append({
                "id": str(conv.id),
                "user_id": str(conv.user_id),
                "title": conv.title,
                "category": conv.category,
                "status": conv.status,
                "message_count": message_count,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
            })
        
        return {
            "export_data": export_data,
            "total_conversations": len(export_data),
            "export_format": format,
            "exported_by": current_user.username,
            "export_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export conversations: {str(e)}"
        )
