"""
Advanced Search API Endpoints
Provides enhanced search capabilities with filtering and sorting
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from core.database import get_db
from models.user import User
from api.deps import get_current_user
from services.advanced_search_service import AdvancedSearchService, SearchFilter, SortOrder

router = APIRouter()


@router.get("/documents")
async def search_documents(
    query: str = Query(..., min_length=1),
    category: Optional[str] = None,
    tags: Optional[str] = None,
    sort_by: str = Query("relevance", regex="^(relevance|date|title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Advanced search for documents
    
    Args:
        query: Search query string
        category: Optional category filter
        tags: Optional comma-separated tags
        sort_by: Sort field (relevance, date, title)
        sort_order: Sort order (asc, desc)
        limit: Results per page
        offset: Pagination offset
    """
    try:
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        
        filter_config = SearchFilter(
            query=query,
            category=category,
            tags=tag_list,
            sort_by=sort_by,
            sort_order=SortOrder(sort_order),
            limit=limit,
            offset=offset
        )
        
        search_service = AdvancedSearchService(db)
        results = await search_service.search_documents(filter_config)
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/faqs")
async def search_faqs(
    query: str = Query(..., min_length=1),
    category: Optional[str] = None,
    priority_min: Optional[int] = Query(None, ge=1, le=5),
    priority_max: Optional[int] = Query(None, ge=1, le=5),
    sort_by: str = Query("relevance", regex="^(relevance|priority|date)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Advanced search for FAQs
    
    Args:
        query: Search query string
        category: Optional category filter
        priority_min: Minimum priority (1-5)
        priority_max: Maximum priority (1-5)
        sort_by: Sort field (relevance, priority, date)
        sort_order: Sort order (asc, desc)
        limit: Results per page
        offset: Pagination offset
    """
    try:
        filter_config = SearchFilter(
            query=query,
            category=category,
            priority_min=priority_min,
            priority_max=priority_max,
            sort_by=sort_by,
            sort_order=SortOrder(sort_order),
            limit=limit,
            offset=offset
        )
        
        search_service = AdvancedSearchService(db)
        results = await search_service.search_faqs(filter_config)
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/conversations")
async def search_conversations(
    query: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = Query("date", regex="^(date|title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search user's conversations
    
    Args:
        query: Optional search query
        category: Optional category filter
        sort_by: Sort field (date, title)
        sort_order: Sort order (asc, desc)
        limit: Results per page
        offset: Pagination offset
    """
    try:
        filter_config = SearchFilter(
            query=query or "",
            category=category,
            sort_by=sort_by,
            sort_order=SortOrder(sort_order),
            limit=limit,
            offset=offset
        )
        
        search_service = AdvancedSearchService(db)
        results = await search_service.search_conversations(
            filter_config,
            user_id=str(current_user.id)
        )
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1),
    search_type: str = Query("all", regex="^(all|documents|faqs)$"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get search suggestions based on query
    
    Args:
        query: Search query for suggestions
        search_type: Type of suggestions (all, documents, faqs)
        limit: Maximum suggestions to return
    """
    try:
        search_service = AdvancedSearchService(db)
        suggestions = []
        
        if search_type in ["all", "documents"]:
            filter_config = SearchFilter(
                query=query,
                sort_by="relevance",
                limit=limit // 2
            )
            doc_results = await search_service.search_documents(filter_config)
            suggestions.extend([
                {
                    "type": "document",
                    "id": r["id"],
                    "title": r["title"],
                    "score": r["relevance_score"]
                }
                for r in doc_results.get("results", [])
            ])
        
        if search_type in ["all", "faqs"]:
            filter_config = SearchFilter(
                query=query,
                sort_by="relevance",
                limit=limit // 2
            )
            faq_results = await search_service.search_faqs(filter_config)
            suggestions.extend([
                {
                    "type": "faq",
                    "id": r["id"],
                    "title": r["question"],
                    "score": r["relevance_score"]
                }
                for r in faq_results.get("results", [])
            ])
        
        # Sort by score and limit
        suggestions = sorted(suggestions, key=lambda x: x["score"], reverse=True)[:limit]
        
        return {"suggestions": suggestions}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")
