"""
Data Export API Endpoints
Handles exporting data in various formats
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
import io

from core.database import get_db
from models.user import User
from api.deps import get_current_user, get_current_admin_user
from services.export_service import ExportService

router = APIRouter()


@router.get("/conversations/csv")
async def export_conversations_csv(
    format: str = "csv",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export user's conversations to CSV"""
    try:
        export_service = ExportService(db)
        csv_data = await export_service.export_conversations_csv(
            user_id=current_user.id,
            limit=1000
        )
        
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=conversations.csv"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export conversations: {str(e)}")


@router.get("/conversations/json")
async def export_conversations_json(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export user's conversations to JSON"""
    try:
        export_service = ExportService(db)
        json_data = await export_service.export_conversations_json(
            user_id=current_user.id,
            limit=1000
        )
        
        return StreamingResponse(
            iter([json_data]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=conversations.json"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export conversations: {str(e)}")


@router.get("/messages/{conversation_id}/csv")
async def export_messages_csv(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export messages from a conversation to CSV"""
    try:
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        export_service = ExportService(db)
        csv_data = await export_service.export_messages_csv(
            conversation_id=conv_uuid,
            limit=5000
        )
        
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=messages_{conversation_id}.csv"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export messages: {str(e)}")


@router.get("/messages/{conversation_id}/json")
async def export_messages_json(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export messages from a conversation to JSON"""
    try:
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
        export_service = ExportService(db)
        json_data = await export_service.export_messages_json(
            conversation_id=conv_uuid,
            limit=5000
        )
        
        return StreamingResponse(
            iter([json_data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=messages_{conversation_id}.json"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export messages: {str(e)}")


@router.get("/feedback/csv")
async def export_feedback_csv(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Export feedback to CSV (admin only)"""
    try:
        export_service = ExportService(db)
        csv_data = await export_service.export_feedback_csv(
            agent_type=agent_type,
            limit=5000
        )
        
        filename = f"feedback_{agent_type}.csv" if agent_type else "feedback_all.csv"
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export feedback: {str(e)}")


@router.get("/feedback/json")
async def export_feedback_json(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Export feedback to JSON (admin only)"""
    try:
        export_service = ExportService(db)
        json_data = await export_service.export_feedback_json(
            agent_type=agent_type,
            limit=5000
        )
        
        filename = f"feedback_{agent_type}.json" if agent_type else "feedback_all.json"
        return StreamingResponse(
            iter([json_data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export feedback: {str(e)}")


@router.get("/agent-interactions/csv")
async def export_agent_interactions_csv(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Export agent interactions to CSV (admin only)"""
    try:
        export_service = ExportService(db)
        csv_data = await export_service.export_agent_interactions_csv(
            agent_type=agent_type,
            limit=5000
        )
        
        filename = f"interactions_{agent_type}.csv" if agent_type else "interactions_all.csv"
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export interactions: {str(e)}")


@router.get("/agent-interactions/json")
async def export_agent_interactions_json(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Export agent interactions to JSON (admin only)"""
    try:
        export_service = ExportService(db)
        json_data = await export_service.export_agent_interactions_json(
            agent_type=agent_type,
            limit=5000
        )
        
        filename = f"interactions_{agent_type}.json" if agent_type else "interactions_all.json"
        return StreamingResponse(
            iter([json_data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export interactions: {str(e)}")


@router.get("/knowledge-base/json")
async def export_knowledge_base_json(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Export knowledge base to JSON (admin only)"""
    try:
        export_service = ExportService(db)
        json_data = await export_service.export_knowledge_base_json(limit=10000)
        
        return StreamingResponse(
            iter([json_data]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=knowledge_base.json"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export knowledge base: {str(e)}")
