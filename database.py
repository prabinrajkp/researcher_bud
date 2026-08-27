"""
Database Manager for Systematic Literature Review System
Uses SQLite for persistent storage of projects, articles, and review logs
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json


class DatabaseManager:
    def __init__(self, db_path: str = "review_system.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Projects table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    inclusion_criteria TEXT,
                    exclusion_criteria TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Articles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    authors TEXT,
                    journal TEXT,
                    year INTEGER,
                    doi TEXT,
                    url TEXT,
                    source TEXT,
                    pdf_url TEXT,
                    full_text TEXT,
                    stage TEXT DEFAULT 'identified',
                    ai_summary TEXT,
                    ai_recommendation TEXT,
                    ai_confidence REAL,
                    user_decision TEXT,
                    user_notes TEXT,
                    included_in_review BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            ''')
            
            # Crawl queue table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    crawled_at TIMESTAMP,
                    articles_found INTEGER DEFAULT 0,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            ''')
            
            # Review logs table (audit trail)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS review_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    previous_value TEXT,
                    new_value TEXT,
                    performed_by TEXT DEFAULT 'user',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (article_id) REFERENCES articles(id)
                )
            ''')
            
            # Cache table for temporary storage
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def create_project(self, title: str, description: str, 
                      inclusion_criteria: str = "", exclusion_criteria: str = "") -> int:
        """Create a new review project"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (title, description, inclusion_criteria, exclusion_criteria)
                VALUES (?, ?, ?, ?)
            ''', (title, description, inclusion_criteria, exclusion_criteria))
            conn.commit()
            return cursor.lastrowid
    
    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get project by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_projects(self) -> List[Dict]:
        """Get all projects"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def update_project(self, project_id: int, updates: Dict):
        """Update project fields"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            fields = []
            values = []
            for key, value in updates.items():
                if key != 'id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(project_id)
                
                query = f'''
                    UPDATE projects 
                    SET {', '.join(fields)}, updated_at = ?
                    WHERE id = ?
                '''
                cursor.execute(query, values)
                conn.commit()
    
    def add_article(self, project_id: int, article_data: Dict) -> int:
        """Add or update an article"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check for duplicate by DOI or URL
            if article_data.get('doi'):
                cursor.execute('''
                    SELECT id FROM articles 
                    WHERE project_id = ? AND doi = ?
                ''', (project_id, article_data['doi']))
                existing = cursor.fetchone()
                if existing:
                    return existing[0]
            
            if article_data.get('url'):
                cursor.execute('''
                    SELECT id FROM articles 
                    WHERE project_id = ? AND url = ?
                ''', (project_id, article_data['url']))
                existing = cursor.fetchone()
                if existing:
                    return existing[0]
            
            # Insert new article
            cursor.execute('''
                INSERT INTO articles 
                (project_id, title, abstract, authors, journal, year, doi, url, 
                 source, pdf_url, full_text, stage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_id,
                article_data.get('title', ''),
                article_data.get('abstract', ''),
                article_data.get('authors', ''),
                article_data.get('journal', ''),
                article_data.get('year'),
                article_data.get('doi', ''),
                article_data.get('url', ''),
                article_data.get('source', 'unknown'),
                article_data.get('pdf_url', ''),
                article_data.get('full_text', ''),
                'identified'
            ))
            conn.commit()
            return cursor.lastrowid
    
    def update_article(self, article_id: int, updates: Dict, performed_by: str = 'user'):
        """Update an article and log the change"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get current values for logging
            cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
            current = cursor.fetchone()
            
            # Build update query
            fields = []
            values = []
            for key, value in updates.items():
                if key != 'id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(article_id)
                
                query = f'''
                    UPDATE articles 
                    SET {', '.join(fields)}, updated_at = ?
                    WHERE id = ?
                '''
                cursor.execute(query, values)
                
                # Log changes
                for key, value in updates.items():
                    if key != 'updated_at':
                        old_val = current[key] if current else None
                        if old_val != value:
                            cursor.execute('''
                                INSERT INTO review_logs (article_id, action, previous_value, new_value, performed_by)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (article_id, f'update_{key}', str(old_val), str(value), performed_by))
                
                conn.commit()
    
    def get_articles(self, project_id: int, stage: Optional[str] = None, 
                    decision: Optional[str] = None) -> List[Dict]:
        """Get articles for a project with optional filters"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM articles WHERE project_id = ?'
            params = [project_id]
            
            if stage:
                query += ' AND stage = ?'
                params.append(stage)
            
            if decision:
                query += ' AND user_decision = ?'
                params.append(decision)
            
            query += ' ORDER BY created_at ASC'
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_article(self, article_id: int) -> Optional[Dict]:
        """Get single article by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_to_crawl_queue(self, project_id: int, query: str, source: str):
        """Add a search query to crawl queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO crawl_queue (project_id, query, source)
                VALUES (?, ?, ?)
            ''', (project_id, query, source))
            conn.commit()
    
    def get_crawl_queue(self, project_id: int, status: str = 'pending') -> List[Dict]:
        """Get pending crawl tasks"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM crawl_queue 
                WHERE project_id = ? AND status = ?
                ORDER BY id ASC
            ''', (project_id, status))
            return [dict(row) for row in cursor.fetchall()]
    
    def update_crawl_status(self, crawl_id: int, status: str, articles_found: int = 0):
        """Update crawl task status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE crawl_queue 
                SET status = ?, crawled_at = ?, articles_found = ?
                WHERE id = ?
            ''', (status, datetime.now(), articles_found, crawl_id))
            conn.commit()
    
    def log_action(self, article_id: int, action: str, previous: Any, 
                   new_value: Any, performed_by: str = 'user'):
        """Log an action for audit trail"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO review_logs (article_id, action, previous_value, new_value, performed_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (article_id, action, str(previous), str(new_value), performed_by))
            conn.commit()
    
    def save_to_cache(self, key: str, value: Any):
        """Save data to cache"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO cache (key, value, created_at)
                VALUES (?, ?, ?)
            ''', (key, json.dumps(value), datetime.now()))
            conn.commit()
    
    def get_from_cache(self, key: str) -> Optional[Any]:
        """Retrieve data from cache"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM cache WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def export_articles_log(self, project_id: int, output_path: str):
        """Export articles log to text file"""
        articles = self.get_articles(project_id)
        
        with open(output_path, 'w') as f:
            f.write(f"Articles Log - Project ID: {project_id}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            for article in articles:
                f.write(f"Title: {article['title']}\n")
                f.write(f"Authors: {article['authors']}\n")
                f.write(f"Journal: {article['journal']}\n")
                f.write(f"Year: {article['year']}\n")
                f.write(f"DOI: {article['doi']}\n")
                f.write(f"URL: {article['url']}\n")
                f.write(f"Source: {article['source']}\n")
                f.write(f"Stage: {article['stage']}\n")
                f.write(f"User Decision: {article['user_decision']}\n")
                f.write(f"Included in Review: {article['included_in_review']}\n")
                if article['ai_summary']:
                    f.write(f"AI Summary: {article['ai_summary']}\n")
                if article['ai_recommendation']:
                    f.write(f"AI Recommendation: {article['ai_recommendation']}\n")
                f.write("-" * 80 + "\n")
    
    def get_prisma_stats(self, project_id: int) -> Dict:
        """Get PRISMA flow statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total identified
            cursor.execute('SELECT COUNT(*) FROM articles WHERE project_id = ?', (project_id,))
            stats['identified'] = cursor.fetchone()[0]
            
            # After duplicates removed (we don't track duplicates explicitly, so same as identified for now)
            stats['after_duplicates'] = stats['identified']
            
            # Screened (articles that have been reviewed)
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE project_id = ? AND user_decision IS NOT NULL
            ''', (project_id,))
            stats['screened'] = cursor.fetchone()[0]
            
            # Excluded at screening
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE project_id = ? AND user_decision = 'exclude_title_abstract'
            ''', (project_id,))
            stats['excluded_screening'] = cursor.fetchone()[0]
            
            # Full text assessed
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE project_id = ? AND stage = 'eligibility'
            ''', (project_id,))
            stats['full_text_assessed'] = cursor.fetchone()[0]
            
            # Excluded at eligibility
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE project_id = ? AND user_decision = 'exclude_full_text'
            ''', (project_id,))
            stats['excluded_eligibility'] = cursor.fetchone()[0]
            
            # Included studies
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE project_id = ? AND included_in_review = TRUE
            ''', (project_id,))
            stats['included'] = cursor.fetchone()[0]
            
            # By country/region (if available)
            # This would require more sophisticated extraction
            
            # Publication years
            cursor.execute('''
                SELECT MIN(year), MAX(year) FROM articles 
                WHERE project_id = ? AND year IS NOT NULL
            ''', (project_id,))
            years = cursor.fetchone()
            stats['year_range'] = f"{years[0]}-{years[1]}" if years[0] and years[1] else "N/A"
            
            # Sample sizes (would need extraction from full text)
            stats['sample_size_range'] = "N/A"
            
            # Data sources
            cursor.execute('''
                SELECT source, COUNT(*) FROM articles 
                WHERE project_id = ? AND included_in_review = TRUE
                GROUP BY source
            ''', (project_id,))
            stats['data_sources'] = dict(cursor.fetchall())
            
            # Risk of bias distribution
            # Would need explicit risk of bias field
            
            return stats
