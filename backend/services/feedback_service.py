"""
User Feedback Service
Handles collection, analysis, and management of user feedback
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload

from models.agent_interaction import UserFeedback, AgentInteraction
from models.user import User
from core.redis_client import RedisClient


class FeedbackService:
    """Service for managing user feedback"""
    
    def __init__(self, db: AsyncSession, redis: RedisClient = None):
        self.db = db
        self.redis = redis
    
    async def submit_feedback(
        self,
        user_id: uuid.UUID,
        agent_type: str,
        message_id: Optional[uuid.UUID],
        rating: int,
        feedback_text: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Submit user feedback for an agent response
        
        Args:
            user_id: User ID
            agent_type: Type of agent (navigation, academic, life, admin)
            message_id: ID of the message being rated
            rating: Rating from 1-5
            feedback_text: Optional feedback text
            tags: Optional tags for categorization
        
        Returns:
            Created feedback record
        """
        try:
            if not 1 <= rating <= 5:
                raise ValueError("Rating must be between 1 and 5")
            
            feedback = UserFeedback(
                user_id=user_id,
                agent_type=agent_type,
                message_id=message_id,
                rating=rating,
                feedback_text=feedback_text,
                tags=tags or [],
                is_helpful=rating >= 4,
                created_at=datetime.now()
            )
            
            self.db.add(feedback)
            await self.db.commit()
            await self.db.refresh(feedback)
            
            # Update Redis cache for quick access
            if self.redis:
                await self._update_feedback_cache(agent_type)
            
            return {
                "id": str(feedback.id),
                "status": "success",
                "message": "Feedback submitted successfully"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to submit feedback: {str(e)}")
    
    async def get_agent_feedback(
        self,
        agent_type: str,
        days: int = 30,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get feedback statistics for an agent
        
        Args:
            agent_type: Type of agent
            days: Number of days to look back
            limit: Maximum number of feedback records to return
        
        Returns:
            Feedback statistics and records
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get feedback records
            query = select(UserFeedback).where(
                and_(
                    UserFeedback.agent_type == agent_type,
                    UserFeedback.created_at >= cutoff_date
                )
            ).order_by(desc(UserFeedback.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            feedback_records = result.scalars().all()
            
            # Calculate statistics
            total_feedback = len(feedback_records)
            avg_rating = 0.0
            helpful_count = 0
            rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            if total_feedback > 0:
                ratings = [f.rating for f in feedback_records]
                avg_rating = sum(ratings) / len(ratings)
                helpful_count = sum(1 for f in feedback_records if f.is_helpful)
                
                for f in feedback_records:
                    rating_distribution[f.rating] += 1
            
            # Get top tags
            all_tags = []
            for f in feedback_records:
                if f.tags:
                    all_tags.extend(f.tags)
            
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "agent_type": agent_type,
                "period_days": days,
                "total_feedback": total_feedback,
                "average_rating": round(avg_rating, 2),
                "helpful_percentage": round((helpful_count / total_feedback * 100) if total_feedback > 0 else 0, 2),
                "rating_distribution": rating_distribution,
                "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
                "recent_feedback": [
                    {
                        "id": str(f.id),
                        "rating": f.rating,
                        "text": f.feedback_text,
                        "tags": f.tags,
                        "created_at": f.created_at.isoformat()
                    }
                    for f in feedback_records[:20]
                ]
            }
        
        except Exception as e:
            print(f"❌ Failed to get agent feedback: {str(e)}")
            return {}
    
    async def get_user_feedback_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get feedback history for a user"""
        try:
            query = select(UserFeedback).where(
                UserFeedback.user_id == user_id
            ).order_by(desc(UserFeedback.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            feedback_records = result.scalars().all()
            
            return [
                {
                    "id": str(f.id),
                    "agent_type": f.agent_type,
                    "rating": f.rating,
                    "text": f.feedback_text,
                    "tags": f.tags,
                    "is_helpful": f.is_helpful,
                    "created_at": f.created_at.isoformat()
                }
                for f in feedback_records
            ]
        
        except Exception as e:
            print(f"❌ Failed to get user feedback history: {str(e)}")
            return []
    
    async def get_system_feedback_summary(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get overall system feedback summary
        
        Args:
            days: Number of days to look back
        
        Returns:
            System-wide feedback statistics
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total feedback
            total_query = select(func.count(UserFeedback.id)).where(
                UserFeedback.created_at >= cutoff_date
            )
            total_result = await self.db.execute(total_query)
            total_feedback = total_result.scalar() or 0
            
            # Average rating
            avg_query = select(func.avg(UserFeedback.rating)).where(
                UserFeedback.created_at >= cutoff_date
            )
            avg_result = await self.db.execute(avg_query)
            avg_rating = avg_result.scalar() or 0.0
            
            # Helpful feedback count
            helpful_query = select(func.count(UserFeedback.id)).where(
                and_(
                    UserFeedback.is_helpful == True,
                    UserFeedback.created_at >= cutoff_date
                )
            )
            helpful_result = await self.db.execute(helpful_query)
            helpful_count = helpful_result.scalar() or 0
            
            # Feedback by agent type
            agent_query = select(
                UserFeedback.agent_type,
                func.count(UserFeedback.id).label("count"),
                func.avg(UserFeedback.rating).label("avg_rating")
            ).where(
                UserFeedback.created_at >= cutoff_date
            ).group_by(UserFeedback.agent_type)
            
            agent_result = await self.db.execute(agent_query)
            agent_stats = agent_result.all()
            
            # Rating distribution
            distribution_query = select(
                UserFeedback.rating,
                func.count(UserFeedback.id).label("count")
            ).where(
                UserFeedback.created_at >= cutoff_date
            ).group_by(UserFeedback.rating)
            
            dist_result = await self.db.execute(distribution_query)
            distribution_data = dist_result.all()
            
            rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for rating, count in distribution_data:
                rating_distribution[rating] = count
            
            return {
                "period_days": days,
                "total_feedback": total_feedback,
                "average_rating": round(float(avg_rating), 2),
                "helpful_percentage": round((helpful_count / total_feedback * 100) if total_feedback > 0 else 0, 2),
                "rating_distribution": rating_distribution,
                "by_agent_type": [
                    {
                        "agent_type": agent_type,
                        "count": count,
                        "average_rating": round(float(avg_rating), 2)
                    }
                    for agent_type, count, avg_rating in agent_stats
                ]
            }
        
        except Exception as e:
            print(f"❌ Failed to get system feedback summary: {str(e)}")
            return {}
    
    async def _update_feedback_cache(self, agent_type: str):
        """Update feedback cache in Redis"""
        try:
            if not self.redis:
                return
            
            feedback_summary = await self.get_agent_feedback(agent_type, days=7)
            cache_key = f"feedback:{agent_type}:summary"
            await self.redis.set(cache_key, feedback_summary, ex=3600)
        
        except Exception as e:
            print(f"❌ Failed to update feedback cache: {str(e)}")
    
    async def get_problematic_agents(
        self,
        days: int = 30,
        rating_threshold: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Get agents with low average ratings
        
        Args:
            days: Number of days to look back
            rating_threshold: Threshold for "problematic" rating
        
        Returns:
            List of agents with low ratings
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = select(
                UserFeedback.agent_type,
                func.count(UserFeedback.id).label("feedback_count"),
                func.avg(UserFeedback.rating).label("avg_rating")
            ).where(
                UserFeedback.created_at >= cutoff_date
            ).group_by(UserFeedback.agent_type).having(
                func.avg(UserFeedback.rating) < rating_threshold
            )
            
            result = await self.db.execute(query)
            problematic_agents = result.all()
            
            return [
                {
                    "agent_type": agent_type,
                    "feedback_count": feedback_count,
                    "average_rating": round(float(avg_rating), 2),
                    "status": "needs_improvement"
                }
                for agent_type, feedback_count, avg_rating in problematic_agents
            ]
        
        except Exception as e:
            print(f"❌ Failed to get problematic agents: {str(e)}")
            return []
