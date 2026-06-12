from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import selectinload

from core.redis_client import RedisClient
from models.conversation import Conversation, Message
from models.user import User
from models.agent_interaction import UserFeedback

# [会话生命周期与上下文管理服务]:
# 专门负责在 SQLite 中双向持久化历史聊天记录。
# 通过关联 conversation_id，为大模型的长期多轮对话记忆(Memory)提供底层数据支撑。
class ConversationService:
    """
    Service for managing conversations and messages
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient = None):
        self.db = db
        self.redis = redis
    
    async def create_conversation(self, user_id: uuid.UUID, title: str, 
                                category: Optional[str] = None, 
                                is_anonymous: bool = False) -> Conversation:
        """Create a new conversation"""
        try:
            conversation = Conversation(
                user_id=user_id,
                title=title,
                category=category,
                is_anonymous=is_anonymous,
                status="active"
            )
            
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)
            
            # Initialize conversation context in Redis
            if self.redis:
                await self.redis.set_conversation_context(
                    str(user_id), 
                    str(conversation.id),
                    {
                        "created_at": datetime.now().isoformat(),
                        "category": category,
                        "message_count": 0
                    }
                )
            
            return conversation
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create conversation: {str(e)}")
    
    async def get_conversation(self, conversation_id: uuid.UUID, 
                             user_id: uuid.UUID) -> Optional[Conversation]:
        """Get conversation by ID and user ID"""
        try:
            query = select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            )
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            print(f"❌ Failed to get conversation: {str(e)}")
            return None
    
    async def get_user_conversations(self, user_id: uuid.UUID, 
                                   limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get user's conversations with pagination"""
        try:
            query = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(desc(Conversation.updated_at))
                .limit(limit)
                .offset(offset)
            )
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            # Convert to dict format
            conversation_list = []
            for conv in conversations:
                # Get message count
                message_count_query = select(Message).where(Message.conversation_id == conv.id)
                message_result = await self.db.execute(message_count_query)
                message_count = len(message_result.scalars().all())
                
                conversation_list.append({
                    "id": str(conv.id),
                    "title": conv.title,
                    "category": conv.category,
                    "status": conv.status,
                    "is_anonymous": conv.is_anonymous,
                    "message_count": message_count,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
                })
            
            return conversation_list
            
        except Exception as e:
            print(f"❌ Failed to get user conversations: {str(e)}")
            return []
    
    async def add_message(self, conversation_id: uuid.UUID, content: str, 
                         role: str, agent_type: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None,
                         is_internal: bool = False) -> Message:
        """Add message to conversation"""
        try:
            message = Message(
                conversation_id=conversation_id,
                content=content,
                role=role,
                agent_type=agent_type,
                message_metadata=metadata,
                is_internal=is_internal,
                token_count=len(content.split()) * 1.3  # Rough token estimation
            )
            
            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)
            
            # Update conversation timestamp
            conversation_update_query = (
                select(Conversation)
                .where(Conversation.id == conversation_id)
            )
            result = await self.db.execute(conversation_update_query)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                conversation.updated_at = datetime.now()
                await self.db.commit()
            
            # Update Redis context
            if self.redis and conversation:
                context = await self.redis.get_conversation_context(
                    str(conversation.user_id), 
                    str(conversation_id)
                )
                if context:
                    context["message_count"] = context.get("message_count", 0) + 1
                    context["last_message_at"] = datetime.now().isoformat()
                    context["last_agent"] = agent_type
                    
                    await self.redis.set_conversation_context(
                        str(conversation.user_id),
                        str(conversation_id),
                        context
                    )
            
            return message
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to add message: {str(e)}")
    
    async def get_conversation_messages(self, conversation_id: uuid.UUID, 
                                      user_id: uuid.UUID, limit: int = 50,
                                      offset: int = 0, include_internal: bool = False) -> List[Dict[str, Any]]:
        """Get conversation messages with pagination"""
        try:
            # Verify conversation ownership
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return []
            
            # Build query
            query = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
            )
            
            if not include_internal:
                query = query.where(Message.is_internal == False)
            
            query = (
                query
                .order_by(Message.created_at)
                .limit(limit)
                .offset(offset)
            )
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            # Convert to dict format
            message_list = []
            for msg in messages:
                message_list.append({
                    "id": str(msg.id),
                    "content": msg.content,
                    "role": msg.role,
                    "agent_type": msg.agent_type,
                    "metadata": msg.message_metadata,
                    "is_internal": msg.is_internal,
                    "token_count": msg.token_count,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None
                })
            
            return message_list
            
        except Exception as e:
            print(f"❌ Failed to get conversation messages: {str(e)}")
            return []
    
    async def update_conversation_context(self, conversation_id: uuid.UUID, 
                                        context_update: Dict[str, Any]):
        """Update conversation context in Redis"""
        try:
            if not self.redis:
                return
            
            # Get conversation to find user_id
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.db.execute(query)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return
            
            # Update context
            current_context = await self.redis.get_conversation_context(
                str(conversation.user_id),
                str(conversation_id)
            )
            
            if current_context:
                current_context.update(context_update)
            else:
                current_context = context_update
            
            current_context["updated_at"] = datetime.now().isoformat()
            
            await self.redis.set_conversation_context(
                str(conversation.user_id),
                str(conversation_id),
                current_context
            )
            
        except Exception as e:
            print(f"❌ Failed to update conversation context: {str(e)}")
    
    async def submit_feedback(self, conversation_id: uuid.UUID, user_id: uuid.UUID,
                            rating: int, feedback_text: Optional[str] = None,
                            feedback_type: str = "general", 
                            agent_type: Optional[str] = None) -> UserFeedback:
        """Submit user feedback for conversation"""
        try:
            feedback = UserFeedback(
                conversation_id=conversation_id,
                user_id=user_id,
                agent_type=agent_type,
                rating=rating,
                feedback_text=feedback_text,
                feedback_type=feedback_type,
                is_anonymous=False
            )
            
            self.db.add(feedback)
            await self.db.commit()
            await self.db.refresh(feedback)
            
            # Store aggregated feedback in Redis for analytics
            if self.redis:
                feedback_key = f"feedback_analytics:{agent_type or 'general'}"
                current_stats = await self.redis.get_json(feedback_key) or {
                    "total_ratings": 0,
                    "sum_ratings": 0,
                    "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                }
                
                current_stats["total_ratings"] += 1
                current_stats["sum_ratings"] += rating
                current_stats["rating_distribution"][rating] += 1
                
                await self.redis.set_json(feedback_key, current_stats, expire=86400 * 30)  # 30 days
            
            return feedback
            
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to submit feedback: {str(e)}")
    
    async def delete_conversation(self, conversation_id: uuid.UUID, 
                                user_id: uuid.UUID) -> bool:
        """Delete conversation and all associated messages"""
        try:
            # Verify ownership
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return False
            
            # Delete associated messages (cascade should handle this, but explicit is better)
            delete_messages_query = select(Message).where(Message.conversation_id == conversation_id)
            message_result = await self.db.execute(delete_messages_query)
            messages = message_result.scalars().all()
            
            for message in messages:
                await self.db.delete(message)
            
            # Delete conversation
            await self.db.delete(conversation)
            await self.db.commit()
            
            # Clear Redis context
            if self.redis:
                await self.redis.delete(f"conversation:{user_id}:{conversation_id}")
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            print(f"❌ Failed to delete conversation: {str(e)}")
            return False
    
    async def get_conversation_statistics(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get conversation statistics for user"""
        try:
            # Total conversations
            total_query = select(Conversation).where(Conversation.user_id == user_id)
            total_result = await self.db.execute(total_query)
            total_conversations = len(total_result.scalars().all())
            
            # Active conversations
            active_query = select(Conversation).where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.status == "active"
                )
            )
            active_result = await self.db.execute(active_query)
            active_conversations = len(active_result.scalars().all())
            
            # Category breakdown
            category_query = select(Conversation).where(Conversation.user_id == user_id)
            category_result = await self.db.execute(category_query)
            conversations = category_result.scalars().all()
            
            category_stats = {}
            for conv in conversations:
                category = conv.category or "general"
                category_stats[category] = category_stats.get(category, 0) + 1
            
            # Message count (approximate)
            total_messages = 0
            for conv in conversations:
                message_query = select(Message).where(Message.conversation_id == conv.id)
                message_result = await self.db.execute(message_query)
                total_messages += len(message_result.scalars().all())
            
            return {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "total_messages": total_messages,
                "category_breakdown": category_stats,
                "avg_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Failed to get conversation statistics: {str(e)}")
            return {
                "total_conversations": 0,
                "active_conversations": 0,
                "total_messages": 0,
                "category_breakdown": {},
                "avg_messages_per_conversation": 0
            }
    
    async def search_conversations(self, user_id: uuid.UUID, query: str, 
                                 category: Optional[str] = None, 
                                 limit: int = 10) -> List[Dict[str, Any]]:
        """Search user's conversations by content"""
        try:
            # Build base query
            base_query = select(Conversation).where(Conversation.user_id == user_id)
            
            if category:
                base_query = base_query.where(Conversation.category == category)
            
            # Add text search
            base_query = base_query.where(Conversation.title.ilike(f"%{query}%"))
            
            result = await self.db.execute(base_query.limit(limit))
            conversations = result.scalars().all()
            
            # Also search in message content
            message_query = (
                select(Message.conversation_id)
                .where(
                    and_(
                        Message.content.ilike(f"%{query}%"),
                        Message.conversation_id.in_(
                            select(Conversation.id).where(Conversation.user_id == user_id)
                        )
                    )
                )
                .distinct()
                .limit(limit)
            )
            
            message_result = await self.db.execute(message_query)
            message_conversation_ids = message_result.scalars().all()
            
            # Get conversations from message matches
            if message_conversation_ids:
                message_conv_query = select(Conversation).where(
                    Conversation.id.in_(message_conversation_ids)
                )
                message_conv_result = await self.db.execute(message_conv_query)
                message_conversations = message_conv_result.scalars().all()
                
                # Combine results
                all_conversations = list(conversations) + list(message_conversations)
                # Remove duplicates
                seen_ids = set()
                unique_conversations = []
                for conv in all_conversations:
                    if conv.id not in seen_ids:
                        seen_ids.add(conv.id)
                        unique_conversations.append(conv)
            else:
                unique_conversations = conversations
            
            # Format results
            search_results = []
            for conv in unique_conversations[:limit]:
                search_results.append({
                    "id": str(conv.id),
                    "title": conv.title,
                    "category": conv.category,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "match_type": "title" if query.lower() in conv.title.lower() else "content"
                })
            
            return search_results
            
        except Exception as e:
            print(f"❌ Failed to search conversations: {str(e)}")
            return []
