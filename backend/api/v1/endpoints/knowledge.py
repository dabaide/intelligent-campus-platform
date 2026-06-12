from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import json
import os

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from services.rag_service import RAGService
from models.user import User
from models.knowledge_base import Document, FAQ, KnowledgeGraph
from api.deps import get_current_user, get_current_admin_user
from sqlalchemy import select, and_, or_, func

router = APIRouter()

@router.get("/search")
async def search_knowledge(
    query: str,
    category: Optional[str] = None,
    search_type: str = "hybrid",
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Search knowledge base
    """
    try:
        rag_service = RAGService(db, redis)
        
        if search_type == "semantic":
            results = await rag_service.semantic_search(
                query=query, 
                category=category, 
                top_k=limit
            )
            return {"results": results, "search_type": "semantic"}
        
        elif search_type == "faq":
            results = await rag_service.search_faqs(
                query=query,
                category=category,
                top_k=limit
            )
            return {"results": results, "search_type": "faq"}
        
        else:  # hybrid
            results = await rag_service.hybrid_search(
                query=query,
                category=category,
                top_k=limit
            )
            return {
                "semantic_results": results["semantic_results"],
                "faq_results": results["faq_results"],
                "total_results": results["total_results"],
                "search_type": "hybrid"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge search failed: {str(e)}"
        )

@router.get("/suggestions")
async def get_search_suggestions(
    partial_query: str,
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get search suggestions for partial query
    """
    try:
        rag_service = RAGService(db, redis)
        suggestions = await rag_service.get_search_suggestions(partial_query, limit)
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get suggestions: {str(e)}"
        )

@router.get("/documents")
# [知识库管理路由与权限拦截]:
# 核心资源访问关卡。提供对底层规章制度内容的增删改查(CRUD)能力，
# 强制校验 current_user.role 实现 RBAC 权限控制，非管理员自动过滤未公开文档。
async def get_documents(
    category: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get documents with pagination
    """
    try:
        query = select(Document).where(Document.is_active == True)
        
        if category:
            query = query.where(Document.category == category)
        
        # Public documents or admin access
        if current_user.role not in ["admin", "staff"]:
            query = query.where(Document.is_public == True)
        
        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        documents = result.scalars().all()
        
        document_list = []
        for doc in documents:
            document_list.append({
                "id": str(doc.id),
                "title": doc.title,
                "category": doc.category,
                "subcategory": doc.subcategory,
                "source": doc.source,
                "file_type": doc.file_type,
                "language": doc.language,
                "tags": doc.tags,
                "version": doc.version,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at
            })
        
        return {"documents": document_list}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get documents: {str(e)}"
        )

@router.get("/documents/{document_id}")
async def get_document_detail(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get detailed document information
    """
    try:
        query = select(Document).where(
            and_(
                Document.id == document_id,
                Document.is_active == True
            )
        )
        
        # Public access control
        if current_user.role not in ["admin", "staff"]:
            query = query.where(Document.is_public == True)
        
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Update view statistics
        rag_service = RAGService(db, redis)
        await rag_service.update_document_view_stats(document_id, str(current_user.id))
        
        return {
            "id": str(document.id),
            "title": document.title,
            "content": document.content,
            "category": document.category,
            "subcategory": document.subcategory,
            "source": document.source,
            "file_type": document.file_type,
            "language": document.language,
            "tags": document.tags,
            "metadata": document.meta_data,
            "version": document.version,
            "created_at": document.created_at,
            "updated_at": document.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get document detail: {str(e)}"
        )

@router.get("/faqs/popular")
async def get_popular_faqs(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get popular FAQ entries (sorted by priority and view count)
    """
    try:
        query = select(FAQ).where(FAQ.is_active == True)
        query = query.order_by(FAQ.priority.desc(), FAQ.view_count.desc()).limit(limit)
        result = await db.execute(query)
        faqs = result.scalars().all()
        
        faq_list = []
        for faq in faqs:
            faq_list.append({
                "id": str(faq.id),
                "question": faq.question,
                "answer": faq.answer,
                "category": faq.category,
                "subcategory": faq.subcategory,
                "keywords": faq.keywords,
                "priority": faq.priority,
                "view_count": faq.view_count,
                "helpful_count": faq.helpful_count,
                "created_at": faq.created_at,
                "updated_at": faq.updated_at
            })
        
        return {"faqs": faq_list}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get popular FAQs: {str(e)}"
        )

@router.get("/faqs")
async def get_faqs(
    category: Optional[str] = None,
    priority: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get FAQ entries with pagination
    """
    try:
        query = select(FAQ).where(FAQ.is_active == True)
        
        if category:
            query = query.where(FAQ.category == category)
            
        if priority:
            query = query.where(FAQ.priority >= priority)
        
        query = query.order_by(FAQ.priority.desc(), FAQ.view_count.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        faqs = result.scalars().all()
        
        faq_list = []
        for faq in faqs:
            faq_list.append({
                "id": str(faq.id),
                "question": faq.question,
                "answer": faq.answer,
                "category": faq.category,
                "subcategory": faq.subcategory,
                "keywords": faq.keywords,
                "priority": faq.priority,
                "view_count": faq.view_count,
                "helpful_count": faq.helpful_count,
                "created_at": faq.created_at,
                "updated_at": faq.updated_at
            })
        
        return {"faqs": faq_list}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get FAQs: {str(e)}"
        )

@router.post("/faqs/{faq_id}/helpful")
async def mark_faq_helpful(
    faq_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark FAQ as helpful
    """
    try:
        query = select(FAQ).where(FAQ.id == faq_id)
        result = await db.execute(query)
        faq = result.scalar_one_or_none()
        
        if not faq:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        faq.helpful_count += 1
        await db.commit()
        
        return {"message": "FAQ marked as helpful", "helpful_count": faq.helpful_count}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark FAQ as helpful: {str(e)}"
        )

@router.get("/categories")
async def get_knowledge_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get available knowledge categories
    """
    try:
        # Get document categories
        doc_query = select(Document.category).where(
            and_(
                Document.is_active == True,
                Document.category.isnot(None)
            )
        ).distinct()
        
        if current_user.role not in ["admin", "staff"]:
            doc_query = doc_query.where(Document.is_public == True)
        
        doc_result = await db.execute(doc_query)
        doc_categories = doc_result.scalars().all()
        
        # Get FAQ categories
        faq_query = select(FAQ.category).where(
            and_(
                FAQ.is_active == True,
                FAQ.category.isnot(None)
            )
        ).distinct()
        
        faq_result = await db.execute(faq_query)
        faq_categories = faq_result.scalars().all()
        
        # Combine and deduplicate
        all_categories = list(set(doc_categories + faq_categories))
        
        # Map category names to display names
        category_display_names = {
            "general": "通用",
            "administrative": "行政",
            "academic": "学术",
            "student_affairs": "学生事务",
            "finance": "财务",
            "library": "图书馆",
            "it_support": "IT支持",
            "campus_life": "校园生活"
        }
        
        # Format categories for frontend with document count
        formatted_categories = []
        for category in sorted(all_categories):
            # Count documents in this category
            doc_count_query = select(func.count(Document.id)).where(
                and_(
                    Document.category == category,
                    Document.is_active.is_(True)
                )
            )
            if current_user.role not in ["admin", "staff"]:
                doc_count_query = doc_count_query.where(Document.is_public.is_(True))
            
            doc_count_result = await db.execute(doc_count_query)
            doc_count = doc_count_result.scalar() or 0
            
            # Count FAQs in this category
            faq_count_query = select(func.count(FAQ.id)).where(
                and_(
                    FAQ.category == category,
                    FAQ.is_active.is_(True)
                )
            )
            faq_count_result = await db.execute(faq_count_query)
            faq_count = faq_count_result.scalar() or 0
            
            formatted_categories.append({
                "id": category,
                "name": category,
                "display_name": category_display_names.get(category, category),
                "document_count": doc_count + faq_count
            })
        
        return {"categories": formatted_categories}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get categories: {str(e)}"
        )

# Admin endpoints
@router.post("/documents", dependencies=[Depends(get_current_admin_user)])
async def create_document(
    title: str = Form(...),
    content: str = Form(...),
    category: str = Form(...),
    subcategory: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    file_type: str = Form("text"),
    language: str = Form("zh-CN"),
    tags: Optional[str] = Form(None),  # JSON string
    is_public: bool = Form(True),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Create new document (admin only)
    """
    try:
        # Handle file upload if provided
        if file:
            # Save uploaded file
            upload_dir = "uploads/documents"
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = f"{upload_dir}/{uuid.uuid4()}_{file.filename}"
            with open(file_path, "wb") as buffer:
                content_bytes = await file.read()
                buffer.write(content_bytes)
            
            # Extract text content based on file type
            if file.content_type == "text/plain":
                content = content_bytes.decode("utf-8")
            else:
                # For other file types, would need proper parsers
                content = f"File uploaded: {file.filename}"
            
            source = file_path
            file_type = file.content_type or "application/octet-stream"
        
        # Parse tags
        tag_list = None
        if tags:
            try:
                tag_list = json.loads(tags)
            except:
                tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Create document
        document = Document(
            title=title,
            content=content,
            category=category,
            subcategory=subcategory,
            source=source,
            file_type=file_type,
            language=language,
            tags=tag_list,
            is_active=True,
            is_public=is_public
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        # Add to RAG index
        rag_service = RAGService(db, redis)
        
        # Simple chunking (in production, would use more sophisticated chunking)
        chunk_size = 500
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
        
        success = await rag_service.add_document(document, chunks)
        if not success:
            # Log warning but don't fail the request
            print(f"Warning: Failed to add document to RAG index: {document.id}")
        
        return {
            "message": "Document created successfully",
            "document_id": str(document.id),
            "indexed": success
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create document: {str(e)}"
        )

@router.post("/faqs", dependencies=[Depends(get_current_admin_user)])
async def create_faq(
    faq_data: dict,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create new FAQ entry (admin only)
    """
    try:
        faq = FAQ(
            question=faq_data["question"],
            answer=faq_data["answer"],
            category=faq_data["category"],
            subcategory=faq_data.get("subcategory"),
            keywords=faq_data.get("keywords", []),
            priority=faq_data.get("priority", 1),
            is_active=True,
            created_by=current_user.username
        )
        
        db.add(faq)
        await db.commit()
        await db.refresh(faq)
        
        return {
            "message": "FAQ created successfully",
            "faq_id": str(faq.id)
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create FAQ: {str(e)}"
        )

@router.put("/documents/{document_id}", dependencies=[Depends(get_current_admin_user)])
async def update_document(
    document_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update document (admin only)
    """
    try:
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Update allowed fields
        updatable_fields = ["title", "content", "category", "subcategory", "tags", "is_public", "is_active"]
        
        for field, value in update_data.items():
            if field in updatable_fields and hasattr(document, field):
                setattr(document, field, value)
        
        document.updated_at = datetime.now()
        await db.commit()
        
        return {"message": "Document updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update document: {str(e)}"
        )

@router.delete("/documents/{document_id}", dependencies=[Depends(get_current_admin_user)])
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete document (admin only)
    """
    try:
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Soft delete
        document.is_active = False
        document.updated_at = datetime.now()
        await db.commit()
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )

@router.get("/analytics")
async def get_knowledge_analytics(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get knowledge base analytics (admin only)
    """
    try:
        # Document statistics
        doc_count_query = select(Document).where(Document.is_active == True)
        doc_result = await db.execute(doc_count_query)
        total_documents = len(doc_result.scalars().all())
        
        # FAQ statistics
        faq_count_query = select(FAQ).where(FAQ.is_active == True)
        faq_result = await db.execute(faq_count_query)
        total_faqs = len(faq_result.scalars().all())
        
        # Category distribution
        category_stats = {}
        
        # Get search analytics from Redis
        search_stats = {}
        try:
            # This would contain search frequency, popular queries, etc.
            search_stats = await redis.get_json("search_analytics") or {}
        except:
            pass
        
        return {
            "total_documents": total_documents,
            "total_faqs": total_faqs,
            "category_distribution": category_stats,
            "search_statistics": search_stats,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics: {str(e)}"
        )
