"""
Streamlit Frontend for Systematic Literature Review System
Human-AI collaborative interface for article screening and classification
Integrated with SQLite database and academic crawler
"""

import streamlit as st
from review_agent import (
    Article, CacheManager, OmniRouteLLM, ReviewAgent, 
    generate_article_id
)
from database import DatabaseManager
from crawler import AcademicCrawler
from datetime import datetime
import json
import hashlib


# Page configuration
st.set_page_config(
    page_title="Systematic Review Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .article-card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #4CAF50;
    }
    .ai-recommendation {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .stage-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        color: white;
    }
    .screening { background-color: #FF9800; }
    .eligibility { background-color: #2196F3; }
    .inclusion { background-color: #4CAF50; }
</style>
""", unsafe_allow_html=True)


def initialize_session():
    """Initialize session state variables."""
    if 'project_initialized' not in st.session_state:
        st.session_state.project_initialized = False
    if 'articles' not in st.session_state:
        st.session_state.articles = {}
    if 'cache_manager' not in st.session_state:
        st.session_state.cache_manager = None
    if 'agent' not in st.session_state:
        st.session_state.agent = None
    if 'db' not in st.session_state:
        st.session_state.db = DatabaseManager()
    if 'current_project_id' not in st.session_state:
        st.session_state.current_project_id = None
    if 'crawler' not in st.session_state:
        st.session_state.crawler = AcademicCrawler(delay=1.0)
    if 'current_review_idx' not in st.session_state:
        st.session_state.current_review_idx = 0
    if 'review_mode' not in st.session_state:
        st.session_state.review_mode = "single"  # single or batch


def main():
    initialize_session()
    
    # Sidebar navigation
    with st.sidebar:
        st.title("📚 Review Assistant")
        st.markdown("---")
        
        menu_options = ["New Project", "Add Articles", "Review Articles", "Saved Reviews", "PRISMA Summary"]
        choice = st.radio("Navigation", menu_options, index=0)
        
        st.markdown("---")
        st.info("""
        **How it works:**
        1. Start a new project with your review criteria
        2. Add articles (title, link, abstract)
        3. AI analyzes and recommends
        4. You make final decisions
        5. Save to permanent storage
        """)
        
        # Quick stats
        if st.session_state.articles:
            st.metric("Total Articles", len(st.session_state.articles))
            included = len([a for a in st.session_state.articles.values() if a.reviewer_decision == "include"])
            excluded = len([a for a in st.session_state.articles.values() if a.reviewer_decision == "exclude"])
            pending = len([a for a in st.session_state.articles.values() if not a.reviewer_decision])
            st.metric("Included", included)
            st.metric("Excluded", excluded)
            st.metric("Pending", pending)
    
    # Main content based on selection
    if choice == "New Project":
        show_new_project()
    elif choice == "Add Articles":
        show_add_articles()
    elif choice == "Review Articles":
        show_review_interface()
    elif choice == "Saved Reviews":
        show_saved_reviews()
    elif choice == "PRISMA Summary":
        show_prisma_summary()


def show_new_project():
    """Display new project creation form."""
    st.title("🔬 Start New Systematic Review")
    st.markdown("Define your review scope and criteria. The AI agent will use these to provide tailored recommendations.")
    
    with st.form("project_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("Review Title*", placeholder="e.g., Maternal Healthcare Access in Sub-Saharan Africa")
            description = st.text_area("Brief Description*", 
                                       placeholder="Describe the focus of your systematic review...",
                                       height=100)
        
        with col2:
            st.markdown("### Inclusion Criteria")
            inc_criteria = st.text_area("Include studies that...",
                                        placeholder="• Published between 2010-2024\n• Use DHS or national survey data\n• Focus on maternal health outcomes",
                                        height=100)
            
            st.markdown("### Exclusion Criteria")
            exc_criteria = st.text_area("Exclude studies that...",
                                        placeholder="• Review articles or editorials\n• Sample size < 100\n• No primary data",
                                        height=100)
        
        submitted = st.form_submit_button("Initialize Project", type="primary")
        
        if submitted:
            if not title or not description:
                st.error("Please fill in required fields (title and description)")
            else:
                # Parse criteria
                inclusion_list = [c.strip().lstrip('•-').strip() for c in inc_criteria.split('\n') if c.strip()]
                exclusion_list = [c.strip().lstrip('•-').strip() for c in exc_criteria.split('\n') if c.strip()]
                
                # Generate project ID
                project_id = hashlib.md5(f"{title}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]
                
                # Initialize components
                llm = OmniRouteLLM(model_name="free")
                agent = ReviewAgent(llm)
                cache_mgr = CacheManager(title)
                
                # Initialize project
                result = agent.initialize_project(
                    title=title,
                    description=description,
                    inclusion_criteria=inclusion_list,
                    exclusion_criteria=exclusion_list
                )
                
                # Save to SQLite database
                st.session_state.db.create_project(
                    project_id=project_id,
                    title=title,
                    description=description,
                    inclusion_criteria=inclusion_list,
                    exclusion_criteria=exclusion_list
                )
                
                # Store in session
                st.session_state.project_initialized = True
                st.session_state.current_project_id = project_id
                st.session_state.project_info = {
                    "title": title,
                    "description": description,
                    "inclusion_criteria": inclusion_list,
                    "exclusion_criteria": exclusion_list
                }
                st.session_state.cache_manager = cache_mgr
                st.session_state.agent = agent
                st.session_state.articles = {}
                
                # Load existing articles from database
                db_articles = st.session_state.db.get_articles(project_id)
                if db_articles:
                    for art in db_articles:
                        article = Article(
                            id=art['id'],
                            title=art['title'],
                            link=art['link'],
                            abstract=art['abstract'],
                            stage=art['stage'],
                            decision=art['decision'],
                            ai_summary=art['ai_summary'],
                            ai_recommendation=art['ai_recommendation'],
                            ai_confidence=art['ai_confidence'],
                            researcher_notes=art['researcher_notes'],
                            reviewer_decision=art['reviewer_decision'],
                            timestamp_added=art['timestamp_added'],
                            timestamp_reviewed=art['timestamp_reviewed']
                        )
                        st.session_state.articles[article.id] = article
                    st.success(f"Project '{title}' loaded with {len(st.session_state.articles)} articles from database!")
                else:
                    st.success(f"✅ Project '{title}' initialized successfully! (ID: {project_id})")
                
                # Show clarification questions
                st.markdown("### 🤔 Clarification Questions")
                st.info("Before you begin, consider these questions to refine your review:")
                questions = agent.ask_clarification_questions()
                for i, q in enumerate(questions[:5], 1):
                    st.write(f"{i}. {q}")
                
                st.balloons()


def show_add_articles():
    """Display article addition interface."""
    if not st.session_state.project_initialized:
        st.warning("⚠️ Please initialize a project first!")
        return
    
    st.title("📥 Add Articles")
    st.markdown("Add articles for screening. You can add them one by one, in batches, or search academic databases.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Single Article", "Batch Import", "Search Databases", "From File"])
    
    with tab1:
        with st.form("add_single"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Article Title*")
                link = st.text_input("DOI/URL*")
            with col2:
                abstract = st.text_area("Abstract", height=150)
            
            submit = st.form_submit_button("Add Article", type="primary")
            
            if submit:
                if title and link:
                    article_id = generate_article_id(title, link)
                    
                    article = Article(
                        id=article_id,
                        title=title,
                        link=link,
                        abstract=abstract,
                        timestamp_added=datetime.now().isoformat()
                    )
                    
                    st.session_state.articles[article_id] = article
                    
                    # Save to database
                    st.session_state.db.add_article({
                        'id': article_id,
                        'project_id': st.session_state.current_project_id,
                        'title': title,
                        'link': link,
                        'abstract': abstract,
                        'stage': 'screening',
                        'decision': 'pending',
                        'timestamp_added': datetime.now().isoformat()
                    })
                    
                    # Auto-save to cache
                    st.session_state.cache_manager.save_cache(st.session_state.articles)
                    
                    st.success(f"✅ Added: {title[:50]}...")
                    
                    # Optionally analyze immediately
                    if st.checkbox("Analyze with AI now"):
                        with st.spinner("AI is analyzing..."):
                            analysis = st.session_state.agent.analyze_article(article)
                            article.ai_summary = analysis['summary']
                            article.ai_recommendation = analysis['recommendation']
                            article.ai_confidence = analysis['confidence']
                            article.stage = analysis['stage']
                            st.session_state.cache_manager.save_cache(st.session_state.articles)
                            st.info("Analysis complete!")
                else:
                    st.error("Title and link are required!")
    
    with tab2:
        st.markdown("### Batch Import")
        st.info("Paste multiple articles in CSV format: `title,link,abstract`")
        
        batch_data = st.text_area("Paste articles here (one per line)",
                                  height=200,
                                  placeholder="Title of paper 1,https://doi.org/xxx,Abstract text here...\nTitle of paper 2,https://doi.org/yyy,Another abstract...")
        
        if st.button("Import Batch"):
            if batch_data:
                lines = batch_data.strip().split('\n')
                imported = 0
                for line in lines:
                    parts = line.split(',', 2)
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        link = parts[1].strip()
                        abstract = parts[2].strip() if len(parts) > 2 else ""
                        
                        if title and link:
                            article_id = generate_article_id(title, link)
                            article = Article(
                                id=article_id,
                                title=title,
                                link=link,
                                abstract=abstract,
                                timestamp_added=datetime.now().isoformat()
                            )
                            st.session_state.articles[article_id] = article
                            
                            # Save to database
                            st.session_state.db.add_article({
                                'id': article_id,
                                'project_id': st.session_state.current_project_id,
                                'title': title,
                                'link': link,
                                'abstract': abstract,
                                'stage': 'screening',
                                'decision': 'pending',
                                'timestamp_added': datetime.now().isoformat()
                            })
                            
                            imported += 1
                
                st.session_state.cache_manager.save_cache(st.session_state.articles)
                st.success(f"✅ Imported {imported} articles!")
    
    with tab3:
        st.markdown("### 🔍 Search Academic Databases")
        st.info("Search PubMed, CrossRef, and arXiv for relevant articles.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input("Search Query", 
                                         placeholder="e.g., maternal health sub-saharan africa",
                                         value=st.session_state.project_info.get('description', '')[:50])
        with col2:
            max_results = st.number_input("Max Results", min_value=10, max_value=200, value=50)
        
        sources = st.multiselect("Select Sources", 
                                 options=['pubmed', 'crossref', 'arxiv'],
                                 default=['pubmed', 'crossref'])
        
        if st.button("🔎 Search", type="primary"):
            if search_query:
                with st.spinner(f"Searching {len(sources)} databases for '{search_query}'..."):
                    crawler = st.session_state.crawler
                    results = crawler.multi_source_search(search_query, sources=sources, max_per_source=max_results//len(sources) if sources else max_results)
                    
                    # Combine and deduplicate
                    all_articles = []
                    for source_arts in results.values():
                        all_articles.extend(source_arts)
                    
                    unique_articles = crawler.deduplicate_articles(all_articles)
                    
                    st.success(f"Found {len(unique_articles)} unique articles!")
                    
                    # Show preview
                    st.markdown(f"### Preview ({len(unique_articles)} articles)")
                    
                    for i, art in enumerate(unique_articles[:10]):
                        with st.expander(f"{i+1}. {art.get('title', 'No title')[:100]}"):
                            st.write(f"**Authors:** {art.get('authors', 'N/A')}")
                            st.write(f"**Journal:** {art.get('journal', 'N/A')}")
                            st.write(f"**Year:** {art.get('publication_year', 'N/A')}")
                            st.write(f"**Source:** {art.get('source', 'Unknown')}")
                            if art.get('abstract'):
                                st.write(f"**Abstract:** {art['abstract'][:300]}...")
                            st.write(f"[Link]({art.get('link', '#')})")
                    
                    # Import button
                    if st.button(f"Import All {len(unique_articles)} Articles"):
                        imported = 0
                        for art in unique_articles:
                            article_id = generate_article_id(art.get('title', ''), art.get('link', ''))
                            
                            article = Article(
                                id=article_id,
                                title=art.get('title', ''),
                                link=art.get('link', ''),
                                abstract=art.get('abstract', ''),
                                timestamp_added=datetime.now().isoformat()
                            )
                            st.session_state.articles[article_id] = article
                            
                            # Save to database
                            st.session_state.db.add_article({
                                'id': article_id,
                                'project_id': st.session_state.current_project_id,
                                'title': art.get('title', ''),
                                'link': art.get('link', ''),
                                'abstract': art.get('abstract', ''),
                                'stage': 'screening',
                                'decision': 'pending',
                                'timestamp_added': datetime.now().isoformat()
                            })
                            
                            imported += 1
                        
                        st.session_state.cache_manager.save_cache(st.session_state.articles)
                        st.success(f"✅ Imported {imported} articles from databases!")
    
    with tab4:
        st.markdown("### Import from File")
        uploaded = st.file_uploader("Upload CSV file", type=['csv', 'txt'])
        
        if uploaded:
            content = uploaded.read().decode('utf-8')
            st.text_area("Preview", content, height=200)
            st.info("File preview shown above. Click import when ready.")
            if st.button("Import File"):
                # Process file
                lines = content.strip().split('\n')
                imported = 0
                for line in lines[1:]:  # Skip header
                    parts = line.split(',', 2)
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        link = parts[1].strip()
                        abstract = parts[2].strip() if len(parts) > 2 else ""
                        
                        if title and link:
                            article_id = generate_article_id(title, link)
                            article = Article(
                                id=article_id,
                                title=title,
                                link=link,
                                abstract=abstract,
                                timestamp_added=datetime.now().isoformat()
                            )
                            st.session_state.articles[article_id] = article
                            
                            st.session_state.db.add_article({
                                'id': article_id,
                                'project_id': st.session_state.current_project_id,
                                'title': title,
                                'link': link,
                                'abstract': abstract,
                                'stage': 'screening',
                                'decision': 'pending',
                                'timestamp_added': datetime.now().isoformat()
                            })
                            
                            imported += 1
                
                st.session_state.cache_manager.save_cache(st.session_state.articles)
                st.success(f"✅ Imported {imported} articles from file!")


def show_review_interface():
    """Display the main review interface with AI and human collaboration."""
    if not st.session_state.project_initialized:
        st.warning("⚠️ Please initialize a project first!")
        return
    
    if not st.session_state.articles:
        st.info("📭 No articles to review yet. Add some articles first!")
        return
    
    st.title("🔍 Review Articles")
    st.markdown("AI provides recommendations, you make the final decision.")
    
    # Filter controls
    col_filters = st.columns(4)
    with col_filters[0]:
        stage_filter = st.selectbox("Stage", ["All", "screening", "eligibility", "inclusion"])
    with col_filters[1]:
        decision_filter = st.selectbox("Decision Status", ["All", "pending", "include", "exclude"])
    with col_filters[2]:
        sort_by = st.selectbox("Sort by", ["Date Added", "AI Confidence", "Title"])
    with col_filters[3]:
        view_mode = st.selectbox("View", ["One at a time", "Grid view"])
    
    # Filter articles
    filtered = list(st.session_state.articles.values())
    
    if stage_filter != "All":
        filtered = [a for a in filtered if a.stage == stage_filter]
    if decision_filter != "All":
        if decision_filter == "pending":
            filtered = [a for a in filtered if not a.reviewer_decision]
        else:
            filtered = [a for a in filtered if a.reviewer_decision == decision_filter]
    
    if sort_by == "Title":
        filtered.sort(key=lambda x: x.title.lower())
    elif sort_by == "AI Confidence":
        filtered.sort(key=lambda x: x.ai_confidence, reverse=True)
    else:
        filtered.sort(key=lambda x: x.timestamp_added, reverse=True)
    
    st.markdown(f"**{len(filtered)} articles** to review")
    
    if view_mode == "One at a time":
        show_single_review(filtered)
    else:
        show_grid_review(filtered)


def show_single_review(articles):
    """Show one article at a time for detailed review."""
    if not articles:
        st.info("No articles match the current filters.")
        return
    
    # Navigation
    col_nav = st.columns([1, 4, 1])
    with col_nav[0]:
        if st.button("← Previous"):
            st.session_state.current_review_idx = max(0, st.session_state.current_review_idx - 1)
    with col_nav[2]:
        if st.button("Next →"):
            st.session_state.current_review_idx = min(len(articles) - 1, st.session_state.current_review_idx + 1)
    
    idx = min(st.session_state.current_review_idx, len(articles) - 1)
    article = articles[idx]
    
    st.markdown(f"### Article {idx + 1} of {len(articles)}")
    
    # Article info
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"#### {article.title}")
        if article.link:
            st.markdown(f"[🔗 View Article]({article.link})")
        if article.abstract:
            st.markdown("**Abstract:**")
            st.write(article.abstract)
    
    with col2:
        st.markdown("### Metadata")
        st.write(f"**ID:** `{article.id}`")
        st.write(f"**Added:** {article.timestamp_added[:10] if article.timestamp_added else 'N/A'}")
        st.write(f"**Stage:** {article.stage}")
        if article.reviewer_decision:
            st.write(f"**Your Decision:** {article.reviewer_decision.upper()}")
    
    st.markdown("---")
    
    # AI Analysis Section
    st.markdown("### 🤖 AI Judge Analysis")
    
    if not article.ai_summary:
        if st.button("Request AI Analysis", type="primary"):
            with st.spinner("AI is analyzing the article..."):
                analysis = st.session_state.agent.analyze_article(article)
                article.ai_summary = analysis['summary']
                article.ai_recommendation = analysis['recommendation']
                article.ai_confidence = analysis['confidence']
                article.stage = analysis['stage']
                st.session_state.cache_manager.save_cache(st.session_state.articles)
                st.rerun()
    else:
        st.markdown(f"""
        <div class="ai-recommendation">
            <strong>Recommendation:</strong> {article.ai_recommendation.upper()}<br>
            <strong>Confidence:</strong> {article.ai_confidence:.0%}<br>
            <strong>Suggested Stage:</strong> {article.stage}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**AI Summary & Rationale:**")
        st.write(article.ai_summary)
        
        # Quick action buttons
        col_act = st.columns(3)
        with col_act[0]:
            if st.button("✓ Accept AI Recommendation", use_container_width=True):
                article.reviewer_decision = article.ai_recommendation
                article.timestamp_reviewed = datetime.now().isoformat()
                st.session_state.cache_manager.save_cache(st.session_state.articles)
                st.success("Decision saved to cache!")
                st.rerun()
        with col_act[1]:
            if st.button("✕ Override - Include", use_container_width=True):
                article.reviewer_decision = "include"
                article.stage = "inclusion"
                article.timestamp_reviewed = datetime.now().isoformat()
                st.session_state.cache_manager.save_cache(st.session_state.articles)
                st.success("Marked as included!")
                st.rerun()
        with col_act[2]:
            if st.button("✕ Override - Exclude", use_container_width=True):
                article.reviewer_decision = "exclude"
                article.timestamp_reviewed = datetime.now().isoformat()
                st.session_state.cache_manager.save_cache(st.session_state.articles)
                st.success("Marked as excluded!")
                st.rerun()
    
    # Human researcher decision
    st.markdown("---")
    st.markdown("### 👤 Your Decision")
    
    with st.form("decision_form"):
        decision = st.radio("Final Decision:", 
                           ["Pending", "Include", "Exclude"],
                           index=["Pending", "Include", "Exclude"].index(article.reviewer_decision) if article.reviewer_decision else 0)
        
        notes = st.text_area("Your Notes (optional)", value=article.researcher_notes,
                            placeholder="Reason for decision, concerns, follow-up needed...")
        
        stage = st.selectbox("PRISMA Stage:", 
                            ["screening", "eligibility", "inclusion"],
                            index=["screening", "eligibility", "inclusion"].index(article.stage))
        
        submitted = st.form_submit_button("Save Decision")
        
        if submitted:
            article.reviewer_decision = decision.lower() if decision != "Pending" else ""
            article.researcher_notes = notes
            article.stage = stage
            article.timestamp_reviewed = datetime.now().isoformat()
            
            # Save to cache
            st.session_state.cache_manager.save_cache(st.session_state.articles)
            
            # Save to database
            st.session_state.db.update_article_decision(
                article_id=article.id,
                decision=article.reviewer_decision,
                stage=article.stage,
                notes=article.researcher_notes
            )
            
            st.success("✅ Decision saved to cache and database! Remember to click 'Save Permanently' when done.")
    
    # Save permanently button
    st.markdown("---")
    col_save = st.columns([4, 1])
    with col_save[1]:
        if st.button("💾 Save Permanently", type="primary", use_container_width=True):
            st.session_state.cache_manager.save_permanent(st.session_state.articles)
            
            # Also export articles log from database
            if st.session_state.current_project_id:
                log_path = f"review_projects/{st.session_state.cache_manager.safe_name}/articles_log_db.txt"
                st.session_state.db.export_articles_log(st.session_state.current_project_id, log_path)
            
            st.success("✅ All reviews saved permanently to disk and database!")


def show_grid_review(articles):
    """Show articles in a grid/card view for quick scanning."""
    st.markdown("### Quick Review Grid")
    
    cols = st.columns(3)
    
    for i, article in enumerate(articles):
        with cols[i % 3]:
            status_emoji = "⏳" if not article.reviewer_decision else ("✅" if article.reviewer_decision == "include" else "❌")
            
            st.markdown(f"""
            <div class="article-card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span>{status_emoji}</span>
                    <span class="stage-badge {article.stage}">{article.stage}</span>
                </div>
                <strong>{article.title[:60]}{'...' if len(article.title) > 60 else ''}</strong><br>
                <small>AI: {article.ai_recommendation or 'Not analyzed'} ({article.ai_confidence:.0%})</small>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Review", key=f"review_{article.id}"):
                st.session_state.current_review_idx = articles.index(article)
                st.rerun()


def show_saved_reviews():
    """Display permanently saved reviews."""
    st.title("💾 Saved Reviews")
    
    # Look for saved projects
    import os
    from pathlib import Path
    
    projects_dir = Path("review_projects")
    
    if not projects_dir.exists():
        st.info("No saved projects found.")
        return
    
    projects = [p for p in projects_dir.iterdir() if p.is_dir()]
    
    if not projects:
        st.info("No projects have been saved permanently yet.")
        return
    
    st.markdown("### Available Projects")
    
    for project in projects:
        saved_file = project / "saved_reviews.json"
        log_file = project / "articles_log.txt"
        
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"#### 📁 {project.name}")
            
            if saved_file.exists():
                with open(saved_file, 'r') as f:
                    data = json.load(f)
                st.write(f"- **Articles:** {len(data)}")
                included = len([a for a in data.values() if a.get('reviewer_decision') == 'include'])
                st.write(f"- **Included:** {included}")
        
        with col2:
            if st.button("View Log", key=f"log_{project.name}"):
                if log_file.exists():
                    content = log_file.read_text()
                    st.text_area("Articles Log", content, height=300)
        
        with col3:
            if st.button("Load Project", key=f"load_{project.name}"):
                # Load this project into session
                if saved_file.exists():
                    with open(saved_file, 'r') as f:
                        data = json.load(f)
                        st.session_state.articles = {k: Article(**v) for k, v in data.items()}
                    st.session_state.project_initialized = True
                    st.session_state.cache_manager = CacheManager(project.name)
                    st.success(f"Loaded {project.name}")


def show_prisma_summary():
    """Display PRISMA flow diagram summary."""
    if not st.session_state.articles:
        st.info("No articles to summarize.")
        return
    
    st.title("📊 PRISMA Flow Summary")
    
    agent = st.session_state.agent
    counts = agent.generate_prisma_counts(st.session_state.articles)
    
    # Display counts in PRISMA format
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Records Identified", counts['identified'])
        st.metric("Screening Stage", counts['screening'])
    
    with col2:
        st.metric("Excluded at Screening", counts['excluded_screening'])
        st.metric("Eligibility Assessment", counts['eligibility'])
    
    with col3:
        st.metric("Excluded at Eligibility", counts['excluded_eligibility'])
        st.metric("Studies Included", counts['included'], delta="Final count")
    
    st.markdown("---")
    
    # Generate text for results section
    st.markdown("### Results Section Draft")
    
    total = counts['identified']
    screening = counts['screening'] + counts['excluded_screening']
    eligibility = counts['eligibility'] + counts['excluded_eligibility']
    included = counts['included']
    
    draft_text = f"""**Results:** The search yielded {total} records after duplicate removal. After title/abstract screening, {eligibility} full texts were assessed for eligibility. {included} studies met inclusion criteria (PRISMA flow diagram: Figure 1). 

Included studies spanned [X] countries across [X] regions, with publication years [XXXX–XXXX]. Sample sizes ranged from [X] to [X] (median [X]). Most studies used DHS or national survey data (n = [X]); others used cohort, census, or longitudinal panel data. Risk of bias was low in [X] studies, moderate in [X], and high in [X]."""
    
    st.code(draft_text, language="markdown")
    
    if st.button("Copy to Clipboard"):
        st.info("Text selected! (Use Ctrl+C to copy)")
    
    # Detailed breakdown
    st.markdown("---")
    st.markdown("### Detailed Breakdown by Stage")
    
    for stage in ["screening", "eligibility", "inclusion"]:
        stage_articles = [a for a in st.session_state.articles.values() if a.stage == stage]
        if stage_articles:
            st.markdown(f"#### {stage.title()} Stage ({len(stage_articles)} articles)")
            
            data = []
            for a in stage_articles:
                status = "✓" if a.reviewer_decision == "include" else ("✗" if a.reviewer_decision == "exclude" else "○")
                data.append({
                    "Status": status,
                    "Title": a.title[:50],
                    "Link": a.link[:40],
                    "AI Rec": a.ai_recommendation,
                    "Your Decision": a.reviewer_decision or "Pending"
                })
            
            st.dataframe(data, use_container_width=True)


if __name__ == "__main__":
    main()
