// ===== API Helper =====
async function apiRequest(url, options = {}) {
    try {
        const resp = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
        return await resp.json();
    } catch (err) {
        return { status: 'erro', mensagem: `Erro de conexão: ${err.message}` };
    }
}

// ===== Status Display =====
function showStatus(elementId, message, type) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.className = `status visible ${type}`;
    el.innerHTML = message;
}

function hideStatus(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.className = 'status';
}

// ===== Auth Check =====
async function checkAuth() {
    const data = await apiRequest('/api/me');
    return data;
}

async function requireAuth() {
    const data = await checkAuth();
    if (!data.logged_in) {
        window.location.href = '/';
        return null;
    }
    return data;
}

// ===== Login =====
async function login(event) {
    event.preventDefault();
    const btn = document.getElementById('btn-login');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Entrando...';
    hideStatus('login-status');

    const professor_id = document.getElementById('professor-id').value.trim();
    const senha = document.getElementById('senha').value;

    const data = await apiRequest('/api/login', {
        method: 'POST',
        body: JSON.stringify({ professor_id, senha }),
    });

    if (data.status === 'sucesso') {
        showStatus('login-status', '✅ Login realizado! Redirecionando...', 'success');
        setTimeout(() => window.location.href = '/lote.html', 800);
    } else {
        showStatus('login-status', `❌ ${data.mensagem}`, 'error');
        btn.disabled = false;
        btn.innerHTML = 'Entrar';
    }
}

// ===== Logout =====
async function logout() {
    await apiRequest('/api/logout', { method: 'POST' });
    window.location.href = '/';
}


// ===== Enviar Lote Excel =====
async function enviarLote(event) {
    event.preventDefault();
    const fileInput = document.getElementById('excel-file');
    const btn = document.getElementById('btn-lote');

    if (!fileInput.files.length) {
        showStatus('lote-status', '❌ Selecione um arquivo Excel (.xlsx)', 'error');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Processando...';
    showStatus('lote-status', '⏳ Enviando planilha para processamento...', 'loading');

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const resp = await fetch('/api/lote', {
            method: 'POST',
            body: formData,
        });
        const data = await resp.json();

        if (data.status === 'sucesso') {
            showStatus('lote-status',
                `✅ Finalizado! OK: ${data.ok} | Erros: ${data.erros} de ${data.total}`,
                data.erros > 0 ? 'error' : 'success'
            );
            renderResults(data);
        } else {
            showStatus('lote-status', `❌ ${data.mensagem}`, 'error');
        }
    } catch (err) {
        showStatus('lote-status', `❌ Erro de conexão: ${err.message}`, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = 'Enviar Planilha';
}

function renderResults(data) {
    const section = document.getElementById('results-section');
    const tbody = document.getElementById('results-body');
    const summaryEl = document.getElementById('results-summary');

    if (!data.resultados || data.resultados.length === 0) {
        section.className = 'results-section';
        return;
    }

    summaryEl.innerHTML = `
        <span class="summary-badge total">📄 Total: ${data.total}</span>
        <span class="summary-badge ok">✅ OK: ${data.ok}</span>
        <span class="summary-badge err">❌ Erros: ${data.erros}</span>
    `;

    tbody.innerHTML = data.resultados.map(r => `
        <tr>
            <td>${r.linha}</td>
            <td><span class="status-badge ${r.status === 'sucesso' ? 'ok' : 'err'}">${r.status}</span></td>
            <td>${r.mensagem}</td>
        </tr>
    `).join('');

    section.className = 'results-section visible';
}

// ===== File Upload UI =====
function setupUpload() {
    const fileInput = document.getElementById('excel-file');
    const fileNameEl = document.getElementById('file-name');
    const uploadArea = document.getElementById('upload-area');

    if (!fileInput) return;

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            fileNameEl.textContent = `📎 ${fileInput.files[0].name}`;
            fileNameEl.className = 'file-name visible';
        }
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', () => {
        uploadArea.classList.remove('dragover');
    });
}

// ===== Init Pages =====


function initLote() {
    requireAuth().then(data => {
        if (data) {
            document.getElementById('professor-badge').textContent = data.professor_id;
        }
    });
    setupUpload();
}
