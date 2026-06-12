from typing import Dict, Any, List, Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import json

from core.redis_client import RedisClient
from services.rag_service import RAGService
from services.ai_service import ai_service

# [细分领域专家 - 校园行政智能体]:
# 封装教务办事、缴费、奖学金申请等高严谨度事务逻辑。
# 对接 RAG 引擎以确切的官方制度文档指导用户办理流程。
class AdminAgent:
    """
    Administrative Agent - Handles scholarship, leave applications, expense reimbursement, and administrative procedures
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient, rag_service: RAGService):
        self.db = db
        self.redis = redis
        self.rag_service = rag_service
        self.agent_name = "AdminAgent"
        
        # Administrative service domains
        self.admin_domains = {
            "scholarship_info": {
                "keywords": ["奖学金", "助学金", "勤工助学", "资助", "补贴", "申请条件", "评选"],
                "context": "financial_aid"
            },
            "leave_application": {
                "keywords": ["请假", "休假", "病假", "事假", "申请流程", "假期", "审批"],
                "context": "leave_policies"
            },
            "expense_reimbursement": {
                "keywords": ["报销", "费用", "发票", "财务", "审核", "流程", "标准"],
                "context": "financial_procedures"
            },
            "certificate_services": {
                "keywords": ["证明", "证件", "学生证", "在读证明", "成绩单", "毕业证", "学位证"],
                "context": "certificate_services"
            },
            "administrative_procedures": {
                "keywords": ["手续", "办理", "申请", "审批", "流程", "材料", "表格", "政策"],
                "context": "admin_procedures"
            },
            "student_status": {
                "keywords": ["学籍", "转专业", "休学", "复学", "退学", "学业警告"],
                "context": "student_affairs"
            },
            "graduation_procedures": {
                "keywords": ["毕业", "学位", "答辩", "论文", "清考", "补考", "毕业设计"],
                "context": "graduation_requirements"
            }
        }
        
        # Application deadlines and important dates
        self.important_dates = {
            "scholarship_deadlines": {
                "国家奖学金": "每年9月30日",
                "国家励志奖学金": "每年10月15日", 
                "学业奖学金": "每学期期末",
                "校级奖学金": "每年11月15日"
            },
            "administrative_deadlines": {
                "转专业申请": "每学期第3周",
                "休学申请": "学期中任何时间",
                "毕业论文提交": "每年5月31日",
                "学位申请": "每年6月15日"
            }
        }
        
        # Common requirements and documents
        self.document_requirements = {
            "scholarship_application": [
                "申请表", "成绩单", "获奖证书", "贫困证明(如适用)", "推荐信"
            ],
            "leave_application": [
                "请假申请表", "医院证明(病假)", "家长同意书", "导师签字"
            ],
            "expense_reimbursement": [
                "报销申请表", "原始发票", "审批单", "银行卡信息"
            ],
            "certificate_request": [
                "申请表", "身份证复印件", "学生证", "照片"
            ]
        }
    
    async def process_request(self, task_type: str, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process administrative related requests
        """
        try:
            db = context.get("db")

            if db:
                ai_response = await ai_service.generate_response_with_rag(
                    agent_type="admin",
                    user_message=query,
                    db=db,
                    context=context
                )
            else:
                ai_response = await ai_service.generate_response(
                    agent_type="admin",
                    user_message=query,
                    context=context
                )

            if ai_response.get("status") == "success":
                return ai_response

            # Identify administrative domain
            domain = self._identify_admin_domain(task_type, query)
            
            # Extract user administrative context
            user_context = self._extract_user_admin_context(context)
            
            # Search administrative knowledge
            search_results = await self._search_admin_knowledge(query, domain, user_context)
            
            # Generate administrative response
            response = await self._generate_admin_response(
                task_type, domain, query, search_results, user_context
            )
            
            return {
                "status": "success",
                "agent_type": "admin",
                "content": response["content"],
                "confidence_score": response["confidence_score"], 
                "sources": response["sources"],
                "suggestions": response["suggestions"],
                "action_items": response.get("action_items", []),
                "deadlines": response.get("deadlines", []),
                "required_documents": response.get("required_documents", []),
                "metadata": {
                    "domain": domain,
                    "urgency": self._assess_urgency(domain, query),
                    "estimated_processing_time": self._estimate_processing_time(domain)
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "agent_type": "admin",
                "error": f"Administrative request processing failed: {str(e)}"
            }
    
    def _identify_admin_domain(self, task_type: str, query: str) -> str:
        """Identify specific administrative domain"""
        query_lower = query.lower()
        
        # Direct mapping from task type
        task_domain_mapping = {
            "scholarship_info": "scholarship_info",
            "leave_application": "leave_application",
            "expense_reimbursement": "expense_reimbursement",
            "certificate_services": "certificate_services",
            "administrative_procedures": "administrative_procedures"
        }
        
        if task_type in task_domain_mapping:
            return task_domain_mapping[task_type]
        
        # Keyword-based identification with weighted scoring
        domain_scores = {}
        for domain, config in self.admin_domains.items():
            score = sum(1 for keyword in config["keywords"] if keyword in query_lower)
            # Weight certain high-impact keywords
            if domain == "scholarship_info" and any(word in query_lower for word in ["急需", "紧急", "截止"]):
                score += 2
            domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return "administrative_procedures"  # Default domain
    
    def _extract_user_admin_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant administrative context"""
        return {
            "user_id": context.get("user_id"),
            "role": context.get("role", "student"),
            "student_id": context.get("student_id"),
            "department": context.get("department"),
            "grade": context.get("grade"),
            "major": context.get("major"),
            "academic_status": context.get("academic_status", "active")
        }
    
    async def _search_admin_knowledge(self, query: str, domain: str,
                                     user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Search administrative knowledge base"""
        try:
            # Enhance query with administrative context
            enhanced_query = self._enhance_query_with_admin_context(query, user_context, domain)
            
            # Search with administrative category filter
            search_results = await self.rag_service.hybrid_search(
                query=enhanced_query,
                category="administrative",
                top_k=6
            )
            
            # Add policy updates and current procedures
            current_policies = await self._get_current_policies(domain)
            if current_policies:
                search_results["current_policies"] = current_policies
            
            # Add deadline information
            deadline_info = self._get_relevant_deadlines(domain, query)
            if deadline_info:
                search_results["deadline_info"] = deadline_info
            
            return search_results
            
        except Exception as e:
            print(f"❌ Administrative knowledge search failed: {str(e)}")
            return {"semantic_results": [], "faq_results": [], "total_results": 0}
    
    def _enhance_query_with_admin_context(self, query: str, user_context: Dict[str, Any], domain: str) -> str:
        """Enhance query with administrative context"""
        enhanced_parts = [query]
        
        # Add role context
        role = user_context.get("role", "student")
        if role == "student":
            enhanced_parts.append("学生")
        elif role == "teacher":
            enhanced_parts.append("教工")
        
        # Add grade context for student-specific procedures
        if role == "student" and user_context.get("grade"):
            enhanced_parts.append(f"年级:{user_context['grade']}")
        
        # Add domain-specific context
        if domain == "scholarship_info" and user_context.get("grade") in ["大三", "大四"]:
            enhanced_parts.append("毕业班")
        
        return " ".join(enhanced_parts)
    
    async def _get_current_policies(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get current policy information from cache"""
        try:
            cache_key = f"current_policies:{domain}"
            cached_policies = await self.redis.get_json(cache_key)
            
            if cached_policies:
                return cached_policies
            
            # Mock current policy information
            current_policies = {}
            
            if domain == "scholarship_info":
                current_policies = {
                    "latest_update": "2024年3月",
                    "changes": [
                        "新增创新创业奖学金类别",
                        "调整国家奖学金GPA要求至3.8以上", 
                        "简化申请材料清单"
                    ],
                    "application_period": "2024年9月1日-30日"
                }
            
            elif domain == "expense_reimbursement":
                current_policies = {
                    "latest_update": "2024年2月",
                    "changes": [
                        "提高差旅费报销标准",
                        "新增电子发票支持",
                        "缩短审批周期至5个工作日"
                    ],
                    "system_upgrade": "财务系统已升级，支持在线申请"
                }
            
            elif domain == "leave_application":
                current_policies = {
                    "latest_update": "2024年1月",
                    "changes": [
                        "病假超过3天需医院证明",
                        "事假需提前3天申请",
                        "新增在线请假系统"
                    ],
                    "contact_info": "学生事务办公室：010-12345678"
                }
            
            # Cache for 1 day
            await self.redis.set_json(cache_key, current_policies, expire=86400)
            
            return current_policies
            
        except Exception as e:
            print(f"❌ Failed to get current policies: {str(e)}")
            return None
    
    def _get_relevant_deadlines(self, domain: str, query: str) -> Optional[Dict[str, Any]]:
        """Get relevant deadlines for the domain"""
        current_date = datetime.now()
        relevant_deadlines = []
        
        if domain == "scholarship_info":
            deadlines = self.important_dates["scholarship_deadlines"]
            for scholarship, deadline in deadlines.items():
                if any(word in query.lower() for word in [scholarship.lower(), "申请", "截止"]):
                    relevant_deadlines.append({
                        "item": scholarship,
                        "deadline": deadline,
                        "category": "奖学金申请"
                    })
        
        elif domain in ["administrative_procedures", "student_status"]:
            deadlines = self.important_dates["administrative_deadlines"]
            for procedure, deadline in deadlines.items():
                if any(word in query.lower() for word in [procedure.lower(), "申请"]):
                    relevant_deadlines.append({
                        "item": procedure,
                        "deadline": deadline,
                        "category": "行政手续"
                    })
        
        if relevant_deadlines:
            return {
                "upcoming_deadlines": relevant_deadlines,
                "note": "请注意相关申请截止时间"
            }
        
        return None
    
    async def _generate_admin_response(self, task_type: str, domain: str, query: str,
                                     search_results: Dict[str, Any],
                                     user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate administrative response"""
        try:
            content_parts = []
            sources = []
            
            # Add domain-specific header
            domain_title = self._get_domain_title(domain)
            content_parts.append(f"## {domain_title}")
            
            # Add current policy updates if available
            current_policies = search_results.get("current_policies")
            if current_policies and current_policies.get("latest_update"):
                content_parts.append(f"📅 **最新更新：** {current_policies['latest_update']}")
                if current_policies.get("changes"):
                    content_parts.append("**主要变化：**")
                    for change in current_policies["changes"][:3]:
                        content_parts.append(f"• {change}")
            
            # Process search results
            semantic_results = search_results.get("semantic_results", [])
            if semantic_results:
                content_parts.append("\n📋 **详细信息：**")
                for i, result in enumerate(semantic_results[:2], 1):
                    content_parts.append(f"**{i}.** {result['content'][:300]}...")
                    sources.append({
                        "type": "document",
                        "title": result["document_title"],
                        "score": result["score"],
                        "category": result["category"]
                    })
            
            # Process FAQ results
            faq_results = search_results.get("faq_results", [])
            if faq_results:
                content_parts.append("\n❓ **常见问题解答：**")
                for faq in faq_results[:2]:
                    content_parts.append(f"**Q**: {faq['question']}")
                    content_parts.append(f"**A**: {faq['answer']}")
                    sources.append({
                        "type": "faq",
                        "question": faq["question"],
                        "category": faq["category"]
                    })
            
            # Add deadline information
            deadline_info = search_results.get("deadline_info")
            if deadline_info:
                content_parts.append(f"\n⏰ **重要截止时间：**")
                for deadline in deadline_info["upcoming_deadlines"]:
                    content_parts.append(f"• **{deadline['item']}**: {deadline['deadline']}")
            
            # Add required documents
            required_docs = self._get_required_documents(domain, query)
            if required_docs:
                content_parts.append(f"\n📄 **所需材料：**")
                for doc in required_docs:
                    content_parts.append(f"• {doc}")
            
            # Add process steps
            process_steps = self._get_process_steps(domain, user_context)
            if process_steps:
                content_parts.append(f"\n🔄 **办理流程：**")
                for i, step in enumerate(process_steps, 1):
                    content_parts.append(f"{i}. {step}")
            
            # Add contact information
            contact_info = self._get_contact_information(domain)
            if contact_info:
                content_parts.append(f"\n📞 **联系方式：** {contact_info}")
            
            # Generate suggestions and action items
            suggestions = self._generate_admin_suggestions(domain, user_context)
            action_items = self._generate_action_items(domain, query, user_context)
            deadlines = deadline_info["upcoming_deadlines"] if deadline_info else []
            
            # Calculate confidence
            confidence = 0.8 if semantic_results or faq_results else 0.6
            if current_policies:
                confidence += 0.1
            
            return {
                "content": "\n".join(content_parts),
                "confidence_score": min(confidence, 1.0),
                "sources": sources,
                "suggestions": suggestions,
                "action_items": action_items,
                "deadlines": deadlines,
                "required_documents": required_docs
            }
            
        except Exception as e:
            return {
                "content": f"抱歉，处理您的行政事务咨询时遇到问题。建议您直接联系相关办公室获取准确信息。",
                "confidence_score": 0.0,
                "sources": [],
                "suggestions": ["联系学生事务办公室", "查看官方网站", "咨询导师或辅导员"]
            }
    
    def _get_domain_title(self, domain: str) -> str:
        """Get friendly title for administrative domain"""
        titles = {
            "scholarship_info": "奖学金资助信息",
            "leave_application": "请假申请指南",
            "expense_reimbursement": "费用报销流程",
            "certificate_services": "证件证明服务",
            "administrative_procedures": "行政办事指南",
            "student_status": "学籍事务管理",
            "graduation_procedures": "毕业相关手续"
        }
        return titles.get(domain, "行政事务咨询")
    
    def _get_required_documents(self, domain: str, query: str) -> List[str]:
        """Get required documents for administrative procedure"""
        if domain in self.document_requirements:
            return self.document_requirements[domain]
        
        # Dynamic document requirements based on query analysis
        if "申请" in query.lower():
            if domain == "scholarship_info":
                return self.document_requirements["scholarship_application"]
            elif domain == "leave_application":
                return self.document_requirements["leave_application"]
        
        return []
    
    def _get_process_steps(self, domain: str, user_context: Dict[str, Any]) -> List[str]:
        """Get process steps for administrative procedure"""
        steps_mapping = {
            "scholarship_info": [
                "查看申请条件和要求",
                "准备相关证明材料",
                "填写申请表格",
                "提交申请材料",
                "等待审核结果"
            ],
            "leave_application": [
                "确定请假事由和时间",
                "准备相关证明文件",
                "填写请假申请表",
                "获得导师/辅导员批准",
                "提交学生事务办审核"
            ],
            "expense_reimbursement": [
                "整理报销发票和凭证",
                "填写报销申请表",
                "部门负责人审批",
                "财务处审核",
                "财务转账发放"
            ],
            "certificate_services": [
                "确认所需证明类型",
                "准备申请材料",
                "在线或现场提交申请",
                "缴纳相关费用",
                "领取证明文件"
            ]
        }
        
        return steps_mapping.get(domain, ["咨询相关部门", "了解具体要求", "准备申请材料", "提交申请"])
    
    def _get_contact_information(self, domain: str) -> str:
        """Get contact information for administrative domain"""
        contacts = {
            "scholarship_info": "学生资助中心：010-12345001",
            "leave_application": "学生事务办公室：010-12345002",
            "expense_reimbursement": "财务处：010-12345003",
            "certificate_services": "教务处：010-12345004",
            "administrative_procedures": "综合办公室：010-12345005",
            "student_status": "学籍管理科：010-12345006",
            "graduation_procedures": "毕业生工作办公室：010-12345007"
        }
        
        return contacts.get(domain, "校务服务中心：010-12345000")
    
    def _generate_admin_suggestions(self, domain: str, user_context: Dict[str, Any]) -> List[str]:
        """Generate administrative suggestions"""
        base_suggestions = {
            "scholarship_info": [
                "查看申请条件详情",
                "了解评选标准",
                "准备申请材料清单",
                "咨询往年获奖情况"
            ],
            "leave_application": [
                "下载请假申请表",
                "了解请假政策",
                "联系导师确认",
                "查看审批流程"
            ],
            "expense_reimbursement": [
                "核对报销标准",
                "准备发票原件",
                "确认审批流程",
                "查询报销进度"
            ],
            "certificate_services": [
                "确认证明用途",
                "准备身份证件",
                "了解办理时限",
                "查看收费标准"
            ]
        }
        
        suggestions = base_suggestions.get(domain, ["获取详细信息", "联系相关部门"])
        
        # Add personalized suggestions
        role = user_context.get("role")
        grade = user_context.get("grade")
        
        if domain == "scholarship_info" and grade == "大四":
            suggestions.insert(0, "优先申请毕业生专项奖学金")
        elif domain == "graduation_procedures" and role == "student":
            suggestions.insert(0, "检查毕业要求完成情况")
        
        return suggestions[:4]
    
    def _generate_action_items(self, domain: str, query: str, user_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate specific action items"""
        action_items = []
        
        if domain == "scholarship_info":
            action_items = [
                {"action": "检查GPA是否满足要求", "deadline": "申请前", "priority": "高"},
                {"action": "准备获奖证书复印件", "deadline": "提交前1周", "priority": "中"},
                {"action": "撰写个人申请陈述", "deadline": "提交前3天", "priority": "高"}
            ]
        
        elif domain == "leave_application":
            action_items = [
                {"action": "确认请假时间和事由", "deadline": "申请前", "priority": "高"},
                {"action": "准备相关证明材料", "deadline": "申请前1天", "priority": "高"},
                {"action": "联系导师获得批准", "deadline": "提交前", "priority": "高"}
            ]
        
        elif domain == "expense_reimbursement":
            action_items = [
                {"action": "整理所有报销发票", "deadline": "申请前", "priority": "高"},
                {"action": "确认报销标准合规", "deadline": "提交前", "priority": "中"},
                {"action": "填写详细报销说明", "deadline": "提交当天", "priority": "中"}
            ]
        
        return action_items
    
    def _assess_urgency(self, domain: str, query: str) -> str:
        """Assess urgency level of the request"""
        urgent_keywords = ["紧急", "急需", "马上", "立即", "截止", "今天", "明天"]
        high_priority_domains = ["leave_application", "certificate_services"]
        
        if any(keyword in query.lower() for keyword in urgent_keywords):
            return "urgent"
        elif domain in high_priority_domains:
            return "high"
        else:
            return "normal"
    
    def _estimate_processing_time(self, domain: str) -> str:
        """Estimate processing time for administrative procedure"""
        time_estimates = {
            "scholarship_info": "2-4周（评选周期）",
            "leave_application": "1-3个工作日",
            "expense_reimbursement": "5-10个工作日",
            "certificate_services": "3-7个工作日",
            "administrative_procedures": "5-15个工作日",
            "student_status": "10-20个工作日",
            "graduation_procedures": "15-30个工作日"
        }
        
        return time_estimates.get(domain, "5-10个工作日")
    
    async def handle_collaboration(self, collaboration_type: str, request_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration requests from other agents"""
        try:
            if collaboration_type == "document_verification":
                # Verify document requirements
                return await self._verify_document_requirements(request_data, context)
            
            elif collaboration_type == "deadline_check":
                # Check application deadlines
                return await self._check_application_deadlines(request_data, context)
            
            elif collaboration_type == "eligibility_assessment":
                # Assess eligibility for administrative procedures
                return await self._assess_eligibility(request_data, context)
            
            else:
                return {
                    "status": "error",
                    "error": f"Unknown collaboration type: {collaboration_type}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": f"Administrative collaboration failed: {str(e)}"
            }
    
    async def _verify_document_requirements(self, request_data: Dict[str, Any],
                                          context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify document requirements for procedures"""
        procedure_type = request_data.get("procedure_type", "")
        submitted_documents = request_data.get("submitted_documents", [])
        
        required_docs = self._get_required_documents(procedure_type, "申请")
        missing_documents = [doc for doc in required_docs if doc not in submitted_documents]
        
        return {
            "status": "success",
            "required_documents": required_docs,
            "submitted_documents": submitted_documents,
            "missing_documents": missing_documents,
            "is_complete": len(missing_documents) == 0,
            "completion_rate": (len(required_docs) - len(missing_documents)) / len(required_docs) if required_docs else 1.0
        }
    
    async def _check_application_deadlines(self, request_data: Dict[str, Any],
                                         context: Dict[str, Any]) -> Dict[str, Any]:
        """Check application deadlines"""
        application_type = request_data.get("application_type", "")
        current_date = datetime.now()
        
        # Get relevant deadlines
        deadline_info = self._get_relevant_deadlines(application_type, application_type)
        
        deadline_status = []
        if deadline_info:
            for deadline in deadline_info["upcoming_deadlines"]:
                # Simple date comparison (in real implementation, would parse dates properly)
                deadline_status.append({
                    "item": deadline["item"],
                    "deadline": deadline["deadline"],
                    "status": "upcoming",  # Would calculate based on actual dates
                    "days_remaining": "待计算"
                })
        
        return {
            "status": "success",
            "deadlines": deadline_status,
            "has_urgent_deadlines": len(deadline_status) > 0,
            "recommendation": "请尽早准备申请材料" if deadline_status else "暂无紧急截止时间"
        }
    
    async def _assess_eligibility(self, request_data: Dict[str, Any],
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess eligibility for administrative procedures"""
        procedure_type = request_data.get("procedure_type", "")
        user_profile = request_data.get("user_profile", {})
        
        eligibility_result = {
            "is_eligible": True,
            "requirements_met": [],
            "requirements_not_met": [],
            "recommendations": []
        }
        
        # Simple eligibility check logic (would be more complex in real implementation)
        if procedure_type == "scholarship_info":
            gpa = user_profile.get("gpa", 0)
            if gpa >= 3.5:
                eligibility_result["requirements_met"].append("GPA要求满足")
            else:
                eligibility_result["requirements_not_met"].append("GPA需达到3.5以上")
                eligibility_result["is_eligible"] = False
        
        return {
            "status": "success",
            "eligibility": eligibility_result,
            "procedure_type": procedure_type
        }
