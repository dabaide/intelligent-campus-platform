from typing import Dict, Any, List, Optional
import asyncio
import uuid
from datetime import datetime
import hashlib
import re
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis_client import RedisClient
from core.config import settings
from services.rag_service import RAGService
from services.ai_service import ai_service
from agents.navigation_agent import NavigationAgent
from agents.academic_agent import AcademicAgent
from agents.life_service_agent import LifeServiceAgent
from agents.admin_agent import AdminAgent
from agents.quality_agent import QualityAgent
from models.agent_interaction import AgentInteraction, AgentCollaboration

class AgentOrchestrator:
    """
    Orchestrates multi-agent interactions for the campus knowledge service platform
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.rag_service = RAGService(db, redis)
        
        # Initialize agents
        self.agents = {
            "navigation": NavigationAgent(db, redis),
            "academic": AcademicAgent(db, redis, self.rag_service),
            "life": LifeServiceAgent(db, redis, self.rag_service),
            "admin": AdminAgent(db, redis, self.rag_service),
            "quality": QualityAgent(db, redis)
        }
        
        self.agent_capabilities = {
            "navigation": ["intent_analysis", "route_request", "general_help"],
            "academic": ["course_selection", "curriculum_planning", "grade_calculation", "academic_policies"],
            "life": ["dining_info", "library_services", "campus_map", "dormitory_info", "transportation"],
            "admin": ["scholarship_info", "leave_application", "expense_reimbursement", "administrative_procedures"],
            "quality": ["response_verification", "accuracy_check", "fact_validation"]
        }
    
        # [MAS 多智能体中枢引擎]:
        # 系统架构的核心大脑。在此拦截用户输入，基于自然语言与特征词库进行意图识别(Intent Analysis)和任务路由分发，实现高内聚、低耦合的业务领域分离。
    async def process_message(self, conversation_id: uuid.UUID, user_message: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user message through the multi-agent system
        
        这是系统的核心调度入口。当收到用户消息时，系统并没有马上调大模型，而是先根据“特征词”去推测用户的意图（Intent Analysis），以此来决定由哪一个 Agent（智能体）来接管对话。
        """
        try:
            # Step 1: Navigation agent analyzes intent and routes request
            navigation_result = await self._route_request(conversation_id, user_message, user_context)
            
            if navigation_result["status"] == "error":
                return self._create_error_response(navigation_result["error"])
            
            primary_agent = navigation_result["primary_agent"]
            task_type = navigation_result["task_type"]
            processed_query = navigation_result["processed_query"]

            # Fallback deterministic routing to avoid canned navigation replies
            if primary_agent in {"navigation", "general", None} and not isinstance(navigation_result.get("response"), dict):
                q = (processed_query or user_message or "").lower()

                life_kw = r"图书馆|食堂|餐厅|宿舍|体育|运动|健身|校园卡|一卡通|充值|门禁|校车|交通|地图|位置|开放时间"
                admin_kw = r"奖学金|助学金|请假|报销|证明|手续|审批|缴费|费用|财务|发票"
                academic_kw = r"选课|课程|学分|成绩|绩点|考试|培养方案|毕业要求|转专业|学籍"

                if re.search(life_kw, q, re.IGNORECASE):
                    primary_agent = "life"
                    task_type = self.agents["navigation"]._determine_task_type("life", processed_query)
                elif re.search(admin_kw, q, re.IGNORECASE):
                    primary_agent = "admin"
                    task_type = self.agents["navigation"]._determine_task_type("admin", processed_query)
                elif re.search(academic_kw, q, re.IGNORECASE):
                    primary_agent = "academic"
                    task_type = self.agents["navigation"]._determine_task_type("academic", processed_query)
            
            # If navigation agent already produced a direct response (e.g. greeting/clarification), return it
            if primary_agent == "navigation" and isinstance(navigation_result.get("response"), dict):
                nav_response = navigation_result["response"]
                return self._format_final_response({
                    "status": "success",
                    "content": nav_response.get("content", ""),
                    "agent_type": "navigation",
                    "confidence_score": navigation_result.get("confidence", 0.9),
                    "sources": [],
                    "suggestions": nav_response.get("suggestions", []),
                    "metadata": {"task_type": task_type, "routed_by": "navigation"}
                })
            
            # Step 2: Primary agent processes the request
            primary_response = await self._execute_primary_task(
                conversation_id, primary_agent, task_type, processed_query, user_context
            )
            
            if primary_response["status"] == "error":
                return self._create_error_response(primary_response["error"])
            
            # Step 3: Quality agent verifies response (if enabled)
            if primary_response.get("requires_verification", False):
                verified_response = await self._verify_response(
                    conversation_id, primary_response, user_message
                )
                primary_response.update(verified_response)
            
            # Step 4: Handle collaborative scenarios
            if primary_response.get("requires_collaboration"):
                collaborative_response = await self._handle_collaboration(
                    conversation_id, primary_agent, primary_response, user_context
                )
                primary_response.update(collaborative_response)
            
            return self._format_final_response(primary_response)
            
        except Exception as e:
            return self._create_error_response(f"Agent orchestration failed: {str(e)}")
    
        # [高并发缓存防击穿拦截策略]:
        # 1. 计算用户输入特征与身份的 MD5 校验和，查询 Redis 连接池。
        # 2. 若命中重复热点查询则直接返回拦截，大幅降低并发状态下底层大模型 API 与关系型数据库的查询压力。
    async def _route_request(self, conversation_id: uuid.UUID, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route request through navigation agent
        
        1. 首先计算用户输入问题与用户ID的 MD5 哈希值
        2. 去 Redis 中查寻是否命中缓存（高频重复问题拦截）
        3. 命中直接返回，减少对数据库和大模型的压力，大幅提升 QPS
        """
        try:
            # Check cache first
            query_hash = hashlib.md5(f"{message}:{context.get('user_id')}".encode()).hexdigest()
            cached_result = await self.redis.get_cached_agent_response("navigation", query_hash)
            
            if cached_result:
                return cached_result
            
            # Record agent interaction
            interaction = AgentInteraction(
                conversation_id=conversation_id,
                agent_type="navigation",
                agent_name="NavigationAgent",
                task_type="intent_analysis",
                input_data={"message": message, "context": context},
                status="processing"
            )
            self.db.add(interaction)
            await self.db.commit()
            
            start_time = datetime.now()
            
            # Execute navigation agent
            result = await self.agents["navigation"].analyze_intent(message, context)
            
            # Update interaction record
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            interaction.output_data = result
            interaction.status = "completed" if result.get("status") == "success" else "failed"
            interaction.execution_time_ms = execution_time
            interaction.completed_at = datetime.now()
            
            await self.db.commit()
            
            # Cache result
            await self.redis.cache_agent_response("navigation", query_hash, result, expire=1800)
            
            return result
            
        except Exception as e:
            if 'interaction' in locals():
                interaction.status = "failed"
                interaction.error_message = str(e)
                interaction.completed_at = datetime.now()
                await self.db.commit()
            
            return {"status": "error", "error": f"Navigation routing failed: {str(e)}"}
    
    async def _execute_primary_task(self, conversation_id: uuid.UUID, agent_type: str, task_type: str, 
                                   query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with primary agent"""
        try:
            agent = self.agents.get(agent_type)
            if not agent:
                return {"status": "error", "error": f"Agent {agent_type} not found"}
            
            # Record agent interaction
            interaction = AgentInteraction(
                conversation_id=conversation_id,
                agent_type=agent_type,
                agent_name=f"{agent_type.capitalize()}Agent",
                task_type=task_type,
                input_data={"query": query, "context": context},
                status="processing"
            )
            self.db.add(interaction)
            await self.db.commit()
            
            start_time = datetime.now()
            
            # Add database session to context for RAG support
            context_with_db = {**context, "db": self.db}
            
            # Execute primary task
            if agent_type == "academic":
                result = await agent.process_request(task_type, query, context_with_db)
            elif agent_type == "life":
                result = await agent.process_request(task_type, query, context_with_db)
            elif agent_type == "admin":
                result = await agent.process_request(task_type, query, context_with_db)
            elif agent_type == "navigation":
                if context_with_db.get("db"):
                    result = await ai_service.generate_response_with_rag(
                        agent_type="navigation",
                        user_message=query,
                        db=context_with_db["db"],
                        context=context_with_db
                    )
                else:
                    result = await ai_service.generate_response(
                        agent_type="navigation",
                        user_message=query,
                        context=context_with_db
                    )
            else:
                result = {"status": "error", "error": f"Unknown agent type: {agent_type}"}
            
            # Update interaction record
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            interaction.output_data = result
            interaction.status = "completed" if result.get("status") == "success" else "failed"
            interaction.execution_time_ms = execution_time
            interaction.confidence_score = result.get("confidence_score")
            interaction.completed_at = datetime.now()
            
            await self.db.commit()
            
            return result
            
        except Exception as e:
            if 'interaction' in locals():
                interaction.status = "failed"
                interaction.error_message = str(e)
                interaction.completed_at = datetime.now()
                await self.db.commit()
            
            return {"status": "error", "error": f"Primary task execution failed: {str(e)}"}
    
    async def _verify_response(self, conversation_id: uuid.UUID, response: Dict[str, Any], 
                              original_query: str) -> Dict[str, Any]:
        """Verify response using quality agent"""
        try:
            quality_agent = self.agents["quality"]
            verification_result = await quality_agent.verify_response(
                original_query, response, conversation_id
            )
            
            return {
                "verification_score": verification_result.get("score", 0.0),
                "verification_notes": verification_result.get("notes", []),
                "is_verified": verification_result.get("is_verified", False)
            }
            
        except Exception as e:
            return {
                "verification_score": 0.0,
                "verification_notes": [f"Verification failed: {str(e)}"],
                "is_verified": False
            }
    
    async def _handle_collaboration(self, conversation_id: uuid.UUID, primary_agent: str, 
                                   primary_response: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle multi-agent collaboration"""
        try:
            collaboration_requests = primary_response.get("collaboration_requests", [])
            collaborative_results = []
            
            for request in collaboration_requests:
                target_agent = request["target_agent"]
                collaboration_type = request["type"]
                request_data = request["data"]
                
                # Record collaboration
                collaboration = AgentCollaboration(
                    conversation_id=conversation_id,
                    initiator_agent=primary_agent,
                    target_agent=target_agent,
                    collaboration_type=collaboration_type,
                    request_data=request_data,
                    status="processing"
                )
                self.db.add(collaboration)
                await self.db.commit()
                
                # Execute collaboration
                target_agent_instance = self.agents.get(target_agent)
                if target_agent_instance:
                    result = await target_agent_instance.handle_collaboration(
                        collaboration_type, request_data, context
                    )
                    
                    collaboration.response_data = result
                    collaboration.status = "completed"
                    collaboration.completed_at = datetime.now()
                    
                    collaborative_results.append({
                        "agent": target_agent,
                        "type": collaboration_type,
                        "result": result
                    })
                else:
                    collaboration.status = "failed"
                    collaboration.completed_at = datetime.now()
                
                await self.db.commit()
            
            return {"collaborative_results": collaborative_results}
            
        except Exception as e:
            return {"collaborative_error": str(e)}
    
    def _format_final_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Format the final response for the user"""
        return {
            "content": response.get("content", "抱歉，我无法处理您的请求。"),
            "agent_type": response.get("agent_type", "unknown"),
            "confidence_score": response.get("confidence_score"),
            "sources": response.get("sources", []),
            "suggestions": response.get("suggestions", []),
            "metadata": {
                "verification": response.get("verification_score"),
                "collaboration": response.get("collaborative_results"),
                "processing_time": response.get("execution_time_ms"),
                "requires_followup": response.get("requires_followup", False)
            }
        }
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "content": f"抱歉，处理您的请求时出现错误：{error_message}。请稍后再试或联系管理员。",
            "agent_type": "system",
            "confidence_score": 0.0,
            "sources": [],
            "suggestions": ["请重新表述您的问题", "联系技术支持", "查看帮助文档"],
            "metadata": {"error": error_message}
        }
