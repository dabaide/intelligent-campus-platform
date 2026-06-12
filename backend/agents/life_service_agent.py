from typing import Dict, Any, List, Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, time
import json
import random

from core.redis_client import RedisClient
from services.rag_service import RAGService
from services.ai_service import ai_service


class LifeServiceAgent:
    """
    生活服务智能体 - 负责校园生活中的餐饮、住宿、交通、医疗、失物招领、校园活动等全方位的后勤服务

    核心能力：
    1. 校园餐饮服务（食堂菜单、营业时间、排队情况、营养推荐）
    2. 图书馆与自习服务（座位预约、开放时间、实时占用率）
    3. 宿舍生活服务（报修、水电、洗衣、网络）
    4. 校园交通与导航（校车班次、路线规划、停车指引）
    5. 体育与健身设施（场馆预约、器材租借、课程查询）
    6. 医疗健康服务（校医院、心理咨询、医保报销）
    7. 失物招领服务（物品挂失、失物查询、认领流程）
    8. 校园活动资讯（社团活动、讲座、演出、比赛）
    9. 校园卡服务（充值、挂失、消费查询、门禁）
    10. 校园商超服务（超市、打印店、快递点）
    """

    def __init__(self, db: AsyncSession, redis: RedisClient, rag_service: RAGService):
        self.db = db
        self.redis = redis
        self.rag_service = rag_service
        self.agent_name = "LifeServiceAgent"

        self.service_domains = {
            "dining_info": {
                "keywords": ["食堂", "餐厅", "菜单", "营业时间", "饭点", "用餐", "食物", "餐饮", "吃饭", "饿了"],
                "context": "dining_services"
            },
            "library_services": {
                "keywords": ["图书馆", "借书", "座位", "预约", "开馆", "闭馆", "自习", "阅览", "还书"],
                "context": "library_info"
            },
            "dormitory_info": {
                "keywords": ["宿舍", "寝室", "住宿", "床位", "宿管", "水电", "网络", "洗衣", "报修"],
                "context": "dormitory_services"
            },
            "campus_map": {
                "keywords": ["地图", "位置", "怎么走", "在哪里", "路线", "方向", "建筑", "教室", "导航"],
                "context": "campus_navigation"
            },
            "sports_facilities": {
                "keywords": ["体育", "运动", "健身", "球场", "游泳", "跑道", "预约", "比赛", "锻炼"],
                "context": "sports_recreation"
            },
            "transport_services": {
                "keywords": ["校车", "班车", "交通", "公交", "地铁", "停车", "出行", "拼车"],
                "context": "transportation"
            },
            "campus_card": {
                "keywords": ["校园卡", "一卡通", "充值", "余额", "消费", "挂失", "补办", "门禁"],
                "context": "campus_card_services"
            },
            "health_services": {
                "keywords": ["医院", "医生", "看病", "挂号", "发烧", "感冒", "牙科", "眼科", "体检", "疫苗", "心理", "咨询"],
                "context": "health_services"
            },
            "lost_found": {
                "keywords": ["丢失", "捡到", "失物", "招领", "遗失", "寻物", "失物招领", "丢了"],
                "context": "lost_and_found"
            },
            "campus_events": {
                "keywords": ["活动", "讲座", "演出", "比赛", "社团", "晚会", "展览", "招聘", "志愿者"],
                "context": "campus_events"
            },
            "campus_store": {
                "keywords": ["超市", "便利店", "打印", "复印", "快递", "理发", "快递点", "买东西"],
                "context": "campus_stores"
            }
        }

        self.operational_info = {
            "library": {
                "weekday_hours": "8:00-22:00",
                "weekend_hours": "9:00-21:00",
                "services": ["图书借阅", "自习座位", "研讨室", "电子资源", "打印复印"]
            },
            "dining": {
                "breakfast": "7:00-9:00",
                "lunch": "11:00-13:30",
                "dinner": "17:00-19:30",
                "locations": ["第一食堂", "第二食堂", "教工餐厅", "清真餐厅", "风味小吃街"],
                "price_range": {"第一食堂": "8-15元", "第二食堂": "10-20元", "教工餐厅": "15-30元", "清真餐厅": "10-18元", "风味小吃街": "5-25元"}
            },
            "sports": {
                "weekday_hours": "6:00-22:00",
                "weekend_hours": "8:00-21:00",
                "facilities": ["体育馆", "游泳馆", "篮球场", "足球场", "网球场", "羽毛球场", "健身房"]
            },
            "health": {
                "weekday_hours": "8:00-12:00, 14:00-17:30",
                "weekend_hours": "8:30-11:30",
                "emergency": "24小时急诊",
                "services": ["内科", "外科", "牙科", "眼科", "体检中心", "心理咨询室"]
            },
            "transport": {
                "shuttle_routes": {
                    "1号线": "南门 → 教学楼 → 图书馆 → 食堂 → 宿舍区",
                    "2号线": "北门 → 行政楼 → 实验楼 → 体育馆 → 宿舍区",
                    "3号线": "地铁站接驳 → 南门 → 图书馆"
                },
                "shuttle_frequency": "工作日每15分钟一班，周末每30分钟一班",
                "shuttle_hours": "7:00-21:00"
            }
        }

    async def process_request(self, task_type: str, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理生活服务相关请求的主入口方法"""
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

            domain = self._identify_service_domain(task_type, query)
            user_context = self._extract_user_location_context(context)
            search_results = await self._search_service_knowledge(query, domain, user_context)

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
                    "location_context": user_context.get("location"),
                    "agent_name": self.agent_name
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "agent_type": "life",
                "error": f"生活服务请求处理失败: {str(e)}"
            }

    def _identify_service_domain(self, task_type: str, query: str) -> str:
        """通过任务类型和查询关键词识别具体的服务领域"""
        query_lower = query.lower()

        task_domain_mapping = {
            "dining_info": "dining_info",
            "library_services": "library_services",
            "dormitory_info": "dormitory_info",
            "campus_map": "campus_map",
            "sports_facilities": "sports_facilities",
            "transport_services": "transport_services",
            "campus_card": "campus_card",
            "health_services": "health_services",
            "lost_found": "lost_found",
            "campus_events": "campus_events",
            "campus_store": "campus_store"
        }

        if task_type in task_domain_mapping:
            return task_domain_mapping[task_type]

        domain_scores = {}
        for domain, config in self.service_domains.items():
            score = sum(1 for keyword in config["keywords"] if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score

        if domain_scores:
            return max(domain_scores, key=domain_scores.get)

        return "campus_map"

    def _extract_user_location_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """提取用户位置与偏好上下文"""
        return {
            "user_id": context.get("user_id"),
            "role": context.get("role", "student"),
            "department": context.get("department"),
            "location": context.get("current_location"),
            "preferences": context.get("preferences", {}),
            "dietary_preferences": context.get("dietary_preferences", []),
            "budget_level": context.get("budget_level", "medium")
        }

    async def _search_service_knowledge(self, query: str, domain: str,
                                        user_context: Dict[str, Any]) -> Dict[str, Any]:
        """搜索生活服务知识库"""
        try:
            enhanced_query = self._enhance_query_with_location(query, user_context)

            search_results = await self.rag_service.hybrid_search(
                query=enhanced_query,
                category="life",
                top_k=6
            )

            real_time_info = await self._get_real_time_service_info(domain)
            if real_time_info:
                search_results["real_time_info"] = real_time_info

            return search_results

        except Exception as e:
            print(f"❌ 生活服务知识搜索失败: {str(e)}")
            return {"semantic_results": [], "faq_results": [], "total_results": 0}

    def _enhance_query_with_location(self, query: str, user_context: Dict[str, Any]) -> str:
        """用位置上下文增强查询"""
        enhanced_parts = [query]

        if user_context.get("department"):
            enhanced_parts.append(f"位置:{user_context['department']}")

        if user_context.get("role") == "teacher":
            enhanced_parts.append("教工")

        if user_context.get("dietary_preferences"):
            prefs = ",".join(user_context["dietary_preferences"])
            enhanced_parts.append(f"偏好:{prefs}")

        return " ".join(enhanced_parts)

    async def _get_real_time_service_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """获取各服务领域的实时信息（优先从 Redis 缓存读取）"""
        try:
            cache_key = f"realtime_service:{domain}"
            cached_info = await self.redis.get_json(cache_key)

            if cached_info:
                return cached_info

            current_time = datetime.now().time()
            current_hour = current_time.hour
            current_weekday = datetime.now().weekday()
            real_time_info = {}

            if domain == "library_services":
                base_occupancy = 65 if current_hour >= 14 and current_hour <= 16 else 45
                real_time_info = {
                    "current_occupancy": f"{base_occupancy}%",
                    "available_seats": random.randint(80, 200),
                    "peak_hours": "14:00-16:00, 19:00-21:00",
                    "special_notices": []
                }
                if current_time > time(21, 0):
                    real_time_info["special_notices"].append("图书馆即将闭馆，请合理安排时间")
                if current_weekday >= 5:
                    real_time_info["special_notices"].append("周末部分阅览区关闭，请前往主阅览区")

            elif domain == "dining_info":
                daily_menus = {
                    0: "今日推荐：红烧排骨、番茄炒蛋、清炒时蔬、冬瓜排骨汤",
                    1: "今日推荐：宫保鸡丁、麻婆豆腐、蒜蓉西兰花、酸辣汤",
                    2: "今日推荐：糖醋里脊、鱼香肉丝、凉拌黄瓜、紫菜蛋花汤",
                    3: "今日推荐：红烧牛肉面、炸酱面、蔬菜沙拉、玉米排骨汤",
                    4: "今日推荐：烤鸭饭、水煮鱼、上汤娃娃菜、番茄蛋汤",
                    5: "周末特供：麻辣香锅、寿司拼盘、水果沙拉",
                    6: "周末特供：火锅自助、烧烤套餐、鲜榨果汁"
                }
                crowd_levels = {7: "较少", 8: "适中", 11: "较多", 12: "高峰", 13: "较多",
                                17: "适中", 18: "高峰", 19: "较多"}
                current_crowd = "较少"
                for h, level in crowd_levels.items():
                    if current_hour == h:
                        current_crowd = level

                real_time_info = {
                    "current_menu": daily_menus.get(current_weekday, daily_menus[0]),
                    "crowd_level": current_crowd,
                    "wait_time": "5-10分钟" if current_crowd != "高峰" else "15-20分钟",
                    "special_offers": ["第二食堂新品8折优惠", "清真餐厅满10减2"]
                }
                if time(11, 0) <= current_time <= time(13, 30):
                    real_time_info["meal_period"] = "午餐时间"
                elif time(17, 0) <= current_time <= time(19, 30):
                    real_time_info["meal_period"] = "晚餐时间"
                elif time(7, 0) <= current_time <= time(9, 0):
                    real_time_info["meal_period"] = "早餐时间"

            elif domain == "sports_facilities":
                weather_impact = "正常开放" if current_hour >= 6 and current_hour <= 20 else "部分室外场地照明有限"
                real_time_info = {
                    "available_courts": {
                        "篮球场": f"{random.randint(2,5)}/8可用",
                        "羽毛球场": f"{random.randint(1,4)}/6可用",
                        "网球场": "全部可用" if current_hour < 18 else "2/4可用",
                        "游泳馆": "开放中" if 14 <= current_hour <= 20 else "已闭馆"
                    },
                    "equipment_rental": "可租借" if current_hour < 20 else "已停止",
                    "weather_impact": weather_impact,
                    "current_courses": ["瑜伽课 16:00-17:00", "动感单车 18:00-19:00"] if current_weekday < 5 else []
                }

            elif domain == "health_services":
                real_time_info = {
                    "is_emergency_available": True,
                    "current_status": "门诊开放" if (
                            time(8, 0) <= current_time <= time(12, 0) or time(14, 0) <= current_time <= time(17, 30)
                    ) else "仅急诊",
                    "departments_available": ["内科", "外科", "药房"],
                    "queue_length": "较短" if current_hour < 10 else "适中",
                    "counseling_available": "9:00-11:30, 14:00-17:00" if current_weekday < 5 else "需预约",
                    "hotline": "校医院急诊: 120 (校内)"
                }

            elif domain == "transport_services":
                real_time_info = {
                    "next_shuttle": f"{current_hour + 1}:00 出发",
                    "route_status": {route: "正常运行" for route in self.operational_info["transport"]["shuttle_routes"]},
                    "peak_warning": "当前为乘车高峰期" if current_hour in [8, 12, 17, 18] else "运力充足",
                    "bike_available": random.randint(10, 50),
                    "parking_spots": "充足" if current_hour < 8 else "紧张"
                }

            elif domain == "campus_events":
                sample_events = [
                    {"name": "校园歌手大赛", "time": "本周五 19:00", "location": "大学生活动中心"},
                    {"name": "学术讲座：人工智能前沿", "time": "本周三 14:30", "location": "学术报告厅"},
                    {"name": "社团招新", "time": "本周六 10:00-16:00", "location": "操场"},
                    {"name": "校园招聘会", "time": "下周一 13:30", "location": "体育馆"}
                ]
                real_time_info = {
                    "upcoming_events": sample_events[:3],
                    "ongoing_events": ["校园摄影展 9:00-17:00 图书馆大厅"],
                    "registration_deadlines": ["辩论赛报名截止: 本周四"]
                }

            # 缓存 15 分钟
            await self.redis.set_json(cache_key, real_time_info, expire=900)
            return real_time_info

        except Exception as e:
            print(f"❌ 获取实时服务信息失败: {str(e)}")
            return None

    async def _get_operational_status(self, domain: str) -> Dict[str, Any]:
        """获取服务设施当前的运营状态"""
        current_time = datetime.now().time()
        current_weekday = datetime.now().weekday()

        status = {"is_open": False, "next_open": "", "current_hours": ""}

        if domain == "library_services":
            if current_weekday < 5:
                open_time, close_time = time(8, 0), time(22, 0)
                status["current_hours"] = "8:00-22:00"
            else:
                open_time, close_time = time(9, 0), time(21, 0)
                status["current_hours"] = "9:00-21:00"
            status["is_open"] = open_time <= current_time <= close_time
            if not status["is_open"]:
                status["next_open"] = "明天 8:00" if current_weekday < 4 else "周一 8:00"

        elif domain == "dining_info":
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
            if not status["is_open"]:
                next_periods = [p for p in dining_periods if p[0] > current_time]
                if next_periods:
                    status["next_open"] = f"下一餐 {next_periods[0][0].strftime('%H:%M')}"

        elif domain == "sports_facilities":
            if current_weekday < 5:
                open_time, close_time = time(6, 0), time(22, 0)
                status["current_hours"] = "6:00-22:00"
            else:
                open_time, close_time = time(8, 0), time(21, 0)
                status["current_hours"] = "8:00-21:00"
            status["is_open"] = open_time <= current_time <= close_time

        elif domain == "health_services":
            morning_start, morning_end = time(8, 0), time(12, 0)
            afternoon_start, afternoon_end = time(14, 0), time(17, 30)
            in_morning = morning_start <= current_time <= morning_end
            in_afternoon = afternoon_start <= current_time <= afternoon_end
            status["is_open"] = in_morning or in_afternoon
            status["current_hours"] = "8:00-12:00, 14:00-17:30"
            status["emergency_available"] = True
            if not status["is_open"]:
                status["next_open"] = "明天 8:00 门诊开放（急诊24小时）"

        elif domain == "transport_services":
            open_time, close_time = time(7, 0), time(21, 0)
            status["is_open"] = open_time <= current_time <= close_time
            status["current_hours"] = "7:00-21:00"

        return status

    async def _generate_service_response(self, task_type: str, domain: str, query: str,
                                         search_results: Dict[str, Any],
                                         user_context: Dict[str, Any]) -> Dict[str, Any]:
        """生成生活服务响应内容"""
        try:
            content_parts = []
            sources = []

            operational_status = await self._get_operational_status(domain)
            status_icon = "🟢" if operational_status["is_open"] else "🔴"
            content_parts.append(f"## {status_icon} {self._get_domain_title(domain)}")

            if operational_status.get("current_hours"):
                content_parts.append(f"**开放时间：** {operational_status['current_hours']}")
            if operational_status.get("next_open") and not operational_status["is_open"]:
                content_parts.append(f"⏰ **下次开放：** {operational_status['next_open']}")

            real_time_info = search_results.get("real_time_info")
            if real_time_info:
                content_parts.append("\n📊 **实时信息：**")
                for key, value in real_time_info.items():
                    if key == "current_menu" and domain == "dining_info":
                        content_parts.append(f"🍽️ {value}")
                    elif key == "crowd_level":
                        crowd_icon = {"较少": "😊", "适中": "🙂", "较多": "😅", "高峰": "🔥"}.get(value, "")
                        content_parts.append(f"👥 **排队情况：** {value} {crowd_icon}")
                    elif key == "wait_time":
                        content_parts.append(f"⏳ **预计等待：** {value}")
                    elif key == "meal_period":
                        content_parts.append(f"🕐 **当前时段：** {value}")
                    elif key == "available_seats":
                        content_parts.append(f"💺 **可用座位：** {value}")
                    elif key == "next_shuttle":
                        content_parts.append(f"🚌 **下一班校车：** {value}")
                    elif key == "upcoming_events":
                        content_parts.append(f"📅 **近期活动：**")
                        for event in value[:3]:
                            content_parts.append(f"  • {event['name']} — {event['time']} @ {event['location']}")
                    elif key not in ["special_notices", "special_offers", "current_courses",
                                     "available_courts", "route_status"]:
                        if isinstance(value, str):
                            content_parts.append(f"• **{key}**: {value}")

                if real_time_info.get("special_notices"):
                    content_parts.append("\n⚠️ **特别提醒：**")
                    for notice in real_time_info["special_notices"]:
                        content_parts.append(f"• {notice}")

                if real_time_info.get("peak_warning"):
                    content_parts.append(f"\n📢 {real_time_info['peak_warning']}")

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

            faq_results = search_results.get("faq_results", [])
            if faq_results:
                content_parts.append("\n❓ **常见问题：**")
                for faq in faq_results[:2]:
                    content_parts.append(f"**Q**: {faq['question']}")
                    content_parts.append(f"**A**: {faq['answer']}")
                    sources.append({"type": "faq", "question": faq["question"]})

            location_tips = self._generate_location_tips(domain, user_context)
            if location_tips:
                content_parts.append(f"\n💡 **温馨提示：** {location_tips}")

            suggestions = self._generate_service_suggestions(domain, operational_status)
            quick_actions = self._generate_quick_actions(domain)

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
                "content": "抱歉，获取生活服务信息时遇到问题。请稍后重试或联系相关服务部门。",
                "confidence_score": 0.0,
                "sources": [],
                "suggestions": ["联系服务热线", "查看官方网站", "前往服务中心咨询"],
                "quick_actions": []
            }

    def _get_domain_title(self, domain: str) -> str:
        """获取服务领域的中文名称"""
        titles = {
            "dining_info": "🍽️ 餐饮服务",
            "library_services": "📚 图书馆服务",
            "dormitory_info": "🏠 宿舍服务",
            "campus_map": "🗺️ 校园导航",
            "sports_facilities": "⚽ 体育设施",
            "transport_services": "🚌 交通服务",
            "campus_card": "💳 校园卡服务",
            "health_services": "🏥 医疗健康服务",
            "lost_found": "🔍 失物招领",
            "campus_events": "🎉 校园活动",
            "campus_store": "🛒 校园商超"
        }
        return titles.get(domain, "🏫 生活服务")

    def _generate_location_tips(self, domain: str, user_context: Dict[str, Any]) -> str:
        """根据用户位置生成个性化提示"""
        department = user_context.get("department")
        role = user_context.get("role", "student")

        tips_map = {
            "dining_info": {
                "计算机学院": "距离计算机学院最近的是第一食堂和风味小吃街，步行约3-5分钟",
                "外国语学院": "第二食堂离您最近，清真餐厅也在附近，步行约4分钟",
                "default": "最近的食堂步行约5分钟即可到达"
            },
            "library_services": {
                "teacher": "教工可使用3楼专用阅览区，凭教工卡进入",
                "student": "考试周建议提前预约座位，2楼和4楼自习区座位较多",
                "default": "建议避开下午2-4点高峰期"
            },
            "sports_facilities": {
                "default": "热门场地建议提前一天预约，周末场地较为紧张"
            },
            "health_services": {
                "default": "校医院在校园北侧，紧急情况可拨打校内120"
            },
            "transport_services": {
                "default": "下载校园地图APP可实时查看校车位置"
            }
        }

        domain_tips = tips_map.get(domain, {})
        if department and department in domain_tips:
            return domain_tips[department]
        if role and role in domain_tips:
            return domain_tips[role]
        return domain_tips.get("default", "")

    def _generate_service_suggestions(self, domain: str, operational_status: Dict[str, Any]) -> List[str]:
        """生成服务相关的后续建议"""
        base_suggestions = {
            "dining_info": [
                "查看今日完整菜单与营养信息",
                "了解各食堂特色菜品与评分",
                "校园卡在线充值",
                "设置用餐提醒"
            ],
            "library_services": [
                "在线预约自习座位",
                "查询图书借阅状态与续借",
                "预约学术研讨室",
                "下载电子资源与论文"
            ],
            "dormitory_info": [
                "在线报修宿舍设施",
                "查看宿舍管理规定",
                "洗衣房使用查询",
                "联系本楼宿管老师"
            ],
            "campus_map": [
                "获取步行/骑行导航路线",
                "查看建筑物详细信息",
                "搜索周边生活设施",
                "保存常用地点"
            ],
            "sports_facilities": [
                "在线预约运动场地",
                "查看体育课程安排",
                "租借运动器材",
                "加入校园运动社团"
            ],
            "health_services": [
                "校医院在线挂号",
                "查看医保报销流程",
                "预约心理咨询",
                "查询体检安排"
            ],
            "lost_found": [
                "发布失物信息",
                "查询失物招领列表",
                "联系失物招领处",
                "认领流程说明"
            ],
            "campus_events": [
                "查看本月活动日历",
                "报名参加社团",
                "获取活动通知推送",
                "申请活动场地"
            ],
            "campus_store": [
                "查看各店铺营业时间",
                "快递取件点查询",
                "打印店位置导航",
                "校园超市优惠信息"
            ]
        }

        suggestions = base_suggestions.get(domain, ["获取更多生活服务信息", "联系校园服务中心"])

        if not operational_status.get("is_open"):
            suggestions.insert(0, "查看完整开放时间安排")

        return suggestions[:4]

    def _generate_quick_actions(self, domain: str) -> List[Dict[str, str]]:
        """生成快捷操作按钮"""
        actions = {
            "dining_info": [
                {"text": "🍽️ 今日菜单", "action": "show_menu"},
                {"text": "💰 校园卡充值", "action": "recharge_card"},
                {"text": "🕐 营业时间", "action": "show_hours"},
                {"text": "⭐ 餐厅评价", "action": "show_reviews"}
            ],
            "library_services": [
                {"text": "💺 预约座位", "action": "reserve_seat"},
                {"text": "📖 续借图书", "action": "renew_books"},
                {"text": "🕐 开馆时间", "action": "library_hours"},
                {"text": "🔍 检索图书", "action": "search_books"}
            ],
            "sports_facilities": [
                {"text": "🏀 预约场地", "action": "reserve_court"},
                {"text": "📊 查看空闲", "action": "check_availability"},
                {"text": "🎿 器材租借", "action": "equipment_rental"},
                {"text": "📅 课程查询", "action": "view_courses"}
            ],
            "campus_map": [
                {"text": "🧭 获取导航", "action": "get_directions"},
                {"text": "📍 附近设施", "action": "nearby_facilities"},
                {"text": "🗺️ 全景地图", "action": "campus_map"}
            ],
            "health_services": [
                {"text": "🏥 在线挂号", "action": "make_appointment"},
                {"text": "💊 药品查询", "action": "medicine_query"},
                {"text": "🧠 心理咨询", "action": "counseling_booking"}
            ],
            "lost_found": [
                {"text": "📢 发布失物", "action": "report_lost"},
                {"text": "🔍 查找失物", "action": "search_lost_items"},
                {"text": "✅ 登记认领", "action": "claim_item"}
            ],
            "campus_events": [
                {"text": "📅 活动日历", "action": "events_calendar"},
                {"text": "✍️ 立即报名", "action": "register_event"},
                {"text": "🔔 活动提醒", "action": "set_reminder"}
            ],
            "transport_services": [
                {"text": "🚌 校车实时", "action": "shuttle_tracker"},
                {"text": "🗺️ 线路查询", "action": "route_query"},
                {"text": "🚲 共享单车", "action": "bike_rental"}
            ]
        }

        return actions.get(domain, [
            {"text": "📞 服务热线", "action": "call_service"},
            {"text": "❓ 常见问题", "action": "show_faq"}
        ])

    # ============ 智能体协作接口 ============

    async def handle_collaboration(self, collaboration_type: str, request_data: Dict[str, Any],
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """处理来自其他智能体的协作请求"""
        try:
            handlers = {
                "location_lookup": self._lookup_location,
                "service_availability": self._check_service_availability,
                "facility_recommendation": self._recommend_facilities,
                "dining_recommendation": self._recommend_dining,
                "route_planning": self._plan_route_to_service,
                "event_query": self._query_campus_events,
                "health_service_query": self._query_health_services
            }

            handler = handlers.get(collaboration_type)
            if handler:
                return await handler(request_data, context)
            else:
                return {
                    "status": "error",
                    "error": f"未知的协作类型: {collaboration_type}"
                }

        except Exception as e:
            return {
                "status": "error",
                "error": f"生活服务协作失败: {str(e)}"
            }

    async def _lookup_location(self, request_data: Dict[str, Any],
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """查询位置信息"""
        location_query = request_data.get("location", "")

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
                    "source": result["document_title"],
                    "score": result["score"]
                })

        return {
            "status": "success",
            "locations": locations,
            "total_found": len(locations)
        }

    async def _check_service_availability(self, request_data: Dict[str, Any],
                                          context: Dict[str, Any]) -> Dict[str, Any]:
        """查询服务可用性"""
        service_type = request_data.get("service_type", "")

        operational_status = await self._get_operational_status(service_type)
        real_time_info = await self._get_real_time_service_info(service_type)

        return {
            "status": "success",
            "service_type": service_type,
            "is_available": operational_status["is_open"],
            "operational_hours": operational_status.get("current_hours", ""),
            "real_time_info": real_time_info,
            "additional_info": operational_status
        }

    async def _recommend_facilities(self, request_data: Dict[str, Any],
                                    context: Dict[str, Any]) -> Dict[str, Any]:
        """根据用户需求推荐校园设施"""
        requirements = request_data.get("requirements", {})
        user_location = request_data.get("user_location", "")

        recommendations = []
        if requirements.get("study_space"):
            recommendations.append({
                "name": "图书馆自习区",
                "type": "study",
                "distance": "约200米",
                "features": ["安静环境", "免费WiFi", "空调开放", "饮水机"],
                "reservation_required": True
            })
        if requirements.get("dining"):
            recommendations.append({
                "name": "第一食堂",
                "type": "dining",
                "distance": "约150米",
                "features": ["菜品多样", "价格实惠", "环境整洁", "支持校园卡"],
                "current_crowd": "适中"
            })
        if requirements.get("sports"):
            recommendations.append({
                "name": "体育馆",
                "type": "sports",
                "distance": "约400米",
                "features": ["室内场地", "器材齐全", "更衣室", "淋浴间"],
                "reservation_required": True
            })
        if requirements.get("printing"):
            recommendations.append({
                "name": "校园打印店",
                "type": "service",
                "distance": "约100米",
                "features": ["黑白/彩色打印", "装订服务", "证件照"],
                "hours": "8:00-20:00"
            })

        return {
            "status": "success",
            "recommendations": recommendations,
            "total_count": len(recommendations),
            "based_on": "用户需求和当前位置"
        }

    async def _recommend_dining(self, request_data: Dict[str, Any],
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """根据偏好推荐餐厅和菜品"""
        preferences = request_data.get("preferences", {})
        budget = preferences.get("budget", "medium")
        dietary = preferences.get("dietary", [])
        current_time = datetime.now().time()

        dining_options = []
        locations = self.operational_info["dining"]["locations"]
        price_map = self.operational_info["dining"]["price_range"]

        # 根据预算筛选
        for location in locations:
            price_range = price_map.get(location, "10-20元")
            if budget == "low" and "15" not in str(price_range):
                dining_options.append({"name": location, "price": price_range,
                                       "recommendation": "经济实惠，适合学生日常用餐"})
            elif budget == "medium" and "30" not in str(price_range):
                dining_options.append({"name": location, "price": price_range,
                                       "recommendation": "性价比高，菜品种类丰富"})
            elif budget == "high":
                dining_options.append({"name": location, "price": price_range,
                                       "recommendation": "优质用餐体验"})

        # 判断当前可用
        in_meal_time = any(
            start <= current_time <= end
            for start, end, _ in [(time(7, 0), time(9, 0)), (time(11, 0), time(13, 30)),
                                  (time(17, 0), time(19, 30))]
        )

        return {
            "status": "success",
            "dining_options": dining_options,
            "currently_open": in_meal_time,
            "total_options": len(dining_options)
        }

    async def _plan_route_to_service(self, request_data: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """规划到服务设施的路线"""
        destination = request_data.get("destination", "")
        start_point = request_data.get("start_point", "当前位置")

        return {
            "status": "success",
            "routes": [
                {"mode": "步行", "duration": "约8分钟", "distance": "约600米", "recommended": True},
                {"mode": "骑行", "duration": "约3分钟", "distance": "约650米"},
                {"mode": "校车", "duration": "约10分钟", "line": "1号线"}
            ],
            "destination": destination,
            "start_point": start_point
        }

    async def _query_campus_events(self, request_data: Dict[str, Any],
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """查询校园活动信息"""
        event_type = request_data.get("event_type", "all")

        real_time_info = await self._get_real_time_service_info("campus_events")

        return {
            "status": "success",
            "events": real_time_info.get("upcoming_events", []) if real_time_info else [],
            "filtered_by": event_type
        }

    async def _query_health_services(self, request_data: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """查询医疗健康服务"""
        service_type = request_data.get("health_service_type", "general")

        real_time_info = await self._get_real_time_service_info("health_services")

        return {
            "status": "success",
            "health_info": real_time_info,
            "service_type": service_type,
            "emergency_contact": "校医院急诊: 120 (校内)"
        }
