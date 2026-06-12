from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import os
import pickle
import asyncio
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, or_

from core.redis_client import RedisClient
from core.config import settings
from models.knowledge_base import Document, DocumentChunk, FAQ
from models.user import User

class RAGService:
    """
    Retrieval-Augmented Generation service for campus knowledge retrieval
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.embedding_model = None
        self.faiss_index = None
        self.chunk_metadata = {}
        self.model_name = settings.EMBEDDING_MODEL
        
        # Initialize embedding model
        asyncio.create_task(self._load_embedding_model())
        
        # Initialize FAISS index
        asyncio.create_task(self._load_faiss_index())
    
    async def _load_embedding_model(self):
        """
        Load sentence transformer model for embeddings
        
        为了兼容离线环境，系统在初始化时会拉起本地的 Embedding 模型（BGE-M3 等）。这是用于把汉字转化为机器能理解的“高维空间向量数组”的关键驱动。
        """
        try:
            loop = asyncio.get_event_loop()
            self.embedding_model = await loop.run_in_executor(
                None, SentenceTransformer, self.model_name
            )
            print(f"✅ Loaded embedding model: {self.model_name}")
        except Exception as e:
            print(f"❌ Failed to load embedding model: {str(e)}")
    
    async def _load_faiss_index(self):
        """Load FAISS index from disk or create new one"""
        try:
            index_path = settings.FAISS_INDEX_PATH
            metadata_path = f"{index_path}_metadata.pkl"
            
            if os.path.exists(f"{index_path}.index") and os.path.exists(metadata_path):
                # Load existing index
                loop = asyncio.get_event_loop()
                self.faiss_index = await loop.run_in_executor(
                    None, faiss.read_index, f"{index_path}.index"
                )
                
                with open(metadata_path, 'rb') as f:
                    self.chunk_metadata = pickle.load(f)
                
                print(f"✅ Loaded FAISS index with {self.faiss_index.ntotal} vectors")
            else:
                # Create new index
                await self._create_new_index()
                
        except Exception as e:
            print(f"❌ Failed to load FAISS index: {str(e)}")
            await self._create_new_index()
    
    async def _create_new_index(self):
        """Create new FAISS index"""
        try:
            # Get embedding dimension
            if not self.embedding_model:
                await self._load_embedding_model()
            
            dimension = self.embedding_model.get_sentence_embedding_dimension()
            
            # Create FAISS index
            self.faiss_index = faiss.IndexFlatIP(dimension)  # Inner Product for cosine similarity
            self.chunk_metadata = {}
            
            print(f"✅ Created new FAISS index with dimension {dimension}")
            
            # Build initial index from database
            await self._build_index_from_database()
            
        except Exception as e:
            print(f"❌ Failed to create FAISS index: {str(e)}")
    
    async def _build_index_from_database(self):
        """Build FAISS index from existing database documents"""
        try:
            # Get all active document chunks
            query = select(DocumentChunk).join(Document).where(Document.is_active == True)
            result = await self.db.execute(query)
            chunks = result.scalars().all()
            
            if not chunks:
                print("ℹ️  No document chunks found in database")
                return
            
            print(f"📚 Building index from {len(chunks)} document chunks...")
            
            # Process chunks in batches
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                await self._add_chunks_to_index(batch)
            
            # Save index to disk
            await self._save_index()
            
            print(f"✅ Built FAISS index with {len(chunks)} chunks")
            
        except Exception as e:
            print(f"❌ Failed to build index from database: {str(e)}")
    
    async def _add_chunks_to_index(self, chunks: List[DocumentChunk]):
        """Add document chunks to FAISS index"""
        try:
            if not self.embedding_model or not self.faiss_index:
                return
            
            texts = [chunk.content for chunk in chunks]
            
            # Generate embeddings
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self.embedding_model.encode, texts, {"normalize_embeddings": True}
            )
            
            # Add to FAISS index
            start_id = self.faiss_index.ntotal
            self.faiss_index.add(embeddings.astype(np.float32))
            
            # Store metadata
            for i, chunk in enumerate(chunks):
                self.chunk_metadata[start_id + i] = {
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content[:500],  # Store preview
                    "metadata": chunk.metadata
                }
                
        except Exception as e:
            print(f"❌ Failed to add chunks to index: {str(e)}")
    
    async def _save_index(self):
        """Save FAISS index and metadata to disk"""
        try:
            index_path = settings.FAISS_INDEX_PATH
            
            # Create directory if not exists
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            
            # Save FAISS index
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, faiss.write_index, self.faiss_index, f"{index_path}.index"
            )
            
            # Save metadata
            with open(f"{index_path}_metadata.pkl", 'wb') as f:
                pickle.dump(self.chunk_metadata, f)
            
            print("✅ Saved FAISS index to disk")
            
        except Exception as e:
            print(f"❌ Failed to save FAISS index: {str(e)}")
    
        # [高维向量引擎相似度检索]:
        # 1. 采用本地加载的 Embedding 模型将自然语言降维映射成密集向量(Dense Vector)。
        # 2. 借助底层 FAISS 引擎计算余弦相似度(Cosine Similarity)，毫秒级召回 Top-K 相关规章制度片段，构建物理级的大模型防幻觉屏障。
    async def semantic_search(self, query: str, category: Optional[str] = None, 
                            top_k: int = 5, min_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform semantic search on document chunks
        
        解决大模型“幻觉”问题的核心武器库。
        1. 先把用户的提问变成向量（query_vector）
        2. 调用 Facebook 的 faiss_index.search()，用余弦相似度算法（Cosine Similarity）在数万条被切块的校园规章文本中，找到距离最近、最贴切的 `top_k` 条记录。
        """
        try:
            # Fallback to keyword search when embeddings/index are unavailable (offline-friendly)
            if not self.embedding_model or not self.faiss_index:
                conditions = [Document.is_active == True]
                if category:
                    conditions.append(Document.category == category)
                if query.strip():
                    like = f"%{query.strip()}%"
                    conditions.append(or_(Document.title.ilike(like), Document.content.ilike(like)))

                stmt = (
                    select(Document)
                    .where(*conditions)
                    .order_by(Document.created_at.desc())
                    .limit(top_k)
                )
                result = await self.db.execute(stmt)
                docs = result.scalars().all()

                results: List[Dict[str, Any]] = []
                for doc in docs:
                    content = (doc.content or "").strip()
                    preview = content[:800] if content else ""
                    score = 0.6
                    results.append({
                        "content": preview,
                        "score": float(score),
                        "chunk_id": None,
                        "document_id": str(doc.id),
                        "document_title": doc.title,
                        "category": doc.category,
                        "source": doc.source,
                        "metadata": {"retrieval": "keyword_fallback"}
                    })
                return results
            
            # Check cache
            cache_key = f"search:{hash(query)}:{category}:{top_k}"
            cached_results = await self.redis.get_json(cache_key)
            if cached_results:
                return cached_results
            
            # Generate query embedding
            loop = asyncio.get_event_loop()
            query_embedding = await loop.run_in_executor(
                None, self.embedding_model.encode, [query], {"normalize_embeddings": True}
            )
            
            # Search FAISS index
            scores, indices = self.faiss_index.search(
                query_embedding.astype(np.float32), min(top_k * 2, 50)
            )
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if score < min_score:
                    continue
                
                if idx in self.chunk_metadata:
                    metadata = self.chunk_metadata[idx]
                    
                    # Get full chunk content
                    chunk_content = await self._get_chunk_content(metadata["chunk_id"])
                    if chunk_content:
                        # Get document info
                        doc_info = await self._get_document_info(metadata["document_id"])
                        
                        # Filter by category if specified
                        if category and doc_info and doc_info.get("category") != category:
                            continue
                        
                        results.append({
                            "content": chunk_content,
                            "score": float(score),
                            "chunk_id": metadata["chunk_id"],
                            "document_id": metadata["document_id"],
                            "document_title": doc_info.get("title", "Unknown") if doc_info else "Unknown",
                            "category": doc_info.get("category", "general") if doc_info else "general",
                            "source": doc_info.get("source") if doc_info else None,
                            "metadata": metadata.get("metadata", {})
                        })
                
                if len(results) >= top_k:
                    break
            
            # Cache results
            await self.redis.set_json(cache_key, results, expire=3600)
            
            return results
            
        except Exception as e:
            print(f"❌ Semantic search failed: {str(e)}")
            return []
    
    async def _get_chunk_content(self, chunk_id: str) -> Optional[str]:
        """Get full chunk content from database"""
        try:
            query = select(DocumentChunk.content).where(DocumentChunk.id == chunk_id)
            result = await self.db.execute(query)
            chunk = result.scalar_one_or_none()
            return chunk
        except Exception:
            return None
    
    async def _get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document information from database"""
        try:
            query = select(Document).where(Document.id == document_id)
            result = await self.db.execute(query)
            doc = result.scalar_one_or_none()
            
            if doc:
                return {
                    "title": doc.title,
                    "category": doc.category,
                    "subcategory": doc.subcategory,
                    "source": doc.source,
                    "tags": doc.tags,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                }
            return None
        except Exception:
            return None
    
    async def search_faqs(self, query: str, category: Optional[str] = None, 
                         top_k: int = 3) -> List[Dict[str, Any]]:
        """Search FAQ database"""
        try:
            # Build query conditions
            conditions = [FAQ.is_active == True]
            if category:
                conditions.append(FAQ.category == category)
            
            # Text search on questions
            query_stmt = select(FAQ).where(*conditions)
            
            if query.strip():
                # Extract lightweight terms for fuzzy matching (handles extra particles like “的”)
                terms = re.findall(r"[\u4e00-\u9fff]{2,}|\d+|[A-Za-z]{2,}", query)
                # Ensure key single-word terms are included when present
                for t in ["地址", "邮编", "电话", "邮箱", "办公时间"]:
                    if t in query and t not in terms:
                        terms.append(t)

                term_conditions = []
                for term in terms[:12]:
                    like = f"%{term}%"
                    term_conditions.append(FAQ.question.ilike(like))
                    term_conditions.append(FAQ.keywords.ilike(like))

                if term_conditions:
                    query_stmt = query_stmt.where(or_(*term_conditions))

                query_stmt = query_stmt.order_by(FAQ.priority.desc(), FAQ.view_count.desc())
            
            query_stmt = query_stmt.limit(top_k)
            
            result = await self.db.execute(query_stmt)
            faqs = result.scalars().all()
            
            return [
                {
                    "id": str(faq.id),
                    "question": faq.question,
                    "answer": faq.answer,
                    "category": faq.category,
                    "subcategory": faq.subcategory,
                    "priority": faq.priority,
                    "keywords": faq.keywords or []
                }
                for faq in faqs
            ]
            
        except Exception as e:
            print(f"❌ FAQ search failed: {str(e)}")
            return []
    
    async def hybrid_search(self, query: str, category: Optional[str] = None, 
                           top_k: int = 5) -> Dict[str, Any]:
        """
        Perform hybrid search combining semantic search and FAQ search
        """
        try:
            # Perform both searches concurrently
            semantic_task = asyncio.create_task(
                self.semantic_search(query, category, top_k)
            )
            faq_task = asyncio.create_task(
                self.search_faqs(query, category, min(3, top_k))
            )
            
            semantic_results, faq_results = await asyncio.gather(semantic_task, faq_task)
            
            return {
                "semantic_results": semantic_results,
                "faq_results": faq_results,
                "total_results": len(semantic_results) + len(faq_results)
            }
            
        except Exception as e:
            print(f"❌ Hybrid search failed: {str(e)}")
            return {"semantic_results": [], "faq_results": [], "total_results": 0}
    
    async def add_document(self, document: Document, content_chunks: List[str]) -> bool:
        """Add new document to knowledge base and index"""
        try:
            # Save document to database
            self.db.add(document)
            await self.db.commit()
            
            # Create document chunks
            chunks = []
            for i, content in enumerate(content_chunks):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    content=content,
                    chunk_size=len(content),
                    embedding_model=self.model_name,
                    embedding_dimension=self.embedding_model.get_sentence_embedding_dimension()
                )
                chunks.append(chunk)
            
            self.db.add_all(chunks)
            await self.db.commit()
            
            # Add chunks to FAISS index
            await self._add_chunks_to_index(chunks)
            await self._save_index()
            
            print(f"✅ Added document '{document.title}' with {len(chunks)} chunks")
            return True
            
        except Exception as e:
            print(f"❌ Failed to add document: {str(e)}")
            await self.db.rollback()
            return False
    
    async def update_document_view_stats(self, document_id: str, user_id: str):
        """Update document view statistics"""
        try:
            # This could be used for analytics and improving search relevance
            stats_key = f"doc_views:{document_id}:{user_id}"
            await self.redis.set_json(stats_key, {
                "viewed_at": asyncio.get_event_loop().time(),
                "user_id": user_id
            }, expire=86400)  # 24 hours
            
        except Exception as e:
            print(f"❌ Failed to update view stats: {str(e)}")
    
    async def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get search suggestions based on partial query"""
        try:
            # This is a simple implementation - could be enhanced with ML models
            suggestions = []
            
            # Search in FAQ questions for matches
            query_stmt = select(FAQ.question).where(
                FAQ.is_active == True,
                FAQ.question.ilike(f"%{partial_query}%")
            ).limit(limit)
            
            result = await self.db.execute(query_stmt)
            questions = result.scalars().all()
            
            suggestions.extend(questions)
            
            # Add some common campus-related suggestions
            if len(suggestions) < limit:
                common_queries = [
                    "如何选课？", "图书馆开放时间", "食堂菜单", "宿舍申请", 
                    "奖学金申请", "课程表查询", "成绩查询", "校园卡充值"
                ]
                
                for query in common_queries:
                    if partial_query.lower() in query.lower() and query not in suggestions:
                        suggestions.append(query)
                        if len(suggestions) >= limit:
                            break
            
            return suggestions[:limit]
            
        except Exception as e:
            print(f"❌ Failed to get search suggestions: {str(e)}")
            return []
