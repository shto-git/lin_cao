/* 林草规划智能编制系统 - 前端逻辑 */

const API_BASE = window.location.origin;

// ── 状态 ──
let currentProjectId = null;
let currentPage = 'projects';

// ── 页面路由 ──
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    document.querySelectorAll('.nav-links a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
    currentPage = page;

    if (page === 'projects') loadProjects();
    if (page === 'project' && currentProjectId) loadProjectDetail();
}

document.querySelectorAll('.nav-links a').forEach(a => {
    a.addEventListener('click', e => { e.preventDefault(); showPage(a.dataset.page); });
});

// ── 标签页切换 ──
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        renderTabContent(tab.dataset.tab);
    });
});

// ── Toast 通知 ──
function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// ── API 调用 ──
async function api(path, opts = {}) {
    const url = API_BASE + path;
    const defaultOpts = { headers: { 'Content-Type': 'application/json' } };
    const resp = await fetch(url, { ...defaultOpts, ...opts });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    return data;
}

// ── 项目列表 ──
async function loadProjects() {
    try {
        const projects = await api('/api/v1/projects');
        window._projects = projects;
        const container = document.getElementById('project-list');
        if (!projects.length) {
            container.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:#999;padding:40px;">暂无项目，点击上方按钮新建</p>';
            return;
        }
        container.innerHTML = projects.map(p => `
            <div class="card">
                <h3>${escapeHtml(p.name)}</h3>
                <p>📍 ${escapeHtml(p.region)} | 📅 ${escapeHtml(p.period)}</p>
                <p>📝 ${escapeHtml(p.planning_type)}</p>
                <div class="card-actions">
                    <button class="btn btn-primary" onclick="openProject('${p.id}')">进入</button>
                    <button class="btn" onclick="deleteProject('${p.id}')">删除</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('project-list').innerHTML = '<p style="color:#999">无法连接后端服务，请确认服务已启动</p>';
    }
}

// ── 创建项目弹窗 ──
function showCreateProject() {
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal(e) {
    if (!e || e.target === document.getElementById('modal-overlay')) {
        document.getElementById('modal-overlay').classList.remove('active');
    }
}

async function createProject(e) {
    e.preventDefault();
    const form = e.target;
    const data = Object.fromEntries(new FormData(form).entries());
    data.target_words = parseInt(data.target_words) || 50000;
    try {
        await api('/api/v1/projects', { method: 'POST', body: JSON.stringify(data) });
        toast('项目创建成功', 'success');
        closeModal();
        form.reset();
        loadProjects();
    } catch (e) { showToastError(e); }
}

// ── 大纲 ──
async function generateOutline() {
    try {
        toast('正在生成大纲...');
        const result = await api(`/api/v1/projects/${currentProjectId}/outline/generate`, { method: 'POST' });
        toast(result.message, 'success');
        renderTabContent('outline');
    } catch (e) { showToastError(e); }
}

async function loadTasks() {
    try {
        return await api(`/api/v1/projects/${currentProjectId}/tasks`);
    } catch (e) { showToastError(e); return []; }
}

async function generateDrafts() {
    try {
        toast('正在生成草稿...');
        const result = await api(`/api/v1/projects/${currentProjectId}/generate?skip_llm=true`, { method: 'POST' });
        toast(result.message, 'success');
        renderTabContent('drafts');
    } catch (e) { showToastError(e); }
}

async function runQualityCheck() {
    try {
        toast('正在质检...');
        await api(`/api/v1/projects/${currentProjectId}/quality-check`, { method: 'POST' });
        toast('质检完成', 'success');
        renderTabContent('quality');
    } catch (e) { showToastError(e); }
}

async function runFullPipeline() {
    try {
        toast('正在执行完整流程...');
        const result = await api(`/api/v1/projects/${currentProjectId}/run-full`, { method: 'POST' });
        toast(`完成！生成 ${result.drafts} 个草稿，发现 ${result.findings} 个问题`, 'success');
        renderTabContent('outline');
    } catch (e) { showToastError(e); }
}

function showToastError(e) {
    toast(e.message || '操作失败', 'error');
}

// ── 标签内容渲染 ──
async function renderTabContent(tab) {
    const container = document.getElementById('tab-content');
    if (tab === 'outline') {
        try {
            const nodes = await api(`/api/v1/projects/${currentProjectId}/outline`);
            if (!nodes.length) { container.innerHTML = '<p style="color:#999">尚未生成大纲</p>'; return; }
            container.innerHTML = '<div class="outline-tree">' + renderOutlineTree(nodes) + '</div>';
        } catch (e) { showToastError(e); }
    } else if (tab === 'tasks') {
        try {
            const tasks = await api(`/api/v1/projects/${currentProjectId}/tasks`);
            if (!tasks.length) { container.innerHTML = '<p style="color:#999">尚未生成任务</p>'; return; }
            container.innerHTML = tasks.map(t => `
                <div class="task-item">
                    <div class="task-header">
                        <span class="task-title">${escapeHtml(t.outline_id)} - ${escapeHtml(escapeJsonArr(t.title_path))}</span>
                        <span class="task-status status-${t.status}">${t.status}</span>
                    </div>
                    <p style="font-size:12px;color:#666;">字数: ${t.target_words} | 检索: ${escapeJsonArr(t.retrieval_queries).substring(0, 80)}</p>
                </div>
            `).join('');
        } catch (e) { showToastError(e); }
    } else if (tab === 'drafts') {
        try {
            const drafts = await api(`/api/v1/projects/${currentProjectId}/drafts`);
            if (!drafts.length) { container.innerHTML = '<p style="color:#999">尚未生成草稿</p>'; return; }
            const options = drafts.map(d => `<option value="${d.outline_id}">${escapeHtml(d.outline_id + ' - ' + d.title)}</option>`).join('');
            container.innerHTML = `
                <select onchange="renderDraft(this.value)" style="margin-bottom:16px;padding:8px;border-radius:8px;border:1px solid #ddd;">
                    <option value="">选择章节...</option>${options}</select>
                <div id="draft-view"></div>`;
            if (drafts[0]) renderDraft(drafts[0].outline_id);
        } catch (e) { showToastError(e); }
    } else if (tab === 'quality') {
        try {
            const result = await api(`/api/v1/projects/${currentProjectId}/quality-check`, { method: 'POST' });
            const summary = `<div class="quality-summary">
                <div class="quality-stat total"><div class="number">${result.total}</div><div class="label">总计</div></div>
                <div class="quality-stat errors"><div class="number">${result.errors}</div><div class="label">错误</div></div>
                <div class="quality-stat warnings"><div class="number">${result.warnings}</div><div class="label">警告</div></div>
            </div>`;
            const findings = result.findings.map(f => `
                <div class="finding-item ${f.severity}">
                    <div class="finding-code">[${f.severity}] ${f.code}</div>
                    <div>位置: ${f.location || '全文'}</div>
                    <div class="finding-msg">${escapeHtml(f.message)}</div>
                    <div style="font-size:12px;color:#888;margin-top:4px;">${escapeHtml(f.suggestion)}</div>
                </div>
            `).join('') || '<p style="color:#4CAF50;">✅ 未发现问题</p>';
            container.innerHTML = summary + findings;
        } catch (e) { showToastError(e); }
    }
}

function escapeJsonArr(s) { try { return JSON.parse(s).join(' / '); } catch { return s; } }

async function renderDraft(outlineId) {
    try {
        const drafts = await api(`/api/v1/projects/${currentProjectId}/drafts`);
        const draft = drafts.find(d => d.outline_id === outlineId);
        document.getElementById('draft-view').innerHTML = draft
            ? `<div class="draft-content">${escapeHtml(draft.content)}</div>` : '';
    } catch (e) { showToastError(e); }
}

function renderOutlineTree(nodes) {
    const topLevel = nodes.filter(n => n.level <= 1);
    return topLevel.map(n => {
        const children = nodes.filter(x => x.parent_id === n.id && x.level === 2);
        let html = `<div class="outline-node"><div class="outline-node-content level-${n.level}">${escapeHtml(n.title)}<span class="outline-words">${n.target_words || ''} 字</span></div>`;
        children.forEach(c => {
            html += `<div class="outline-node"><div class="outline-node-content level-2">${escapeHtml(c.title)}<span class="outline-words">${c.target_words || ''} 字</span></div></div>`;
        });
        html += '</div>';
        return html;
    }).join('');
}

// ── 工具函数 ──
function escapeHtml(s) {
    const d = document.createElement('d');
    d.textContent = s;
    return d.innerHTML;
}

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
});
