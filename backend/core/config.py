from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

# [全局配置与环境注入中心]:
# 采用 pydantic BaseSettings 动态挂载 .env 环境变量。
# 实现数据库 DSN、大模型 API Key 等机密配置的集中式、强类型管理。
class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Intelligent Campus Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/campus_platform")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI Models API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    QWEN_API_KEY: Optional[str] = os.getenv("QWEN_API_KEY")
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    
    # Vector Database
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./data/vector_db/faiss_index")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/vector_db/chroma")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    
    # Campus Configuration
    CAMPUS_NAME: str = os.getenv("CAMPUS_NAME", "智慧校园大学")
    CAMPUS_CODE: str = os.getenv("CAMPUS_CODE", "ZHXY")
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "zh-CN")
    
    # CrewAI
    CREWAI_TELEMETRY_ENABLED: bool = False
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    class Config:
        case_sensitive = True

settings = Settings()
