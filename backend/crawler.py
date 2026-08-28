import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
import xml.etree.ElementTree as ET

class AcademicCrawler:
    def __init__(self):
        self.base_urls = {
            "pubmed": "https://pubmed.ncbi.nlm.nih.gov",
            "crossref": "https://api.crossref.org/works",
            "arxiv": "http://export.arxiv.org/api/query"
        }
    
    async def search_pubmed(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search PubMed API"""
        articles = []
        try:
            # Search for IDs
            search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(search_url, params=params)
                if resp.status_code != 200:
                    return articles
                
                data = resp.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                
                if not ids:
                    return articles
                
                # Fetch details
                fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "json"
                }
                resp = await client.get(fetch_url, params=fetch_params)
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get("result", {})
                    
                    for pmid in ids:
                        if pmid in result:
                            item = result[pmid]
                            # Handle authors - they might be dicts or strings
                            authors_data = item.get("authors", [])
                            if authors_data and isinstance(authors_data[0], dict):
                                author_names = [a.get("name", a.get("fullname", "")) for a in authors_data if isinstance(a, dict)]
                            else:
                                author_names = authors_data
                            
                            articles.append({
                                "title": item.get("title", ""),
                                "authors": ", ".join(author_names) if author_names else "",
                                "abstract": "",  # Need separate call for abstract
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                "source": "pubmed",
                                "pmid": str(pmid),
                                "doi": "",
                                "published_year": int(str(item.get("pubdate", "0"))[:4]) if item.get("pubdate") else None,
                                "journal": item.get("fulljournalname", ""),
                                "metadata": item
                            })
        except Exception as e:
            print(f"PubMed search error: {e}")
        
        return articles
    
    async def search_crossref(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search CrossRef API"""
        articles = []
        try:
            url = self.base_urls["crossref"]
            params = {
                "query": query,
                "rows": max_results,
                "select": "title,author,DOI,published,container-title,abstract,URL"
            }
            headers = {"User-Agent": "ReviewSystem/1.0"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    return articles
                
                data = resp.json()
                items = data.get("message", {}).get("items", [])
                
                for item in items:
                    authors = item.get("author", [])
                    author_names = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors]
                    
                    published = item.get("published", {})
                    year = None
                    if "date-parts" in published and published["date-parts"]:
                        year = published["date-parts"][0][0]
                    
                    articles.append({
                        "title": " ".join(item.get("title", [])),
                        "authors": ", ".join(author_names),
                        "abstract": item.get("abstract", ""),
                        "url": item.get("URL", ""),
                        "source": "crossref",
                        "doi": item.get("DOI", ""),
                        "pmid": "",
                        "published_year": year,
                        "journal": " ".join(item.get("container-title", [])),
                        "metadata": item
                    })
        except Exception as e:
            print(f"CrossRef search error: {e}")
        
        return articles
    
    async def search_arxiv(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search arXiv API"""
        articles = []
        try:
            url = self.base_urls["arxiv"]
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return articles
                
                # Parse XML
                root = ET.fromstring(resp.content)
                ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
                
                for entry in root.findall("atom:entry", ns):
                    title_elem = entry.find("atom:title", ns)
                    summary_elem = entry.find("atom:summary", ns)
                    published_elem = entry.find("atom:published", ns)
                    id_elem = entry.find("atom:id", ns)
                    
                    authors = []
                    for author in entry.findall("atom:author", ns):
                        name_elem = author.find("atom:name", ns)
                        if name_elem is not None:
                            authors.append(name_elem.text)
                    
                    year = None
                    if published_elem is not None and published_elem.text:
                        year = int(published_elem.text[:4])
                    
                    articles.append({
                        "title": title_elem.text.strip() if title_elem is not None else "",
                        "authors": ", ".join(authors),
                        "abstract": summary_elem.text.strip() if summary_elem is not None else "",
                        "url": id_elem.text if id_elem is not None else "",
                        "source": "arxiv",
                        "doi": "",
                        "pmid": "",
                        "published_year": year,
                        "journal": "arXiv",
                        "metadata": {}
                    })
        except Exception as e:
            print(f"arXiv search error: {e}")
        
        return articles
    
    async def crawl(self, query: str, sources: List[str] = ["pubmed", "crossref", "arxiv"], max_per_source: int = 50) -> List[Dict]:
        """Crawl multiple sources and deduplicate"""
        all_articles = []
        
        tasks = []
        if "pubmed" in sources:
            tasks.append(self.search_pubmed(query, max_per_source))
        if "crossref" in sources:
            tasks.append(self.search_crossref(query, max_per_source))
        if "arxiv" in sources:
            tasks.append(self.search_arxiv(query, max_per_source))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        seen_dois = set()
        seen_titles = set()
        
        for result in results:
            if isinstance(result, Exception):
                continue
            for article in result:
                # Deduplicate by DOI or title
                doi = article.get("doi", "").lower()
                title = re.sub(r'[^a-z0-9]', '', article.get("title", "").lower())
                
                if doi and doi in seen_dois:
                    continue
                if title and title in seen_titles:
                    continue
                
                if doi:
                    seen_dois.add(doi)
                if title:
                    seen_titles.add(title)
                
                all_articles.append(article)
        
        return all_articles

# Import asyncio for the gather call
import asyncio
