from fastapi import APIRouter
from api.v1.endpoints import auth, chat, agents, knowledge, admin, feedback, export, search, monitoring, knowledge_management

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(knowledge_management.router, prefix="/knowledge-management", tags=["knowledge-management"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
