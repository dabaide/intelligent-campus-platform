from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    student_id = Column(String(20), unique=True, index=True, nullable=True)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="student")  # student, teacher, staff, admin
    department = Column(String(100), nullable=True)
    grade = Column(String(20), nullable=True)  # 年级
    major = Column(String(100), nullable=True)  # 专业
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    hashed_password = Column(String(255), nullable=False)
    preferences = Column(Text, nullable=True)  # JSON string for user preferences
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - temporarily disabled for testing
    # conversations = relationship("Conversation", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
