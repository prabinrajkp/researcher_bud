from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Float
from datetime import datetime
import json

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    inclusion_criteria = Column(Text)
    exclusion_criteria = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    articles = relationship("Article", back_populates="project", cascade="all, delete-orphan")
    review_logs = relationship("ReviewLog", back_populates="project")

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    authors = Column(Text)
    abstract = Column(Text)
    url = Column(String)
    source = Column(String)  # pubmed, crossref, arxiv, manual
    doi = Column(String)
    pmid = Column(String)
    published_year = Column(Integer)
    journal = Column(String)
    
    # Review status
    stage = Column(String, default="identified")  # identified, screening, eligibility, included, excluded
    ai_summary = Column(Text)
    ai_recommendation = Column(String)  # include, exclude, unsure
    ai_confidence = Column(Float)
    user_decision = Column(String)  # include, exclude, None
    user_notes = Column(Text)
    metadata_json = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project", back_populates="articles")
    review_logs = relationship("ReviewLog", back_populates="article")

class ReviewLog(Base):
    __tablename__ = "review_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    action = Column(String)  # ai_review, user_accept, user_reject, user_override
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="review_logs")
    article = relationship("Article", back_populates="review_logs")

class CrawlQueue(Base):
    __tablename__ = "crawl_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    query = Column(String, nullable=False)
    source = Column(String)  # pubmed, crossref, arxiv
    status = Column(String, default="pending")  # pending, processing, completed, failed
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

async def get_db_session():
    from config import settings
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
