"""
AI Review Agent using OmniRoute/OpenRouter Free Models
Provides article summaries, recommendations, and confidence scores for systematic reviews
"""
import os
from typing import Dict, Optional, List
from openai import OpenAI
import json


class ReviewAgent:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://openrouter.ai/api/v1"):
        """
        Initialize the review agent with OpenRouter API.
        Uses free models by default.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = base_url
        
        # Default to a free model - google/gemma-2-9b-it:free is reliable
        self.model = "google/gemma-2-9b-it:free"
        
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self.client = None
    
    def _get_system_prompt(self, inclusion_criteria: str, exclusion_criteria: str) -> str:
        """Generate system prompt based on review criteria"""
        return f"""You are an expert systematic literature review assistant helping a researcher screen academic articles.

Your role is to:
1. Analyze article titles and abstracts (and full text if available)
2. Provide concise bullet-point summaries
3. Recommend whether to include or exclude based on the criteria below
4. Assign a confidence score (0.0 to 1.0) to your recommendation

INCLUSION CRITERIA:
{inclusion_criteria}

EXCLUSION CRITERIA:
{exclusion_criteria}

Respond in JSON format with these exact keys:
- "summary": List of 3-5 bullet points summarizing key aspects (population, methods, outcomes, setting)
- "recommendation": One of "include", "exclude_title_abstract", "exclude_full_text", "needs_review"
- "confidence": Float between 0.0 and 1.0 indicating your confidence
- "reasoning": Brief explanation of why you made this recommendation
- "relevant_criteria": Which specific inclusion/exclusion criteria this article meets or violates

Be conservative - when in doubt, recommend "needs_review" for human judgment."""

    def analyze_article(self, title: str, abstract: str, full_text: Optional[str] = None,
                       inclusion_criteria: str = "", exclusion_criteria: str = "") -> Dict:
        """
        Analyze an article and provide summary + recommendation.
        
        Returns dict with: summary, recommendation, confidence, reasoning, relevant_criteria
        """
        if not self.client:
            return self._mock_analysis(title, abstract)
        
        content = f"TITLE: {title}\n\n"
        
        if abstract:
            content += f"ABSTRACT:\n{abstract}\n\n"
        
        if full_text and len(full_text) > 100:
            # Truncate very long full texts
            truncated = full_text[:8000] + "\n...[truncated]" if len(full_text) > 8000 else full_text
            content += f"FULL TEXT:\n{truncated}\n\n"
        
        content += "Please analyze this article according to the systematic review criteria provided in the system prompt."
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(inclusion_criteria, exclusion_criteria)},
                    {"role": "user", "content": content}
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                # Look for JSON block in response
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = result_text[json_start:json_end]
                    result = json.loads(json_str)
                    
                    # Ensure all required fields exist
                    required_fields = ['summary', 'recommendation', 'confidence', 'reasoning']
                    for field in required_fields:
                        if field not in result:
                            if field == 'summary':
                                result[field] = [f"No summary available"]
                            elif field == 'recommendation':
                                result[field] = 'needs_review'
                            elif field == 'confidence':
                                result[field] = 0.5
                            elif field == 'reasoning':
                                result[field] = "Analysis completed"
                    
                    return result
                else:
                    raise ValueError("No JSON found")
                    
            except json.JSONDecodeError:
                # Fallback: create structured response from text
                return {
                    'summary': [result_text[:500]],
                    'recommendation': 'needs_review',
                    'confidence': 0.5,
                    'reasoning': result_text[:300],
                    'relevant_criteria': []
                }
                
        except Exception as e:
            print(f"AI analysis error: {e}")
            return self._mock_analysis(title, abstract)
    
    def _mock_analysis(self, title: str, abstract: str) -> Dict:
        """Return mock analysis when API is not available"""
        return {
            'summary': [
                f"Title: {title[:100]}",
                f"Abstract available: {'Yes' if abstract else 'No'}",
                "AI analysis unavailable - API key not configured",
                "Please review manually"
            ],
            'recommendation': 'needs_review',
            'confidence': 0.0,
            'reasoning': "AI judge unavailable. Configure OPENROUTER_API_KEY environment variable for automated analysis.",
            'relevant_criteria': []
        }
    
    def generate_clarification_questions(self, title: str, description: str) -> List[str]:
        """
        Generate clarification questions to help refine the review scope.
        These questions help the researcher think through their inclusion/exclusion criteria.
        """
        if not self.client:
            return self._default_clarification_questions()
        
        prompt = f"""A researcher is starting a systematic literature review with:

TITLE: {title}
DESCRIPTION: {description}

Generate 8 specific clarification questions that will help define clear inclusion and exclusion criteria. Focus on:
- Population characteristics (age, demographics, conditions)
- Study designs (RCT, observational, qualitative, etc.)
- Time periods and publication dates
- Geographic regions or settings
- Language restrictions
- Specific interventions or exposures
- Outcome measures
- Sample size requirements

Format as a numbered list of questions only."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            questions_text = response.choices[0].message.content.strip()
            
            # Parse into list
            questions = []
            for line in questions_text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Remove numbering
                    cleaned = line.lstrip('0123456789.- ')
                    if cleaned:
                        questions.append(cleaned)
            
            return questions if questions else self._default_clarification_questions()
            
        except Exception as e:
            print(f"Question generation error: {e}")
            return self._default_clarification_questions()
    
    def _default_clarification_questions(self) -> List[str]:
        """Default clarification questions"""
        return [
            "What specific population are you studying? (age range, demographics, health conditions)",
            "Which study designs will you include? (RCTs, observational, qualitative, mixed methods)",
            "Are there any date restrictions for publications?",
            "What geographic regions or settings are relevant?",
            "Will you include studies in languages other than English?",
            "What specific interventions, exposures, or phenomena are you examining?",
            "What outcome measures must studies report?",
            "Are there minimum sample size requirements?"
        ]
    
    def generate_prisma_summary(self, included_articles: List[Dict]) -> str:
        """
        Generate a draft results section text based on included articles.
        """
        if not included_articles:
            return "No articles included yet."
        
        if not self.client:
            return self._mock_prisma_summary(included_articles)
        
        # Prepare article data for the prompt
        articles_info = []
        for i, article in enumerate(included_articles[:20]):  # Limit to first 20 for context
            info = f"{i+1}. {article.get('title', 'Unknown')} ({article.get('year', 'N/A')})"
            if article.get('authors'):
                info += f" - {article['authors'][:50]}"
            articles_info.append(info)
        
        prompt = f"""Based on these {len(included_articles)} included studies in a systematic review, generate a draft Results section paragraph following PRISMA guidelines.

INCLUDED STUDIES:
{chr(10).join(articles_info)}

Create a paragraph with this structure:
"The search yielded [X] records after duplicate removal. After title/abstract screening, [X] full texts were assessed for eligibility. [X] studies met inclusion criteria (PRISMA flow diagram: Figure 1). Included studies spanned [X] countries across [X] regions, with publication years [XXXX–XXXX]. Sample sizes ranged from [X] to [X] (median [X]). Most studies used DHS or national survey data (n = [X]); others used cohort, census, or longitudinal panel data. Risk of bias was low in [X] studies, moderate in [X], and high in [X]."

Fill in bracketed values with realistic estimates based on the article information. If specific data is not available, use placeholders like [X] but provide reasonable estimates where possible."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"PRISMA summary error: {e}")
            return self._mock_prisma_summary(included_articles)
    
    def _mock_prisma_summary(self, included_articles: List[Dict]) -> str:
        """Mock PRISMA summary when API unavailable"""
        count = len(included_articles)
        years = [a.get('year') for a in included_articles if a.get('year')]
        year_range = f"{min(years)}-{max(years)}" if years else "[XXXX-XXXX]"
        
        return f"""Results: The search yielded [{count}] records after duplicate removal. After title/abstract screening, [{count}] full texts were assessed for eligibility. [{count}] studies met inclusion criteria (PRISMA flow diagram: Figure 1). Included studies spanned [X] countries across [X] regions, with publication years [{year_range}]. Sample sizes ranged from [X] to [X] (median [X]). Most studies used DHS or national survey data (n = [X]); others used cohort, census, or longitudinal panel data. Risk of bias was low in [X] studies, moderate in [X], and high in [X]."""
    
    def batch_analyze(self, articles: List[Dict], inclusion_criteria: str, 
                     exclusion_criteria: str, batch_size: int = 5) -> List[Dict]:
        """
        Analyze multiple articles in batches.
        Returns list of analysis results.
        """
        results = []
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            
            for article in batch:
                analysis = self.analyze_article(
                    title=article.get('title', ''),
                    abstract=article.get('abstract', ''),
                    full_text=article.get('full_text'),
                    inclusion_criteria=inclusion_criteria,
                    exclusion_criteria=exclusion_criteria
                )
                
                results.append({
                    'article_id': article.get('id'),
                    'analysis': analysis
                })
            
            # Small delay between batches to avoid rate limits
            if i + batch_size < len(articles):
                import time
                time.sleep(1)
        
        return results
