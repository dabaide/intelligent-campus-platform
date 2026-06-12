from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
import uuid

from core.database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # academic, life, administrative, general
    subcategory = Column(String(100), nullable=True)  # specific subcategory
    source = Column(String(200), nullable=True)  # source file or URL
    file_type = Column(String(20), nullable=True)  # pdf, docx, txt, html
    language = Column(String(10), nullable=False, default="zh-CN")
    tags = Column(Text, nullable=True)  # searchable tags as JSON string
    meta_data = Column(JSON, nullable=True)  # additional metadata
    version = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title[:50]}, category={self.category})>"

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)  # Foreign key reference
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    overlap_size = Column(Integer, nullable=False, default=0)
    embedding_model = Column(String(100), nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    chunk_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"

class FAQ(Base):
    __tablename__ = "faqs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(100), nullable=True)
    keywords = Column(Text, nullable=True)  # keywords as JSON string
    priority = Column(Integer, nullable=False, default=1)  # 1-5, higher is more important
    view_count = Column(Integer, nullable=False, default=0)
    helpful_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<FAQ(id={self.id}, category={self.category}, priority={self.priority})>"

class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graphs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_name = Column(String(200), nullable=False)
    entity_type = Column(String(50), nullable=False)  # person, place, concept, policy, etc.
    description = Column(Text, nullable=True)
    properties = Column(JSON, nullable=True)  # flexible properties storage
    relationships = Column(JSON, nullable=True)  # related entities and relationships
    confidence_score = Column(Float, nullable=False, default=1.0)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<KnowledgeGraph(id={self.id}, entity={self.entity_name}, type={self.entity_type})>"
