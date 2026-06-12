from typing import Dict, Any, List, Optional
import asyncio
import re
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.redis_client import RedisClient
from services.ai_service import ai_service
from core.config import settings

# [导航意图识别与前置拦截器]:
# 作为多智能体系统(MAS)的首层哨兵。负责查询的标准化预处理、
# 闲聊寒暄的直接拦截，以及为调度器提供特征值与路由决策支撑。
class NavigationAgent:
    """
    Navigation Agent - Analyzes user intent and routes requests to appropriate specialized agents
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.agent_name = "NavigationAgent"
        
        # Intent classification patterns
        self.intent_patterns = {
            "academic": [
                r"选课|课程|学分|成绩|考试|作业|教学|老师|导师|专业|培养方案|毕业要求",
                r"course|credit|grade|exam|homework|teacher|professor|major|curriculum",
                r"学术|研究|论文|实验|实习|学业"
            ],
            "life": [
                r"食堂|图书馆|宿舍|体育|运动|健身|校园卡|充值|门禁|校车|交通",
                r"canteen|library|dormitory|sports|gym|card|transport|bus|dining",
                r"生活|娱乐|社团|活动|设施|场馆|地图|位置|开放时间"
            ],
            "admin": [
                r"奖学金|助学金|请假|报销|证明|手续|申请|审批|流程|办理|政策",
                r"scholarship|grant|leave|reimbursement|certificate|application|procedure",
                r"行政|管理|财务|人事|档案|证件|表格|材料"
            ],
            "general": [
                r"帮助|指南|介绍|什么是|如何|怎么|查询|搜索|找到",
                r"help|guide|what|how|search|find|about|info",
                r"你好|您好|问候|感谢"
            ]
        }
        
        # Response templates
        self.greeting_responses = [
            "您好！我是智能校园助手，很高兴为您服务！",
            "欢迎使用智能校园知识服务平台！请问有什么可以帮助您的吗？",
            "您好！我可以帮您解决学术咨询、生活服务和行政事务等相关问题。"
        ]
    
    async def analyze_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user intent using DeepSeek AI and determine appropriate agent routing
        """
        try:
            # Check for greeting patterns first
            normalized_message = message.lower().strip()
            if self._is_greeting(normalized_message):
                return await self._handle_greeting(message, context)

            intent_scores = self._classify_intent(normalized_message)
            best_intent = max(intent_scores, key=intent_scores.get)
            best_score = intent_scores.get(best_intent, 0.0)

            # Force routing based on explicit keyword patterns (prevents falling back to navigation)
            forced_scores: Dict[str, int] = {}
            for forced_intent in ["academic", "life", "admin"]:
                forced_scores[forced_intent] = 0
                for pattern in self.intent_patterns.get(forced_intent, []):
                    forced_scores[forced_intent] += len(re.findall(pattern, normalized_message, re.IGNORECASE))

            forced_best_intent = max(forced_scores, key=forced_scores.get)
            if forced_scores.get(forced_best_intent, 0) > 0:
                return {
                    "status": "success",
                    "primary_agent": forced_best_intent,
                    "task_type": self._determine_task_type(forced_best_intent, message),
                    "processed_query": message,
                    "confidence": 0.9,
                    "agent_type": "navigation",
                    "fallback_used": True
                }
            
            # Use DeepSeek AI for intent analysis
            ai_result = await ai_service.analyze_intent(message, context)

            if ai_result.get("status") == "success":
                primary_agent = ai_result.get("primary_agent")
                if best_intent in {"academic", "life", "admin"} and best_score >= 0.6:
                    if primary_agent in {"navigation", "general", None}:
                        ai_result["primary_agent"] = best_intent
                    else:
                        try:
                            ai_conf = float(ai_result.get("confidence", 0.0) or 0.0)
                        except Exception:
                            ai_conf = 0.0
                        if ai_conf < best_score:
                            ai_result["primary_agent"] = best_intent
                    ai_result["task_type"] = self._determine_task_type(best_intent, message)
                    ai_result["processed_query"] = message
                    ai_result["confidence"] = max(float(ai_result.get("confidence", 0.0) or 0.0), best_score)
            
            if ai_result.get("status") == "error":
                # Fallback to pattern matching if AI fails
                primary_intent = best_intent
                confidence = best_score
                
                return {
                    "status": "success",
                    "primary_agent": primary_intent if confidence > 0.5 else "navigation",
                    "task_type": self._determine_task_type(primary_intent, message),
                    "processed_query": message,
                    "confidence": confidence,
                    "agent_type": "navigation",
                    "fallback_used": True
                }
            
            return ai_result
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Intent analysis failed: {str(e)}",
                "agent_type": "navigation"
            }
    
    def _is_greeting(self, message: str) -> bool:
        """Check if message is a greeting"""
        greeting_patterns = [
            r"你好|您好|hello|hi|嗨|哈喽",
            r"早上好|下午好|晚上好|good morning|good afternoon|good evening",
            r"谢谢|感谢|thank you|thanks"
        ]
        
        for pattern in greeting_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
    
    def _classify_intent(self, message: str) -> Dict[str, float]:
        """Classify message intent using pattern matching"""
        scores = {
            "academic": 0.0,
            "life": 0.0,
            "admin": 0.0,
            "general": 0.0
        }
        
        # Count pattern matches
        for intent, patterns in self.intent_patterns.items():
            match_count = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, message, re.IGNORECASE))
                match_count += matches
            
            # Calculate score based on matches and message length
            if match_count > 0:
                message_length = len(message.split())
                scores[intent] = min(match_count / message_length * 2, 1.0)
        
        # Normalize scores
        total_score = sum(scores.values())
        if total_score > 0:
            scores = {k: v / total_score for k, v in scores.items()}
        else:
            # Default to general if no patterns match
            scores["general"] = 1.0
        
        return scores
    
    async def _handle_greeting(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle greeting messages"""
        import random
        
        user_name = context.get("full_name", "同学")
        greeting = random.choice(self.greeting_responses)
        
        return {
            "status": "success",
            "primary_agent": "navigation",
            "task_type": "greeting",
            "processed_query": message,
            "response": {
                "content": f"{user_name}，{greeting}",
                "suggestions": [
                    "我想了解选课流程",
                    "图书馆开放时间是什么？",
                    "如何申请奖学金？",
                    "校园地图在哪里？"
                ]
            }
        }
    
    async def _direct_routing(self, intent: str, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Direct routing for high-confidence intents"""
        agent_mapping = {
            "academic": "academic",
            "life": "life",
            "admin": "admin",
            "general": "navigation"
        }
        
        target_agent = agent_mapping.get(intent, "navigation")
        
        # Determine specific task type
        task_type = self._determine_task_type(intent, message)
        
        return {
            "status": "success",
            "primary_agent": target_agent,
            "task_type": task_type,
            "processed_query": message,
            "routing_reason": f"High confidence match for {intent} intent",
            "requires_verification": target_agent != "navigation"
        }
    
    async def _clarification_routing(self, intent_scores: Dict[str, float], 
                                   message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle medium-confidence scenarios requiring clarification"""
        # Get top 2 intents
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        top_intents = sorted_intents[:2]
        
        clarification_options = []
        for intent, score in top_intents:
            if score > 0.3:
                option = self._get_clarification_option(intent)
                clarification_options.append(option)
        
        return {
            "status": "success",
            "primary_agent": "navigation",
            "task_type": "clarification",
            "processed_query": message,
            "response": {
                "content": "我理解您的问题可能涉及多个方面，请选择最符合您需求的类别：",
                "options": clarification_options,
                "original_query": message
            },
            "requires_followup": True
        }
    
    async def _general_routing(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle low-confidence scenarios with general assistance"""
        return {
            "status": "success",
            "primary_agent": "navigation",
            "task_type": "general_help",
            "processed_query": message,
            "response": {
                "content": "我来帮您解答问题！请您详细描述一下需要了解的内容，或者选择以下分类：",
                "suggestions": [
                    "🎓 学术相关 - 选课、成绩、培养方案等",
                    "🏠 生活服务 - 食堂、图书馆、宿舍等",
                    "📋 行政事务 - 奖学金、请假、报销等",
                    "❓ 其他问题 - 校园信息查询"
                ]
            }
        }
    
    def _determine_task_type(self, intent: str, message: str) -> str:
        """Determine specific task type based on intent and message"""
        task_mapping = {
            "academic": {
                "选课|课程": "course_selection",
                "成绩|分数": "grade_inquiry",
                "学分": "credit_calculation", 
                "培养方案": "curriculum_planning",
                "考试": "exam_info"
            },
            "life": {
                "食堂|餐厅": "dining_info",
                "图书馆": "library_services",
                "宿舍": "dormitory_info",
                "地图|位置": "campus_map",
                "体育|运动": "sports_facilities"
            },
            "admin": {
                "奖学金|助学金": "scholarship_info",
                "请假": "leave_application",
                "报销": "expense_reimbursement",
                "证明|证件": "certificate_services",
                "申请|手续": "administrative_procedures"
            },
            "general": {
                "帮助|指南": "help_guide",
                "查询|搜索": "general_search",
                "介绍": "introduction"
            }
        }
        
        message_lower = message.lower()
        
        if intent in task_mapping:
            for pattern, task_type in task_mapping[intent].items():
                if re.search(pattern, message_lower):
                    return task_type
        
        # Default task types
        defaults = {
            "academic": "general_academic",
            "life": "general_life",
            "admin": "general_admin",
            "general": "general_query"
        }
        
        return defaults.get(intent, "general_query")
    
    def _get_clarification_option(self, intent: str) -> Dict[str, str]:
        """Get clarification option for specific intent"""
        options = {
            "academic": {
                "title": "🎓 学术咨询",
                "description": "选课、成绩、培养方案、学分计算等",
                "value": "academic"
            },
            "life": {
                "title": "🏠 生活服务", 
                "description": "食堂、图书馆、宿舍、校园地图等",
                "value": "life"
            },
            "admin": {
                "title": "📋 行政事务",
                "description": "奖学金、请假、报销、各类申请等",
                "value": "admin"
            },
            "general": {
                "title": "❓ 一般咨询",
                "description": "校园基本信息、使用指南等",
                "value": "general"
            }
        }
        
        return options.get(intent, options["general"])
    
    async def handle_collaboration(self, collaboration_type: str, request_data: Dict[str, Any], 
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration requests from other agents"""
        try:
            if collaboration_type == "intent_reanalysis":
                # Re-analyze intent based on new context
                return await self._reanalyze_with_context(request_data, context)
            
            elif collaboration_type == "routing_suggestion":
                # Provide routing suggestions based on conversation history
                return await self._provide_routing_suggestions(request_data, context)
            
            else:
                return {
                    "status": "error",
                    "error": f"Unknown collaboration type: {collaboration_type}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": f"Navigation collaboration failed: {str(e)}"
            }
    
    async def _reanalyze_with_context(self, request_data: Dict[str, Any], 
                                    context: Dict[str, Any]) -> Dict[str, Any]:
        """Re-analyze intent with additional context"""
        original_message = request_data.get("original_message", "")
        additional_context = request_data.get("additional_context", {})
        
        # Merge contexts
        enhanced_context = {**context, **additional_context}
        
        # Re-run intent analysis
        result = await self.analyze_intent(original_message, enhanced_context)
        
        return {
            "status": "success",
            "reanalyzed_intent": result,
            "context_enhancement": "Applied additional context for better routing"
        }
    
    async def _provide_routing_suggestions(self, request_data: Dict[str, Any], 
                                         context: Dict[str, Any]) -> Dict[str, Any]:
        """Provide routing suggestions based on conversation patterns"""
        conversation_history = request_data.get("conversation_history", [])
        current_agent = request_data.get("current_agent", "")
        
        suggestions = []
        
        # Analyze conversation patterns
        if len(conversation_history) > 1:
            # Look for patterns indicating need for different agent
            recent_messages = conversation_history[-3:]
            
            # Simple heuristics for routing suggestions
            if any("不知道" in msg.get("content", "") for msg in recent_messages):
                suggestions.append({
                    "agent": "quality",
                    "reason": "Detection of uncertainty in responses",
                    "confidence": 0.8
                })
            
            if current_agent != "navigation" and any("还有其他" in msg.get("content", "") for msg in recent_messages):
                suggestions.append({
                    "agent": "navigation", 
                    "reason": "User asking for additional options",
                    "confidence": 0.7
                })
        
        return {
            "status": "success",
            "routing_suggestions": suggestions,
            "analysis_context": f"Analyzed {len(conversation_history)} conversation turns"
        }
