from typing import Dict, Any, List, Optional, Tuple
import asyncio
import re
import json
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid

from core.redis_client import RedisClient
from core.config import settings

# [输出质量评估与验证引擎]:
# 质量审查智能体。对生成的复杂回答进行后置校验(Post-Verification)，
# 确保内容合规、无毒且符合校园语境基准。
class QualityAgent:
    """
    Quality Agent - Cross-validates responses from other agents, reduces hallucinations, and ensures accuracy
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
        self.agent_name = "QualityAgent"
        
        # Quality assessment criteria
        self.quality_criteria = {
            "factual_accuracy": {
                "weight": 0.4,
                "checks": ["source_verification", "consistency_check", "fact_validation"]
            },
            "relevance": {
                "weight": 0.3,
                "checks": ["query_relevance", "context_alignment", "user_intent_match"]
            },
            "completeness": {
                "weight": 0.2,
                "checks": ["information_coverage", "missing_elements", "detail_sufficiency"]
            },
            "clarity": {
                "weight": 0.1,
                "checks": ["language_clarity", "structure_coherence", "user_friendliness"]
            }
        }
        
        # Common hallucination patterns to detect
        self.hallucination_patterns = [
            r"据我所知|根据我的理解|我认为|可能是|大概是",  # Uncertainty indicators
            r"\d{4}年\d{1,2}月\d{1,2}日",  # Specific dates without sources
            r"联系电话：\d{3}-\d{8}",  # Phone numbers without verification
            r"地址：.*具体位置.*",  # Specific addresses without verification
            r"价格：.*元|费用：.*元",  # Specific prices without sources
        ]
        
        # Response quality thresholds
        self.quality_thresholds = {
            "excellent": 0.85,
            "good": 0.70,
            "acceptable": 0.55,
            "poor": 0.40,
            "unacceptable": 0.25
        }
        
        # Domain-specific verification rules
        self.verification_rules = {
            "academic": {
                "require_sources": True,
                "check_policy_dates": True,
                "verify_course_codes": True,
                "validate_gpa_calculations": True
            },
            "administrative": {
                "require_sources": True,
                "check_deadlines": True,
                "verify_procedures": True,
                "validate_contact_info": True
            },
            "life": {
                "check_operating_hours": True,
                "verify_locations": True,
                "validate_service_availability": True,
                "require_real_time_data": False
            }
        }
    
    async def verify_response(self, original_query: str, response: Dict[str, Any], 
                            conversation_id: uuid.UUID) -> Dict[str, Any]:
        """
        Main verification method that assesses response quality and accuracy
        """
        try:
            # Extract response details
            response_content = response.get("content", "")
            agent_type = response.get("agent_type", "unknown")
            sources = response.get("sources", [])
            confidence_score = response.get("confidence_score", 0.0)
            
            # Perform comprehensive quality assessment
            quality_assessment = await self._assess_response_quality(
                original_query, response_content, agent_type, sources, confidence_score
            )
            
            # Check for potential hallucinations
            hallucination_check = await self._detect_hallucinations(response_content, sources)
            
            # Verify factual accuracy
            accuracy_verification = await self._verify_factual_accuracy(
                response_content, agent_type, sources
            )
            
            # Cross-reference with knowledge base
            cross_reference_check = await self._cross_reference_knowledge(
                original_query, response_content, agent_type
            )
            
            # Calculate overall verification score
            verification_score = self._calculate_verification_score(
                quality_assessment, hallucination_check, accuracy_verification, cross_reference_check
            )
            
            # Generate verification report
            verification_report = self._generate_verification_report(
                verification_score, quality_assessment, hallucination_check, 
                accuracy_verification, cross_reference_check
            )
            
            # Record verification interaction
            await self._record_verification_interaction(
                conversation_id, original_query, response, verification_report
            )
            
            return {
                "status": "success",
                "score": verification_score,
                "is_verified": verification_score >= self.quality_thresholds["acceptable"],
                "quality_level": self._get_quality_level(verification_score),
                "notes": verification_report["notes"],
                "recommendations": verification_report["recommendations"],
                "hallucination_risk": hallucination_check["risk_level"],
                "requires_human_review": verification_score < self.quality_thresholds["poor"],
                "metadata": {
                    "verification_timestamp": datetime.now().isoformat(),
                    "agent_verified": agent_type,
                    "verification_criteria": list(self.quality_criteria.keys())
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Quality verification failed: {str(e)}",
                "score": 0.0,
                "is_verified": False
            }
    
    async def _assess_response_quality(self, query: str, content: str, agent_type: str, 
                                     sources: List[Dict], confidence_score: float) -> Dict[str, Any]:
        """Assess overall response quality based on multiple criteria"""
        quality_scores = {}
        
        # Factual Accuracy Assessment
        factual_score = await self._assess_factual_accuracy(content, sources, agent_type)
        quality_scores["factual_accuracy"] = factual_score
        
        # Relevance Assessment
        relevance_score = self._assess_relevance(query, content, agent_type)
        quality_scores["relevance"] = relevance_score
        
        # Completeness Assessment
        completeness_score = self._assess_completeness(query, content, sources)
        quality_scores["completeness"] = completeness_score
        
        # Clarity Assessment
        clarity_score = self._assess_clarity(content)
        quality_scores["clarity"] = clarity_score
        
        # Calculate weighted overall score
        overall_score = sum(
            score * self.quality_criteria[criterion]["weight"] 
            for criterion, score in quality_scores.items()
        )
        
        return {
            "overall_score": overall_score,
            "detailed_scores": quality_scores,
            "confidence_alignment": abs(confidence_score - overall_score) <= 0.2
        }
    
    async def _assess_factual_accuracy(self, content: str, sources: List[Dict], agent_type: str) -> float:
        """Assess factual accuracy of the response"""
        accuracy_score = 0.5  # Base score
        
        # Source quality check
        if sources:
            source_quality = len([s for s in sources if s.get("type") == "document"]) / len(sources)
            accuracy_score += source_quality * 0.3
        else:
            accuracy_score -= 0.2  # Penalty for no sources
        
        # Domain-specific checks
        domain_rules = self.verification_rules.get(agent_type, {})
        
        if domain_rules.get("require_sources") and not sources:
            accuracy_score -= 0.3
        
        # Check for specific factual claims without sources
        unsupported_claims = self._detect_unsupported_claims(content)
        if unsupported_claims:
            accuracy_score -= min(0.4, len(unsupported_claims) * 0.1)
        
        return max(0.0, min(1.0, accuracy_score))
    
    def _assess_relevance(self, query: str, content: str, agent_type: str) -> float:
        """Assess relevance of response to the query"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        # Calculate word overlap
        common_words = query_words.intersection(content_words)
        relevance_ratio = len(common_words) / len(query_words) if query_words else 0
        
        base_score = min(relevance_ratio * 2, 1.0)  # Scale to [0, 1]
        
        # Check for query-specific keywords
        if agent_type == "academic" and any(word in query.lower() for word in ["选课", "成绩", "学分"]):
            if any(word in content.lower() for word in ["选课", "成绩", "学分", "课程"]):
                base_score += 0.2
        
        elif agent_type == "life" and any(word in query.lower() for word in ["食堂", "图书馆", "宿舍"]):
            if any(word in content.lower() for word in ["食堂", "图书馆", "宿舍", "开放", "时间"]):
                base_score += 0.2
        
        return min(1.0, base_score)
    
    def _assess_completeness(self, query: str, content: str, sources: List[Dict]) -> float:
        """Assess completeness of the response"""
        base_score = 0.6
        
        # Length-based assessment
        content_length = len(content.strip())
        if content_length < 50:
            base_score -= 0.3
        elif content_length > 200:
            base_score += 0.2
        
        # Structure assessment
        if "**" in content or "#" in content:  # Has formatting
            base_score += 0.1
        
        if any(marker in content for marker in ["1.", "2.", "•", "-"]):  # Has lists
            base_score += 0.1
        
        # Source diversity
        if sources:
            source_types = set(s.get("type", "") for s in sources)
            if len(source_types) > 1:
                base_score += 0.1
        
        return min(1.0, base_score)
    
    def _assess_clarity(self, content: str) -> float:
        """Assess clarity and readability of the response"""
        base_score = 0.7
        
        # Sentence structure check
        sentences = content.split('。')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        
        if 5 <= avg_sentence_length <= 20:  # Optimal sentence length
            base_score += 0.1
        elif avg_sentence_length > 30:  # Too long sentences
            base_score -= 0.2
        
        # Check for clear structure
        if any(marker in content for marker in ["**", "##", "###"]):  # Has headings
            base_score += 0.1
        
        # Check for unclear language
        unclear_phrases = ["可能", "大概", "应该是", "或许"]
        unclear_count = sum(content.count(phrase) for phrase in unclear_phrases)
        if unclear_count > 2:
            base_score -= 0.2
        
        return min(1.0, base_score)
    
    async def _detect_hallucinations(self, content: str, sources: List[Dict]) -> Dict[str, Any]:
        """Detect potential hallucinations in the response"""
        hallucination_indicators = []
        risk_score = 0.0
        
        # Pattern-based detection
        for pattern in self.hallucination_patterns:
            matches = re.findall(pattern, content)
            if matches:
                hallucination_indicators.append({
                    "type": "pattern_match",
                    "pattern": pattern,
                    "matches": matches,
                    "severity": "medium"
                })
                risk_score += 0.1 * len(matches)
        
        # Specific claim verification
        specific_claims = self._extract_specific_claims(content)
        for claim in specific_claims:
            if not self._is_claim_supported(claim, sources):
                hallucination_indicators.append({
                    "type": "unsupported_claim",
                    "claim": claim,
                    "severity": "high"
                })
                risk_score += 0.3
        
        # Determine risk level
        if risk_score >= 0.7:
            risk_level = "high"
        elif risk_score >= 0.4:
            risk_level = "medium"  
        elif risk_score >= 0.1:
            risk_level = "low"
        else:
            risk_level = "minimal"
        
        return {
            "risk_score": min(1.0, risk_score),
            "risk_level": risk_level,
            "indicators": hallucination_indicators,
            "total_indicators": len(hallucination_indicators)
        }
    
    def _extract_specific_claims(self, content: str) -> List[str]:
        """Extract specific factual claims from content"""
        claims = []
        
        # Extract phone numbers
        phone_matches = re.findall(r'电话：(\d{3}-\d{8}|\d{11})', content)
        claims.extend([f"电话：{phone}" for phone in phone_matches])
        
        # Extract specific dates
        date_matches = re.findall(r'(\d{4}年\d{1,2}月\d{1,2}日)', content)
        claims.extend([f"日期：{date}" for date in date_matches])
        
        # Extract specific prices
        price_matches = re.findall(r'(\d+\.?\d*元)', content)
        claims.extend([f"价格：{price}" for price in price_matches])
        
        # Extract specific addresses
        address_matches = re.findall(r'地址：([^。\n]+)', content)
        claims.extend([f"地址：{addr}" for addr in address_matches])
        
        return claims
    
    def _is_claim_supported(self, claim: str, sources: List[Dict]) -> bool:
        """Check if a specific claim is supported by sources"""
        if not sources:
            return False
        
        # Simple keyword matching (would be more sophisticated in practice)
        claim_keywords = claim.lower().split()
        
        for source in sources:
            source_text = ""
            if source.get("title"):
                source_text += source["title"].lower()
            if source.get("content"):
                source_text += source["content"].lower()
            if source.get("description"):
                source_text += source["description"].lower()
            
            # Check if source contains claim keywords
            if any(keyword in source_text for keyword in claim_keywords):
                return True
        
        return False
    
    def _detect_unsupported_claims(self, content: str) -> List[str]:
        """Detect claims that appear unsupported"""
        unsupported = []
        
        # Claims that should have sources
        factual_claim_patterns = [
            r'根据.*规定',
            r'学校政策.*',
            r'最新消息.*',
            r'官方公布.*',
            r'数据显示.*'
        ]
        
        for pattern in factual_claim_patterns:
            matches = re.findall(pattern, content)
            unsupported.extend(matches)
        
        return unsupported
    
    async def _verify_factual_accuracy(self, content: str, agent_type: str, 
                                     sources: List[Dict]) -> Dict[str, Any]:
        """Verify factual accuracy using additional checks"""
        verification_results = {
            "verified_facts": [],
            "questionable_facts": [],
            "accuracy_score": 0.7  # Default score
        }
        
        # Domain-specific verification
        if agent_type == "academic":
            # Check for academic policy consistency
            policy_claims = re.findall(r'(GPA.*?\d+\.?\d*)', content)
            for claim in policy_claims:
                # Would verify against academic policy database
                verification_results["verified_facts"].append(f"Academic policy: {claim}")
        
        elif agent_type == "administrative":
            # Check for deadline accuracy
            deadline_claims = re.findall(r'(\d+月\d+日)', content)
            for claim in deadline_claims:
                # Would verify against administrative calendar
                verification_results["verified_facts"].append(f"Deadline: {claim}")
        
        elif agent_type == "life":
            # Check for operational hours
            time_claims = re.findall(r'(\d{1,2}:\d{2}-\d{1,2}:\d{2})', content)
            for claim in time_claims:
                verification_results["verified_facts"].append(f"Operating hours: {claim}")
        
        # Adjust accuracy score based on verification results
        if verification_results["questionable_facts"]:
            verification_results["accuracy_score"] -= 0.2 * len(verification_results["questionable_facts"])
        
        if verification_results["verified_facts"]:
            verification_results["accuracy_score"] += 0.1 * min(3, len(verification_results["verified_facts"]))
        
        verification_results["accuracy_score"] = max(0.0, min(1.0, verification_results["accuracy_score"]))
        
        return verification_results
    
    async def _cross_reference_knowledge(self, query: str, content: str, agent_type: str) -> Dict[str, Any]:
        """Cross-reference response with knowledge base"""
        try:
            # This would query the RAG service for verification
            # For now, simulate cross-referencing
            cross_ref_score = 0.6  # Base score
            
            # Check content length and detail level
            if len(content) > 100:
                cross_ref_score += 0.2
            
            # Check for structured information
            if any(marker in content for marker in ["**", "##", "1.", "•"]):
                cross_ref_score += 0.1
            
            return {
                "cross_reference_score": min(1.0, cross_ref_score),
                "knowledge_conflicts": [],  # Would detect conflicts with knowledge base
                "additional_sources_found": 0  # Would count additional supporting sources
            }
            
        except Exception as e:
            return {
                "cross_reference_score": 0.5,
                "knowledge_conflicts": [],
                "additional_sources_found": 0,
                "error": str(e)
            }
    
    def _calculate_verification_score(self, quality_assessment: Dict, hallucination_check: Dict,
                                    accuracy_verification: Dict, cross_reference: Dict) -> float:
        """Calculate overall verification score"""
        # Weight different components
        weights = {
            "quality": 0.4,
            "hallucination": 0.3,
            "accuracy": 0.2,
            "cross_reference": 0.1
        }
        
        quality_score = quality_assessment["overall_score"]
        hallucination_penalty = hallucination_check["risk_score"]
        accuracy_score = accuracy_verification["accuracy_score"]
        cross_ref_score = cross_reference["cross_reference_score"]
        
        verification_score = (
            quality_score * weights["quality"] +
            (1.0 - hallucination_penalty) * weights["hallucination"] +
            accuracy_score * weights["accuracy"] +
            cross_ref_score * weights["cross_reference"]
        )
        
        return max(0.0, min(1.0, verification_score))
    
    def _generate_verification_report(self, verification_score: float, quality_assessment: Dict,
                                    hallucination_check: Dict, accuracy_verification: Dict,
                                    cross_reference: Dict) -> Dict[str, Any]:
        """Generate comprehensive verification report"""
        notes = []
        recommendations = []
        
        # Quality notes
        if quality_assessment["overall_score"] < 0.6:
            notes.append("响应质量需要改进")
            recommendations.append("增加更多详细信息和可靠来源")
        
        # Hallucination warnings
        if hallucination_check["risk_level"] in ["high", "medium"]:
            notes.append(f"检测到{hallucination_check['risk_level']}风险的不准确信息")
            recommendations.append("验证所有具体事实和数据")
        
        # Accuracy concerns
        if accuracy_verification["accuracy_score"] < 0.5:
            notes.append("事实准确性存在问题")
            recommendations.append("需要人工审核和事实验证")
        
        # Cross-reference findings
        if cross_reference["cross_reference_score"] < 0.5:
            notes.append("与知识库交叉验证分数较低")
            recommendations.append("补充更多权威来源")
        
        # Overall assessment
        quality_level = self._get_quality_level(verification_score)
        if quality_level in ["poor", "unacceptable"]:
            recommendations.insert(0, "建议重新生成响应或寻求人工帮助")
        
        return {
            "notes": notes,
            "recommendations": recommendations,
            "quality_breakdown": quality_assessment["detailed_scores"],
            "verification_summary": f"验证分数: {verification_score:.2f} ({quality_level})"
        }
    
    def _get_quality_level(self, score: float) -> str:
        """Get quality level based on score"""
        for level, threshold in sorted(self.quality_thresholds.items(), 
                                     key=lambda x: x[1], reverse=True):
            if score >= threshold:
                return level
        return "unacceptable"
    
    async def _record_verification_interaction(self, conversation_id: uuid.UUID, 
                                             original_query: str, response: Dict[str, Any],
                                             verification_report: Dict[str, Any]):
        """Record verification interaction for analytics"""
        try:
            interaction_data = {
                "conversation_id": str(conversation_id),
                "original_query": original_query,
                "verified_agent": response.get("agent_type"),
                "verification_score": verification_report.get("verification_summary", ""),
                "quality_level": self._get_quality_level(verification_report.get("score", 0.0)),
                "timestamp": datetime.now().isoformat()
            }
            
            # Store in Redis for analytics
            await self.redis.set_json(
                f"verification:{conversation_id}:{datetime.now().timestamp()}",
                interaction_data,
                expire=86400 * 7  # Keep for 7 days
            )
            
        except Exception as e:
            print(f"❌ Failed to record verification interaction: {str(e)}")
    
    async def handle_collaboration(self, collaboration_type: str, request_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle collaboration requests from other agents"""
        try:
            if collaboration_type == "fact_check":
                # Perform fact-checking on specific claims
                return await self._fact_check_claims(request_data, context)
            
            elif collaboration_type == "response_review":
                # Review complete response for quality
                return await self._review_response_quality(request_data, context)
            
            elif collaboration_type == "source_validation":
                # Validate source credibility
                return await self._validate_sources(request_data, context)
            
            else:
                return {
                    "status": "error",
                    "error": f"Unknown collaboration type: {collaboration_type}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": f"Quality collaboration failed: {str(e)}"
            }
    
    async def _fact_check_claims(self, request_data: Dict[str, Any], 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """Fact-check specific claims"""
        claims = request_data.get("claims", [])
        fact_check_results = []
        
        for claim in claims:
            # Simple fact-checking logic
            result = {
                "claim": claim,
                "verified": True,  # Would perform actual verification
                "confidence": 0.8,
                "sources": ["知识库验证"]
            }
            fact_check_results.append(result)
        
        return {
            "status": "success",
            "fact_check_results": fact_check_results,
            "overall_accuracy": sum(r["confidence"] for r in fact_check_results) / len(fact_check_results) if fact_check_results else 0
        }
    
    async def _review_response_quality(self, request_data: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """Review overall response quality"""
        response_content = request_data.get("content", "")
        agent_type = request_data.get("agent_type", "unknown")
        
        quality_review = await self._assess_response_quality(
            query="", content=response_content, agent_type=agent_type, 
            sources=[], confidence_score=0.5
        )
        
        return {
            "status": "success",
            "quality_score": quality_review["overall_score"],
            "detailed_assessment": quality_review["detailed_scores"],
            "improvement_suggestions": self._generate_improvement_suggestions(quality_review)
        }
    
    def _generate_improvement_suggestions(self, quality_review: Dict[str, Any]) -> List[str]:
        """Generate suggestions for improving response quality"""
        suggestions = []
        scores = quality_review["detailed_scores"]
        
        if scores.get("factual_accuracy", 0) < 0.7:
            suggestions.append("增加更多可靠来源支持")
        
        if scores.get("relevance", 0) < 0.7:
            suggestions.append("更直接地回答用户问题")
        
        if scores.get("completeness", 0) < 0.7:
            suggestions.append("提供更全面的信息覆盖")
        
        if scores.get("clarity", 0) < 0.7:
            suggestions.append("改进语言表达和结构组织")
        
        return suggestions
    
    async def _validate_sources(self, request_data: Dict[str, Any],
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate source credibility and relevance"""
        sources = request_data.get("sources", [])
        validation_results = []
        
        for source in sources:
            credibility_score = self._assess_source_credibility(source)
            relevance_score = self._assess_source_relevance(source, request_data.get("query", ""))
            
            validation_results.append({
                "source": source,
                "credibility_score": credibility_score,
                "relevance_score": relevance_score,
                "overall_score": (credibility_score + relevance_score) / 2,
                "is_reliable": (credibility_score + relevance_score) / 2 > 0.6
            })
        
        return {
            "status": "success",
            "validation_results": validation_results,
            "reliable_sources_count": len([r for r in validation_results if r["is_reliable"]]),
            "total_sources": len(sources)
        }
    
    def _assess_source_credibility(self, source: Dict[str, Any]) -> float:
        """Assess credibility of a source"""
        credibility_score = 0.5  # Base score
        
        source_type = source.get("type", "")
        if source_type == "document":
            credibility_score += 0.3
        elif source_type == "faq":
            credibility_score += 0.2
        
        # Check for official source indicators
        title = source.get("title", "").lower()
        if any(indicator in title for indicator in ["官方", "政策", "规定", "通知"]):
            credibility_score += 0.2
        
        return min(1.0, credibility_score)
    
    def _assess_source_relevance(self, source: Dict[str, Any], query: str) -> float:
        """Assess relevance of source to query"""
        if not query:
            return 0.5
        
        query_words = set(query.lower().split())
        
        # Check title relevance
        title = source.get("title", "").lower()
        title_words = set(title.split())
        title_overlap = len(query_words.intersection(title_words))
        
        # Check content relevance if available
        content = source.get("content", "").lower()
        content_words = set(content.split())
        content_overlap = len(query_words.intersection(content_words))
        
        relevance_score = min(1.0, (title_overlap * 0.3 + content_overlap * 0.1) / len(query_words) if query_words else 0.5)
        
        return relevance_score
