"""
Data Export Service
Handles exporting data in various formats (CSV, JSON, Excel)
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import csv
import json
from io import StringIO, BytesIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from models.conversation import Conversation, Message
from models.user import User
from models.knowledge_base import Document, FAQ
from models.agent_interaction import AgentInteraction, UserFeedback


class ExportService:
    """Service for exporting data in various formats"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def export_conversations_csv(
        self,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 1000
    ) -> str:
        """
        Export conversations to CSV format
        
        Args:
            user_id: Optional user ID to filter conversations
            limit: Maximum number of conversations to export
        
        Returns:
            CSV string
        """
        try:
            query = select(Conversation)
            if user_id:
                query = query.where(Conversation.user_id == user_id)
            query = query.order_by(desc(Conversation.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "User ID", "Title", "Category", "Status",
                "Message Count", "Created At", "Updated At"
            ])
            
            # Write data
            for conv in conversations:
                writer.writerow([
                    str(conv.id),
                    str(conv.user_id),
                    conv.title,
                    conv.category or "",
                    conv.status,
                    conv.message_count or 0,
                    conv.created_at.isoformat(),
                    conv.updated_at.isoformat() if conv.updated_at else ""
                ])
            
            return output.getvalue()
        
        except Exception as e:
            raise Exception(f"Failed to export conversations to CSV: {str(e)}")
    
    async def export_conversations_json(
        self,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 1000
    ) -> str:
        """Export conversations to JSON format"""
        try:
            query = select(Conversation)
            if user_id:
                query = query.where(Conversation.user_id == user_id)
            query = query.order_by(desc(Conversation.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            data = {
                "export_date": datetime.now().isoformat(),
                "total_conversations": len(conversations),
                "conversations": [
                    {
                        "id": str(conv.id),
                        "user_id": str(conv.user_id),
                        "title": conv.title,
                        "category": conv.category,
                        "status": conv.status,
                        "message_count": conv.message_count or 0,
                        "created_at": conv.created_at.isoformat(),
                        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
                    }
                    for conv in conversations
                ]
            }
            
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        except Exception as e:
            raise Exception(f"Failed to export conversations to JSON: {str(e)}")
    
    async def export_messages_csv(
        self,
        conversation_id: uuid.UUID,
        limit: int = 5000
    ) -> str:
        """Export messages from a conversation to CSV"""
        try:
            query = select(Message).where(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).limit(limit)
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Conversation ID", "Role", "Content",
                "Agent Type", "Confidence Score", "Created At"
            ])
            
            # Write data
            for msg in messages:
                writer.writerow([
                    str(msg.id),
                    str(msg.conversation_id),
                    msg.role,
                    msg.content,
                    msg.agent_type or "",
                    msg.confidence_score or 0.0,
                    msg.created_at.isoformat()
                ])
            
            return output.getvalue()
        
        except Exception as e:
            raise Exception(f"Failed to export messages to CSV: {str(e)}")
    
    async def export_messages_json(
        self,
        conversation_id: uuid.UUID,
        limit: int = 5000
    ) -> str:
        """Export messages from a conversation to JSON"""
        try:
            query = select(Message).where(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).limit(limit)
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            data = {
                "export_date": datetime.now().isoformat(),
                "conversation_id": str(conversation_id),
                "total_messages": len(messages),
                "messages": [
                    {
                        "id": str(msg.id),
                        "role": msg.role,
                        "content": msg.content,
                        "agent_type": msg.agent_type,
                        "confidence_score": msg.confidence_score,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
            
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        except Exception as e:
            raise Exception(f"Failed to export messages to JSON: {str(e)}")
    
    async def export_feedback_csv(
        self,
        agent_type: Optional[str] = None,
        limit: int = 5000
    ) -> str:
        """Export user feedback to CSV"""
        try:
            query = select(UserFeedback)
            if agent_type:
                query = query.where(UserFeedback.agent_type == agent_type)
            query = query.order_by(desc(UserFeedback.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            feedback_records = result.scalars().all()
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "User ID", "Agent Type", "Rating", "Feedback Text",
                "Tags", "Is Helpful", "Created At"
            ])
            
            # Write data
            for feedback in feedback_records:
                writer.writerow([
                    str(feedback.id),
                    str(feedback.user_id),
                    feedback.agent_type,
                    feedback.rating,
                    feedback.feedback_text or "",
                    ",".join(feedback.tags) if feedback.tags else "",
                    feedback.is_helpful,
                    feedback.created_at.isoformat()
                ])
            
            return output.getvalue()
        
        except Exception as e:
            raise Exception(f"Failed to export feedback to CSV: {str(e)}")
    
    async def export_feedback_json(
        self,
        agent_type: Optional[str] = None,
        limit: int = 5000
    ) -> str:
        """Export user feedback to JSON"""
        try:
            query = select(UserFeedback)
            if agent_type:
                query = query.where(UserFeedback.agent_type == agent_type)
            query = query.order_by(desc(UserFeedback.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            feedback_records = result.scalars().all()
            
            data = {
                "export_date": datetime.now().isoformat(),
                "agent_type": agent_type or "all",
                "total_feedback": len(feedback_records),
                "feedback": [
                    {
                        "id": str(feedback.id),
                        "user_id": str(feedback.user_id),
                        "agent_type": feedback.agent_type,
                        "rating": feedback.rating,
                        "feedback_text": feedback.feedback_text,
                        "tags": feedback.tags,
                        "is_helpful": feedback.is_helpful,
                        "created_at": feedback.created_at.isoformat()
                    }
                    for feedback in feedback_records
                ]
            }
            
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        except Exception as e:
            raise Exception(f"Failed to export feedback to JSON: {str(e)}")
    
    async def export_agent_interactions_csv(
        self,
        agent_type: Optional[str] = None,
        limit: int = 5000
    ) -> str:
        """Export agent interactions to CSV"""
        try:
            query = select(AgentInteraction)
            if agent_type:
                query = query.where(AgentInteraction.agent_type == agent_type)
            query = query.order_by(desc(AgentInteraction.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            interactions = result.scalars().all()
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Agent Type", "Task Type", "Status", "Execution Time (ms)",
                "Confidence Score", "Error Message", "Created At"
            ])
            
            # Write data
            for interaction in interactions:
                writer.writerow([
                    str(interaction.id),
                    interaction.agent_type,
                    interaction.task_type,
                    interaction.status,
                    interaction.execution_time_ms or 0,
                    interaction.confidence_score or 0.0,
                    interaction.error_message or "",
                    interaction.created_at.isoformat()
                ])
            
            return output.getvalue()
        
        except Exception as e:
            raise Exception(f"Failed to export agent interactions to CSV: {str(e)}")
    
    async def export_agent_interactions_json(
        self,
        agent_type: Optional[str] = None,
        limit: int = 5000
    ) -> str:
        """Export agent interactions to JSON"""
        try:
            query = select(AgentInteraction)
            if agent_type:
                query = query.where(AgentInteraction.agent_type == agent_type)
            query = query.order_by(desc(AgentInteraction.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            interactions = result.scalars().all()
            
            data = {
                "export_date": datetime.now().isoformat(),
                "agent_type": agent_type or "all",
                "total_interactions": len(interactions),
                "interactions": [
                    {
                        "id": str(interaction.id),
                        "agent_type": interaction.agent_type,
                        "task_type": interaction.task_type,
                        "status": interaction.status,
                        "execution_time_ms": interaction.execution_time_ms,
                        "confidence_score": interaction.confidence_score,
                        "error_message": interaction.error_message,
                        "created_at": interaction.created_at.isoformat()
                    }
                    for interaction in interactions
                ]
            }
            
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        except Exception as e:
            raise Exception(f"Failed to export agent interactions to JSON: {str(e)}")
    
    async def export_knowledge_base_json(
        self,
        limit: int = 10000
    ) -> str:
        """Export knowledge base (documents and FAQs) to JSON"""
        try:
            # Get documents
            doc_query = select(Document).where(
                Document.is_active == True
            ).limit(limit)
            doc_result = await self.db.execute(doc_query)
            documents = doc_result.scalars().all()
            
            # Get FAQs
            faq_query = select(FAQ).where(
                FAQ.is_active == True
            ).limit(limit)
            faq_result = await self.db.execute(faq_query)
            faqs = faq_result.scalars().all()
            
            data = {
                "export_date": datetime.now().isoformat(),
                "documents": [
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "content": doc.content,
                        "category": doc.category,
                        "source": doc.source,
                        "tags": doc.tags,
                        "created_at": doc.created_at.isoformat()
                    }
                    for doc in documents
                ],
                "faqs": [
                    {
                        "id": str(faq.id),
                        "question": faq.question,
                        "answer": faq.answer,
                        "category": faq.category,
                        "keywords": faq.keywords,
                        "priority": faq.priority,
                        "created_at": faq.created_at.isoformat()
                    }
                    for faq in faqs
                ]
            }
            
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        except Exception as e:
            raise Exception(f"Failed to export knowledge base to JSON: {str(e)}")
