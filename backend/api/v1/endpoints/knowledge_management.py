"""
Knowledge Base Management API Endpoints
Admin endpoints for managing knowledge base content
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from models.user import User
from api.deps import get_current_admin_user
from services.knowledge_management_service import KnowledgeManagementService

router = APIRouter()


# ==================== Document Management ====================

@router.post("/documents")
async def create_document(
    title: str,
    content: str,
    category: str,
    subcategory: Optional[str] = None,
    source: Optional[str] = None,
    file_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: bool = True,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Create a new document (admin only)
    
    Args:
        title: Document title
        content: Document content
        category: Document category (academic, life, administrative, general)
        subcategory: Optional subcategory
        source: Optional source reference
        file_type: Optional file type (pdf, docx, txt, html)
        tags: Optional tags for categorization
        is_public: Whether document is public
    """
    try:
        service = KnowledgeManagementService(db, redis)
        result = await service.create_document(
            title=title,
            content=content,
            category=category,
            subcategory=subcategory,
            source=source,
            file_type=file_type,
            tags=tags,
            is_public=is_public
        )
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")


@router.put("/documents/{document_id}")
async def update_document(
    document_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: Optional[bool] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Update a document (admin only)"""
    try:
        doc_uuid = uuid.UUID(document_id)
        service = KnowledgeManagementService(db, redis)
        result = await service.update_document(
            document_id=doc_uuid,
            title=title,
            content=content,
            category=category,
            subcategory=subcategory,
            tags=tags,
            is_public=is_public
        )
        return result
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update document: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Delete a document (admin only)"""
    try:
        doc_uuid = uuid.UUID(document_id)
        service = KnowledgeManagementService(db, redis)
        result = await service.delete_document(doc_uuid)
        return result
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Get document details (admin only)"""
    try:
        doc_uuid = uuid.UUID(document_id)
        service = KnowledgeManagementService(db, redis)
        doc = await service.get_document(doc_uuid)
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return doc
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@router.get("/documents")
async def list_documents(
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """List documents (admin only)"""
    try:
        service = KnowledgeManagementService(db, redis)
        result = await service.list_documents(category=category, skip=skip, limit=limit)
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


# ==================== FAQ Management ====================

@router.post("/faqs")
async def create_faq(
    question: str,
    answer: str,
    category: str,
    subcategory: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    priority: int = 1,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Create a new FAQ (admin only)
    
    Args:
        question: FAQ question
        answer: FAQ answer
        category: FAQ category
        subcategory: Optional subcategory
        keywords: Optional keywords for search
        priority: Priority level (1-5, higher is more important)
    """
    try:
        service = KnowledgeManagementService(db, redis)
        result = await service.create_faq(
            question=question,
            answer=answer,
            category=category,
            subcategory=subcategory,
            keywords=keywords,
            priority=priority
        )
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create FAQ: {str(e)}")


@router.put("/faqs/{faq_id}")
async def update_faq(
    faq_id: str,
    question: Optional[str] = None,
    answer: Optional[str] = None,
    category: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    priority: Optional[int] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Update a FAQ (admin only)"""
    try:
        faq_uuid = uuid.UUID(faq_id)
        service = KnowledgeManagementService(db, redis)
        result = await service.update_faq(
            faq_id=faq_uuid,
            question=question,
            answer=answer,
            category=category,
            keywords=keywords,
            priority=priority
        )
        return result
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FAQ ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update FAQ: {str(e)}")


@router.delete("/faqs/{faq_id}")
async def delete_faq(
    faq_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Delete a FAQ (admin only)"""
    try:
        faq_uuid = uuid.UUID(faq_id)
        service = KnowledgeManagementService(db, redis)
        result = await service.delete_faq(faq_uuid)
        return result
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FAQ ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete FAQ: {str(e)}")


@router.get("/faqs")
async def list_faqs(
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """List FAQs (admin only)"""
    try:
        service = KnowledgeManagementService(db, redis)
        result = await service.list_faqs(category=category, skip=skip, limit=limit)
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list FAQs: {str(e)}")


# ==================== Knowledge Statistics ====================

@router.get("/statistics")
async def get_knowledge_statistics(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get knowledge base statistics (admin only)
    
    Returns:
        - Total documents, FAQs, entities, chunks
        - Documents and FAQs by category
        - Timestamp
    """
    try:
        service = KnowledgeManagementService(db, redis)
        stats = await service.get_knowledge_statistics()
        return stats
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")
