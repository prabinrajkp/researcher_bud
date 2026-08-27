# Systematic Literature Review Assistant

A human-AI collaborative system for conducting systematic literature reviews with PRISMA compliance. Built with Streamlit, SQLite, and free LLM models via OmniRoute/OpenRouter.

## Features

- **🔍 Academic Database Search**: Crawl PubMed, CrossRef, and arXiv for relevant articles
- **🤖 AI Judge**: Provides summary points and inclusion/exclusion recommendations using free LLM models
- **👤 Human Researcher**: Final decision maker with override capability
- **📊 PRISMA Flow**: Automatic tracking of screening → eligibility → inclusion stages
- **💾 Dual Storage**: Auto-cache + manual "Save Permanently" button
- **📝 Article Logging**: Stores names and links in organized documents
- **🗄️ SQLite Database**: Persistent storage for projects and articles
- **🐳 Docker Ready**: Containerized deployment option

## Quick Start

### Local Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up OpenRouter API key (optional, for real AI):
```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

3. Run the application:
```bash
streamlit run app.py
```

4. Open http://localhost:8501 in your browser

### Docker Installation

1. Build the image:
```bash
docker build -t review-system .
```

2. Run the container:
```bash
docker run -p 8501:8501 \
  -e OPENROUTER_API_KEY="your-key" \
  -v $(pwd)/review_projects:/app/review_projects \
  review-system
```

## Usage Workflow

### 1. Start New Project
- Enter review title and description
- Define inclusion/exclusion criteria
- Answer clarification questions to refine scope

### 2. Add Articles
Choose from four methods:
- **Single Article**: Manual entry of title, link, abstract
- **Batch Import**: Paste CSV-formatted data
- **Search Databases**: Query PubMed, CrossRef, arXiv directly
- **From File**: Upload CSV files

### 3. Review Articles
- AI analyzes each article and provides:
  - Summary (3-4 bullet points)
  - Recommendation (INCLUDE/EXCLUDE/UNCERTAIN)
  - Confidence score (0-100%)
  - Suggested PRISMA stage
- Human researcher makes final decision
- Can accept or override AI recommendation

### 4. Save Progress
- Cache auto-saves after each action
- Click "Save Permanently" to commit to database
- Articles log exported automatically

### 5. Generate PRISMA Summary
- View counts for each stage
- Export draft text for results section
- Download articles log with names and links

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit Frontend                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Project │  │  Article │  │   Review         │  │
│  │  Setup   │  │  Import  │  │   Interface      │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ ReviewAgent  │ │  Database    │ │  Crawler     │
│ (AI Judge)   │ │  Manager     │ │  (Scraper)   │
│              │ │  (SQLite)    │ │              │
│ - Summarize  │ │ - Projects   │ │ - PubMed     │
│ - Recommend  │ │ - Articles   │ │ - CrossRef   │
│ - Classify   │ │ - Metadata   │ │ - arXiv      │
└──────────────┘ └──────────────┘ └──────────────┘
        │
        ▼
┌──────────────┐
│ OmniRoute    │
│ LLM Client   │
│ (Free Models)│
└──────────────┘
```

## File Structure

```
/workspace/
├── app.py                 # Streamlit frontend
├── review_agent.py        # AI agent and cache management
├── database.py            # SQLite database manager
├── crawler.py             # Academic article crawler
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── README.md             # This file
└── review_projects/      # Project data storage
    └── [Project Name]/
        ├── cache.json           # Auto-save cache
        ├── saved_reviews.json   # Permanent storage
        └── articles_log.txt     # Article names and links
```

## Database Schema

### Tables
- **projects**: Review project metadata
- **articles**: Article details and review decisions
- **article_metadata**: Scraped metadata (authors, journal, etc.)
- **crawl_queue**: Background crawl jobs
- **review_logs**: Audit trail of decisions

## AI Models

The system uses free models from OpenRouter:
- Default: `google/gemma-2-9b-it:free`
- Fallback: Mock responses (demo mode)

To use a different free model, edit `review_agent.py`:
```python
payload = {
    "model": "meta-llama/llama-3-8b-instruct:free",  # Alternative free model
    ...
}
```

## PRISMA Compliance

The system tracks all stages required for PRISMA flow diagrams:
1. **Identification**: Records from databases
2. **Screening**: Title/abstract review
3. **Eligibility**: Full-text assessment
4. **Included**: Final studies in review

Results section draft is auto-generated with placeholders for:
- Number of records at each stage
- Geographic distribution
- Publication years
- Sample sizes
- Data sources
- Risk of bias assessments

## Customization

### Adding New Data Sources
Edit `crawler.py` to add new search functions:
```python
def search_new_source(self, query: str, max_results: int = 50):
    # Implement API call or scraping logic
    pass
```

### Modifying AI Prompts
Edit the `_create_system_prompt()` method in `ReviewAgent` class to customize how the AI evaluates articles based on your specific criteria.

### Changing Storage Location
Modify the `base_dir` in `CacheManager.__init__()` or set environment variable `REVIEW_PROJECTS_DIR`.

## Troubleshooting

**No AI responses?**
- Check if `OPENROUTER_API_KEY` is set
- Verify internet connectivity
- The system will fall back to mock mode if API fails

**Database errors?**
- Ensure write permissions in `/workspace`
- Check if `review_system.db` is not corrupted

**Docker build fails?**
- Make sure `requirements.txt` exists
- Try: `docker build --no-cache -t review-system .`

## License

MIT License - Free for academic and commercial use.

## Citation

If you use this tool in your research, please cite:
```
Systematic Literature Review Assistant v1.0. 
Available at: https://github.com/your-repo/review-system
```
