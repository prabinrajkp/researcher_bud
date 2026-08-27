const API_BASE = 'http://localhost:8000';

class ReviewSystemAPI {
    // Projects
    static async createProject(data) {
        const resp = await fetch(`${API_BASE}/projects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return resp.json();
    }

    static async getProjects() {
        const resp = await fetch(`${API_BASE}/projects`);
        return resp.json();
    }

    static async getProject(id) {
        const resp = await fetch(`${API_BASE}/projects/${id}`);
        return resp.json();
    }

    static async updateProject(id, data) {
        const resp = await fetch(`${API_BASE}/projects/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return resp.json();
    }

    // Articles
    static async getArticles(projectId, filters = {}) {
        const params = new URLSearchParams(filters);
        const resp = await fetch(`${API_BASE}/projects/${projectId}/articles?${params}`);
        return resp.json();
    }

    static async crawlArticles(projectId, query, sources = ['pubmed', 'crossref', 'arxiv'], maxPerSource = 50) {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/articles/crawl`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, sources, max_per_source: maxPerSource })
        });
        return resp.json();
    }

    static async batchAnalyze(projectId, articleIds) {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/articles/batch-analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ article_ids: articleIds })
        });
        return resp.json();
    }

    static async updateDecision(articleId, decision, notes = '') {
        const resp = await fetch(`${API_BASE}/articles/${articleId}/decision`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision, notes })
        });
        return resp.json();
    }

    static async getArticle(id) {
        const resp = await fetch(`${API_BASE}/articles/${id}`);
        return resp.json();
    }

    // Export
    static async exportArticlesLog(projectId) {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/export/articles-log`);
        return resp.json();
    }

    static async exportPrisimaSummary(projectId) {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/export/prisima-summary`);
        return resp.json();
    }

    static async getProjectStats(projectId) {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/stats`);
        return resp.json();
    }
}

export default ReviewSystemAPI;
