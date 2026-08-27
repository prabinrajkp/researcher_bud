import React, { useState, useEffect } from 'react';
import ReviewSystemAPI from './api.js';

function App() {
    const [activeTab, setActiveTab] = useState('projects');
    const [projects, setProjects] = useState([]);
    const [currentProject, setCurrentProject] = useState(null);
    const [articles, setArticles] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [message, setMessage] = useState(null);

    // New Project Form
    const [newProject, setNewProject] = useState({
        title: '',
        description: '',
        inclusion_criteria: '',
        exclusion_criteria: ''
    });
    const [clarificationQuestions, setClarificationQuestions] = useState([]);

    // Crawl Form
    const [crawlQuery, setCrawlQuery] = useState('');
    const [crawlSources, setCrawlSources] = useState(['pubmed', 'crossref', 'arxiv']);
    const [crawling, setCrawling] = useState(false);

    // Selected article for review
    const [selectedArticle, setSelectedArticle] = useState(null);
    const [userNotes, setUserNotes] = useState('');

    // Export data
    const [exportedLog, setExportedLog] = useState('');
    const [prisimaSummary, setPrisimaSummary] = useState('');

    useEffect(() => {
        loadProjects();
    }, []);

    useEffect(() => {
        if (currentProject) {
            loadArticles();
            loadStats();
        }
    }, [currentProject]);

    async function loadProjects() {
        try {
            const data = await ReviewSystemAPI.getProjects();
            setProjects(data);
        } catch (err) {
            setError('Failed to load projects');
        }
    }

    async function loadArticles(filters = {}) {
        if (!currentProject) return;
        try {
            const data = await ReviewSystemAPI.getArticles(currentProject.id, filters);
            setArticles(data);
        } catch (err) {
            setError('Failed to load articles');
        }
    }

    async function loadStats() {
        if (!currentProject) return;
        try {
            const data = await ReviewSystemAPI.getProjectStats(currentProject.id);
            setStats(data);
        } catch (err) {
            setError('Failed to load stats');
        }
    }

    async function handleCreateProject(e) {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const data = await ReviewSystemAPI.createProject(newProject);
            setCurrentProject(data);
            setClarificationQuestions(data.clarification_questions || []);
            setMessage(`Project "${data.title}" created successfully!`);
            loadProjects();
            setActiveTab('review');
        } catch (err) {
            setError('Failed to create project');
        } finally {
            setLoading(false);
        }
    }

    async function handleCrawl(e) {
        e.preventDefault();
        if (!currentProject || !crawlQuery) return;
        setCrawling(true);
        setError(null);
        try {
            await ReviewSystemAPI.crawlArticles(currentProject.id, crawlQuery, crawlSources, 50);
            setMessage('Crawl started! Articles will be available shortly.');
            setTimeout(() => loadArticles(), 3000);
        } catch (err) {
            setError('Failed to start crawl');
        } finally {
            setCrawling(false);
        }
    }

    async function handleBatchAnalyze() {
        if (!currentProject || articles.length === 0) return;
        setLoading(true);
        try {
            const ids = articles.filter(a => !a.ai_summary).map(a => a.id);
            if (ids.length === 0) {
                setMessage('All articles already analyzed');
                return;
            }
            await ReviewSystemAPI.batchAnalyze(currentProject.id, ids);
            setMessage(`Analyzing ${ids.length} articles... Refresh in 30 seconds`);
            setTimeout(() => loadArticles(), 30000);
        } catch (err) {
            setError('Failed to analyze articles');
        } finally {
            setLoading(false);
        }
    }

    async function handleDecision(decision) {
        if (!selectedArticle) return;
        try {
            await ReviewSystemAPI.updateDecision(selectedArticle.id, decision, userNotes);
            setMessage(`Decision saved: ${decision}`);
            setSelectedArticle(null);
            setUserNotes('');
            loadArticles();
            loadStats();
        } catch (err) {
            setError('Failed to save decision');
        }
    }

    async function loadExport() {
        if (!currentProject) return;
        try {
            const logData = await ReviewSystemAPI.exportArticlesLog(currentProject.id);
            setExportedLog(logData.content);
            
            const summaryData = await ReviewSystemAPI.exportPrisimaSummary(currentProject.id);
            setPrisimaSummary(summaryData.summary);
        } catch (err) {
            setError('Failed to export');
        }
    }

    function getRecClass(rec) {
        if (rec === 'include') return 'rec-include';
        if (rec === 'exclude') return 'rec-exclude';
        return 'rec-unsure';
    }

    return (
        <div className="app">
            <header>
                <h1>🔬 Systematic Review Agent</h1>
                <p>AI-powered literature review with human oversight • PRISMA compliant</p>
            </header>

            {message && (
                <div className="alert alert-success" onClick={() => setMessage(null)}>
                    ✓ {message}
                </div>
            )}

            {error && (
                <div className="alert alert-error" onClick={() => setError(null)}>
                    ✗ {error}
                </div>
            )}

            <div className="tabs">
                <button 
                    className={`tab-btn ${activeTab === 'projects' ? 'active' : ''}`}
                    onClick={() => setActiveTab('projects')}
                >
                    📁 Projects
                </button>
                <button 
                    className={`tab-btn ${activeTab === 'review' ? 'active' : ''}`}
                    onClick={() => setActiveTab('review')}
                    disabled={!currentProject}
                >
                    🔍 Review Articles
                </button>
                <button 
                    className={`tab-btn ${activeTab === 'export' ? 'active' : ''}`}
                    onClick={() => setActiveTab('export')}
                    disabled={!currentProject}
                >
                    📤 Export
                </button>
            </div>

            {/* PROJECTS TAB */}
            {activeTab === 'projects' && (
                <div>
                    <div className="card">
                        <h2>Create New Review Project</h2>
                        <form onSubmit={handleCreateProject}>
                            <div className="form-group">
                                <label>Review Title *</label>
                                <input
                                    type="text"
                                    value={newProject.title}
                                    onChange={(e) => setNewProject({...newProject, title: e.target.value})}
                                    placeholder="e.g., Impact of X on Y in Z population"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Brief Description</label>
                                <textarea
                                    value={newProject.description}
                                    onChange={(e) => setNewProject({...newProject, description: e.target.value})}
                                    placeholder="Describe the scope and objectives of your review..."
                                />
                            </div>
                            <div className="form-group">
                                <label>Inclusion Criteria</label>
                                <textarea
                                    value={newProject.inclusion_criteria}
                                    onChange={(e) => setNewProject({...newProject, inclusion_criteria: e.target.value})}
                                    placeholder="e.g., Population: adults 18+, Study design: RCTs, Language: English"
                                />
                            </div>
                            <div className="form-group">
                                <label>Exclusion Criteria</label>
                                <textarea
                                    value={newProject.exclusion_criteria}
                                    onChange={(e) => setNewProject({...newProject, exclusion_criteria: e.target.value})}
                                    placeholder="e.g., Case reports, Animal studies, Reviews"
                                />
                            </div>
                            <button type="submit" className="btn btn-primary" disabled={loading}>
                                {loading ? 'Creating...' : 'Create Project & Get Questions'}
                            </button>
                        </form>
                    </div>

                    {clarificationQuestions.length > 0 && (
                        <div className="card">
                            <h2>🤖 AI Clarification Questions</h2>
                            <p style={{marginBottom: '15px', color: '#666'}}>
                                The agent suggests these questions to refine your review criteria:
                            </p>
                            <ul className="questions-list">
                                {clarificationQuestions.map((q, i) => (
                                    <li key={i}>❓ {q}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {projects.length > 0 && (
                        <div className="card">
                            <h2>Existing Projects</h2>
                            <div className="article-list">
                                {projects.map(p => (
                                    <div 
                                        key={p.id} 
                                        className={`article-item ${currentProject?.id === p.id ? 'selected' : ''}`}
                                        onClick={() => {setCurrentProject(p); setActiveTab('review');}}
                                        style={{cursor: 'pointer'}}
                                    >
                                        <div className="article-title">{p.title}</div>
                                        <div className="article-meta">
                                            {p.article_count} articles • Created {new Date(p.created_at).toLocaleDateString()}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* REVIEW TAB */}
            {activeTab === 'review' && currentProject && (
                <div>
                    <div className="card">
                        <h2>{currentProject.title}</h2>
                        <p style={{color: '#666', marginBottom: '15px'}}>{currentProject.description}</p>
                        
                        {stats && (
                            <div className="stats-grid">
                                <div className="stat-card">
                                    <div className="stat-number">{stats.total || 0}</div>
                                    <div className="stat-label">Total</div>
                                </div>
                                <div className="stat-card pending">
                                    <div className="stat-number">{stats.pending_review || 0}</div>
                                    <div className="stat-label">Pending</div>
                                </div>
                                <div className="stat-card included">
                                    <div className="stat-number">{stats.included || 0}</div>
                                    <div className="stat-label">Included</div>
                                </div>
                                <div className="stat-card excluded">
                                    <div className="stat-number">{stats.excluded || 0}</div>
                                    <div className="stat-label">Excluded</div>
                                </div>
                            </div>
                        )}

                        <div className="form-group">
                            <label>Crawl for Articles</label>
                            <form onSubmit={handleCrawl} style={{display: 'flex', gap: '10px', alignItems: 'flex-end'}}>
                                <div style={{flex: 1}}>
                                    <input
                                        type="text"
                                        value={crawlQuery}
                                        onChange={(e) => setCrawlQuery(e.target.value)}
                                        placeholder="Search query (e.g., 'diabetes AND lifestyle intervention')"
                                        required
                                    />
                                </div>
                                <div>
                                    <label style={{fontSize: '12px'}}>Sources:</label>
                                    <div className="checkbox-list">
                                        <label className="checkbox-item">
                                            <input 
                                                type="checkbox" 
                                                checked={crawlSources.includes('pubmed')}
                                                onChange={(e) => {
                                                    if (e.target.checked) setCrawlSources([...crawlSources, 'pubmed']);
                                                    else setCrawlSources(crawlSources.filter(s => s !== 'pubmed'));
                                                }}
                                            /> PubMed
                                        </label>
                                        <label className="checkbox-item">
                                            <input 
                                                type="checkbox" 
                                                checked={crawlSources.includes('crossref')}
                                                onChange={(e) => {
                                                    if (e.target.checked) setCrawlSources([...crawlSources, 'crossref']);
                                                    else setCrawlSources(crawlSources.filter(s => s !== 'crossref'));
                                                }}
                                            /> CrossRef
                                        </label>
                                        <label className="checkbox-item">
                                            <input 
                                                type="checkbox" 
                                                checked={crawlSources.includes('arxiv')}
                                                onChange={(e) => {
                                                    if (e.target.checked) setCrawlSources([...crawlSources, 'arxiv']);
                                                    else setCrawlSources(crawlSources.filter(s => s !== 'arxiv'));
                                                }}
                                            /> arXiv
                                        </label>
                                    </div>
                                </div>
                                <button type="submit" className="btn btn-primary" disabled={crawling}>
                                    {crawling ? <span className="loading"></span> : '🔎 Crawl'}
                                </button>
                            </form>
                        </div>

                        <div className="btn-group">
                            <button className="btn btn-secondary" onClick={() => loadArticles()}>
                                🔄 Refresh
                            </button>
                            <button className="btn btn-primary" onClick={handleBatchAnalyze} disabled={loading || articles.length === 0}>
                                🤖 AI Analyze All Pending
                            </button>
                        </div>
                    </div>

                    <div className="card">
                        <h2>Articles ({articles.length})</h2>
                        <div className="article-list">
                            {articles.length === 0 ? (
                                <p style={{color: '#666'}}>No articles yet. Use the crawl feature above to find articles.</p>
                            ) : (
                                articles.map(article => (
                                    <div 
                                        key={article.id}
                                        className={`article-item ${selectedArticle?.id === article.id ? 'selected' : ''}`}
                                        onClick={() => setSelectedArticle(article)}
                                    >
                                        <div className="article-header">
                                            <div className="article-title">{article.title}</div>
                                            {article.ai_recommendation && (
                                                <span className={`recommendation-badge ${getRecClass(article.ai_recommendation)}`}>
                                                    {article.ai_recommendation}
                                                    <span className="confidence-score">
                                                        ({Math.round(article.ai_confidence * 100)}% confidence)
                                                    </span>
                                                </span>
                                            )}
                                        </div>
                                        <div className="article-meta">
                                            {article.authors && <span>{article.authors.split(',')[0]} et al.</span>}
                                            {article.published_year && <span> • {article.published_year}</span>}
                                            {article.journal && <span> • {article.journal}</span>}
                                            {article.source && <span> • Source: {article.source}</span>}
                                        </div>
                                        {article.url && (
                                            <a href={article.url} target="_blank" rel="noopener noreferrer" className="article-link">
                                                🔗 View Article
                                            </a>
                                        )}
                                        
                                        {article.ai_summary && (
                                            <div className="ai-summary">
                                                <h4>🤖 AI Judge Summary</h4>
                                                <ul>
                                                    {JSON.parse(article.ai_summary).map((point, i) => (
                                                        <li key={i}>{point}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}

                                        {selectedArticle?.id === article.id && (
                                            <div className="decision-buttons">
                                                <div style={{flex: 1}}>
                                                    <label style={{fontSize: '13px', display: 'block', marginBottom: '5px'}}>
                                                        Your Notes:
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={userNotes}
                                                        onChange={(e) => setUserNotes(e.target.value)}
                                                        placeholder="Optional notes about this decision..."
                                                        style={{width: '100%', padding: '8px', border: '1px solid #ddd', borderRadius: '6px'}}
                                                    />
                                                </div>
                                                <button 
                                                    className="btn btn-success"
                                                    onClick={(e) => {e.stopPropagation(); handleDecision('include');}}
                                                >
                                                    ✓ Include
                                                </button>
                                                <button 
                                                    className="btn btn-danger"
                                                    onClick={(e) => {e.stopPropagation(); handleDecision('exclude');}}
                                                >
                                                    ✗ Exclude
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* EXPORT TAB */}
            {activeTab === 'export' && currentProject && (
                <div>
                    <div className="card">
                        <h2>📤 Export Results</h2>
                        <button className="btn btn-primary" onClick={loadExport}>
                            Generate Exports
                        </button>
                    </div>

                    {exportedLog && (
                        <div className="card">
                            <h2>📋 Articles Log</h2>
                            <div className="export-content">{exportedLog}</div>
                            <button 
                                className="btn btn-secondary" 
                                style={{marginTop: '15px'}}
                                onClick={() => {
                                    navigator.clipboard.writeText(exportedLog);
                                    setMessage('Copied to clipboard!');
                                }}
                            >
                                📋 Copy to Clipboard
                            </button>
                        </div>
                    )}

                    {prisimaSummary && (
                        <div className="card">
                            <h2>📊 PRISMA Results Summary</h2>
                            <div className="export-content">{prisimaSummary}</div>
                            <button 
                                className="btn btn-secondary" 
                                style={{marginTop: '15px'}}
                                onClick={() => {
                                    navigator.clipboard.writeText(prisimaSummary);
                                    setMessage('Copied to clipboard!');
                                }}
                            >
                                📋 Copy to Clipboard
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default App;
