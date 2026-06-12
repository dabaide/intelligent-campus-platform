"""
Knowledge Base Management Service
Enhanced knowledge base management with advanced features
"""

from typing import List, Dict, Any, Optional, Tuple
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
import json

from models.knowledge_base import Document, DocumentChunk, FAQ, KnowledgeGraph
from core.redis_client import RedisClient


class KnowledgeManagementService:
    """Service for managing knowledge base content"""
    
    def __init__(self, db: AsyncSession, redis: RedisClient = None):
        self.db = db
        self.redis = redis
    
    # ==================== Document Management ====================
    
    async def create_document(
        self,
        title: str,
        content: str,
        category: str,
        subcategory: Optional[str] = None,
        source: Optional[str] = None,
        file_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_public: bool = True
    ) -> Dict[str, Any]:
        """Create a new document"""
        try:
            doc = Document(
                id=uuid.uuid4(),
                title=title,
                content=content,
                category=category,
                subcategory=subcategory,
                source=source,
                file_type=file_type,
                tags=json.dumps(tags) if tags else None,
                meta_data=metadata,
                is_public=is_public,
                is_active=True,
                created_at=datetime.now()
            )
            
            self.db.add(doc)
            await self.db.commit()
            await self.db.refresh(doc)
            
            # Invalidate cache
            if self.redis:
                await self.redis.delete_pattern("search:*")
            
            return {
                "id": str(doc.id),
                "title": doc.title,
                "category": doc.category,
                "status": "created"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create document: {str(e)}")
    
    async def update_document(
        self,
        document_id: uuid.UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_public: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an existing document"""
        try:
            query = select(Document).where(Document.id == document_id)
            result = await self.db.execute(query)
            doc = result.scalar_one_or_none()
            
            if not doc:
                raise ValueError("Document not found")
            
            # Update fields
            if title:
                doc.title = title
            if content:
                doc.content = content
            if category:
                doc.category = category
            if subcategory:
                doc.subcategory = subcategory
            if tags is not None:
                doc.tags = json.dumps(tags)
            if metadata:
                doc.meta_data = metadata
            if is_public is not None:
                doc.is_public = is_public
            
            doc.updated_at = datetime.now()
            
            await self.db.commit()
            
            # Invalidate cache
            if self.redis:
                await self.redis.delete_pattern("search:*")
            
            return {
                "id": str(doc.id),
                "status": "updated"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update document: {str(e)}")
    
    async def delete_document(self, document_id: uuid.UUID) -> Dict[str, Any]:
        """Soft delete a document"""
        try:
            query = select(Document).where(Document.id == document_id)
            result = await self.db.execute(query)
            doc = result.scalar_one_or_none()
            
            if not doc:
                raise ValueError("Document not found")
            
            doc.is_active = False
            doc.updated_at = datetime.now()
            
            await self.db.commit()
            
            # Invalidate cache
            if self.redis:
                await self.redis.delete_pattern("search:*")
            
            return {
                "id": str(doc.id),
                "status": "deleted"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to delete document: {str(e)}")
    
    async def get_document(self, document_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get document details"""
        try:
            query = select(Document).where(
                and_(Document.id == document_id, Document.is_active == True)
            )
            result = await self.db.execute(query)
            doc = result.scalar_one_or_none()
            
            if not doc:
                return None
            
            return {
                "id": str(doc.id),
                "title": doc.title,
                "content": doc.content,
                "category": doc.category,
                "subcategory": doc.subcategory,
                "source": doc.source,
                "file_type": doc.file_type,
                "tags": json.loads(doc.tags) if doc.tags else [],
                "metadata": doc.meta_data,
                "is_public": doc.is_public,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
            }
        
        except Exception as e:
            print(f"❌ Failed to get document: {str(e)}")
            return None
    
    async def list_documents(
        self,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """List documents with pagination"""
        try:
            query = select(Document).where(Document.is_active == True)
            
            if category:
                query = query.where(Document.category == category)
            
            # Get total count
            count_query = select(func.count(Document.id)).where(Document.is_active == True)
            if category:
                count_query = count_query.where(Document.category == category)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0
            
            # Get paginated results
            query = query.order_by(desc(Document.created_at)).offset(skip).limit(limit)
            result = await self.db.execute(query)
            docs = result.scalars().all()
            
            return {
                "total": total,
                "skip": skip,
                "limit": limit,
                "documents": [
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "category": doc.category,
                        "subcategory": doc.subcategory,
                        "source": doc.source,
                        "created_at": doc.created_at.isoformat()
                    }
                    for doc in docs
                ]
            }
        
        except Exception as e:
            print(f"❌ Failed to list documents: {str(e)}")
            return {"total": 0, "documents": []}
    
    # ==================== FAQ Management ====================
    
    async def create_faq(
        self,
        question: str,
        answer: str,
        category: str,
        subcategory: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        priority: int = 1
    ) -> Dict[str, Any]:
        """Create a new FAQ"""
        try:
            faq = FAQ(
                id=uuid.uuid4(),
                question=question,
                answer=answer,
                category=category,
                subcategory=subcategory,
                keywords=json.dumps(keywords) if keywords else None,
                priority=priority,
                is_active=True,
                created_at=datetime.now()
            )
            
            self.db.add(faq)
            await self.db.commit()
            await self.db.refresh(faq)
            
            # Invalidate cache
            if self.redis:
                await self.redis.delete_pattern("search:*")
            
            return {
                "id": str(faq.id),
                "question": faq.question,
                "category": faq.category,
                "status": "created"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create FAQ: {str(e)}")
    
    async def update_faq(
        self,
        faq_id: uuid.UUID,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        priority: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update an existing FAQ"""
        try:
            query = select(FAQ).where(FAQ.id == faq_id)
            result = await self.db.execute(query)
            faq = result.scalar_one_or_none()
            
            if not faq:
                raise ValueError("FAQ not found")
            
            if question:
                faq.question = question
            if answer:
                faq.answer = answer
            if category:
                faq.category = category
            if keywords is not None:
                faq.keywords = json.dumps(keywords)
            if priority is not None:
                faq.priority = priority
            
            faq.updated_at = datetime.now()
            
            await self.db.commit()
            
            # Invalidate cache
            if self.redis:
                await self.redis.delete_pattern("search:*")
            
            return {
                "id": str(faq.id),
                "status": "updated"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update FAQ: {str(e)}")
    
    async def delete_faq(self, faq_id: uuid.UUID) -> Dict[str, Any]:
        """Soft delete a FAQ"""
        try:
            query = select(FAQ).where(FAQ.id == faq_id)
            result = await self.db.execute(query)
            faq = result.scalar_one_or_none()
            
            if not faq:
                raise ValueError("FAQ not found")
            
            faq.is_active = False
            faq.updated_at = datetime.now()
            
            await self.db.commit()
            
            # Invalidate cache
            if self.redis:
                await self.redis.delete_pattern("search:*")
            
            return {
                "id": str(faq.id),
                "status": "deleted"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to delete FAQ: {str(e)}")
    
    async def list_faqs(
        self,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """List FAQs with pagination"""
        try:
            query = select(FAQ).where(FAQ.is_active == True)
            
            if category:
                query = query.where(FAQ.category == category)
            
            # Get total count
            count_query = select(func.count(FAQ.id)).where(FAQ.is_active == True)
            if category:
                count_query = count_query.where(FAQ.category == category)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0
            
            # Get paginated results
            query = query.order_by(desc(FAQ.priority), desc(FAQ.created_at)).offset(skip).limit(limit)
            result = await self.db.execute(query)
            faqs = result.scalars().all()
            
            return {
                "total": total,
                "skip": skip,
                "limit": limit,
                "faqs": [
                    {
                        "id": str(faq.id),
                        "question": faq.question,
                        "answer": faq.answer[:200] + "..." if len(faq.answer) > 200 else faq.answer,
                        "category": faq.category,
                        "priority": faq.priority,
                        "view_count": faq.view_count,
                        "created_at": faq.created_at.isoformat()
                    }
                    for faq in faqs
                ]
            }
        
        except Exception as e:
            print(f"❌ Failed to list FAQs: {str(e)}")
            return {"total": 0, "faqs": []}
    
    async def increment_faq_view_count(self, faq_id: uuid.UUID) -> bool:
        """Increment FAQ view count"""
        try:
            query = select(FAQ).where(FAQ.id == faq_id)
            result = await self.db.execute(query)
            faq = result.scalar_one_or_none()
            
            if faq:
                faq.view_count = (faq.view_count or 0) + 1
                await self.db.commit()
                return True
            
            return False
        
        except Exception as e:
            print(f"❌ Failed to increment view count: {str(e)}")
            return False
    
    # ==================== Knowledge Graph Management ====================
    
    async def create_knowledge_entity(
        self,
        entity_name: str,
        entity_type: str,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        relationships: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a knowledge graph entity"""
        try:
            entity = KnowledgeGraph(
                id=uuid.uuid4(),
                entity_name=entity_name,
                entity_type=entity_type,
                description=description,
                properties=properties,
                relationships=relationships,
                is_verified=False,
                created_at=datetime.now()
            )
            
            self.db.add(entity)
            await self.db.commit()
            await self.db.refresh(entity)
            
            return {
                "id": str(entity.id),
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "status": "created"
            }
        
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to create knowledge entity: {str(e)}")
    
    async def get_knowledge_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        try:
            # Count documents
            doc_query = select(func.count(Document.id)).where(Document.is_active == True)
            doc_result = await self.db.execute(doc_query)
            total_documents = doc_result.scalar() or 0
            
            # Count FAQs
            faq_query = select(func.count(FAQ.id)).where(FAQ.is_active == True)
            faq_result = await self.db.execute(faq_query)
            total_faqs = faq_result.scalar() or 0
            
            # Count knowledge entities
            entity_query = select(func.count(KnowledgeGraph.id))
            entity_result = await self.db.execute(entity_query)
            total_entities = entity_result.scalar() or 0
            
            # Count document chunks
            chunk_query = select(func.count(DocumentChunk.id))
            chunk_result = await self.db.execute(chunk_query)
            total_chunks = chunk_result.scalar() or 0
            
            # Documents by category
            cat_query = select(
                Document.category,
                func.count(Document.id).label("count")
            ).where(Document.is_active == True).group_by(Document.category)
            
            cat_result = await self.db.execute(cat_query)
            docs_by_category = {row[0]: row[1] for row in cat_result.all()}
            
            # FAQs by category
            faq_cat_query = select(
                FAQ.category,
                func.count(FAQ.id).label("count")
            ).where(FAQ.is_active == True).group_by(FAQ.category)
            
            faq_cat_result = await self.db.execute(faq_cat_query)
            faqs_by_category = {row[0]: row[1] for row in faq_cat_result.all()}
            
            return {
                "total_documents": total_documents,
                "total_faqs": total_faqs,
                "total_entities": total_entities,
                "total_chunks": total_chunks,
                "documents_by_category": docs_by_category,
                "faqs_by_category": faqs_by_category,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"❌ Failed to get knowledge statistics: {str(e)}")
            return {}
