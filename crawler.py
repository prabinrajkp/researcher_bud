"""
Academic Article Crawler for Systematic Literature Review
Scrapes articles from PubMed, Google Scholar, and other academic sources
"""

import requests
import re
import time
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import quote_plus, urlparse
import json


class AcademicCrawler:
    """
    Crawler for fetching academic articles from various sources.
    Uses free APIs and respectful scraping practices.
    """
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay  # Delay between requests (seconds)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.results_cache = {}
    
    def search_pubmed(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search PubMed using E-utilities API (free, no key required for basic use).
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            # Step 1: Search for IDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            response = self.session.get(search_url, params=search_params, timeout=30)
            response.raise_for_status()
            search_data = response.json()
            
            ids = search_data.get('esearchresult', {}).get('idlist', [])
            
            if not ids:
                return articles
            
            # Step 2: Fetch details for each ID
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            
            # Process in batches of 10
            for i in range(0, len(ids), 10):
                batch_ids = ids[i:i+10]
                
                params = {
                    'db': 'pubmed',
                    'id': ','.join(batch_ids),
                    'retmode': 'json'
                }
                
                response = self.session.get(fetch_url, params=params, timeout=30)
                response.raise_for_status()
                summary_data = response.json()
                
                result = summary_data.get('result', {})
                
                for pmid in batch_ids:
                    if pmid in result:
                        article = result[pmid]
                        articles.append({
                            'id': f"pubmed_{pmid}",
                            'title': article.get('title', ''),
                            'authors': ', '.join(article.get('authors', [])),
                            'journal': article.get('fulljournalname', ''),
                            'publication_year': article.get('pubdate', '')[:4] if article.get('pubdate') else None,
                            'doi': article.get('doi', ''),
                            'link': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            'abstract': article.get('abstract', ''),
                            'source': 'PubMed',
                            'pmid': pmid
                        })
                
                time.sleep(self.delay)
            
        except Exception as e:
            print(f"PubMed search error: {e}")
        
        return articles
    
    def search_doi_crossref(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search Crossref DOI database (free API).
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            url = "https://api.crossref.org/works"
            params = {
                'query': query,
                'rows': max_results,
                'select': 'DOI,title,author,container-title,published,abstract,URL,is-referenced-by-count'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            items = data.get('message', {}).get('items', [])
            
            for item in items:
                # Extract authors
                authors = []
                if 'author' in item:
                    for author in item['author']:
                        given = author.get('given', '')
                        family = author.get('family', '')
                        if given or family:
                            authors.append(f"{given} {family}".strip())
                
                # Extract year
                pub_year = None
                if 'published' in item and 'date-parts' in item['published']:
                    date_parts = item['published']['date-parts'][0]
                    if len(date_parts) > 0:
                        pub_year = date_parts[0]
                
                articles.append({
                    'id': f"crossref_{hashlib.md5(item.get('DOI', '').encode()).hexdigest()[:12]}",
                    'title': item.get('title', [''])[0],
                    'authors': ', '.join(authors),
                    'journal': item.get('container-title', [''])[0] if item.get('container-title') else '',
                    'publication_year': pub_year,
                    'doi': item.get('DOI', ''),
                    'link': item.get('URL', ''),
                    'abstract': item.get('abstract', ''),
                    'source': 'CrossRef',
                    'citation_count': item.get('is-referenced-by-count', 0)
                })
                
        except Exception as e:
            print(f"CrossRef search error: {e}")
        
        return articles
    
    def search_core_api(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search CORE API (free tier available, requires registration for higher limits).
        Falls back to mock data if no API key.
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            List of article dictionaries
        """
        api_key = ""  # User can set their own CORE API key
        
        articles = []
        
        if not api_key:
            # Return empty list - user needs to add their own API key
            print("CORE API key not set. Skipping CORE search.")
            return articles
        
        try:
            url = "https://api.core.ac.uk/v3/search/outputs"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'query': query,
                'limit': max_results
            }
            
            response = self.session.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = data.get('results', [])
            
            for item in results:
                articles.append({
                    'id': f"core_{item.get('id', hashlib.md5(str(time.time()).encode()).hexdigest()[:12])}",
                    'title': item.get('title', ''),
                    'authors': ', '.join(item.get('authors', [])),
                    'journal': item.get('publisher', ''),
                    'publication_year': item.get('yearPublished'),
                    'doi': item.get('doi', ''),
                    'link': item.get('sourceFulltextUrls', [item.get('browserUrl', '')])[0] if item.get('sourceFulltextUrls') else item.get('browserUrl', ''),
                    'abstract': item.get('abstractTexts', [''])[0] if item.get('abstractTexts') else '',
                    'source': 'CORE'
                })
                
        except Exception as e:
            print(f"CORE API search error: {e}")
        
        return articles
    
    def crawl_arxiv(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search arXiv preprint server (free API).
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            url = "http://export.arxiv.org/api/query"
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse XML response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            # Namespace for Atom feed
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}
            
            for entry in root.findall('atom:entry', ns):
                title_elem = entry.find('atom:title', ns)
                summary_elem = entry.find('atom:summary', ns)
                published_elem = entry.find('atom:published', ns)
                id_elem = entry.find('atom:id', ns)
                
                # Get authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                
                title = title_elem.text.strip() if title_elem is not None else ''
                summary = summary_elem.text.strip() if summary_elem is not None else ''
                published = published_elem.text[:10] if published_elem is not None else ''
                arxiv_id = id_elem.text if id_elem is not None else ''
                
                articles.append({
                    'id': f"arxiv_{hashlib.md5(arxiv_id.encode()).hexdigest()[:12]}",
                    'title': title,
                    'authors': ', '.join(authors),
                    'journal': 'arXiv',
                    'publication_year': published[:4] if published else None,
                    'doi': '',
                    'link': arxiv_id,
                    'abstract': summary,
                    'source': 'arXiv'
                })
                
                if len(articles) >= max_results:
                    break
                
        except Exception as e:
            print(f"arXiv search error: {e}")
        
        return articles
    
    def multi_source_search(self, query: str, sources: List[str] = None,
                           max_per_source: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search multiple sources simultaneously.
        
        Args:
            query: Search query
            sources: List of sources to search (default: all)
            max_per_source: Max results per source
            
        Returns:
            Dictionary with source names as keys and article lists as values
        """
        if sources is None:
            sources = ['pubmed', 'crossref', 'arxiv']
        
        results = {}
        
        if 'pubmed' in sources:
            print(f"Searching PubMed for: {query}")
            results['pubmed'] = self.search_pubmed(query, max_per_source)
            time.sleep(self.delay)
        
        if 'crossref' in sources:
            print(f"Searching CrossRef for: {query}")
            results['crossref'] = self.search_doi_crossref(query, max_per_source)
            time.sleep(self.delay)
        
        if 'arxiv' in sources:
            print(f"Searching arXiv for: {query}")
            results['arxiv'] = self.crawl_arxiv(query, max_per_source)
            time.sleep(self.delay)
        
        if 'core' in sources:
            print(f"Searching CORE for: {query}")
            results['core'] = self.search_core_api(query, max_per_source)
        
        return results
    
    def deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate articles based on title similarity and DOI.
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            Deduplicated list
        """
        seen_dois = set()
        seen_titles = set()
        unique = []
        
        for article in articles:
            doi = article.get('doi', '').lower()
            title = re.sub(r'[^\w\s]', '', article.get('title', '').lower()).strip()
            
            # Skip if DOI already seen
            if doi and doi in seen_dois:
                continue
            
            # Skip if title too similar to existing
            if title in seen_titles:
                continue
            
            seen_dois.add(doi)
            seen_titles.add(title)
            unique.append(article)
        
        return unique
    
    def save_to_file(self, articles: List[Dict[str, Any]], filepath: str,
                    format: str = 'json') -> bool:
        """
        Save articles to file.
        
        Args:
            articles: List of articles
            filepath: Output file path
            format: 'json' or 'csv'
            
        Returns:
            True if successful
        """
        try:
            if format == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(articles, f, indent=2, ensure_ascii=False)
            elif format == 'csv':
                import csv
                if articles:
                    keys = articles[0].keys()
                    with open(filepath, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=keys)
                        writer.writeheader()
                        writer.writerows(articles)
            
            print(f"Saved {len(articles)} articles to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving articles: {e}")
            return False
    
    def generate_search_queries(self, topic: str, keywords: List[str] = None) -> List[str]:
        """
        Generate optimized search queries for academic databases.
        
        Args:
            topic: Main research topic
            keywords: Additional keywords
            
        Returns:
            List of search queries
        """
        queries = []
        
        # Basic query
        queries.append(topic)
        
        # With Boolean operators
        if keywords:
            kw_string = ' OR '.join(keywords)
            queries.append(f"{topic} AND ({kw_string})")
            
            # Phrase searching
            queries.append(f'"{topic}"')
            
            # Field-specific (for PubMed)
            queries.append(f'{topic}[Title/Abstract]')
        
        return queries


# Example usage and testing
if __name__ == "__main__":
    crawler = AcademicCrawler(delay=1.0)
    
    # Test search
    test_query = "maternal health sub-saharan africa"
    
    print(f"\nTesting search for: {test_query}\n")
    
    # Multi-source search
    results = crawler.multi_source_search(test_query, max_per_source=5)
    
    for source, articles in results.items():
        print(f"\n{source.upper()}: Found {len(articles)} articles")
        for i, article in enumerate(articles[:3], 1):
            print(f"  {i}. {article.get('title', 'No title')[:80]}...")
    
    # Deduplication test
    all_articles = []
    for articles in results.values():
        all_articles.extend(articles)
    
    unique = crawler.deduplicate_articles(all_articles)
    print(f"\nTotal: {len(all_articles)}, Unique: {len(unique)}")
