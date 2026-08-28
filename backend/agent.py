import httpx
from typing import Dict, List, Optional
from config import settings

class ReviewAgent:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.model = settings.FREE_MODEL
    
    async def analyze_article(self, title: str, abstract: str, inclusion_criteria: str, exclusion_criteria: str) -> Dict:
        """Analyze a single article and provide summary + recommendation"""
        
        if not self.api_key:
            # Mock response for testing without API key
            return {
                "summary": ["Study objective not analyzed (no API key)", "Methods not analyzed", "Results not analyzed"],
                "recommendation": "unsure",
                "confidence": 0.5,
                "reasoning": "API key not configured. Please set OPENROUTER_API_KEY to enable AI analysis."
            }
        
        prompt = f"""You are an expert systematic review assistant. Analyze this research article for inclusion in a systematic review.

PROJECT CRITERIA:
Inclusion: {inclusion_criteria}
Exclusion: {exclusion_criteria}

ARTICLE:
Title: {title}
Abstract: {abstract if abstract else "No abstract available"}

Provide your analysis in the following JSON format exactly:
{{
    "summary": [
        "Bullet point 1: Study objective/design",
        "Bullet point 2: Population/sample",
        "Bullet point 3: Key methods",
        "Bullet point 4: Main findings"
    ],
    "recommendation": "include" or "exclude" or "unsure",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of why this recommendation was made based on the criteria"
}}

Be strict about the inclusion/exclusion criteria. Only recommend inclusion if the study clearly meets all inclusion criteria and has no exclusion criteria."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Systematic Review Agent"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant for systematic literature reviews. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                }
                
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                if resp.status_code != 200:
                    return {
                        "summary": ["Analysis failed - API error"],
                        "recommendation": "unsure",
                        "confidence": 0.0,
                        "reasoning": f"API returned status {resp.status_code}"
                    }
                
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Parse JSON from response
                import json
                # Try to extract JSON from the response
                start_idx = content.find("{")
                end_idx = content.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    result = json.loads(json_str)
                    return result
                
                return {
                    "summary": ["Could not parse AI response"],
                    "recommendation": "unsure",
                    "confidence": 0.0,
                    "reasoning": content[:200]
                }
                
        except Exception as e:
            return {
                "summary": [f"Analysis error: {str(e)}"],
                "recommendation": "unsure",
                "confidence": 0.0,
                "reasoning": str(e)
            }
    
    async def generate_prisima_summary(self, project_title: str, articles: List[Dict]) -> str:
        """Generate PRISMA flow summary text"""
        
        counts = {
            "identified": 0,
            "screening": 0,
            "eligibility": 0,
            "included": 0,
            "excluded": 0
        }
        
        countries = set()
        years = []
        sample_sizes = []
        
        for art in articles:
            stage = art.get("stage", "identified")
            if stage in counts:
                counts[stage] += 1
            
            # Extract metadata if available
            meta = art.get("metadata_json", {})
            if meta:
                if isinstance(meta, str):
                    import json
                    try:
                        meta = json.loads(meta)
                    except:
                        meta = {}
                
                # Try to extract country/year info from notes or metadata
                if art.get("published_year"):
                    years.append(art["published_year"])
        
        included_articles = [a for a in articles if a.get("stage") == "included"]
        
        if not self.api_key or len(included_articles) == 0:
            # Generate basic template
            year_range = f"{min(years) if years else 'XXXX'}–{max(years) if years else 'XXXX'}"
            return f"""Results: The search yielded {counts['identified']} records after duplicate removal. After title/abstract screening, {counts['eligibility']} full texts were assessed for eligibility. {counts['included']} studies met inclusion criteria (PRISMA flow diagram: Figure 1). Included studies spanned [X] countries across [X] regions, with publication years [{year_range}]. Sample sizes ranged from [X] to [X] (median [X]). Most studies used DHS or national survey data (n = [X]); others used cohort, census, or longitudinal panel data. Risk of bias was low in [X] studies, moderate in [X], and high in [X]."""
        
        # Use AI to generate summary
        prompt = f"""Generate a PRISMA results section paragraph for a systematic review titled "{project_title}".

STATISTICS:
- Records identified: {counts['identified']}
- Full texts assessed: {counts['eligibility']}
- Studies included: {counts['included']}
- Studies excluded: {counts['excluded']}

INCLUDED STUDIES:
{chr(10).join([f"- {a['title']} ({a.get('published_year', 'N/A')})" for a in included_articles[:10]])}

Write a concise results paragraph following this template:
"Results: The search yielded [X] records after duplicate removal. After title/abstract screening, [X] full texts were assessed for eligibility. [X] studies met inclusion criteria (PRISMA flow diagram: Figure 1). Included studies spanned [X] countries across [X] regions, with publication years [XXXX–XXXX]. Sample sizes ranged from [X] to [X] (median [X]). Most studies used [data types]; others used [other types]. Risk of bias was low in [X] studies, moderate in [X], and high in [X]."

Fill in the actual numbers where possible. For unknown values (countries, sample sizes), keep the bracketed placeholders."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Systematic Review Agent"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant for writing systematic review results sections."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 800
                }
                
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                
                return f"Results generation failed with status {resp.status_code}"
                
        except Exception as e:
            return f"Results generation error: {str(e)}"
    
    async def ask_clarification_questions(self, title: str, description: str) -> List[str]:
        """Generate clarification questions for the researcher"""
        
        if not self.api_key:
            return [
                "What specific population are you studying?",
                "What interventions or exposures are you interested in?",
                "What comparator groups should be considered?",
                "What outcomes are you measuring?",
                "What study designs will you include (RCT, observational, etc.)?",
                "Are there any language restrictions?",
                "What is the time period for included studies?",
                "Are there any geographic restrictions?"
            ]
        
        prompt = f"""A researcher is starting a systematic review with:
Title: {title}
Description: {description}

Generate 8 specific clarification questions to help define the inclusion/exclusion criteria more precisely. Focus on PICO elements (Population, Intervention, Comparator, Outcome) and study design constraints.

Respond with a JSON array of strings, like:
["Question 1?", "Question 2?", ...]"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Systematic Review Agent"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON arrays."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
                
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    import json
                    start_idx = content.find("[")
                    end_idx = content.rfind("]") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = content[start_idx:end_idx]
                        return json.loads(json_str)
                
                return ["Could not generate questions. Please define your criteria manually."]
                
        except Exception as e:
            return [f"Error generating questions: {str(e)}"]
