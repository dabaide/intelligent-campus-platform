from typing import Dict, Any, List, Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, time
import json

from core.redis_client import RedisClient
from services.rag_service import RAGService
from services.ai_service import ai_service

# [细分领域专家 - 校园生活智能体]:
# 专职处理食堂、宿舍、交通等后勤意图。封装垂直领域 Prompt，
# 结合 RAG 服务提供具备强地理位置和时间属性的精准向导。
class LifeServiceAgent:
    """
    Life Service Agent - Handles dining, library, dormitory, campus map, and daily life services
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient, rag_service: RAGService):
        self.db = db
        self.redis = redis
        self.rag_service = rag_service
        self.agent_name = "LifeServiceAgent"
        
        # Life service domains
        self.service_domains = {
            "dining_info": {
                "keywords": ["食堂", "餐厅", "菜单", "营业时间", "饭点", "用餐", "食物", "餐饮"],
                "context": "dining_services"
            },
            "library_services": {
                "keywords": ["图书馆", "借书", "座位", "预约", "开馆", "闭馆", "自习", "阅览"],
                "context": "library_info"
            },
            "dormitory_info": {
                "keywords": ["宿舍", "寝室", "住宿", "床位", "宿管", "水电", "网络", "洗衣"],
                "context": "dormitory_services"
            },
            "campus_map": {
                "keywords": ["地图", "位置", "怎么走", "在哪里", "路线", "方向", "建筑", "教室"],
                "context": "campus_navigation"
            },
            "sports_facilities": {
                "keywords": ["体育", "运动", "健身", "球场", "游泳", "跑道", "预约", "开放时间"],
                "context": "sports_recreation"
            },
            "transport_services": {
                "keywords": ["校车", "班车", "交通", "公交", "地铁", "停车", "出行"],
                "context": "transportation"
            },
            "campus_card": {
                "keywords": ["校园卡", "一卡通", "充值", "余额", "消费", "挂失", "补办"],
                "context": "campus_card_services"
            }
        }
        
        # Operational hours and common info
        self.operational_info = {
            "library": {
                "weekday_hours": "8:00-22:00",
                "weekend_hours": "9:00-21:00",
                "services": ["借阅", "自习", "研讨", "电子资源"]
            },
            "dining": {
                "breakfast": "7:00-9:00",
                "lunch": "11:00-13:30", 
                "dinner": "17:00-19:30",
                "locations": ["第一食堂", "第二食堂", "教工餐厅", "清真餐厅"]
            },
            "sports": {
                "weekday_hours": "6:00-22:00",
                "weekend_hours": "8:00-21:00",
                "facilities": ["体育馆", "游泳馆", "篮球场", "足球场", "网球场"]
            }
        }
    
    async def process_request(self, task_type: str, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process life service related requests
        """
        try:
            db = context.get("db")

            if db:
                ai_response = await ai_service.generate_response_with_rag(
                    agent_type="life",
                    user_message=query,
                    db=db,
                    context=context
                )
            else:
                ai_response = await ai_service.generate_response(
                    agent_type="life",
                    user_message=query,
                    context=context
                )

            if ai_response.get("status") == "success":
                return ai_response

            # Identify service domain
            domain = self._identify_service_domain(task_type, query)
            
            # Get user location context if available
            user_context = self._extract_user_location_context(context)
            
            # Search for relevant service information
            search_results = await self._search_service_knowledge(query, domain, user_context)
            
            # Generate service response
            response = await self._generate_service_response(
                task_type, domain, query, search_results, user_context
            )
            
            return {
                "status": "success",
                "agent_type": "life",
                "content": response["content"],
                "confidence_score": response["confidence_score"],
                "sources": response["sources"],
                "suggestions": response["suggestions"],
                "quick_actions": response.get("quick_actions", []),
                "metadata": {
                    "domain": domain,
                    "operational_status": await self._get_operational_status(domain),
                    "location_context": user_context.get("location")
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "agent_type": "life",
                "error": f"Life service request processing failed: {str(e)}"
            }
    
    def _identify_service_domain(self, task_type: str, query: str) -> str:
        """Identify specific service domain"""
        query_lower = query.lower()
        
        # Direct mapping from task type
        task_domain_mapping = {
            "dining_info": "dining_info",
            "library_services": "library_services", 
            "dormitory_info": "dormitory_info",
            "campus_map": "campus_map",
            "sports_facilities": "sports_facilities"
        }
        
        if task_type in task_domain_mapping:
            return task_domain_mapping[task_type]
        
        # Keyword-based identification
        domain_scores = {}
        for domain, config in self.service_domains.items():
            score = sum(1 for keyword in config["keywords"] if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return "campus_map"  # Default to general campus information
    
    def _extract_user_location_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user location and preference context"""
        return {
            "user_id": context.get("user_id"),
            "role": context.get("role", "student"),
            "department": context.get("department"),
            "location": context.get("current_location"),
            "preferences": context.get("preferences", {})
        }
    
    async def _search_service_knowledge(self, query: str, domain: str,
                                      user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Search life service knowledge base"""
        try:
            # Enhance query with location context
            enhanced_query = self._enhance_query_with_location(query, user_context)
            
            # Search with life service category filter
            search_results = await self.rag_service.hybrid_search(
                query=enhanced_query,
                category="life",
                top_k=6
            )
            
            # Add real-time information if available
            real_time_info = await self._get_real_time_service_info(domain)
            if real_time_info:
                search_results["real_time_info"] = real_time_info
            
            return search_results
            
        except Exception as e:
            print(f"❌ Life service knowledge search failed: {str(e)}")
            return {"semantic_results": [], "faq_results": [], "total_results": 0}
    
    def _enhance_query_with_location(self, query: str, user_context: Dict[str, Any]) -> str:
        """Enhance query with location context"""
        enhanced_parts = [query]
        
        # Add department location if available
        if user_context.get("department"):
            enhanced_parts.append(f"位置:{user_context['department']}")
        
        # Add role-specific context
        if user_context.get("role") == "teacher":
            enhanced_parts.append("教工")
        
        return " ".join(enhanced_parts)
    
    async def _get_real_time_service_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get real-time service information"""
        try:
            # Check Redis cache for real-time info
            cache_key = f"realtime_service:{domain}"
            cached_info = await self.redis.get_json(cache_key)
            
            if cached_info:
                return cached_info
            
            # Generate mock real-time information
            current_time = datetime.now().time()
            real_time_info = {}
            
            if domain == "library_services":
                real_time_info = {
                    "current_occupancy": "65%",
                    "available_seats": 156,
                    "peak_hours": "14:00-16:00, 19:00-21:00",
                    "special_notices": []
                }
                
                # Add time-based notices
                if current_time > time(21, 0):
                    real_time_info["special_notices"].append("图书馆即将闭馆，请合理安排时间")
            
            elif domain == "dining_info":
                real_time_info = {
                    "current_menu": "今日推荐：宫保鸡丁、麻婆豆腐、酸辣土豆丝",
                    "crowd_level": "适中",
                    "wait_time": "5-10分钟",
                    "special_offers": ["第二食堂新品8折优惠"]
                }
                
                # Add meal time context
                if time(11, 0) <= current_time <= time(13, 30):
                    real_time_info["meal_period"] = "午餐时间"
                elif time(17, 0) <= current_time <= time(19, 30):
                    real_time_info["meal_period"] = "晚餐时间"
            
            elif domain == "sports_facilities":
                real_time_info = {
                    "available_courts": {
                        "篮球场": "3/8可用",
                        "羽毛球场": "2/6可用",
                        "网球场": "全部可用"
                    },
                    "equipment_rental": "可租借",
                    "weather_impact": "室外场地正常开放"
                }
            
            # Cache for 15 minutes
            await self.redis.set_json(cache_key, real_time_info, expire=900)
            
            return real_time_info
            
        except Exception as e:
            print(f"❌ Failed to get real-time service info: {str(e)}")
            return None
    
    async def _get_operational_status(self, domain: str) -> Dict[str, Any]:
        """Get current operational status for service domain"""
        current_time = datetime.now().time()
        current_weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday
        
        status = {"is_open": False, "next_open": "", "current_hours": ""}
        
        if domain == "library_services":
            if current_weekday < 5:  # Weekday
                open_time, close_time = time(8, 0), time(22, 0)
                status["current_hours"] = "8:00-22:00"
            else:  # Weekend
                open_time, close_time = time(9, 0), time(21, 0)
                status["current_hours"] = "9:00-21:00"
            
            status["is_open"] = open_time <= current_time <= close_time
        
        elif domain == "dining_info":
            # Multiple dining periods
            dining_periods = [
                (time(7, 0), time(9, 0), "早餐"),
                (time(11, 0), time(13, 30), "午餐"),
                (time(17, 0), time(19, 30), "晚餐")
            ]
            
            for start, end, period in dining_periods:
                if start <= current_time <= end:
                    status["is_open"] = True
                    status["current_period"] = period
                    break
            
            status["current_hours"] = "7:00-9:00, 11:00-13:30, 17:00-19:30"
        
        elif domain == "sports_facilities":
            if current_weekday < 5:  # Weekday
                open_time, close_time = time(6, 0), time(22, 0)
                status["current_hours"] = "6:00-22:00"
            else:  # Weekend
                open_time, close_time = time(8, 0), time(21, 0)
                status["current_hours"] = "8:00-21:00"
            
            status["is_open"] = open_time <= current_time <= close_time
        
        return status
    
    async def _generate_service_response(self, task_type: str, domain: str, query: str,
                                       search_results: Dict[str, Any],
                                       user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate life service response"""
        try:
            # Build response content
            content_parts = []
            sources = []
            
            # Add greeting with current service status
            operational_status = await self._get_operational_status(domain)
            status_text = "🟢 正在开放" if operational_status["is_open"] else "🔴 暂时关闭"
            content_parts.append(f"## {self._get_domain_title(domain)} {status_text}")
            
            if operational_status.get("current_hours"):
                content_parts.append(f"**开放时间：** {operational_status['current_hours']}")
            
            # Add real-time information
            real_time_info = search_results.get("real_time_info")
            if real_time_info:
                content_parts.append("\n📊 **实时信息：**")
                for key, value in real_time_info.items():
                    if key not in ["special_notices", "special_offers"]:
                        content_parts.append(f"• **{key}**: {value}")
                
                # Add special notices
                if real_time_info.get("special_notices"):
                    content_parts.append("\n⚠️  **特别提醒：**")
                    for notice in real_time_info["special_notices"]:
                        content_parts.append(f"• {notice}")
            
            # Process search results
            semantic_results = search_results.get("semantic_results", [])
            if semantic_results:
                content_parts.append("\n📋 **详细信息：**")
                for i, result in enumerate(semantic_results[:2], 1):
                    content_parts.append(f"**{i}.** {result['content'][:250]}...")
                    sources.append({
                        "type": "document",
                        "title": result["document_title"],
                        "score": result["score"]
                    })
            
            # Process FAQ results  
            faq_results = search_results.get("faq_results", [])
            if faq_results:
                content_parts.append("\n❓ **常见问题：**")
                for faq in faq_results[:2]:
                    content_parts.append(f"**Q**: {faq['question']}")
                    content_parts.append(f"**A**: {faq['answer']}")
                    sources.append({
                        "type": "faq",
                        "question": faq["question"]
                    })
            
            # Add location-specific tips
            location_tips = self._generate_location_tips(domain, user_context)
            if location_tips:
                content_parts.append(f"\n💡 **温馨提示：** {location_tips}")
            
            # Generate suggestions and quick actions
            suggestions = self._generate_service_suggestions(domain, operational_status)
            quick_actions = self._generate_quick_actions(domain)
            
            # Calculate confidence
            confidence = 0.8 if semantic_results or faq_results else 0.6
            if real_time_info:
                confidence += 0.1
            
            return {
                "content": "\n".join(content_parts),
                "confidence_score": min(confidence, 1.0),
                "sources": sources,
                "suggestions": suggestions,
                "quick_actions": quick_actions
            }
            
        except Exception as e:
            return {
                "content": f"抱歉，获取生活服务信息时遇到问题。请稍后重试或联系相关服务部门。",
                "confidence_score": 0.0,
                "sources": [],
                "suggestions": ["联系服务热线", "查看官方网站", "前往服务中心咨询"]
            }
    
    def _get_domain_title(self, domain: str) -> str:
        """Get friendly title for domain"""
        titles = {
            "dining_info": "餐饮服务",
            "library_services": "图书馆服务",
            "dormitory_info": "宿舍服务",
            "campus_map": "校园导航",
            "sports_facilities": "体育设施",
            "transport_services": "交通服务",
            "campus_card": "校园卡服务"
        }
        return titles.get(domain, "生活服务")
    
    def _generate_location_tips(self, domain: str, user_context: Dict[str, Any]) -> str:
        """Generate location-specific tips"""
        department = user_context.get("department")
        role = user_context.get("role")
        
        if domain == "dining_info" and department:
            return f"距离{department}最近的食堂是第一食堂，步行约3分钟"
        
        if domain == "library_services" and role == "teacher":
            return "教工可使用专用阅览区，位于图书馆3楼"
        
        if domain == "sports_facilities":
            return "建议提前电话预约热门时段，避免长时间等待"
        
        return ""
    
    def _generate_service_suggestions(self, domain: str, operational_status: Dict[str, Any]) -> List[str]:
        """Generate service-specific suggestions"""
        base_suggestions = {
            "dining_info": [
                "查看今日完整菜单",
                "了解营养价值信息", 
                "查询餐厅评价",
                "设置用餐提醒"
            ],
            "library_services": [
                "在线预约座位",
                "查看图书借阅记录",
                "预约研讨室",
                "下载数字资源"
            ],
            "dormitory_info": [
                "查看宿舍分配",
                "报修宿舍设施",
                "了解宿舍规定",
                "联系宿舍管理员"
            ],
            "campus_map": [
                "获取实时导航",
                "查看建筑详情",
                "了解周边设施",
                "保存常用路线"
            ],
            "sports_facilities": [
                "在线预约场地",
                "查看课程安排", 
                "租借运动器材",
                "加入运动社团"
            ]
        }
        
        suggestions = base_suggestions.get(domain, ["获取更多服务信息"])
        
        # Add time-based suggestions
        if not operational_status.get("is_open"):
            suggestions.insert(0, "查看开放时间安排")
        
        return suggestions[:4]
    
    def _generate_quick_actions(self, domain: str) -> List[Dict[str, str]]:
        """Generate quick action buttons"""
        actions = {
            "dining_info": [
                {"text": "今日菜单", "action": "show_menu"},
                {"text": "充值校园卡", "action": "recharge_card"},
                {"text": "营业时间", "action": "show_hours"}
            ],
            "library_services": [
                {"text": "预约座位", "action": "reserve_seat"},
                {"text": "续借图书", "action": "renew_books"},
                {"text": "开馆时间", "action": "library_hours"}
            ],
            "sports_facilities": [
                {"text": "预约场地", "action": "reserve_court"},
                {"text": "查看空闲", "action": "check_availability"},
                {"text": "器材租借", "action": "equipment_rental"}
            ],
            "campus_map": [
                {"text": "获取导航", "action": "get_directions"},
                {"text": "附近设施", "action": "nearby_facilities"},
                {"text": "全景地图", "action": "campus_map"}
            ]
        }
        
        return actions.get(domain, [])
    
    async def handle_collaboration(self, collaboration_type: str, request_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration requests from other agents"""
        try:
            if collaboration_type == "location_lookup":
                # Provide location information
                return await self._lookup_location(request_data, context)
            
            elif collaboration_type == "service_availability":
                # Check service availability
                return await self._check_service_availability(request_data, context)
            
            elif collaboration_type == "facility_recommendation":
                # Recommend facilities based on requirements
                return await self._recommend_facilities(request_data, context)
            
            else:
                return {
                    "status": "error",
                    "error": f"Unknown collaboration type: {collaboration_type}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": f"Life service collaboration failed: {str(e)}"
            }
    
    async def _lookup_location(self, request_data: Dict[str, Any], 
                             context: Dict[str, Any]) -> Dict[str, Any]:
        """Look up location information"""
        location_query = request_data.get("location", "")
        
        # Search campus locations
        search_results = await self.rag_service.semantic_search(
            query=f"位置 地点 {location_query}",
            category="life",
            top_k=3,
            min_score=0.6
        )
        
        locations = []
        for result in search_results:
            if "位置" in result["content"] or "地点" in result["content"]:
                locations.append({
                    "name": location_query,
                    "description": result["content"][:200],
                    "source": result["document_title"]
                })
        
        return {
            "status": "success",
            "locations": locations,
            "total_found": len(locations)
        }
    
    async def _check_service_availability(self, request_data: Dict[str, Any],
                                        context: Dict[str, Any]) -> Dict[str, Any]:
        """Check service availability status"""
        service_type = request_data.get("service_type", "")
        
        # Get operational status
        operational_status = await self._get_operational_status(service_type)
        
        return {
            "status": "success",
            "service_type": service_type,
            "is_available": operational_status["is_open"],
            "operational_hours": operational_status.get("current_hours", ""),
            "additional_info": operational_status
        }
    
    async def _recommend_facilities(self, request_data: Dict[str, Any],
                                  context: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend facilities based on requirements"""
        requirements = request_data.get("requirements", {})
        user_location = request_data.get("user_location", "")
        
        # Simple facility recommendation logic
        recommendations = []
        
        if requirements.get("study_space"):
            recommendations.append({
                "name": "图书馆自习区",
                "type": "study",
                "distance": "200米",
                "features": ["安静环境", "WiFi", "空调"]
            })
        
        if requirements.get("dining"):
            recommendations.append({
                "name": "第一食堂",
                "type": "dining",  
                "distance": "150米",
                "features": ["多样菜品", "价格实惠", "环境整洁"]
            })
        
        return {
            "status": "success",
            "recommendations": recommendations,
            "total_count": len(recommendations),
            "based_on": "用户需求和位置"
        }
