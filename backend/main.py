from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
import json

from config import settings
from database import get_db_session, Project, Article, ReviewLog, CrawlQueue
from crawler import AcademicCrawler
from agent import ReviewAgent

app = FastAPI(title="Systematic Review Agent API")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

crawler = AcademicCrawler()
agent = ReviewAgent()

# Dependency
async def get_db():
    async for session in get_db_session():
        yield session

# ==================== PROJECT ENDPOINTS ====================

@app.post("/projects")
async def create_project(project_data: dict, db: AsyncSession = Depends(get_db)):
    """Create a new review project"""
    project = Project(
        title=project_data["title"],
        description=project_data.get("description", ""),
        inclusion_criteria=project_data.get("inclusion_criteria", ""),
        exclusion_criteria=project_data.get("exclusion_criteria", "")
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    # Generate clarification questions
    questions = await agent.ask_clarification_questions(project.title, project.description or "")
    
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "inclusion_criteria": project.inclusion_criteria,
        "exclusion_criteria": project.exclusion_criteria,
        "clarification_questions": questions,
        "created_at": project.created_at.isoformat()
    }

@app.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects"""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "created_at": p.created_at.isoformat(),
            "article_count": len(p.articles)
        }
        for p in projects
    ]

@app.get("/projects/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get project details with article counts by stage"""
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.articles))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    stage_counts = {}
    for article in project.articles:
        stage = article.stage
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "inclusion_criteria": project.inclusion_criteria,
        "exclusion_criteria": project.exclusion_criteria,
        "stage_counts": stage_counts,
        "total_articles": len(project.articles),
        "created_at": project.created_at.isoformat()
    }

@app.put("/projects/{project_id}")
async def update_project(project_id: int, project_data: dict, db: AsyncSession = Depends(get_db)):
    """Update project criteria"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.title = project_data.get("title", project.title)
    project.description = project_data.get("description", project.description)
    project.inclusion_criteria = project_data.get("inclusion_criteria", project.inclusion_criteria)
    project.exclusion_criteria = project_data.get("exclusion_criteria", project.exclusion_criteria)
    
    await db.commit()
    await db.refresh(project)
    
    return {"id": project.id, "message": "Project updated"}

# ==================== ARTICLE ENDPOINTS ====================

@app.get("/projects/{project_id}/articles")
async def list_articles(
    project_id: int,
    stage: Optional[str] = None,
    decision: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List articles for a project with optional filters"""
    query = select(Article).where(Article.project_id == project_id)
    
    if stage:
        query = query.where(Article.stage == stage)
    if decision:
        query = query.where(Article.user_decision == decision)
    
    query = query.order_by(Article.created_at.desc())
    result = await db.execute(query)
    articles = result.scalars().all()
    
    return [
        {
            "id": a.id,
            "title": a.title,
            "authors": a.authors,
            "abstract": a.abstract,
            "url": a.url,
            "source": a.source,
            "doi": a.doi,
            "pmid": a.pmid,
            "published_year": a.published_year,
            "journal": a.journal,
            "stage": a.stage,
            "ai_summary": json.loads(a.ai_summary) if a.ai_summary else None,
            "ai_recommendation": a.ai_recommendation,
            "ai_confidence": a.ai_confidence,
            "user_decision": a.user_decision,
            "user_notes": a.user_notes,
            "created_at": a.created_at.isoformat()
        }
        for a in articles
    ]

@app.post("/projects/{project_id}/articles/crawl")
async def crawl_articles(
    project_id: int,
    crawl_data: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start crawling for articles"""
    query = crawl_data.get("query", "")
    sources = crawl_data.get("sources", ["pubmed", "crossref", "arxiv"])
    max_per_source = crawl_data.get("max_per_source", 50)
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    # Create crawl queue entry
    crawl_job = CrawlQueue(
        project_id=project_id,
        query=query,
        source=",".join(sources),
        status="processing"
    )
    db.add(crawl_job)
    await db.commit()
    await db.refresh(crawl_job)
    
    # Run crawl in background
    async def run_crawl():
        try:
            articles = await crawler.crawl(query, sources, max_per_source)
            
            # Add articles to database
            for art_data in articles:
                # Check for duplicates
                existing = await db.execute(
                    select(Article).where(
                        Article.project_id == project_id,
                        ((Article.doi == art_data.get("doi", "")) & (Article.doi != "")) |
                        (Article.title == art_data.get("title", ""))
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                
                article = Article(
                    project_id=project_id,
                    title=art_data.get("title", ""),
                    authors=art_data.get("authors", ""),
                    abstract=art_data.get("abstract", ""),
                    url=art_data.get("url", ""),
                    source=art_data.get("source", "unknown"),
                    doi=art_data.get("doi", ""),
                    pmid=art_data.get("pmid", ""),
                    published_year=art_data.get("published_year"),
                    journal=art_data.get("journal", ""),
                    metadata_json=art_data.get("metadata", {}),
                    stage="identified"
                )
                db.add(article)
            
            crawl_job.status = "completed"
            crawl_job.results_count = len(articles)
            await db.commit()
            
        except Exception as e:
            crawl_job.status = "failed"
            await db.commit()
            print(f"Crawl error: {e}")
    
    background_tasks.add_task(run_crawl)
    
    return {
        "crawl_id": crawl_job.id,
        "status": "started",
        "query": query,
        "sources": sources
    }

@app.post("/projects/{project_id}/articles/batch-analyze")
async def batch_analyze_articles(
    project_id: int,
    analyze_data: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Analyze multiple articles with AI"""
    article_ids = analyze_data.get("article_ids", [])
    
    # Get project criteria
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    async def run_analysis():
        for article_id in article_ids:
            try:
                art_result = await db.execute(
                    select(Article).where(Article.id == article_id)
                )
                article = art_result.scalar_one_or_none()
                if not article:
                    continue
                
                # Analyze with AI
                analysis = await agent.analyze_article(
                    article.title,
                    article.abstract,
                    project.inclusion_criteria or "",
                    project.exclusion_criteria or ""
                )
                
                # Update article
                article.ai_summary = json.dumps(analysis.get("summary", []))
                article.ai_recommendation = analysis.get("recommendation", "unsure")
                article.ai_confidence = analysis.get("confidence", 0.0)
                article.stage = "screening"
                
                # Log the action
                log = ReviewLog(
                    project_id=project_id,
                    article_id=article_id,
                    action="ai_review",
                    details=analysis
                )
                db.add(log)
                
            except Exception as e:
                print(f"Analysis error for article {article_id}: {e}")
        
        await db.commit()
    
    background_tasks.add_task(run_analysis)
    
    return {"status": "started", "article_count": len(article_ids)}

@app.put("/articles/{article_id}/decision")
async def update_article_decision(
    article_id: int,
    decision_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Update user decision on an article"""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    old_decision = article.user_decision
    new_decision = decision_data.get("decision")  # include, exclude
    user_notes = decision_data.get("notes", "")
    
    # Update stage based on decision
    if new_decision == "include":
        article.stage = "included"
    elif new_decision == "exclude":
        if article.stage == "identified":
            article.stage = "excluded"
        elif article.stage == "screening":
            article.stage = "eligibility"
            # Could add another decision point here for full text
        else:
            article.stage = "excluded"
    
    article.user_decision = new_decision
    article.user_notes = user_notes
    article.updated_at = datetime.utcnow()
    
    # Log the action
    action = "user_override" if old_decision and old_decision != new_decision else \
             "user_accept" if new_decision == article.ai_recommendation else "user_reject"
    
    log = ReviewLog(
        project_id=article.project_id,
        article_id=article_id,
        action=action,
        details={"old_decision": old_decision, "new_decision": new_decision, "notes": user_notes}
    )
    db.add(log)
    
    await db.commit()
    
    return {"id": article_id, "decision": new_decision, "stage": article.stage}

@app.get("/articles/{article_id}")
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Get single article details"""
    result = await db.execute(
        select(Article).where(Article.id == article_id).options(selectinload(Article.review_logs))
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {
        "id": article.id,
        "title": article.title,
        "authors": article.authors,
        "abstract": article.abstract,
        "url": article.url,
        "source": article.source,
        "doi": article.doi,
        "pmid": article.pmid,
        "published_year": article.published_year,
        "journal": article.journal,
        "stage": article.stage,
        "ai_summary": json.loads(article.ai_summary) if article.ai_summary else None,
        "ai_recommendation": article.ai_recommendation,
        "ai_confidence": article.ai_confidence,
        "user_decision": article.user_decision,
        "user_notes": article.user_notes,
        "review_history": [
            {
                "action": log.action,
                "details": log.details,
                "timestamp": log.timestamp.isoformat()
            }
            for log in article.review_logs
        ],
        "created_at": article.created_at.isoformat()
    }

# ==================== EXPORT ENDPOINTS ====================

@app.get("/projects/{project_id}/export/articles-log")
async def export_articles_log(project_id: int, db: AsyncSession = Depends(get_db)):
    """Export articles log with names and links"""
    result = await db.execute(
        select(Article).where(Article.project_id == project_id).order_by(Article.created_at)
    )
    articles = result.scalars().all()
    
    lines = ["SYSTEMATIC REVIEW - ARTICLES LOG", "=" * 50, ""]
    lines.append(f"Project ID: {project_id}")
    lines.append(f"Export Date: {datetime.utcnow().isoformat()}")
    lines.append("")
    
    for stage in ["identified", "screening", "eligibility", "included", "excluded"]:
        stage_articles = [a for a in articles if a.stage == stage]
        if stage_articles:
            lines.append(f"\n### {stage.upper()} ({len(stage_articles)} articles)")
            lines.append("-" * 40)
            for a in stage_articles:
                lines.append(f"- Title: {a.title}")
                lines.append(f"  Authors: {a.authors or 'N/A'}")
                lines.append(f"  URL: {a.url or 'N/A'}")
                lines.append(f"  DOI: {a.doi or 'N/A'}")
                lines.append(f"  Source: {a.source}")
                lines.append(f"  Decision: {a.user_decision or 'Pending'}")
                if a.user_notes:
                    lines.append(f"  Notes: {a.user_notes}")
                lines.append("")
    
    return {"content": "\n".join(lines), "format": "text"}

@app.get("/projects/{project_id}/export/prisima-summary")
async def export_prisima_summary(project_id: int, db: AsyncSession = Depends(get_db)):
    """Generate PRISMA summary"""
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.articles))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    articles_data = [
        {
            "title": a.title,
            "stage": a.stage,
            "published_year": a.published_year,
            "metadata_json": a.metadata_json
        }
        for a in project.articles
    ]
    
    summary = await agent.generate_prisima_summary(project.title, articles_data)
    
    return {"summary": summary, "project_title": project.title}

@app.get("/projects/{project_id}/stats")
async def get_project_stats(project_id: int, db: AsyncSession = Depends(get_db)):
    """Get PRISMA flow statistics"""
    result = await db.execute(
        select(Article).where(Article.project_id == project_id)
    )
    articles = result.scalars().all()
    
    stats = {
        "identified": len([a for a in articles if a.stage == "identified"]),
        "screening": len([a for a in articles if a.stage == "screening"]),
        "eligibility": len([a for a in articles if a.stage == "eligibility"]),
        "included": len([a for a in articles if a.stage == "included"]),
        "excluded": len([a for a in articles if a.stage == "excluded"]),
        "pending_review": len([a for a in articles if not a.user_decision])
    }
    stats["total"] = sum([stats["identified"], stats["screening"], stats["eligibility"], stats["included"], stats["excluded"]])
    
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
