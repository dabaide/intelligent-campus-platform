from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
import uvicorn
import os
from dotenv import load_dotenv

from core.config import settings
from api.v1.api import api_router
from core.database import init_db
from core.redis_client import init_redis

load_dotenv()

# [核心流程解析]: FastAPI 应用初始化工厂，用于挂载所有中间件和路由分发。
# [系统应用层工厂模式]:
# 框架全局唯一入口，统合 CORS 跨域安全中间件、路由分发总线注册及核心环境变量的动态加载。
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="基于多智能体的智能校园知识服务平台",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# [安全机制解析]: 配置 CORS (跨源资源共享) 中间件，允许前端项目通过浏览器跨域访问后端的 API。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize database
        await init_db()
        
        # Initialize Redis
        await init_redis()
        
        print(f"🚀 {settings.PROJECT_NAME} started successfully!")
        print(f"📚 API Documentation: http://localhost:8000{settings.API_V1_STR}/docs")
        
    except Exception as e:
        print(f"❌ Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down Intelligent Campus Platform...")

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "欢迎使用智能校园知识服务平台",
        "version": "1.0.0",
        "docs": f"{settings.API_V1_STR}/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
