/* 林草规划智能编制系统 - 前端逻辑 */

const API_BASE = window.location.origin;

// ── 状态 ──
let currentProjectId = null;
let currentPage = 'projects';
let wsConnection = null;

// ── WebSocket 连接 ──
function connectWebSocket(projectId) {
    if (wsConnection) { wsConnection.close(); }
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/progress/${projectId}`;
    wsConnection = new WebSocket(wsUrl);
    wsConnection.onopen = () => console.log('WebSocket 已连接');
    wsConnection.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
    };
    wsConnection.onclose = () => console.log('WebSocket 已断开');
    wsConnection.onerror = (err) => console.error('WebSocket 错误:', err);
}

function handleWSMessage(msg) {
    switch(msg.type) {
        case 'connected':
            console.log('WebSocket 连接确认:', msg.project_id);
            break;
        case 'task_start':
            showProgress(msg.chapter, 0, msg.message || '开始...');
            break;
        case 'task_progress':
            updateProgress(msg.percent, msg.message);
            break;
        case 'task_complete':
            hideProgress();
            showToast(`${msg.chapter || '任务'} 完成，字数: ${msg.result?.word_count || 0}`, 'success');
            loadDrafts();
            break;
        case 'task_error':
            hideProgress();
            showToast(`错误: ${msg.error}`, 'error');
            break;
    }
}

// ── 进度条 ──
function showProgress(chapter, percent, message) {
    let bar = document.getElementById('progress-bar');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'progress-bar';
        bar.className = 'progress-bar';
        bar.innerHTML = `<div class="progress-fill" style="width:0%"></div><div class="progress-text"></div>`;
        document.getElementById('tab-content').prepend(bar);
    }
    bar.style.display = 'block';
    bar.querySelector('.progress-fill').style.width = percent + '%';
    bar.querySelector('.progress-text').textContent = `${chapter}: ${message || percent + '%'}`;
}

function updateProgress(percent, message) {
    const bar = document.getElementById('progress-bar');
    if (bar) {
        bar.querySelector('.progress-fill').style.width = percent + '%';
        bar.querySelector('.progress-text').textContent = message || percent + '%';
    }
}

function hideProgress() {
    const bar = document.getElementById('progress-bar');
    if (bar) setTimeout(() => bar.style.display = 'none', 2000);
}

// ── 页面路由 ──
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    document.querySelectorAll('.nav-links a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
    currentPage = page;
    if (page === 'projects') loadProjects();
}

// ── Toast 通知 ──
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ── 项目列表 ──
async function loadProjects() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects`);
        const projects = await res.json();
        const list = document.getElementById('project-list');
        if (projects.length === 0) {
            list.innerHTML = '<div class="empty-state"><p>暂无项目，点击"新建项目"开始</p></div>';
            return;
        }
        list.innerHTML = projects.map(p => `
            <div class="card" onclick="openProject('${p.id}')">
                <h3>${p.name}</h3>
                <p class="meta">${p.region} · ${p.period} · ${p.planning_type}</p>
                <p class="meta">目标: ${p.target_words?.toLocaleString() || 0} 字</p>
                <span class="badge badge-${p.status === 'active' ? 'success' : 'default'}">${p.status}</span>
            </div>
        `).join('');
    } catch(e) {
        showToast('加载项目列表失败', 'error');
    }
}

async function openProject(id) {
    currentProjectId = id;
    connectWebSocket(id);
    showPage('project');
    await loadProjectDetail();
    await loadOutline();
}

async function loadProjectDetail() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}`);
        const project = await res.json();
        document.getElementById('project-title').textContent = project.name;
    } catch(e) { console.error('加载项目详情失败', e); }
}

// ── 创建项目 ──
function showCreateProject() {
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal(e) {
    if (!e || e.target === document.getElementById('modal-overlay') || e.target.closest('.modal') === null) {
        document.getElementById('modal-overlay').classList.remove('active');
    }
}

async function createProject(e) {
    e.preventDefault();
    const form = e.target;
    const data = Object.fromEntries(new FormData(form));
    data.target_words = parseInt(data.target_words) || 50000;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error('创建失败');
        closeModal();
        showToast('项目创建成功', 'success');
        loadProjects();
    } catch(e) {
        showToast('创建项目失败: ' + e.message, 'error');
    }
}

// ── Tab 切换 ──
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const tabName = tab.dataset.tab;
        if (tabName === 'documents') loadDocuments();
        else if (tabName === 'outline') loadOutline();
        else if (tabName === 'tasks') loadTasks();
        else if (tabName === 'drafts') loadDrafts();
        else if (tabName === 'quality') loadQualityReport();
    });
});

// ── 资料管理 ──
async function loadDocuments() {
    if (!currentProjectId) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/documents`);
        const docs = await res.json();
        const content = document.getElementById('tab-content');
        
        // 上传区域
        let html = `<div class="upload-area" id="upload-area">
            <h3>📤 上传资料</h3>
            <p>支持 PDF、Word、Excel、Markdown、TXT 格式</p>
            <input type="file" id="file-input" accept=".pdf,.docx,.doc,.xlsx,.xls,.md,.txt,.csv" style="margin:10px 0">
            <button class="btn btn-primary" onclick="uploadFile()">上传</button>
            <div id="upload-status" style="margin-top:10px"></div>
        </div>`;
        
        if (!docs.length) {
            html += '<div class="empty-state"><p>暂无资料，请上传相关文件</p></div>';
        } else {
            html += '<div class="doc-list">';
            docs.forEach(d => {
                html += `<div class="doc-card">
                    <div class="doc-info">
                        <strong>${d.file_name}</strong>
                        <span class="meta">${d.file_type} · ${d.file_size ? (d.file_size/1024).toFixed(1)+'KB' : ''}</span>
                        <span class="badge badge-${d.parse_status === 'completed' ? 'success' : 'default'}">${d.parse_status}</span>
                        ${d.chunk_count ? `<span class="meta">分块: ${d.chunk_count}</span>` : ''}
                    </div>
                    <button class="btn btn-sm btn-danger" onclick="deleteDocument('${d.id}')">删除</button>
                </div>`;
            });
            html += '</div>';
        }
        content.innerHTML = html;
    } catch(e) {
        document.getElementById('tab-content').innerHTML = '<p class="error">加载资料失败</p>';
    }
}

async function uploadFile() {
    const input = document.getElementById('file-input');
    const status = document.getElementById('upload-status');
    if (!input.files.length) { showToast('请选择文件', 'warning'); return; }
    const formData = new FormData();
    formData.append('file', input.files[0]);
    status.textContent = '上传中...';
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/documents`, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error('上传失败');
        const result = await res.json();
        showToast('上传成功', 'success');
        loadDocuments();
    } catch(e) {
        status.textContent = '上传失败: ' + e.message;
    }
}

async function deleteDocument(docId) {
    if (!confirm('确定删除该资料？')) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/documents/${docId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('删除失败');
        showToast('已删除', 'success');
        loadDocuments();
    } catch(e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

// ── 大纲 ──
async function loadOutline() {
    if (!currentProjectId) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/outline`);
        const nodes = await res.json();
        const content = document.getElementById('tab-content');
        if (!nodes.length) {
            content.innerHTML = '<div class="empty-state"><p>暂无大纲，点击"生成大纲"开始</p></div>';
            return;
        }
        let html = '<div class="outline-tree">';
        const chapters = nodes.filter(n => n.level === 1);
        chapters.forEach(ch => {
            html += `<div class="outline-chapter">
                <h3>${ch.title} <span class="word-count">(${ch.target_words}字)</span></h3>
                <ul class="outline-sections">`;
            const sections = nodes.filter(n => n.level === 2 && n.parent_id === ch.id);
            sections.forEach(sec => {
                html += `<li>${sec.title} <span class="word-count">(${sec.target_words}字)</span>
                    <div class="evidence-types">依据: ${sec.required_evidence_types?.join(', ') || '不限'}</div>
                </li>`;
            });
            html += '</ul></div>';
        });
        html += '</div>';
        content.innerHTML = html;
    } catch(e) {
        document.getElementById('tab-content').innerHTML = '<p class="error">加载大纲失败</p>';
    }
}

async function generateOutline() {
    if (!currentProjectId) return;
    showToast('正在生成大纲...');
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/outline/generate`, { method: 'POST' });
        if (!res.ok) throw new Error('生成失败');
        const result = await res.json();
        showToast(result.message, 'success');
        // 自动生成检索任务
        await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/tasks/generate`, { method: 'POST' });
        loadOutline();
    } catch(e) {
        showToast('生成大纲失败: ' + e.message, 'error');
    }
}

// ── 任务 ──
async function loadTasks() {
    if (!currentProjectId) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/tasks`);
        const tasks = await res.json();
        const content = document.getElementById('tab-content');
        if (!tasks.length) {
            content.innerHTML = '<div class="empty-state"><p>暂无任务，先生成大纲</p></div>';
            return;
        }
        let html = '<div class="task-list">';
        tasks.forEach(t => {
            html += `<div class="task-card">
                <div class="task-header">
                    <span class="task-title">${t.title_path?.join(' / ') || t.outline_id}</span>
                    <span class="badge badge-${t.status === 'completed' ? 'success' : 'default'}">${t.status}</span>
                </div>
                <p>目标: ${t.target_words}字 | 依据: ${t.required_evidence_types?.join(', ') || '不限'}</p>
                <details>
                    <summary>检索问题 (${t.retrieval_queries?.length || 0})</summary>
                    <ul>${(t.retrieval_queries || []).map(q => `<li>${q}</li>`).join('')}</ul>
                </details>
                <button class="btn btn-sm btn-primary" onclick="generateSingleDraft('${t.id}')">生成草稿</button>
            </div>`;
        });
        html += '</div>';
        content.innerHTML = html;
    } catch(e) {
        document.getElementById('tab-content').innerHTML = '<p class="error">加载任务失败</p>';
    }
}

async function generateSingleDraft(taskId) {
    if (!currentProjectId) return;
    showProgress('章节生成', 0, '开始生成草稿...');
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/tasks/${taskId}/generate-draft`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skip_llm: true })  // 默认用模拟数据，真实 LLM 需要配置 API Key
        });
        if (!res.ok) throw new Error('生成失败');
        const result = await res.json();
        hideProgress();
        showToast(`草稿生成完成: ${result.word_count}字`, 'success');
        loadDrafts();
    } catch(e) {
        hideProgress();
        showToast('生成失败: ' + e.message, 'error');
    }
}

// ── 草稿 ──
async function loadDrafts() {
    if (!currentProjectId) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/drafts`);
        const drafts = await res.json();
        const content = document.getElementById('tab-content');
        if (!drafts.length) {
            content.innerHTML = '<div class="empty-state"><p>暂无草稿，点击任务页面的"生成草稿"开始</p></div>';
            return;
        }
        let html = '<div class="draft-list">';
        drafts.forEach(d => {
            html += `<div class="draft-card">
                <div class="draft-header">
                    <h3>${d.title || d.outline_id}</h3>
                    <span class="word-count">${d.content?.length || 0}字</span>
                </div>
                <details open>
                    <summary>查看/编辑内容</summary>
                    <div class="draft-editor" data-outline="${d.outline_id}">
                        <textarea class="tinymce-editor" id="editor-${d.outline_id}">${(d.content || '(空)').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</textarea>
                        <div class="editor-actions">
                            <button class="btn btn-sm btn-primary" onclick="saveDraft('${d.outline_id}')">保存</button>
                            <span class="save-status" id="status-${d.outline_id}"></span>
                        </div>
                    </div>
                </details>
            </div>`;
        });
        html += '</div>';
        content.innerHTML = html;
    } catch(e) {
        document.getElementById('tab-content').innerHTML = '<p class="error">加载草稿失败</p>';
    }
}

async function generateDrafts() {
    if (!currentProjectId) return;
    showProgress('批量生成', 0, '开始生成所有章节草稿...');
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skip_llm: true })
        });
        if (!res.ok) throw new Error('生成失败');
        const result = await res.json();
        hideProgress();
        showToast(result.message, 'success');
        loadDrafts();
    } catch(e) {
        hideProgress();
        showToast('批量生成失败: ' + e.message, 'error');
    }
}

// ── 质检 ──
async function runQualityCheck() {
    if (!currentProjectId) return;
    showToast('正在执行质检...');
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/quality-check`, { method: 'POST' });
        if (!res.ok) throw new Error('质检失败');
        const result = await res.json();
        showToast(`质检完成: ${result.errors}个错误, ${result.warnings}个警告`, result.errors > 0 ? 'warning' : 'success');
        document.querySelector('.tab[data-tab="quality"]').click();
    } catch(e) {
        showToast('质检失败: ' + e.message, 'error');
    }
}

function loadQualityReport() {
    if (!currentProjectId) return;
    fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/quality-check`)
        .then(r => r.json())
        .then(result => {
            const content = document.getElementById('tab-content');
            if (!result.findings || result.findings.length === 0) {
                content.innerHTML = '<div class="empty-state"><p>✅ 未发现问题</p></div>';
                return;
            }
            let html = `<div class="quality-summary">
                <span class="badge badge-error">${result.errors} 错误</span>
                <span class="badge badge-warning">${result.warnings} 警告</span>
            </div>
            <div class="quality-findings">`;
            result.findings.forEach(f => {
                html += `<div class="finding finding-${f.severity}">
                    <span class="finding-code">${f.code}</span>
                    <span class="finding-location">${f.location}</span>
                    <p>${f.message}</p>
                    <p class="suggestion">建议: ${f.suggestion}</p>
                </div>`;
            });
            html += '</div>';
            content.innerHTML = html;
        }).catch(e => {
            document.getElementById('tab-content').innerHTML = '<p class="error">加载质检报告失败</p>';
        });
}

// ── 一键执行 ──
async function runFullPipeline() {
    if (!currentProjectId) return;
    showProgress('一键执行', 0, '开始完整流程...');
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/run-full`, { method: 'POST' });
        if (!res.ok) throw new Error('执行失败');
        const result = await res.json();
        updateProgress(100, '完成');
        hideProgress();
        showToast(result.message, 'success');
        loadOutline();
        loadDrafts();
    } catch(e) {
        hideProgress();
        showToast('执行失败: ' + e.message, 'error');
    }
}

// ── 导出 ──
async function exportMarkdown() {
    if (!currentProjectId) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/export/markdown`, { method: 'POST' });
        if (!res.ok) throw new Error('导出失败');
        const result = await res.json();
        // 下载文件
        const blob = new Blob([result.content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentProjectId}_output.md`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('导出成功', 'success');
    } catch(e) {
        showToast('导出失败: ' + e.message, 'error');
    }
}

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    // 添加导出按钮到 actions-bar
    const actionsBar = document.querySelector('.actions-bar');
    if (actionsBar && !actionsBar.querySelector('[onclick*="export"]')) {
        const exportBtn = document.createElement('button');
        exportBtn.className = 'btn';
        exportBtn.textContent = '📥 导出 Markdown';
        exportBtn.onclick = exportMarkdown;
        actionsBar.appendChild(exportBtn);
    }
});


// ── TinyMCE Rich Text Editor (S4) ──────────────────────

function initTinyMCE() {
    document.querySelectorAll('.tinymce-editor').forEach(textarea => {
        if (textarea.dataset.initialized) return;
        textarea.dataset.initialized = 'true';
        
        tinymce.init({
            target: textarea,
            language: 'zh_CN',
            plugins: 'lists link table code wordcount',
            toolbar: 'undo redo | formatselect | bold italic | alignleft aligncenter alignright | bullist numlist | table | link | code',
            menubar: false,
            height: 400,
            setup: function(editor) {
                editor.on('change', function() {
                    editor.save(); // 同步到 textarea
                }
            }
        });
    });
}

async function saveDraft(outlineId) {
    const statusEl = document.getElementById('status-' + outlineId);
    statusEl.textContent = '保存中...';
    
    const editor = tinymce.get('editor-' + outlineId);
    const content = editor ? editor.getContent() : document.getElementById('editor-' + outlineId).value;
    
    try {
        const res = await fetch(`${API_BASE}/api/v1/projects/${currentProjectId}/drafts/${outlineId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });
        if (!res.ok) throw new Error('保存失败');
        const result = await res.json();
        statusEl.textContent = `✓ 已保存 (${result.word_count}字)`;
        statusEl.style.color = '#059669';
    } catch(e) {
        statusEl.textContent = '✗ 保存失败: ' + e.message;
        statusEl.style.color = '#dc2626';
    }
}

// 在 loadDrafts 完成后初始化 TinyMCE
const originalLoadDrafts = loadDrafts;
loadDrafts = async function() {
    await originalLoadDrafts();
    // 延迟初始化 TinyMCE（确保 DOM 已更新）
    setTimeout(initTinyMCE, 100);
};
