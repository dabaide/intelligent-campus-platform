from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    preferred_language: Optional[str] = Field("zh-CN", description="Preferred response language")

class ChatResponse(BaseModel):
    message_id: str
    content: str
    agent_type: str
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    created_at: datetime

class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, description="Conversation category")
    is_anonymous: bool = Field(False, description="Whether conversation is anonymous")

class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: Optional[str]
    status: str
    is_anonymous: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: str
    content: str
    role: str
    agent_type: Optional[str]
    created_at: datetime
    metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class ConversationHistoryResponse(BaseModel):
    messages: List[MessageResponse]
    total_count: int
    has_more: bool

class FeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback_text: Optional[str] = Field(None, max_length=1000)
    feedback_type: str = Field("general", description="Type of feedback")
    agent_type: Optional[str] = Field(None, description="Specific agent to rate")

class AgentInteractionRequest(BaseModel):
    agent_type: str = Field(..., description="Type of agent to interact with")
    task_type: str = Field(..., description="Type of task to perform")
    input_data: Dict[str, Any] = Field(..., description="Input data for the agent")
    priority: int = Field(1, ge=1, le=5, description="Task priority")

class AgentInteractionResponse(BaseModel):
    interaction_id: str
    agent_type: str
    status: str
    output_data: Optional[Dict[str, Any]]
    confidence_score: Optional[float]
    execution_time_ms: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
