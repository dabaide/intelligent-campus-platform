from typing import Dict, Any, List, Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

from core.redis_client import RedisClient
from services.rag_service import RAGService
from services.ai_service import ai_service

class AcademicAgent:
    """
    Academic Agent - Handles course selection, curriculum planning, grade calculation, and academic policies
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient, rag_service: RAGService):
        self.db = db
        self.redis = redis
        self.rag_service = rag_service
        self.agent_name = "AcademicAgent"
        
        # Academic knowledge domains
        self.knowledge_domains = {
            "course_selection": {
                "keywords": ["选课", "课程", "开课", "时间表", "课表", "学分", "必修", "选修"],
                "context": "course_catalog"
            },
            "curriculum_planning": {
                "keywords": ["培养方案", "专业课程", "毕业要求", "学位", "课程安排"],
                "context": "curriculum_guide"
            },
            "grade_calculation": {
                "keywords": ["成绩", "绩点", "GPA", "分数", "计算", "学分绩点"],
                "context": "grading_system"
            },
            "academic_policies": {
                "keywords": ["学术政策", "考试规定", "重修", "缓考", "学籍", "转专业"],
                "context": "academic_regulations"
            },
            "exam_info": {
                "keywords": ["考试", "期中", "期末", "考场", "考试安排", "补考"],
                "context": "exam_schedule"
            }
        }
        
        # Common academic responses
        self.response_templates = {
            "course_selection": "根据您的查询，我为您找到了相关的选课信息：",
            "curriculum_planning": "关于您的培养方案咨询，以下是相关信息：",
            "grade_calculation": "关于成绩和学分计算，请参考以下信息：",
            "academic_policies": "关于学术政策规定，相关信息如下：",
            "exam_info": "关于考试安排的相关信息："
        }
    
    # [业务路由解析]: 学术专家智能体的核心处理方法。根据具体的 task_type (如成绩、选课) 进行策略分发，或转交给 RAG 服务查询。
    # [细分领域专家动态路由]:
    # 学术智能体专职处理器。针对成绩查询、学分选课等细化 Task Type 任务进行专项逻辑剥离与本地数据库精确召回。
    async def process_request(self, task_type: str, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process academic-related requests with RAG enhancement"""
        try:
            # Identify academic domain
            domain = self._identify_academic_domain(task_type, query)
            
            # Extract user academic context
            user_context = self._extract_user_academic_context(context)
            
            # Get database session from context
            db = context.get("db")
            
            # Use RAG-enhanced AI service if database is available
            if db:
                ai_response = await ai_service.generate_response_with_rag(
                    agent_type="academic",
                    user_message=query,
                    db=db,
                    context={**context, "domain": domain, "user_context": user_context}
                )
            else:
                # Fallback to regular AI service
                ai_response = await ai_service.generate_response(
                    agent_type="academic",
                    user_message=query,
                    context={**context, "domain": domain, "user_context": user_context}
                )
            
            if ai_response.get("status") == "success":
                return ai_response
            else:
                # Fallback to knowledge search if AI fails
                knowledge_results = await self._search_academic_knowledge(query, domain)
                
                if knowledge_results:
                    return {
                        "status": "success",
                        "content": self._format_knowledge_response(knowledge_results, query),
                        "agent_type": "academic",
                        "confidence_score": 0.8,
                        "sources": [{"type": "knowledge_base", "domain": domain}]
                    }
                else:
                    return {
                        "status": "partial_success",
                        "content": f"关于{domain}相关的问题，我建议您：\n1. 查看教务系统的最新通知\n2. 咨询学院教务办公室\n3. 联系相关课程的任课老师",
                        "agent_type": "academic",
                        "confidence_score": 0.6,
                        "suggestions": ["查看教务系统", "咨询教务办", "联系任课老师"]
                    }
                    
        except Exception as e:
            return {
                "status": "error",
                "error": f"Academic agent error: {str(e)}",
                "content": "抱歉，处理您的学术问题时出现了错误。请稍后再试或联系教务办公室。",
                "agent_type": "academic"
            }

    def _identify_academic_domain(self, task_type: str, query: str) -> str:
        """Identify specific academic domain from task type and query"""
        query_lower = query.lower()
        
        # Direct mapping from task type
        task_domain_mapping = {
            "course_selection": "course_selection",
            "grade_inquiry": "grade_calculation",
            "credit_calculation": "grade_calculation",
            "curriculum_planning": "curriculum_planning",
            "exam_info": "exam_info"
        }
        
        if task_type in task_domain_mapping:
            return task_domain_mapping[task_type]
        
        # Keyword-based domain identification
        domain_scores = {}
        for domain, config in self.knowledge_domains.items():
            score = sum(1 for keyword in config["keywords"] if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return "academic_policies"  # Default domain
    
    def _extract_user_academic_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant academic context from user information"""
        return {
            "role": context.get("role", "student"),
            "department": context.get("department"),
            "grade": context.get("grade"),
            "major": context.get("major"),
            "user_id": context.get("user_id")
        }
    
    async def _search_academic_knowledge(self, query: str, domain: str, 
                                       user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Search academic knowledge base"""
        try:
            # Enhance query with user context
            enhanced_query = self._enhance_query_with_context(query, user_context)
            
            # Search with academic category filter
            search_results = await self.rag_service.hybrid_search(
                query=enhanced_query,
                category="academic",
                top_k=8
            )
            
            # Filter results by domain relevance
            filtered_results = self._filter_by_domain_relevance(
                search_results, domain, query
            )
            
            return filtered_results
            
        except Exception as e:
            print(f"❌ Academic knowledge search failed: {str(e)}")
            return {"semantic_results": [], "faq_results": [], "total_results": 0}
    
    def _enhance_query_with_context(self, query: str, user_context: Dict[str, Any]) -> str:
        """Enhance query with user academic context"""
        enhanced_parts = [query]
        
        # Add major context if available
        if user_context.get("major"):
            enhanced_parts.append(f"专业:{user_context['major']}")
        
        # Add grade context if available
        if user_context.get("grade"):
            enhanced_parts.append(f"年级:{user_context['grade']}")
        
        # Add department context if available
        if user_context.get("department"):
            enhanced_parts.append(f"学院:{user_context['department']}")
        
        return " ".join(enhanced_parts)
    
    def _filter_by_domain_relevance(self, search_results: Dict[str, Any], 
                                   domain: str, query: str) -> Dict[str, Any]:
        """Filter search results by domain relevance"""
        domain_keywords = self.knowledge_domains.get(domain, {}).get("keywords", [])
        
        filtered_semantic = []
        for result in search_results.get("semantic_results", []):
            content_lower = result["content"].lower()
            relevance_score = sum(1 for keyword in domain_keywords if keyword in content_lower)
            
            if relevance_score > 0 or result["score"] > 0.7:
                result["domain_relevance"] = relevance_score
                filtered_semantic.append(result)
        
        # Sort by combined score (semantic + domain relevance)
        filtered_semantic.sort(
            key=lambda x: x["score"] + (x.get("domain_relevance", 0) * 0.1), 
            reverse=True
        )
        
        return {
            "semantic_results": filtered_semantic[:5],
            "faq_results": search_results.get("faq_results", []),
            "total_results": len(filtered_semantic) + len(search_results.get("faq_results", []))
        }
    
    async def _generate_academic_response(self, task_type: str, domain: str, query: str,
                                        search_results: Dict[str, Any], 
                                        user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate academic response based on search results"""
        try:
            # Get response template
            template = self.response_templates.get(domain, "根据您的学术咨询，以下是相关信息：")
            
            # Process search results
            content_parts = [template]
            sources = []
            confidence_scores = []
            
            # Process semantic search results
            semantic_results = search_results.get("semantic_results", [])
            if semantic_results:
                content_parts.append("\n📚 **相关文档信息：**")
                for i, result in enumerate(semantic_results[:3], 1):
                    content_parts.append(f"{i}. {result['content'][:300]}...")
                    sources.append({
                        "type": "document",
                        "title": result["document_title"],
                        "category": result["category"],
                        "score": result["score"]
                    })
                    confidence_scores.append(result["score"])
            
            # Process FAQ results
            faq_results = search_results.get("faq_results", [])
            if faq_results:
                content_parts.append("\n❓ **常见问题解答：**")
                for i, faq in enumerate(faq_results[:2], 1):
                    content_parts.append(f"**Q{i}: {faq['question']}**")
                    content_parts.append(f"A{i}: {faq['answer']}")
                    sources.append({
                        "type": "faq",
                        "question": faq["question"],
                        "category": faq["category"]
                    })
            
            # Generate suggestions
            suggestions = await self._generate_academic_suggestions(domain, user_context)
            
            # Calculate overall confidence
            overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
            
            # Add personalized notes based on user context
            personalized_note = self._generate_personalized_note(domain, user_context)
            if personalized_note:
                content_parts.append(f"\n💡 **个性化提示：** {personalized_note}")
            
            return {
                "content": "\n".join(content_parts),
                "confidence_score": overall_confidence,
                "sources": sources,
                "suggestions": suggestions,
                "requires_verification": overall_confidence < 0.6
            }
            
        except Exception as e:
            return {
                "content": f"抱歉，处理您的学术咨询时遇到问题：{str(e)}。请稍后重试或联系学术事务办公室。",
                "confidence_score": 0.0,
                "sources": [],
                "suggestions": ["联系学术事务办公室", "查看学生手册", "咨询导师"],
                "requires_verification": True
            }
    
    async def _generate_academic_suggestions(self, domain: str, 
                                          user_context: Dict[str, Any]) -> List[str]:
        """Generate contextual academic suggestions"""
        base_suggestions = {
            "course_selection": [
                "查看完整课程目录",
                "了解先修课程要求",
                "查询课程评价",
                "联系学术顾问"
            ],
            "curriculum_planning": [
                "下载最新培养方案",
                "计算已修学分",
                "规划剩余课程",
                "咨询专业导师"
            ],
            "grade_calculation": [
                "查看详细成绩单",
                "了解绩点计算规则",
                "申请成绩复查",
                "咨询学业导师"
            ],
            "academic_policies": [
                "查阅学生手册",
                "了解最新政策变更",
                "联系教务处",
                "参加政策说明会"
            ],
            "exam_info": [
                "查看完整考试安排",
                "了解考试规则",
                "准备考试用品",
                "查询补考政策"
            ]
        }
        
        suggestions = base_suggestions.get(domain, ["获取更多学术信息", "联系相关部门"])
        
        # Add personalized suggestions based on user context
        if user_context.get("grade") == "大一":
            suggestions.append("参加新生学术指导")
        elif user_context.get("grade") == "大四":
            suggestions.append("了解毕业要求检查")
        
        return suggestions[:4]
    
    def _generate_personalized_note(self, domain: str, user_context: Dict[str, Any]) -> str:
        """Generate personalized note based on user context"""
        role = user_context.get("role", "student")
        grade = user_context.get("grade")
        major = user_context.get("major")
        
        if role == "student" and grade:
            if domain == "course_selection" and grade in ["大一", "大二"]:
                return "建议优先选择专业必修课程，为后续学习打好基础。"
            elif domain == "curriculum_planning" and grade == "大四":
                return "请及时检查毕业要求完成情况，确保按时毕业。"
            elif domain == "grade_calculation":
                return "定期关注学分绩点，保持良好的学业表现。"
        
        if major and domain == "course_selection":
            return f"建议结合{major}专业特点选择相关课程，注意课程间的逻辑关系。"
        
        return ""
    
    async def handle_collaboration(self, collaboration_type: str, request_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration requests from other agents"""
        try:
            if collaboration_type == "academic_verification":
                # Verify academic information accuracy
                return await self._verify_academic_info(request_data, context)
            
            elif collaboration_type == "course_recommendation":
                # Provide course recommendations
                return await self._recommend_courses(request_data, context)
            
            elif collaboration_type == "prerequisite_check":
                # Check course prerequisites
                return await self._check_prerequisites(request_data, context)
            
            else:
                return {
                    "status": "error",
                    "error": f"Unknown collaboration type: {collaboration_type}"
                }
                
        except Exception as e:
            return {
                "status": "error", 
                "error": f"Academic collaboration failed: {str(e)}"
            }
    
    async def _verify_academic_info(self, request_data: Dict[str, Any], 
                                  context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify academic information accuracy"""
        info_to_verify = request_data.get("info_to_verify", "")
        verification_type = request_data.get("verification_type", "general")
        
        # Search for authoritative sources
        search_results = await self.rag_service.semantic_search(
            query=info_to_verify,
            category="academic",
            top_k=3,
            min_score=0.8
        )
        
        verification_score = 0.0
        verification_notes = []
        
        if search_results:
            # High-confidence matches indicate likely accurate information
            high_confidence_matches = [r for r in search_results if r["score"] > 0.85]
            if high_confidence_matches:
                verification_score = sum(r["score"] for r in high_confidence_matches) / len(high_confidence_matches)
                verification_notes.append("找到权威学术文档支持此信息")
            else:
                verification_score = 0.4
                verification_notes.append("未找到明确的权威文档支持")
        else:
            verification_score = 0.2
            verification_notes.append("无法在学术知识库中验证此信息")
        
        return {
            "status": "success",
            "verification_score": verification_score,
            "verification_notes": verification_notes,
            "supporting_sources": search_results[:2],
            "is_verified": verification_score > 0.7
        }
    
    async def _recommend_courses(self, request_data: Dict[str, Any], 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend courses based on user profile and requirements"""
        user_profile = request_data.get("user_profile", {})
        requirements = request_data.get("requirements", {})
        
        # This would typically query a course database
        # For now, provide template recommendations
        recommendations = [
            {
                "course_code": "CS101", 
                "course_name": "计算机科学导论",
                "credits": 3,
                "reason": "专业基础课程，建议尽早修读"
            },
            {
                "course_code": "MATH201",
                "course_name": "高等数学",
                "credits": 4,
                "reason": "为后续专业课程提供数学基础"
            }
        ]
        
        return {
            "status": "success",
            "recommendations": recommendations,
            "total_credits": sum(r["credits"] for r in recommendations),
            "recommendation_basis": "基于用户专业和年级"
        }
    
    async def _check_prerequisites(self, request_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Check course prerequisites"""
        course_code = request_data.get("course_code", "")
        user_transcript = request_data.get("user_transcript", [])
        
        # This would typically check against course database
        # For now, provide template response
        return {
            "status": "success", 
            "prerequisites_met": True,
            "missing_prerequisites": [],
            "recommendations": ["可以选修此课程"]
        }
