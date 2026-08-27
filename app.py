"""
Systematic Literature Review Assistant
Human-AI Collaborative Review System with Agentic Workflow
"""
import streamlit as st
from database import DatabaseManager
from crawler import AcademicCrawler
from review_agent import ReviewAgent
from pathlib import Path
import os
from datetime import datetime


# Page configuration
st.set_page_config(
    page_title="Systematic Review Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components
@st.cache_resource
def get_db():
    return DatabaseManager()

@st.cache_resource
def get_crawler():
    return AcademicCrawler()

@st.cache_resource
def get_agent():
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    return ReviewAgent(api_key=api_key if api_key else None)

db = get_db()
crawler = get_crawler()
agent = get_agent()

# Session state initialization
if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None
if 'clarification_answered' not in st.session_state:
    st.session_state.clarification_answered = False
if 'pending_reviews' not in st.session_state:
    st.session_state.pending_reviews = []
if 'cache_dirty' not in st.session_state:
    st.session_state.cache_dirty = False


def save_to_cache():
    """Save current state to cache"""
    if st.session_state.current_project_id:
        cache_data = {
            'project_id': st.session_state.current_project_id,
            'timestamp': datetime.now().isoformat(),
            'pending_count': len(st.session_state.pending_reviews)
        }
        db.save_to_cache(f"session_{st.session_state.current_project_id}", cache_data)
        st.session_state.cache_dirty = False


def load_from_cache(project_id: int):
    """Load state from cache"""
    cache_data = db.get_from_cache(f"session_{project_id}")
    if cache_data:
        st.session_state.current_project_id = cache_data.get('project_id')
        return True
    return False


# Sidebar - Project Selection
with st.sidebar:
    st.header("📁 Projects")
    
    # Show all projects
    projects = db.get_all_projects()
    
    if projects:
        project_options = {p['title']: p['id'] for p in projects}
        selected_title = st.selectbox(
            "Select Project",
            options=list(project_options.keys()),
            index=0
        )
        
        if st.button("Load Project"):
            st.session_state.current_project_id = project_options[selected_title]
            load_from_cache(st.session_state.current_project_id)
            st.rerun()
    else:
        st.info("No projects yet. Create one below.")
    
    st.divider()
    
    # Quick stats
    if st.session_state.current_project_id:
        stats = db.get_prisma_stats(st.session_state.current_project_id)
        st.metric("Total Articles", stats['identified'])
        st.metric("Included", stats['included'])
        st.metric("Pending Review", stats['identified'] - stats['screened'])


# Main App
st.title("📚 Systematic Literature Review Assistant")
st.markdown("**Human-AI Collaborative Review System** • Powered by Free LLM Models via OpenRouter")

# Tab navigation
tabs = st.tabs([
    "🚀 Start New Project",
    "🤖 AI Agent Search",
    "📋 Review Articles",
    "📊 PRISMA Summary",
    "💾 Data Management"
])

# TAB 1: Start New Project
with tabs[0]:
    st.header("Start a New Systematic Review")
    
    with st.form("new_project_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("Review Title*", placeholder="e.g., Impact of Digital Health Interventions on Diabetes Management")
            description = st.text_area("Brief Description", 
                                      placeholder="Describe the research question and scope...",
                                      height=100)
        
        with col2:
            inclusion = st.text_area("Inclusion Criteria",
                                    placeholder="- Population: ...\n- Study design: ...\n- Outcomes: ...",
                                    height=150)
            exclusion = st.text_area("Exclusion Criteria",
                                    placeholder="- Exclude: ...\n- Date restrictions: ...",
                                    height=150)
        
        submitted = st.form_submit_button("Create Project & Get Clarification Questions", use_container_width=True)
        
        if submitted:
            if not title:
                st.error("Title is required!")
            else:
                # Create project
                project_id = db.create_project(
                    title=title,
                    description=description or "",
                    inclusion_criteria=inclusion or "",
                    exclusion_criteria=exclusion or ""
                )
                
                st.session_state.current_project_id = project_id
                st.success(f"Project '{title}' created successfully!")
                
                # Generate clarification questions using AI agent
                with st.spinner("🤖 AI Agent generating clarification questions..."):
                    questions = agent.generate_clarification_questions(title, description or "")
                
                st.session_state.clarification_questions = questions
                st.session_state.show_questions = True
    
    # Show clarification questions if available
    if st.session_state.get('show_questions', False) and st.session_state.current_project_id:
        st.divider()
        st.subheader("🤔 AI Agent Clarification Questions")
        st.info("Answer these questions to refine your inclusion/exclusion criteria. This helps the AI provide better recommendations.")
        
        questions = st.session_state.get('clarification_questions', [])
        
        with st.form("clarification_form"):
            answers = {}
            for i, q in enumerate(questions):
                answers[f"q{i}"] = st.text_area(f"Q{i+1}: {q}", height=60)
            
            save_answers = st.form_submit_button("Save Answers & Update Criteria")
            
            if save_answers:
                # Get project to update criteria
                project = db.get_project(st.session_state.current_project_id)
                
                # Append answers to criteria
                updated_inclusion = project['inclusion_criteria'] + "\n\nCLARIFICATIONS:\n"
                
                for i, q in enumerate(questions):
                    answer = answers[f"q{i}"]
                    if answer.strip():
                        updated_inclusion += f"- {answer}\n"
                
                # Update project with clarified criteria
                db.update_project(st.session_state.current_project_id, {
                    'inclusion_criteria': updated_inclusion
                })
                
                st.success("Clarification answers saved! The AI will use these for better recommendations.")
                st.session_state.show_questions = False
                st.session_state.clarification_answered = True

# TAB 2: AI Agent Search
with tabs[1]:
    if not st.session_state.current_project_id:
        st.warning("⚠️ Please create or select a project first.")
    else:
        st.header("🤖 AI-Powered Article Discovery")
        
        project = db.get_project(st.session_state.current_project_id)
        st.info(f"**Project:** {project['title']}")
        
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            search_query = st.text_input(
                "Search Query",
                value=project['title'] if project else "",
                placeholder="Enter keywords for article search",
                help="The AI agent will search PubMed, CrossRef, and arXiv"
            )
        
        with col2:
            max_results = st.number_input("Max Results", min_value=10, max_value=200, value=50)
        
        with col3:
            sources = st.multiselect(
                "Sources",
                ["PubMed", "CrossRef", "arXiv"],
                default=["PubMed", "CrossRef"]
            )
        
        if st.button("🔍 Search & Import Articles", type="primary", use_container_width=True):
            if not search_query:
                st.error("Please enter a search query")
            elif not sources:
                st.error("Please select at least one source")
            else:
                with st.spinner(f"🤖 AI Agent searching {len(sources)} databases..."):
                    articles = crawler.search(
                        query=search_query,
                        sources=sources,
                        max_results_per_source=max_results // len(sources) if sources else 50
                    )
                    
                    if articles:
                        # Add to database
                        added_count = 0
                        for article in articles:
                            article_id = db.add_article(st.session_state.current_project_id, article)
                            if article_id:
                                added_count += 1
                        
                        st.success(f"✅ Found and imported {added_count} unique articles!")
                        
                        # Auto-analyze first few articles
                        if added_count > 0 and agent.client:
                            st.info("ℹ️ Tip: Go to 'Review Articles' tab to see AI analysis of each paper")
                    else:
                        st.warning("No articles found. Try different keywords.")
        
        # Show crawl queue status
        st.divider()
        st.subheader("Recent Searches")
        crawl_tasks = db.get_crawl_queue(st.session_state.current_project_id, status='completed')[-5:]
        
        if crawl_tasks:
            for task in reversed(crawl_tasks):
                st.write(f"✅ {task['source']}: '{task['query']}' - {task['articles_found']} articles ({task['crawled_at']})")
        else:
            st.info("No searches yet.")

# TAB 3: Review Articles
with tabs[2]:
    if not st.session_state.current_project_id:
        st.warning("⚠️ Please create or select a project first.")
    else:
        st.header("📋 Article Review - Human + AI Judge")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_stage = st.selectbox(
                "Filter by Stage",
                ["All", "identified", "screening", "eligibility", "included", "excluded"]
            )
        
        with col2:
            filter_decision = st.selectbox(
                "Filter by Decision",
                ["All", "include", "exclude_title_abstract", "exclude_full_text", "needs_review"]
            )
        
        with col3:
            show_analyzed = st.checkbox("Show Unanalyzed First", value=True)
        
        # Get articles
        stage_filter = None if filter_stage == "All" else filter_stage
        decision_filter = None if filter_decision == "All" else filter_decision
        
        articles = db.get_articles(
            st.session_state.current_project_id,
            stage=stage_filter,
            decision=decision_filter
        )
        
        if not articles:
            st.info("No articles found. Use the 'AI Agent Search' tab to find articles.")
        else:
            st.divider()
            st.write(f"**{len(articles)} articles** to review")
            
            # Progress bar
            reviewed = sum(1 for a in articles if a.get('user_decision'))
            progress = reviewed / len(articles) if articles else 0
            st.progress(progress, text=f"Review Progress: {reviewed}/{len(articles)}")
            
            st.divider()
            
            # Review interface - show one article at a time or list view
            view_mode = st.radio("View Mode", ["Single Article", "List View"], horizontal=True)
            
            if view_mode == "Single Article":
                # Get unanalyzed or pending articles first
                pending = [a for a in articles if not a.get('ai_summary')]
                if not pending:
                    pending = [a for a in articles if not a.get('user_decision')]
                
                if pending:
                    current_article = pending[0]
                else:
                    current_article = articles[0]
                
                # Display article
                st.subsection(f"📄 {current_article['title']}")
                
                col_meta, col_ai = st.columns([1, 1])
                
                with col_meta:
                    st.markdown(f"""
                    **Authors:** {current_article.get('authors', 'N/A')}  
                    **Journal:** {current_article.get('journal', 'N/A')}  
                    **Year:** {current_article.get('year', 'N/A')}  
                    **Source:** {current_article.get('source', 'N/A')}  
                    **DOI:** [{current_article.get('doi', 'N/A')}]({current_article.get('url', '#')})  
                    """)
                    
                    if current_article.get('abstract'):
                        with st.expander("📝 Abstract", expanded=True):
                            st.write(current_article['abstract'])
                    
                    st.link_button("🔗 View Original", current_article.get('url', '#'))
                
                with col_ai:
                    # AI Analysis
                    if not current_article.get('ai_summary'):
                        with st.spinner("🤖 AI Judge analyzing..."):
                            project = db.get_project(st.session_state.current_project_id)
                            analysis = agent.analyze_article(
                                title=current_article['title'],
                                abstract=current_article.get('abstract', ''),
                                full_text=current_article.get('full_text'),
                                inclusion_criteria=project.get('inclusion_criteria', ''),
                                exclusion_criteria=project.get('exclusion_criteria', '')
                            )
                            
                            # Save analysis to DB
                            db.update_article(current_article['id'], {
                                'ai_summary': '\n'.join(analysis['summary']),
                                'ai_recommendation': analysis['recommendation'],
                                'ai_confidence': analysis['confidence']
                            }, performed_by='ai_agent')
                            
                            st.session_state.cache_dirty = True
                            st.rerun()
                    else:
                        st.success("✅ AI Analysis Complete")
                        analysis = {
                            'summary': current_article['ai_summary'].split('\n'),
                            'recommendation': current_article['ai_recommendation'],
                            'confidence': current_article['ai_confidence'],
                            'reasoning': ''
                        }
                        
                        st.markdown("### 🤖 AI Judge Assessment")
                        
                        # Summary bullets
                        for point in analysis['summary']:
                            st.write(f"• {point}")
                        
                        # Recommendation badge
                        rec_emoji = {"include": "✅", "exclude_title_abstract": "❌", 
                                    "exclude_full_text": "❌", "needs_review": "⏳"}
                        rec_label = {"include": "Include", "exclude_title_abstract": "Exclude (Title/Abstract)",
                                    "exclude_full_text": "Exclude (Full Text)", "needs_review": "Needs Human Review"}
                        
                        emoji = rec_emoji.get(analysis['recommendation'], "⏳")
                        label = rec_label.get(analysis['recommendation'], "Unknown")
                        st.metric("AI Recommendation", f"{emoji} {label}")
                        
                        # Confidence score
                        conf_color = "green" if analysis['confidence'] > 0.7 else "orange" if analysis['confidence'] > 0.4 else "red"
                        st.markdown(f"**Confidence:** :{conf_color}[{analysis['confidence']*100:.0f}%]")
                
                # Human decision
                st.divider()
                st.subheader("👤 Researcher Decision")
                
                h_col1, h_col2, h_col3 = st.columns(3)
                
                with h_col1:
                    if st.button("✅ Include", type="positive", use_container_width=True,
                                key=f"include_{current_article['id']}"):
                        db.update_article(current_article['id'], {
                            'user_decision': 'include',
                            'stage': 'included',
                            'included_in_review': True
                        })
                        st.session_state.cache_dirty = True
                        st.balloons()
                        st.rerun()
                
                with h_col2:
                    if st.button("❌ Exclude", type="secondary", use_container_width=True,
                                key=f"exclude_{current_article['id']}"):
                        exclude_reason = st.selectbox(
                            "Reason",
                            ["exclude_title_abstract", "exclude_full_text"],
                            key=f"reason_{current_article['id']}"
                        )
                        db.update_article(current_article['id'], {
                            'user_decision': exclude_reason,
                            'stage': 'excluded',
                            'included_in_review': False
                        })
                        st.session_state.cache_dirty = True
                        st.rerun()
                
                with h_col3:
                    if st.button("⏳ Defer", type="tertiary", use_container_width=True,
                                key=f"defer_{current_article['id']}"):
                        db.update_article(current_article['id'], {
                            'user_decision': 'needs_review',
                            'stage': 'screening'
                        })
                        st.session_state.cache_dirty = True
                        st.rerun()
                
                # Notes
                user_notes = st.text_area("Your Notes (optional)", 
                                         key=f"notes_{current_article['id']}",
                                         on_change=lambda: setattr(st.session_state, 'cache_dirty', True))
                
                if user_notes:
                    db.update_article(current_article['id'], {'user_notes': user_notes})
            
            else:
                # List view
                for article in articles[:20]:  # Limit display
                    with st.expander(f"{'✅' if article.get('included_in_review') else '❌' if article.get('user_decision') else '⏳'} {article['title']}", 
                                   expanded=False):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**Authors:** {article.get('authors', 'N/A')}")
                            st.write(f"**Journal:** {article.get('journal', 'N/A')} | **Year:** {article.get('year', 'N/A')}")
                            
                            if article.get('ai_summary'):
                                st.info(f"🤖 AI: {article['ai_summary'][:200]}...")
                        
                        with col2:
                            if not article.get('user_decision'):
                                c1, c2 = st.columns(2)
                                with c1:
                                    if st.button("Include", key=f"inc_{article['id']}"):
                                        db.update_article(article['id'], {
                                            'user_decision': 'include',
                                            'included_in_review': True
                                        })
                                        st.rerun()
                                with c2:
                                    if st.button("Exclude", key=f"exc_{article['id']}"):
                                        db.update_article(article['id'], {
                                            'user_decision': 'exclude_title_abstract',
                                            'included_in_review': False
                                        })
                                        st.rerun()
                            else:
                                st.write(f"Decision: {article['user_decision']}")

# TAB 4: PRISMA Summary
with tabs[3]:
    if not st.session_state.current_project_id:
        st.warning("⚠️ Please create or select a project first.")
    else:
        st.header("📊 PRISMA Flow Diagram & Results Draft")
        
        stats = db.get_prisma_stats(st.session_state.current_project_id)
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Identified", stats['identified'])
        col2.metric("Screened", stats['screened'])
        col3.metric("Full-Text Assessed", stats['full_text_assessed'])
        col4.metric("Included", stats['included'])
        
        st.divider()
        
        # PRISMA flow visualization (simplified)
        st.subheader("PRISMA Flow")
        
        flow_data = f"""
        ┌─────────────────────┐
        │   Identified: {stats['identified']:>3}   │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │   Screened: {stats['screened']:>3}     │
        │   Excluded: {stats['excluded_screening']:>3}   │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  Full-Text: {stats['full_text_assessed']:>3}      │
        │   Excluded: {stats['excluded_eligibility']:>3}   │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │   Included: {stats['included']:>3}     │
        └─────────────────────┘
        """
        st.code(flow_data, language="text")
        
        st.divider()
        
        # Generate results draft
        st.subheader("📝 Draft Results Section")
        
        included_articles = db.get_articles(st.session_state.current_project_id, decision='include')
        
        if st.button("🤖 Generate Results Draft with AI", type="primary"):
            with st.spinner("AI generating PRISMA summary..."):
                draft = agent.generate_prisma_summary(included_articles)
                st.session_state.prism_draft = draft
        
        if st.session_state.get('prism_draft'):
            st.text_area("Results Draft", value=st.session_state.prism_draft, height=200)
            st.download_button(
                "📥 Download Draft",
                data=st.session_state.prism_draft,
                file_name="results_draft.txt",
                mime="text/plain"
            )
        else:
            st.info("Click 'Generate Results Draft with AI' to create a draft based on included studies.")

# TAB 5: Data Management
with tabs[4]:
    if not st.session_state.current_project_id:
        st.warning("⚠️ Please create or select a project first.")
    else:
        st.header("💾 Data Management")
        
        # Cache status
        st.subheader("Cache Status")
        if st.session_state.cache_dirty:
            st.warning("⚠️ You have unsaved changes in cache.")
            if st.button("💾 Save Permanently to Database", type="primary"):
                save_to_cache()
                st.success("✅ Changes saved permanently!")
        else:
            st.success("✅ All changes saved")
        
        st.divider()
        
        # Export
        st.subheader("Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 Export Articles Log", use_container_width=True):
                output_path = f"articles_log_{st.session_state.current_project_id}.txt"
                db.export_articles_log(st.session_state.current_project_id, output_path)
                
                with open(output_path, 'r') as f:
                    content = f.read()
                
                st.download_button(
                    "📥 Download Articles Log",
                    data=content,
                    file_name=output_path,
                    mime="text/plain"
                )
        
        with col2:
            if st.button("📊 Export PRISMA Stats", use_container_width=True):
                stats = db.get_prisma_stats(st.session_state.current_project_id)
                import json
                stats_json = json.dumps(stats, indent=2)
                
                st.download_button(
                    "📥 Download Stats JSON",
                    data=stats_json,
                    file_name=f"prisma_stats_{st.session_state.current_project_id}.json",
                    mime="application/json"
                )
        
        st.divider()
        
        # Audit trail
        st.subheader("Recent Activity Log")
        # Would need to implement get_recent_logs in database
        st.info("Activity logging enabled. All decisions are tracked in the database.")

# Auto-save reminder
if st.session_state.cache_dirty:
    st.toast("💡 Don't forget to save your changes permanently!", icon="⚠️")

# Footer
st.divider()
st.caption("""
**Systematic Review Assistant** • Built for researchers • Uses free LLM models via OpenRouter  
Articles are stored locally in SQLite database • Export anytime for backup
""")
