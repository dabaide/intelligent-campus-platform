from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from core.database import get_db
from core.redis_client import get_redis, RedisClient
from schemas.chat import AgentInteractionRequest, AgentInteractionResponse
from services.agent_orchestrator import AgentOrchestrator
from models.user import User
from models.agent_interaction import AgentInteraction, AgentPerformance
from api.deps import get_current_user, get_current_admin_user
from sqlalchemy import select, func

router = APIRouter()

@router.post("/interact/{agent_type}", response_model=AgentInteractionResponse)
async def interact_with_agent(
    agent_type: str,
    interaction_request: AgentInteractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Direct interaction with a specific agent
    """
    try:
        # Validate agent type
        valid_agents = ["navigation", "academic", "life", "admin", "quality"]
        if agent_type not in valid_agents:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid agent type. Must be one of: {', '.join(valid_agents)}"
            )
        
        # Initialize agent orchestrator
        agent_orchestrator = AgentOrchestrator(db, redis)
        
        # Get the specific agent
        if agent_type not in agent_orchestrator.agents:
            raise HTTPException(status_code=500, detail=f"Agent {agent_type} not available")
        
        agent = agent_orchestrator.agents[agent_type]
        
        # Create conversation context
        user_context = {
            "user_id": str(current_user.id),
            "role": current_user.role,
            "department": current_user.department,
            "grade": current_user.grade,
            "major": current_user.major
        }
        
        # Record interaction start
        interaction = AgentInteraction(
            conversation_id=uuid.uuid4(),  # Create temporary conversation ID
            agent_type=agent_type,
            agent_name=f"{agent_type.capitalize()}Agent",
            task_type=interaction_request.task_type,
            input_data=interaction_request.input_data,
            status="processing"
        )
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)
        
        start_time = datetime.now()
        
        # Process request
        if agent_type == "navigation":
            # For navigation agent, use analyze_intent method
            result = await agent.analyze_intent(
                interaction_request.input_data.get("message", ""),
                user_context
            )
        else:
            # For other agents, use process_request method
            result = await agent.process_request(
                interaction_request.task_type,
                interaction_request.input_data.get("query", ""),
                user_context
            )
        
        # Update interaction record
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        interaction.output_data = result
        interaction.status = "completed" if result.get("status") == "success" else "failed"
        interaction.execution_time_ms = execution_time
        interaction.confidence_score = result.get("confidence_score")
        interaction.completed_at = datetime.now()
        
        if result.get("status") == "error":
            interaction.error_message = result.get("error", "Unknown error")
        
        await db.commit()
        
        return AgentInteractionResponse(
            interaction_id=str(interaction.id),
            agent_type=agent_type,
            status=interaction.status,
            output_data=result,
            confidence_score=interaction.confidence_score,
            execution_time_ms=execution_time,
            created_at=interaction.started_at,
            completed_at=interaction.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if 'interaction' in locals():
            interaction.status = "failed"
            interaction.error_message = str(e)
            interaction.completed_at = datetime.now()
            await db.commit()
        
        raise HTTPException(
            status_code=500, 
            detail=f"Agent interaction failed: {str(e)}"
        )

@router.get("/performance")
async def get_agent_performance(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get agent performance statistics
    """
    try:
        query = select(AgentPerformance)
        
        if agent_type:
            query = query.where(AgentPerformance.agent_type == agent_type)
        
        result = await db.execute(query)
        performance_records = result.scalars().all()
        
        performance_data = []
        for record in performance_records:
            performance_data.append({
                "agent_type": record.agent_type,
                "agent_name": record.agent_name,
                "success_rate": record.success_rate,
                "avg_response_time_ms": record.avg_response_time_ms,
                "total_interactions": record.total_interactions,
                "successful_interactions": record.successful_interactions,
                "failed_interactions": record.failed_interactions,
                "user_satisfaction_score": record.user_satisfaction_score,
                "last_updated": record.last_updated
            })
        
        return {"performance_data": performance_data}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent performance: {str(e)}"
        )

@router.get("/interactions/history")
async def get_interaction_history(
    agent_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's agent interaction history
    """
    try:
        # Get user's conversations first
        from models.conversation import Conversation
        user_conversations_query = select(Conversation.id).where(Conversation.user_id == current_user.id)
        user_conv_result = await db.execute(user_conversations_query)
        user_conversation_ids = [row[0] for row in user_conv_result.fetchall()]
        
        if not user_conversation_ids:
            return {"interactions": [], "total": 0}
        
        # Query interactions
        query = select(AgentInteraction).where(
            AgentInteraction.conversation_id.in_(user_conversation_ids)
        )
        
        if agent_type:
            query = query.where(AgentInteraction.agent_type == agent_type)
        
        # Get total count
        count_query = select(func.count()).select_from(
            query.order_by(AgentInteraction.started_at.desc()).subquery()
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Get paginated results
        query = query.order_by(AgentInteraction.started_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        interactions = result.scalars().all()
        
        interaction_list = []
        for interaction in interactions:
            interaction_list.append({
                "id": str(interaction.id),
                "agent_type": interaction.agent_type,
                "agent_name": interaction.agent_name,
                "task_type": interaction.task_type,
                "status": interaction.status,
                "confidence_score": interaction.confidence_score,
                "execution_time_ms": interaction.execution_time_ms,
                "created_at": interaction.started_at,
                "completed_at": interaction.completed_at,
                "error_message": interaction.error_message
            })
        
        return {
            "interactions": interaction_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get interaction history: {str(e)}"
        )

@router.get("/capabilities")
async def get_agent_capabilities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get available agents and their capabilities
    """
    try:
        agent_orchestrator = AgentOrchestrator(db, redis)
        
        capabilities = {}
        for agent_type, capabilities_list in agent_orchestrator.agent_capabilities.items():
            agent_info = {
                "capabilities": capabilities_list,
                "description": _get_agent_description(agent_type),
                "example_tasks": _get_example_tasks(agent_type)
            }
            capabilities[agent_type] = agent_info
        
        return {"agents": capabilities}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent capabilities: {str(e)}"
        )

@router.post("/collaboration/{initiator_agent}/{target_agent}")
async def request_agent_collaboration(
    initiator_agent: str,
    target_agent: str,
    collaboration_request: dict,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    Request collaboration between agents (admin only)
    """
    try:
        valid_agents = ["navigation", "academic", "life", "admin", "quality"]
        
        if initiator_agent not in valid_agents or target_agent not in valid_agents:
            raise HTTPException(
                status_code=400,
                detail="Invalid agent types specified"
            )
        
        agent_orchestrator = AgentOrchestrator(db, redis)
        
        target_agent_instance = agent_orchestrator.agents.get(target_agent)
        if not target_agent_instance:
            raise HTTPException(
                status_code=500,
                detail=f"Target agent {target_agent} not available"
            )
        
        # Execute collaboration
        collaboration_type = collaboration_request.get("type", "general")
        request_data = collaboration_request.get("data", {})
        
        user_context = {
            "user_id": str(current_user.id),
            "role": current_user.role,
            "admin_request": True
        }
        
        result = await target_agent_instance.handle_collaboration(
            collaboration_type, request_data, user_context
        )
        
        return {
            "collaboration_result": result,
            "initiator_agent": initiator_agent,
            "target_agent": target_agent,
            "collaboration_type": collaboration_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent collaboration failed: {str(e)}"
        )

def _get_agent_description(agent_type: str) -> str:
    """Get description for agent type"""
    descriptions = {
        "navigation": "分析用户意图并将请求路由到相应的专业智能体",
        "academic": "处理学术相关问题：选课、成绩、培养方案、学分计算等",
        "life": "提供生活服务信息：食堂、图书馆、宿舍、校园地图等",
        "admin": "处理行政事务：奖学金、请假、报销、各类申请流程等",
        "quality": "交叉验证其他智能体的回答准确性，减少幻觉问题"
    }
    return descriptions.get(agent_type, "未知智能体")

def _get_example_tasks(agent_type: str) -> List[str]:
    """Get example tasks for agent type"""
    examples = {
        "navigation": [
            "我想了解学校相关信息",
            "帮我找到合适的服务",
            "这个问题应该问谁？"
        ],
        "academic": [
            "如何选择下学期的课程？",
            "我的GPA是如何计算的？",
            "专业培养方案是什么？",
            "考试安排查询"
        ],
        "life": [
            "食堂今天的菜单是什么？",
            "图书馆开放时间",
            "如何预约体育设施？",
            "宿舍相关问题"
        ],
        "admin": [
            "如何申请奖学金？",
            "请假流程是什么？",
            "费用报销怎么办理？",
            "需要开什么证明？"
        ],
        "quality": [
            "验证信息准确性",
            "检查回答质量",
            "交叉验证事实"
        ]
    }
    return examples.get(agent_type, ["通用任务处理"])
