"""
Systematic Literature Review Agent System
A RAG-based system for classifying research articles through PRISMA stages
with AI recommendations and human researcher approval.
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Article:
    """Represents a research article in the review process."""
    id: str
    title: str
    link: str
    abstract: str = ""
    stage: str = "screening"  # screening, eligibility, inclusion
    decision: str = "pending"  # pending, include, exclude
    ai_summary: str = ""
    ai_recommendation: str = ""
    ai_confidence: float = 0.0
    researcher_notes: str = ""
    reviewer_decision: str = ""
    timestamp_added: str = ""
    timestamp_reviewed: str = ""


class CacheManager:
    """Manages temporary cache and permanent storage of review data."""
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
        self.base_dir = Path("review_projects") / self.safe_name
        self.cache_file = self.base_dir / "cache.json"
        self.saved_file = self.base_dir / "saved_reviews.json"
        self.articles_log = self.base_dir / "articles_log.txt"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create necessary directories."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def load_cache(self) -> Dict[str, Article]:
        """Load articles from cache."""
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {k: Article(**v) for k, v in data.items()}
        return {}
    
    def save_cache(self, articles: Dict[str, Article]):
        """Save articles to cache (temporary)."""
        self._ensure_dirs()
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump({k: asdict(v) for k, v in articles.items()}, f, indent=2, ensure_ascii=False)
    
    def save_permanent(self, articles: Dict[str, Article]):
        """Save articles to permanent storage."""
        self._ensure_dirs()
        with open(self.saved_file, 'w', encoding='utf-8') as f:
            json.dump({k: asdict(v) for k, v in articles.items()}, f, indent=2, ensure_ascii=False)
        
        # Also update articles log
        self._update_articles_log(articles)
    
    def _update_articles_log(self, articles: Dict[str, Article]):
        """Update the articles log file with names and links."""
        with open(self.articles_log, 'w', encoding='utf-8') as f:
            f.write(f"Systematic Literature Review - Articles Log\n")
            f.write(f"Project: {self.project_name}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            for stage in ["screening", "eligibility", "inclusion"]:
                stage_articles = [a for a in articles.values() if a.stage == stage]
                f.write(f"\n## {stage.upper()} STAGE ({len(stage_articles)} articles)\n")
                f.write("-" * 40 + "\n")
                for article in stage_articles:
                    status = "✓" if article.reviewer_decision == "include" else ("✗" if article.reviewer_decision == "exclude" else "○")
                    f.write(f"[{status}] {article.title}\n")
                    f.write(f"    Link: {article.link}\n")
                    f.write(f"    ID: {article.id}\n")
                    if article.decision != "pending":
                        f.write(f"    Decision: {article.decision}\n")
                    f.write("\n")


class OmniRouteLLM:
    """
    Simple LLM client using free models available locally or via free APIs.
    Falls back to mock responses if no API is configured.
    """
    
    def __init__(self, model_name: str = "free"):
        self.model_name = model_name
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1"
    
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response using available free model."""
        
        # Try OpenRouter with free models if API key exists
        if self.api_key:
            try:
                return self._call_openrouter(prompt, system_prompt)
            except Exception as e:
                print(f"OpenRouter failed: {e}, falling back to mock mode")
        
        # Fallback to mock/simulated responses for demo
        return self._mock_response(prompt)
    
    def _call_openrouter(self, prompt: str, system_prompt: str) -> str:
        """Call OpenRouter API with free model."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8501",
        }
        
        # Use a free model from OpenRouter
        payload = {
            "model": "google/gemma-2-9b-it:free",  # Free tier model
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful research assistant."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def _mock_response(self, prompt: str) -> str:
        """Generate mock response for demonstration without API."""
        # Simple keyword-based mock responses
        prompt_lower = prompt.lower()
        
        if "summarize" in prompt_lower or "summary" in prompt_lower:
            return """**Summary:**
- This study examines [key topic] using [methodology]
- Sample included [population] from [location/timeframe]
- Key findings suggest [main result]
- Limitations include [common limitation]
- Relevance to review question: [moderate/high]"""
        
        elif "recommend" in prompt_lower or "decision" in prompt_lower:
            return """**Recommendation:** INCLUDE
**Confidence:** 0.75
**Rationale:** 
- Study appears to meet inclusion criteria based on title/abstract
- Uses appropriate methodology (survey/cohort data)
- Reports relevant outcomes
**Suggested checks:**
- Verify sample size meets minimum threshold
- Confirm publication year falls within range
- Check if data source is DHS or national survey"""
        
        elif "classify" in prompt_lower or "categorize" in prompt_lower:
            return """**Classification:**
- Study type: Cross-sectional survey
- Data source: National survey
- Region: [To be verified]
- Quality indicators: Appears moderate-high
- PRISMA stage recommendation: Full-text assessment"""
        
        else:
            return """**AI Analysis:**
This article appears relevant to the systematic review topic. The study design and methodology seem appropriate. Recommend proceeding to full-text assessment for detailed evaluation."""


class ReviewAgent:
    """AI Agent for assisting in systematic literature review."""
    
    def __init__(self, llm: OmniRouteLLM):
        self.llm = llm
        self.project_info = {}
    
    def initialize_project(self, title: str, description: str, inclusion_criteria: List[str], 
                          exclusion_criteria: List[str]) -> Dict[str, Any]:
        """Initialize a new review project with researcher input."""
        self.project_info = {
            "title": title,
            "description": description,
            "inclusion_criteria": inclusion_criteria,
            "exclusion_criteria": exclusion_criteria,
            "created_at": datetime.now().isoformat()
        }
        
        # Generate tailored system prompt
        system_prompt = self._create_system_prompt()
        
        return {
            "status": "initialized",
            "project_id": hashlib.md5(title.encode()).hexdigest()[:8],
            "criteria_count": len(inclusion_criteria) + len(exclusion_criteria),
            "ready_for_articles": True
        }
    
    def _create_system_prompt(self) -> str:
        """Create customized system prompt based on project criteria."""
        return f"""You are an AI research assistant helping with a systematic literature review.

Review Topic: {self.project_info.get('title', 'N/A')}
Description: {self.project_info.get('description', 'N/A')}

INCLUSION CRITERIA:
{chr(10).join('- ' + c for c in self.project_info.get('inclusion_criteria', []))}

EXCLUSION CRITERIA:
{chr(10).join('- ' + c for c in self.project_info.get('exclusion_criteria', []))}

Your role:
1. Summarize article titles and abstracts concisely
2. Provide inclusion/exclusion recommendations with confidence scores
3. Identify which PRISMA stage each article belongs to
4. Flag potential issues or missing information
5. Always defer final decisions to the human researcher

Respond in a structured format with clear sections."""
    
    def analyze_article(self, article: Article) -> Dict[str, Any]:
        """Analyze a single article and provide AI judgment."""
        
        prompt = f"""Analyze this research article for systematic review:

TITLE: {article.title}
LINK: {article.link}
ABSTRACT: {article.abstract or 'Not provided'}

Please provide:
1. A brief summary (3-4 bullet points)
2. Your recommendation (INCLUDE/EXCLUDE/UNCERTAIN)
3. Confidence score (0.0-1.0)
4. Which PRISMA stage this belongs to (screening/eligibility/inclusion)
5. Any concerns or notes for the researcher

Format your response clearly with headings."""
        
        response = self.llm.generate(prompt, system_prompt=self._create_system_prompt())
        
        # Parse response (simple extraction)
        recommendation = "UNCERTAIN"
        confidence = 0.5
        stage = "screening"
        
        if "INCLUDE" in response.upper():
            recommendation = "include"
            confidence = 0.75
        elif "EXCLUDE" in response.upper():
            recommendation = "exclude"
            confidence = 0.70
        
        if "full-text" in response.lower() or "eligibility" in response.lower():
            stage = "eligibility"
        elif "final" in response.lower() or "included" in response.lower():
            stage = "inclusion"
        
        return {
            "summary": response,
            "recommendation": recommendation,
            "confidence": confidence,
            "stage": stage,
            "raw_response": response
        }
    
    def batch_analyze(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Analyze multiple articles (processes one at a time for simplicity)."""
        results = []
        for article in articles:
            result = self.analyze_article(article)
            result["article_id"] = article.id
            results.append(result)
        return results
    
    def generate_prisma_counts(self, articles: Dict[str, Article]) -> Dict[str, int]:
        """Generate counts for PRISMA flow diagram."""
        counts = {
            "identified": len(articles),
            "screening": len([a for a in articles.values() if a.stage == "screening"]),
            "eligibility": len([a for a in articles.values() if a.stage == "eligibility"]),
            "included": len([a for a in articles.values() if a.stage == "inclusion" and a.reviewer_decision == "include"]),
            "excluded_screening": len([a for a in articles.values() if a.reviewer_decision == "exclude" and a.stage == "screening"]),
            "excluded_eligibility": len([a for a in articles.values() if a.reviewer_decision == "exclude" and a.stage == "eligibility"])
        }
        return counts
    
    def ask_clarification_questions(self) -> List[str]:
        """Generate clarification questions for the researcher."""
        questions = [
            "What is the specific population of interest? (e.g., age range, demographic)",
            "What types of study designs are acceptable? (e.g., RCT, cohort, cross-sectional)",
            "Are there any language restrictions for included studies?",
            "What is the minimum sample size requirement?",
            "What date range should publications fall within?",
            "Which geographic regions are you focusing on?",
            "What are the primary outcomes of interest?",
            "Are grey literature or unpublished studies to be included?"
        ]
        return questions


def generate_article_id(title: str, link: str) -> str:
    """Generate unique ID for an article."""
    content = f"{title}:{link}:{datetime.now().isoformat()}"
    return hashlib.md5(content.encode()).hexdigest()[:12]
