"""
Advanced Search Service
Provides enhanced search capabilities with filtering, sorting, and faceting
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
import re

from models.knowledge_base import Document, FAQ
from models.conversation import Conversation, Message
from models.agent_interaction import AgentInteraction


class SortOrder(str, Enum):
    """Sort order enumeration"""
    ASC = "asc"
    DESC = "desc"


class SearchFilter:
    """Search filter configuration"""
    
    def __init__(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        priority_min: Optional[int] = None,
        priority_max: Optional[int] = None,
        sort_by: str = "relevance",
        sort_order: SortOrder = SortOrder.DESC,
        limit: int = 20,
        offset: int = 0
    ):
        self.query = query
        self.category = category
        self.tags = tags or []
        self.date_from = date_from
        self.date_to = date_to
        self.priority_min = priority_min
        self.priority_max = priority_max
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.limit = limit
        self.offset = offset


class AdvancedSearchService:
    """Service for advanced search operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def search_documents(
        self,
        filter_config: SearchFilter
    ) -> Dict[str, Any]:
        """
        Advanced search for documents
        
        Args:
            filter_config: Search filter configuration
        
        Returns:
            Search results with metadata
        """
        try:
            # Build base query
            query = select(Document).where(Document.is_active == True)
            
            # Apply text search
            if filter_config.query.strip():
                search_terms = filter_config.query.split()
                conditions = []
                for term in search_terms:
                    term_pattern = f"%{term}%"
                    conditions.append(
                        or_(
                            Document.title.ilike(term_pattern),
                            Document.content.ilike(term_pattern),
                            Document.tags.ilike(term_pattern)
                        )
                    )
                if conditions:
                    query = query.where(and_(*conditions))
            
            # Apply category filter
            if filter_config.category:
                query = query.where(Document.category == filter_config.category)
            
            # Apply tag filter
            if filter_config.tags:
                for tag in filter_config.tags:
                    query = query.where(Document.tags.ilike(f"%{tag}%"))
            
            # Apply date range filter
            if filter_config.date_from:
                query = query.where(Document.created_at >= filter_config.date_from)
            if filter_config.date_to:
                query = query.where(Document.created_at <= filter_config.date_to)
            
            # Get total count before pagination
            count_query = select(func.count(Document.id)).select_from(Document).where(
                and_(*[c for c in query.whereclause.clauses if c is not None])
            ) if query.whereclause else select(func.count(Document.id)).select_from(Document)
            
            count_result = await self.db.execute(count_query)
            total_count = count_result.scalar() or 0
            
            # Apply sorting
            if filter_config.sort_by == "relevance":
                # Simple relevance: prioritize title matches
                query = query.order_by(
                    desc(Document.title.ilike(f"%{filter_config.query}%")),
                    desc(Document.created_at)
                )
            elif filter_config.sort_by == "date":
                sort_col = desc(Document.created_at) if filter_config.sort_order == SortOrder.DESC else Document.created_at
                query = query.order_by(sort_col)
            elif filter_config.sort_by == "title":
                sort_col = desc(Document.title) if filter_config.sort_order == SortOrder.DESC else Document.title
                query = query.order_by(sort_col)
            
            # Apply pagination
            query = query.limit(filter_config.limit).offset(filter_config.offset)
            
            result = await self.db.execute(query)
            documents = result.scalars().all()
            
            # Calculate relevance scores
            results = []
            for doc in documents:
                relevance_score = self._calculate_relevance(doc, filter_config.query)
                results.append({
                    "id": str(doc.id),
                    "title": doc.title,
                    "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                    "category": doc.category,
                    "source": doc.source,
                    "tags": doc.tags,
                    "relevance_score": relevance_score,
                    "created_at": doc.created_at.isoformat()
                })
            
            return {
                "total": total_count,
                "limit": filter_config.limit,
                "offset": filter_config.offset,
                "results": results,
                "facets": await self._get_document_facets()
            }
        
        except Exception as e:
            raise Exception(f"Failed to search documents: {str(e)}")
    
    async def search_faqs(
        self,
        filter_config: SearchFilter
    ) -> Dict[str, Any]:
        """Advanced search for FAQs"""
        try:
            # Build base query
            query = select(FAQ).where(FAQ.is_active == True)
            
            # Apply text search
            if filter_config.query.strip():
                search_terms = filter_config.query.split()
                conditions = []
                for term in search_terms:
                    term_pattern = f"%{term}%"
                    conditions.append(
                        or_(
                            FAQ.question.ilike(term_pattern),
                            FAQ.answer.ilike(term_pattern),
                            FAQ.keywords.ilike(term_pattern)
                        )
                    )
                if conditions:
                    query = query.where(and_(*conditions))
            
            # Apply category filter
            if filter_config.category:
                query = query.where(FAQ.category == filter_config.category)
            
            # Apply priority filter
            if filter_config.priority_min is not None:
                query = query.where(FAQ.priority >= filter_config.priority_min)
            if filter_config.priority_max is not None:
                query = query.where(FAQ.priority <= filter_config.priority_max)
            
            # Get total count
            count_result = await self.db.execute(select(func.count(FAQ.id)).select_from(FAQ))
            total_count = count_result.scalar() or 0
            
            # Apply sorting
            if filter_config.sort_by == "priority":
                sort_col = desc(FAQ.priority) if filter_config.sort_order == SortOrder.DESC else FAQ.priority
                query = query.order_by(sort_col)
            elif filter_config.sort_by == "date":
                sort_col = desc(FAQ.created_at) if filter_config.sort_order == SortOrder.DESC else FAQ.created_at
                query = query.order_by(sort_col)
            elif filter_config.sort_by == "relevance":
                query = query.order_by(
                    desc(FAQ.question.ilike(f"%{filter_config.query}%")),
                    desc(FAQ.priority)
                )
            
            # Apply pagination
            query = query.limit(filter_config.limit).offset(filter_config.offset)
            
            result = await self.db.execute(query)
            faqs = result.scalars().all()
            
            results = []
            for faq in faqs:
                relevance_score = self._calculate_relevance(faq, filter_config.query)
                results.append({
                    "id": str(faq.id),
                    "question": faq.question,
                    "answer": faq.answer[:200] + "..." if len(faq.answer) > 200 else faq.answer,
                    "category": faq.category,
                    "keywords": faq.keywords,
                    "priority": faq.priority,
                    "relevance_score": relevance_score,
                    "view_count": faq.view_count or 0,
                    "created_at": faq.created_at.isoformat()
                })
            
            return {
                "total": total_count,
                "limit": filter_config.limit,
                "offset": filter_config.offset,
                "results": results,
                "facets": await self._get_faq_facets()
            }
        
        except Exception as e:
            raise Exception(f"Failed to search FAQs: {str(e)}")
    
    async def search_conversations(
        self,
        filter_config: SearchFilter,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Advanced search for conversations"""
        try:
            query = select(Conversation)
            
            # Filter by user if provided
            if user_id:
                query = query.where(Conversation.user_id == user_id)
            
            # Apply text search on title
            if filter_config.query.strip():
                query = query.where(Conversation.title.ilike(f"%{filter_config.query}%"))
            
            # Apply category filter
            if filter_config.category:
                query = query.where(Conversation.category == filter_config.category)
            
            # Apply date range filter
            if filter_config.date_from:
                query = query.where(Conversation.created_at >= filter_config.date_from)
            if filter_config.date_to:
                query = query.where(Conversation.created_at <= filter_config.date_to)
            
            # Get total count
            count_result = await self.db.execute(select(func.count(Conversation.id)))
            total_count = count_result.scalar() or 0
            
            # Apply sorting
            if filter_config.sort_by == "date":
                sort_col = desc(Conversation.created_at) if filter_config.sort_order == SortOrder.DESC else Conversation.created_at
                query = query.order_by(sort_col)
            elif filter_config.sort_by == "title":
                sort_col = desc(Conversation.title) if filter_config.sort_order == SortOrder.DESC else Conversation.title
                query = query.order_by(sort_col)
            else:
                query = query.order_by(desc(Conversation.updated_at))
            
            # Apply pagination
            query = query.limit(filter_config.limit).offset(filter_config.offset)
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            results = []
            for conv in conversations:
                results.append({
                    "id": str(conv.id),
                    "title": conv.title,
                    "category": conv.category,
                    "status": conv.status,
                    "message_count": conv.message_count or 0,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
                })
            
            return {
                "total": total_count,
                "limit": filter_config.limit,
                "offset": filter_config.offset,
                "results": results
            }
        
        except Exception as e:
            raise Exception(f"Failed to search conversations: {str(e)}")
    
    def _calculate_relevance(self, item: Any, query: str) -> float:
        """Calculate relevance score for a search result"""
        if not query.strip():
            return 0.5
        
        score = 0.0
        query_lower = query.lower()
        
        # Check title/question match
        title_attr = getattr(item, 'title', None) or getattr(item, 'question', None)
        if title_attr and query_lower in title_attr.lower():
            score += 0.7
        
        # Check content/answer match
        content_attr = getattr(item, 'content', None) or getattr(item, 'answer', None)
        if content_attr and query_lower in content_attr.lower():
            score += 0.3
        
        # Check keywords/tags match
        keywords_attr = getattr(item, 'keywords', None) or getattr(item, 'tags', None)
        if keywords_attr and query_lower in keywords_attr.lower():
            score += 0.2
        
        return min(score, 1.0)
    
    async def _get_document_facets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get document facets for filtering"""
        try:
            # Get category facets
            category_query = select(
                Document.category,
                func.count(Document.id).label("count")
            ).where(Document.is_active == True).group_by(Document.category)
            
            category_result = await self.db.execute(category_query)
            categories = category_result.all()
            
            return {
                "categories": [
                    {"name": cat, "count": count}
                    for cat, count in categories if cat
                ]
            }
        except Exception as e:
            print(f"❌ Failed to get document facets: {str(e)}")
            return {}
    
    async def _get_faq_facets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get FAQ facets for filtering"""
        try:
            # Get category facets
            category_query = select(
                FAQ.category,
                func.count(FAQ.id).label("count")
            ).where(FAQ.is_active == True).group_by(FAQ.category)
            
            category_result = await self.db.execute(category_query)
            categories = category_result.all()
            
            # Get priority facets
            priority_query = select(
                FAQ.priority,
                func.count(FAQ.id).label("count")
            ).where(FAQ.is_active == True).group_by(FAQ.priority)
            
            priority_result = await self.db.execute(priority_query)
            priorities = priority_result.all()
            
            return {
                "categories": [
                    {"name": cat, "count": count}
                    for cat, count in categories if cat
                ],
                "priorities": [
                    {"priority": pri, "count": count}
                    for pri, count in priorities if pri
                ]
            }
        except Exception as e:
            print(f"❌ Failed to get FAQ facets: {str(e)}")
            return {}
