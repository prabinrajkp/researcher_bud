"""
SQLite Database Manager for Systematic Literature Review System
Handles persistent storage of projects, articles, and review decisions
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json


class DatabaseManager:
    """Manages SQLite database for article reviews."""
    
    def __init__(self, db_path: str = "review_system.db"):
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                inclusion_criteria TEXT,
                exclusion_criteria TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT,
                abstract TEXT,
                stage TEXT DEFAULT 'screening',
                decision TEXT DEFAULT 'pending',
                ai_summary TEXT,
                ai_recommendation TEXT,
                ai_confidence REAL DEFAULT 0.0,
                researcher_notes TEXT,
                reviewer_decision TEXT,
                timestamp_added TEXT,
                timestamp_reviewed TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        # Article metadata table (for scraped data)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                source TEXT,
                authors TEXT,
                publication_year INTEGER,
                journal TEXT,
                doi TEXT,
                citation_count INTEGER DEFAULT 0,
                full_text_path TEXT,
                scraped_at TEXT,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
        """)
        
        # Crawl queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                query TEXT,
                source_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT,
                articles_found INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        # Review logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                action TEXT,
                old_value TEXT,
                new_value TEXT,
                timestamp TEXT,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def create_project(self, project_id: str, title: str, description: str,
                      inclusion_criteria: List[str], exclusion_criteria: List[str]) -> bool:
        """Create a new review project."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO projects 
                (id, title, description, inclusion_criteria, exclusion_criteria, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, title, description,
                json.dumps(inclusion_criteria),
                json.dumps(exclusion_criteria),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating project: {e}")
            return False
        finally:
            conn.close()
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_article(self, article_data: Dict[str, Any]) -> bool:
        """Add or update an article."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO articles 
                (id, project_id, title, link, abstract, stage, decision,
                 ai_summary, ai_recommendation, ai_confidence, researcher_notes,
                 reviewer_decision, timestamp_added, timestamp_reviewed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_data.get('id'),
                article_data.get('project_id'),
                article_data.get('title'),
                article_data.get('link'),
                article_data.get('abstract', ''),
                article_data.get('stage', 'screening'),
                article_data.get('decision', 'pending'),
                article_data.get('ai_summary', ''),
                article_data.get('ai_recommendation', ''),
                article_data.get('ai_confidence', 0.0),
                article_data.get('researcher_notes', ''),
                article_data.get('reviewer_decision', ''),
                article_data.get('timestamp_added', datetime.now().isoformat()),
                article_data.get('timestamp_reviewed')
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding article: {e}")
            return False
        finally:
            conn.close()
    
    def add_article_metadata(self, article_id: str, metadata: Dict[str, Any]) -> bool:
        """Add metadata for an article (from scraping)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO article_metadata 
                (article_id, source, authors, publication_year, journal, doi, 
                 citation_count, full_text_path, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id,
                metadata.get('source', ''),
                metadata.get('authors', ''),
                metadata.get('publication_year'),
                metadata.get('journal', ''),
                metadata.get('doi', ''),
                metadata.get('citation_count', 0),
                metadata.get('full_text_path'),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding metadata: {e}")
            return False
        finally:
            conn.close()
    
    def get_articles(self, project_id: str, stage: Optional[str] = None,
                    decision: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get articles for a project with optional filters."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM articles WHERE project_id = ?"
        params = [project_id]
        
        if stage:
            query += " AND stage = ?"
            params.append(stage)
        
        if decision:
            if decision == "pending":
                query += " AND (reviewer_decision IS NULL OR reviewer_decision = '')"
            else:
                query += " AND reviewer_decision = ?"
                params.append(decision)
        
        query += " ORDER BY timestamp_added DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get single article by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_article_decision(self, article_id: str, decision: str,
                               stage: str, notes: str = "") -> bool:
        """Update article review decision."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get old decision for logging
            cursor.execute("SELECT reviewer_decision, stage FROM articles WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            old_decision = row['reviewer_decision'] if row else ''
            old_stage = row['stage'] if row else ''
            
            cursor.execute("""
                UPDATE articles 
                SET reviewer_decision = ?, stage = ?, researcher_notes = ?,
                    timestamp_reviewed = ?
                WHERE id = ?
            """, (decision, stage, notes, datetime.now().isoformat(), article_id))
            
            # Log the change
            cursor.execute("""
                INSERT INTO review_logs (article_id, action, old_value, new_value, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (article_id, 'decision_update', 
                  f"{old_decision}/{old_stage}", f"{decision}/{stage}",
                  datetime.now().isoformat()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating decision: {e}")
            return False
        finally:
            conn.close()
    
    def add_crawl_job(self, project_id: str, query: str, source_url: str = "") -> int:
        """Add a crawl job to the queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO crawl_queue (project_id, query, source_url, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (project_id, query, source_url, datetime.now().isoformat()))
        
        crawl_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return crawl_id
    
    def get_crawl_jobs(self, project_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get crawl jobs for a project."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM crawl_queue WHERE project_id = ?"
        params = [project_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_crawl_job(self, crawl_id: int, status: str, articles_found: int = 0) -> bool:
        """Update crawl job status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crawl_queue 
            SET status = ?, articles_found = ?, completed_at = ?
            WHERE id = ?
        """, (status, articles_found, datetime.now().isoformat(), crawl_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_prisma_counts(self, project_id: str) -> Dict[str, int]:
        """Get PRISMA flow counts for a project."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        counts = {
            'identified': 0,
            'screening': 0,
            'eligibility': 0,
            'included': 0,
            'excluded_screening': 0,
            'excluded_eligibility': 0
        }
        
        # Total identified
        cursor.execute("SELECT COUNT(*) as count FROM articles WHERE project_id = ?", (project_id,))
        counts['identified'] = cursor.fetchone()['count']
        
        # By stage
        cursor.execute("""
            SELECT stage, COUNT(*) as count 
            FROM articles 
            WHERE project_id = ? 
            GROUP BY stage
        """, (project_id,))
        
        for row in cursor.fetchall():
            if row['stage'] == 'screening':
                counts['screening'] = row['count']
            elif row['stage'] == 'eligibility':
                counts['eligibility'] = row['count']
            elif row['stage'] == 'inclusion':
                counts['included'] = row['count']
        
        # Excluded counts
        cursor.execute("""
            SELECT stage, COUNT(*) as count 
            FROM articles 
            WHERE project_id = ? AND reviewer_decision = 'exclude'
            GROUP BY stage
        """, (project_id,))
        
        for row in cursor.fetchall():
            if row['stage'] == 'screening':
                counts['excluded_screening'] = row['count']
            elif row['stage'] == 'eligibility':
                counts['excluded_eligibility'] = row['count']
        
        conn.close()
        return counts
    
    def export_articles_log(self, project_id: str, output_path: str) -> bool:
        """Export articles log to text file."""
        try:
            articles = self.get_articles(project_id)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Systematic Literature Review - Articles Log\n")
                f.write(f"Project ID: {project_id}\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                
                for stage in ["screening", "eligibility", "inclusion"]:
                    stage_articles = [a for a in articles if a['stage'] == stage]
                    f.write(f"\n## {stage.upper()} STAGE ({len(stage_articles)} articles)\n")
                    f.write("-" * 40 + "\n")
                    for article in stage_articles:
                        status = "✓" if article.get('reviewer_decision') == 'include' else \
                                ("✗" if article.get('reviewer_decision') == 'exclude' else "○")
                        f.write(f"[{status}] {article['title']}\n")
                        f.write(f"    Link: {article.get('link', 'N/A')}\n")
                        f.write(f"    ID: {article['id']}\n")
                        if article.get('reviewer_decision'):
                            f.write(f"    Decision: {article['reviewer_decision']}\n")
                        f.write("\n")
            
            return True
        except Exception as e:
            print(f"Error exporting log: {e}")
            return False
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its articles."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete related records first
            cursor.execute("DELETE FROM review_logs WHERE article_id IN (SELECT id FROM articles WHERE project_id = ?)", (project_id,))
            cursor.execute("DELETE FROM article_metadata WHERE article_id IN (SELECT id FROM articles WHERE project_id = ?)", (project_id,))
            cursor.execute("DELETE FROM articles WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM crawl_queue WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting project: {e}")
            return False
        finally:
            conn.close()
