# Systematic Literature Review Assistant

A human-AI collaborative system for conducting systematic literature reviews with automated article discovery, AI-powered screening, and PRISMA-compliant reporting.

## Features

### 🤖 AI Agent Capabilities
- **Automated Article Discovery**: Searches PubMed, CrossRef, and arXiv using academic APIs
- **Intelligent Screening**: Provides bullet-point summaries and inclusion/exclusion recommendations
- **Clarification Questions**: Generates questions to refine review scope when starting a project
- **PRISMA Summary Generation**: Drafts results section text based on included studies
- **Free Models**: Uses `google/gemma-2-9b-it:free` via OpenRouter (no cost)

### 👤 Human Researcher Controls
- Final decision authority on all articles
- Override AI recommendations
- Add notes and annotations
- Filter by stage (identified, screening, eligibility, included, excluded)
- Single article or list view modes

### 💾 Data Management
- **SQLite Database**: Persistent local storage
- **Dual Storage System**: Auto-cache + manual "Save Permanently" button
- **Article Logging**: Export articles with names, links, decisions to text files
- **Audit Trail**: All decisions tracked in database
- **PRISMA Flow**: Automatic statistics generation

## Quick Start

### Local Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set your OpenRouter API key (optional, works without for mock mode)
export OPENROUTER_API_KEY="your-api-key"

# Run the application
streamlit run app.py
```

The app opens at `http://localhost:8501`

### Docker Deployment

```bash
# Build the image
docker build -t systematic-review-assistant .

# Run the container
docker run -p 8501:8501 \
  -e OPENROUTER_API_KEY="your-api-key" \
  -v $(pwd)/data:/app/data \
  systematic-review-assistant
```

## Usage Workflow

### 1. Start New Project
- Enter review title and description
- Define inclusion/exclusion criteria
- AI generates 8 clarification questions
- Answer questions to refine criteria

### 2. AI Agent Search
- Enter search query (auto-populated from project title)
- Select sources: PubMed, CrossRef, arXiv
- Set maximum results (default: 50)
- Click "Search & Import Articles"
- Agent crawls databases and deduplicates results

### 3. Review Articles
**AI Judge Panel:**
- Bullet-point summary (population, methods, outcomes)
- Recommendation: Include/Exclude/Needs Review
- Confidence score (0-100%)
- Reasoning explanation

**Human Decision:**
- ✅ Include → Moves to included studies
- ❌ Exclude → Specify reason (title/abstract or full-text)
- ⏳ Defer → Flag for later review
- Add personal notes

### 4. PRISMA Summary
- View flow diagram with counts
- Metrics: Identified, Screened, Full-Text Assessed, Included
- Generate draft Results section text
- Download for manuscript

### 5. Data Management
- Cache status indicator
- "Save Permanently" button
- Export articles log (TXT)
- Export PRISMA stats (JSON)

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────▶│  Review Agent    │────▶│  OpenRouter API │
│   (Frontend)    │◀────│  (AI Judge)      │◀────│  (Free LLMs)    │
└────────┬────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   Database      │◀────│  Academic        │
│   (SQLite)      │     │  Crawler         │
└─────────────────┘     └──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌─────────┐   ┌───────────┐   ┌─────────┐
         │ PubMed  │   │ CrossRef  │   │  arXiv  │
         └─────────┘   └───────────┘   └─────────┘
```

## File Structure

```
/workspace/
├── app.py              # Streamlit frontend
├── database.py         # SQLite database manager
├── crawler.py          # Academic article crawler
├── review_agent.py     # AI review agent
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration
├── README.md           # This file
└── review_system.db    # SQLite database (created on first run)
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENROUTER_API_KEY` | OpenRouter API key for AI features | No* |

*App works in mock mode without API key (shows placeholder analysis)

### Free Model Selection

The system uses `google/gemma-2-9b-it:free` by default. Other free models available via OpenRouter:

- `google/gemma-2-9b-it:free` (default)
- `meta-llama/llama-3-8b-instruct:free`
- `mistralai/mistral-7b-instruct:free`

Edit `review_agent.py` to change:
```python
self.model = "google/gemma-2-9b-it:free"  # Change this line
```

## PRISMA Compliance

The system tracks all stages required for PRISMA 2020 reporting:

1. **Identification**: Records from databases
2. **Screening**: Title/abstract review
3. **Eligibility**: Full-text assessment
4. **Included**: Studies in final synthesis

Auto-generated text follows this template:
> "The search yielded [X] records after duplicate removal. After title/abstract screening, [X] full texts were assessed for eligibility. [X] studies met inclusion criteria..."

## Batch Processing

For large reviews (300-400+ articles):

1. Use batch search with multiple queries
2. Enable "Show Unanalyzed First" in review tab
3. AI analyzes articles on-demand
4. Progress bar tracks completion
5. Export anytime for backup

## API Rate Limits

- PubMed: ~3 requests/second (built-in throttling)
- CrossRef: Polite pool (no key needed)
- arXiv: 1 request/second recommended
- OpenRouter: Depends on model (free models have limits)

## Troubleshooting

### No AI Analysis
- Check `OPENROUTER_API_KEY` environment variable
- Verify internet connectivity
- Try different free model in `review_agent.py`

### Search Returns No Results
- Simplify search query
- Check source selection
- Verify API endpoints accessible

### Database Errors
- Delete `review_system.db` to reset
- Check write permissions in `/workspace`

## License

MIT License - Free for academic and commercial use.
