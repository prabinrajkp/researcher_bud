"""
Academic Article Crawler for Systematic Literature Review
Supports PubMed, CrossRef, and arXiv APIs
"""
import requests
import re
from typing import List, Dict, Optional
from datetime import datetime
import time


class AcademicCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SystematicReviewBot/1.0 (academic research)'
        })
    
    def search_pubmed(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search PubMed using E-utilities API"""
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
            data = response.json()
            
            if 'esearchresult' not in data or 'idlist' not in data['esearchresult']:
                return articles
            
            ids = data['esearchresult']['idlist'][:max_results]
            
            if not ids:
                return articles
            
            # Step 2: Fetch details
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(ids),
                'retmode': 'json'
            }
            
            response = self.session.get(fetch_url, params=fetch_params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'result' not in data:
                return articles
            
            for pmid in ids:
                if pmid not in data['result']:
                    continue
                
                paper = data['result'][pmid]
                
                # Extract authors
                authors = []
                if 'authors' in paper:
                    for author in paper['authors'][:5]:  # Limit to first 5
                        if 'name' in author:
                            authors.append(author['name'])
                        elif 'lastname' in author:
                            name = author['lastname']
                            if 'firstname' in author:
                                name += f" {author['firstname']}"
                            authors.append(name)
                
                article = {
                    'title': paper.get('title', ''),
                    'abstract': '',  # Need separate fetch for abstract
                    'authors': '; '.join(authors),
                    'journal': paper.get('fulljournalname', ''),
                    'year': int(paper.get('pubdate', '0')[:4]) if paper.get('pubdate') else None,
                    'doi': paper.get('doi', ''),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    'source': 'PubMed',
                    'pmid': pmid,
                    'pdf_url': ''
                }
                
                # Fetch abstract separately
                if pmid:
                    abstract_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    abstract_params = {
                        'db': 'pubmed',
                        'id': pmid,
                        'retmode': 'json'
                    }
                    try:
                        abs_response = self.session.get(abstract_url, params=abstract_params, timeout=10)
                        if abs_response.ok:
                            abs_data = abs_response.json()
                            if 'result' in abs_data and pmid in abs_data['result']:
                                article['abstract'] = abs_data['result'][pmid].get('abstract', '')
                    except:
                        pass
                
                articles.append(article)
                time.sleep(0.1)  # Rate limiting
            
            return articles
            
        except Exception as e:
            print(f"PubMed search error: {e}")
            return articles
    
    def search_crossref(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search CrossRef API"""
        articles = []
        
        try:
            url = "https://api.crossref.org/works"
            params = {
                'query': query,
                'rows': max_results,
                'select': 'DOI,title,author,container-title,published,URL,is-referenced-by-count',
                'sort': 'relevance'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'message' not in data or 'items' not in data['message']:
                return articles
            
            for item in data['message']['items']:
                # Extract authors
                authors = []
                if 'author' in item:
                    for author in item['author'][:5]:
                        name_parts = []
                        if 'given' in author:
                            name_parts.append(author['given'])
                        if 'family' in author:
                            name_parts.append(author['family'])
                        if name_parts:
                            authors.append(' '.join(name_parts))
                
                # Extract year
                year = None
                if 'published' in item and 'date-parts' in item['published']:
                    date_parts = item['published']['date-parts']
                    if date_parts and len(date_parts[0]) > 0:
                        year = date_parts[0][0]
                
                article = {
                    'title': item.get('title', [''])[0],
                    'abstract': item.get('abstract', ''),
                    'authors': '; '.join(authors),
                    'journal': item.get('container-title', [''])[0] if item.get('container-title') else '',
                    'year': year,
                    'doi': item.get('DOI', ''),
                    'url': item.get('URL', ''),
                    'source': 'CrossRef',
                    'pdf_url': ''
                }
                
                articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"CrossRef search error: {e}")
            return articles
    
    def search_arxiv(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search arXiv API"""
        articles = []
        
        try:
            # Clean query for arXiv
            clean_query = re.sub(r'[^\w\s]', ' ', query)
            
            url = "http://export.arxiv.org/api/query"
            params = {
                'search_query': f'all:{clean_query}',
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
            
            # Namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            entries = root.findall('atom:entry', ns)
            
            for entry in entries:
                # Extract title
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.strip() if title_elem is not None else ''
                
                # Extract summary (abstract)
                summary_elem = entry.find('atom:summary', ns)
                abstract = summary_elem.text.strip() if summary_elem is not None else ''
                
                # Extract authors
                authors = []
                for author_elem in entry.findall('atom:author', ns):
                    name_elem = author_elem.find('atom:name', ns)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text.strip())
                
                # Extract published date
                published_elem = entry.find('atom:published', ns)
                year = None
                if published_elem is not None and published_elem.text:
                    try:
                        year = int(published_elem.text[:4])
                    except:
                        pass
                
                # Extract DOI if available
                doi_elem = entry.find('arxiv:doi', {'arxiv': 'http://arxiv.org/schemas/atom'})
                doi = doi_elem.text if doi_elem is not None else ''
                
                # Get PDF URL
                pdf_url = ''
                for link_elem in entry.findall('atom:link', ns):
                    if link_elem.get('type') == 'application/pdf':
                        pdf_url = link_elem.get('href', '')
                        break
                
                # Get arXiv ID and URL
                id_elem = entry.find('atom:id', ns)
                arxiv_url = id_elem.text if id_elem is not None else ''
                
                article = {
                    'title': title,
                    'abstract': abstract,
                    'authors': '; '.join(authors[:5]),
                    'journal': 'arXiv',
                    'year': year,
                    'doi': doi,
                    'url': arxiv_url,
                    'source': 'arXiv',
                    'pdf_url': pdf_url
                }
                
                articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"arXiv search error: {e}")
            return articles
    
    def search(self, query: str, sources: List[str] = ['PubMed', 'CrossRef', 'arXiv'], 
               max_results_per_source: int = 50) -> List[Dict]:
        """Search multiple sources and combine results"""
        all_articles = []
        
        if 'PubMed' in sources:
            pubmed_articles = self.search_pubmed(query, max_results_per_source)
            all_articles.extend(pubmed_articles)
            time.sleep(0.5)  # Rate limiting between sources
        
        if 'CrossRef' in sources:
            crossref_articles = self.search_crossref(query, max_results_per_source)
            all_articles.extend(crossref_articles)
            time.sleep(0.5)
        
        if 'arXiv' in sources:
            arxiv_articles = self.search_arxiv(query, max_results_per_source)
            all_articles.extend(arxiv_articles)
        
        # Remove duplicates based on DOI or title similarity
        unique_articles = self._deduplicate(all_articles)
        
        return unique_articles
    
    def _deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicate articles"""
        seen_dois = set()
        seen_titles = set()
        unique = []
        
        for article in articles:
            doi = article.get('doi', '').lower()
            title = article.get('title', '').lower().strip()
            
            # Skip if DOI already seen
            if doi and doi in seen_dois:
                continue
            
            # Skip if title is very similar (simple check)
            title_key = title[:50] if len(title) > 50 else title
            if title_key and title_key in seen_titles:
                continue
            
            if doi:
                seen_dois.add(doi)
            if title_key:
                seen_titles.add(title_key)
            
            unique.append(article)
        
        return unique
    
    def fetch_full_text(self, article: Dict) -> Optional[str]:
        """Attempt to fetch full text if available"""
        # This is a simplified version - full text fetching often requires subscriptions
        url = article.get('pdf_url') or article.get('url')
        
        if not url:
            return None
        
        try:
            response = self.session.get(url, timeout=30)
            if response.ok:
                # Check if it's PDF
                content_type = response.headers.get('Content-Type', '')
                if 'application/pdf' in content_type:
                    return "[PDF Document - Text extraction not implemented]"
                else:
                    # Try to extract text from HTML
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Remove scripts and styles
                    for script in soup(['script', 'style']):
                        script.decompose()
                    
                    text = soup.get_text(separator=' ', strip=True)
                    return text[:10000]  # Limit length
        except Exception as e:
            print(f"Full text fetch error: {e}")
        
        return None
