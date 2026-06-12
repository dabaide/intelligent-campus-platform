from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base

class AgentInteraction(Base):
    __tablename__ = "agent_interactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    agent_type = Column(String(50), nullable=False)  # navigation, academic, life, admin, quality
    agent_name = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)  # route, query, verify, etc.
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    execution_time_ms = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    interaction_metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships - temporarily disabled for testing
    # conversation = relationship("Conversation", back_populates="agent_interactions")
    
    def __repr__(self):
        return f"<AgentInteraction(id={self.id}, agent_type={self.agent_type}, status={self.status})>"

class AgentCollaboration(Base):
    __tablename__ = "agent_collaborations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    initiator_agent = Column(String(50), nullable=False)
    target_agent = Column(String(50), nullable=False)
    collaboration_type = Column(String(30), nullable=False)  # handoff, consultation, verification
    request_data = Column(JSON, nullable=False)
    response_data = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    priority = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<AgentCollaboration(id={self.id}, {self.initiator_agent}->{self.target_agent})>"

class AgentPerformance(Base):
    __tablename__ = "agent_performance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type = Column(String(50), nullable=False)
    agent_name = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)
    success_rate = Column(Float, nullable=False, default=0.0)
    avg_response_time_ms = Column(Integer, nullable=False, default=0)
    total_interactions = Column(Integer, nullable=False, default=0)
    successful_interactions = Column(Integer, nullable=False, default=0)
    failed_interactions = Column(Integer, nullable=False, default=0)
    user_satisfaction_score = Column(Float, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AgentPerformance(agent_type={self.agent_type}, success_rate={self.success_rate})>"

class UserFeedback(Base):
    __tablename__ = "user_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_type = Column(String(50), nullable=True)
    rating = Column(Integer, nullable=False)  # 1-5 scale
    feedback_text = Column(Text, nullable=True)
    feedback_type = Column(String(30), nullable=False)  # helpful, accurate, fast, etc.
    is_anonymous = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<UserFeedback(id={self.id}, rating={self.rating}, type={self.feedback_type})>"
