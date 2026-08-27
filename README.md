# Systematic Literature Review Agent

An agentic AI-powered system for conducting systematic literature reviews with human oversight. The system automatically crawls academic databases, analyzes articles using free LLM models, and provides recommendations while keeping the researcher in full control.

## Features

- **🤖 AI Agent**: Uses free models from OpenRouter (google/gemma-2-9b-it:free) to analyze articles
- **🔍 Academic Crawler**: Searches PubMed, CrossRef, and arXiv automatically
- **👤 Human-in-the-Loop**: Researcher makes final accept/reject decisions
- **📊 PRISMA Compliant**: Tracks articles through screening → eligibility → inclusion
- **💾 SQLite Database**: Persistent storage for projects and articles
- **📤 Export**: Generate articles log and PRISMA results summary
- **🐳 Docker Ready**: Containerized deployment

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React UI      │────▶│  FastAPI Backend │────▶│  SQLite DB      │
│   (Port 3000)   │◀────│  (Port 8000)     │◀────▶│  (.db file)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  AI Agent        │
                    │  (OpenRouter)    │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Academic APIs   │
                    │  PubMed/CrossRef │
                    │  arXiv           │
                    └──────────────────┘
```

## Quick Start

### Option 1: Local Development

#### Backend
```bash
cd backend
pip install -r requirements.txt

# Set your OpenRouter API key (optional, works without for testing)
export OPENROUTER_API_KEY="your-key-here"

# Run backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm start
```

Open http://localhost:3000

### Option 2: Docker

```bash
# Build image
docker build -t review-system .

# Run container
docker run -p 8000:8000 -p 3000:3000 -e OPENROUTER_API_KEY="your-key" review-system
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Usage Flow

1. **Create Project**: Enter title, description, inclusion/exclusion criteria
2. **Get Questions**: AI agent generates clarification questions to refine scope
3. **Crawl Articles**: Search PubMed, CrossRef, arXiv with your query
4. **AI Analysis**: Agent analyzes each article providing:
   - Bullet-point summary (objective, methods, population, findings)
   - Recommendation (include/exclude/unsure)
   - Confidence score
5. **Human Decision**: Review each article and accept/reject (can override AI)
6. **Export**: Generate articles log and PRISMA results summary

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /projects | Create new review project |
| GET | /projects | List all projects |
| GET | /projects/{id} | Get project details |
| PUT | /projects/{id} | Update project criteria |
| GET | /projects/{id}/articles | List articles (filter by stage/decision) |
| POST | /projects/{id}/articles/crawl | Start crawling for articles |
| POST | /projects/{id}/articles/batch-analyze | Analyze articles with AI |
| PUT | /articles/{id}/decision | Set user decision (include/exclude) |
| GET | /projects/{id}/export/articles-log | Export articles log |
| GET | /projects/{id}/export/prisima-summary | Generate PRISMA summary |
| GET | /projects/{id}/stats | Get PRISMA flow statistics |

## Configuration

Create `backend/.env`:

```env
OPENROUTER_API_KEY=sk-or-xxx-your-key-here
DATABASE_URL=sqlite+aiosqlite:///./review_system.db
FREE_MODEL=google/gemma-2-9b-it:free
```

## Free Models Available

The system uses these free models from OpenRouter:
- `google/gemma-2-9b-it:free` (default)
- Other free models can be configured in `config.py`

## File Structure

```
/workspace
├── backend/
│   ├── main.py          # FastAPI application
│   ├── config.py        # Settings & environment
│   ├── database.py      # SQLite models & session
│   ├── crawler.py       # Academic source crawler
│   ├── agent.py         # AI review agent
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── styles.css
│   ├── src/
│   │   ├── App.js       # Main React component
│   │   ├── api.js       # API client
│   │   └── index.js     # Entry point
│   └── package.json
├── Dockerfile
└── README.md
```

## PRISMA Flow

The system tracks articles through standard PRISMA stages:

1. **Identified**: Articles found via crawling
2. **Screening**: AI analyzed, awaiting human decision
3. **Eligibility**: Passed initial screening
4. **Included**: Final included studies
5. **Excluded**: Rejected at any stage

## License

MIT
