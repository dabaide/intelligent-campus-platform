from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from datetime import datetime
import re

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from schemas.chat import ChatRequest, ChatResponse, ConversationCreate, ConversationResponse
from services.agent_orchestrator import AgentOrchestrator
from services.conversation_service import ConversationService
from services.rag_service import RAGService
from models.user import User
from api.deps import get_current_user

router = APIRouter()

@router.post("/start", response_model=ConversationResponse)
async def start_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """Start a new conversation"""
    try:
        conversation_service = ConversationService(db, redis)
        conversation = await conversation_service.create_conversation(
            user_id=current_user.id,
            title=conversation_data.title,
            category=conversation_data.category,
            is_anonymous=conversation_data.is_anonymous
        )
        return conversation
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start conversation: {str(e)}")

@router.post("/{conversation_id}/message", response_model=ChatResponse)
# [全局对话总线枢纽]:
# 1. 利用 FastAPI 依赖注入自动校验前端 JWT Token 鉴权状态。
# 2. 将消息数据双向持久化至异步 SQLite 数据库。
# 3. 将上下文环境投递至中枢大脑 AgentOrchestrator 进行智能调度。
async def send_message(
    conversation_id: str,
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Send a message and get AI response
    
    1. 接收前端消息请求，依赖注入 `get_current_user` 自动校验 JWT Token。
    2. 首先持久化用户发送的消息至数据库。
    3. 调用 AgentOrchestrator （意图调度器）将消息路由给不同的智能体专家处理。
    4. 拿到回答后持久化 AI 响应，并返回给前端。
    """
    try:
        # Validate conversation ownership
        conversation_service = ConversationService(db, redis)
        conversation = await conversation_service.get_conversation(
            conversation_id=uuid.UUID(conversation_id),
            user_id=current_user.id
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Save user message
        user_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            content=chat_request.message,
            role="user"
        )
        
        # Initialize agent orchestrator
        agent_orchestrator = AgentOrchestrator(db, redis)

        user_context = {
            "user_id": str(current_user.id),
            "role": current_user.role,
            "department": current_user.department,
            "grade": current_user.grade,
            "major": current_user.major,
            "db": db
        }

        # Deterministic routing for clear domain queries (prevents navigation canned replies)
        msg_text = chat_request.message or ""

        # Deterministic FAQ-direct answers for factual queries
        try:
            rag_service = RAGService(db, redis)
            faq_hits = await rag_service.search_faqs(query=msg_text, category=None, top_k=1)
        except Exception:
            faq_hits = []

        if faq_hits and (faq_hits[0].get("priority", 0) or 0) >= 4:
            faq = faq_hits[0]
            content = (faq.get("answer") or "").rstrip()
            if "来源" not in content:
                content = content + "\n\n来源：\n- 校园知识库（FAQ）"

            ai_response = {
                "status": "success",
                "content": content,
                "agent_type": "navigation",
                "confidence_score": 0.99,
                "sources": [
                    {
                        "type": "faq",
                        "title": faq.get("question") or "FAQ",
                        "category": faq.get("category") or "general",
                        "priority": faq.get("priority", 1)
                    }
                ],
                "suggestions": [],
                "metadata": {"answer_mode": "faq_direct"}
            }
        else:
            life_kw = r"图书馆|食堂|餐厅|宿舍|体育|运动|健身|校园卡|一卡通|充值|门禁|校车|交通|地图|位置|开放时间"
            admin_kw = r"奖学金|助学金|请假|报销|证明|手续|审批|缴费|费用|财务|发票"
            academic_kw = r"选课|课程|学分|成绩|绩点|考试|培养方案|毕业要求|转专业|学籍"

            if re.search(life_kw, msg_text, re.IGNORECASE):
                task_type = agent_orchestrator.agents["navigation"]._determine_task_type("life", msg_text)
                ai_response = await agent_orchestrator.agents["life"].process_request(task_type, msg_text, user_context)
            elif re.search(admin_kw, msg_text, re.IGNORECASE):
                task_type = agent_orchestrator.agents["navigation"]._determine_task_type("admin", msg_text)
                ai_response = await agent_orchestrator.agents["admin"].process_request(task_type, msg_text, user_context)
            elif re.search(academic_kw, msg_text, re.IGNORECASE):
                task_type = agent_orchestrator.agents["navigation"]._determine_task_type("academic", msg_text)
                ai_response = await agent_orchestrator.agents["academic"].process_request(task_type, msg_text, user_context)
            else:
                # Process message through multi-agent system
                ai_response = await agent_orchestrator.process_message(
                    conversation_id=conversation.id,
                    user_message=chat_request.message,
                    user_context={
                        "user_id": str(current_user.id),
                        "role": current_user.role,
                        "department": current_user.department,
                        "grade": current_user.grade,
                        "major": current_user.major
                    }
                )

        

        # Save AI response
        ai_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            content=ai_response["content"],
            role="assistant",
            agent_type=ai_response["agent_type"],
            metadata=ai_response.get("metadata", {})
        )
        
        # Update conversation context in background
        background_tasks.add_task(
            conversation_service.update_conversation_context,
            conversation.id,
            ai_response.get("context", {})
        )
        
        return ChatResponse(
            message_id=str(ai_message.id),
            content=ai_response["content"],
            agent_type=ai_response["agent_type"],
            confidence_score=ai_response.get("confidence_score"),
            sources=ai_response.get("sources", []),
            suggestions=ai_response.get("suggestions", []),
            created_at=ai_message.created_at
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

@router.get("/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation history"""
    try:
        conversation_service = ConversationService(db)
        messages = await conversation_service.get_conversation_messages(
            conversation_id=uuid.UUID(conversation_id),
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

@router.get("/conversations")
async def get_user_conversations(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's conversations"""
    try:
        conversation_service = ConversationService(db)
        conversations = await conversation_service.get_user_conversations(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")

@router.post("/{conversation_id}/feedback")
async def submit_feedback(
    conversation_id: str,
    rating: int,
    feedback_text: Optional[str] = None,
    feedback_type: str = "general",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit user feedback for conversation"""
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        conversation_service = ConversationService(db)
        feedback = await conversation_service.submit_feedback(
            conversation_id=uuid.UUID(conversation_id),
            user_id=current_user.id,
            rating=rating,
            feedback_text=feedback_text,
            feedback_type=feedback_type
        )
        
        return {"message": "Feedback submitted successfully", "feedback_id": str(feedback.id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation"""
    try:
        conversation_service = ConversationService(db)
        success = await conversation_service.delete_conversation(
            conversation_id=uuid.UUID(conversation_id),
            user_id=current_user.id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")
