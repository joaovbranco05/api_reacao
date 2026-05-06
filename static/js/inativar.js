/**
 * inativar.js
 * Lógica de frontend para a página de Inativação de Matrículas em Lote.
 * Depende de app.js (checkAuth, requireAuth, logout, showStatus, hideStatus).
 */

// Estado do módulo
let _pendingFile = null;
let _lastResultados = null;

// ──────────────────────────────────────────────
// Inicialização da página
// ──────────────────────────────────────────────
function initInativar() {
    requireAuth().then(data => {
        if (data) {
            document.getElementById('professor-badge').textContent = data.professor_id;
        }
    });
    setupUploadInativar();
}

// ──────────────────────────────────────────────
// Setup da área de upload
// ──────────────────────────────────────────────
function setupUploadInativar() {
    const fileInput = document.getElementById('excel-inativar');
    const fileNameEl = document.getElementById('file-name-inativar');
    const uploadArea = document.getElementById('upload-area-inativar');

    if (!fileInput) return;

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            const f = fileInput.files[0];
            fileNameEl.textContent = `📎 ${f.name}`;
            fileNameEl.className = 'file-name visible';
            _pendingFile = f;
        }
    });

    // Clicar na área de upload abre o seletor de arquivo
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== fileInput) fileInput.click();
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) {
            const f = files[0];
            if (!f.name.toLowerCase().endsWith('.xlsx')) {
                showStatus('inativar-status', '❌ Apenas arquivos .xlsx são aceitos.', 'error');
                return;
            }
            fileInput.files = files; // não suportado em todos os browsers, mas funciona no Chrome
            _pendingFile = f;
            fileNameEl.textContent = `📎 ${f.name}`;
            fileNameEl.className = 'file-name visible';
        }
    });
}

// ──────────────────────────────────────────────
// Fluxo de confirmação
// ──────────────────────────────────────────────
function confirmarInativacao(event) {
    event.preventDefault();

    const fileInput = document.getElementById('excel-inativar');
    if (!fileInput.files.length && !_pendingFile) {
        showStatus('inativar-status', '❌ Selecione um arquivo Excel (.xlsx).', 'error');
        return;
    }

    _pendingFile = fileInput.files[0] || _pendingFile;

    // Mostra modal de confirmação
    const msg = document.getElementById('confirm-msg');
    msg.innerHTML = `Tem certeza que deseja inativar as matrículas do arquivo:<br>
        <strong>${_pendingFile.name}</strong>?<br><br>
        Esta ação <strong>não pode ser desfeita automaticamente</strong>.`;

    document.getElementById('confirm-overlay').classList.add('visible');
}

function cancelarConfirmacao() {
    document.getElementById('confirm-overlay').classList.remove('visible');
}

// ──────────────────────────────────────────────
// Execução da inativação
// ──────────────────────────────────────────────
async function executarInativacao() {
    cancelarConfirmacao();

    if (!_pendingFile) {
        showStatus('inativar-status', '❌ Nenhum arquivo selecionado.', 'error');
        return;
    }

    const btn = document.getElementById('btn-inativar');
    const progressWrap = document.getElementById('progress-wrap');
    const progressBar = document.getElementById('progress-bar');
    const downloadBtn = document.getElementById('btn-download');

    // Resetar UI
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Processando...';
    downloadBtn.classList.remove('visible');
    _lastResultados = null;
    limparResultados();

    showStatus('inativar-status', '⏳ Enviando planilha para a API EAD...', 'loading');
    progressWrap.classList.add('visible');

    // Animar barra de progresso enquanto espera (indeterminado)
    let progVal = 0;
    const progInterval = setInterval(() => {
        progVal = Math.min(progVal + 1.2, 88);
        progressBar.style.width = progVal + '%';
    }, 180);

    const formData = new FormData();
    formData.append('file', _pendingFile);

    try {
        const resp = await fetch('/api/inativar-lote', {
            method: 'POST',
            body: formData,
        });

        clearInterval(progInterval);
        progressBar.style.width = '100%';

        const data = await resp.json();

        if (data.status === 'sucesso') {
            const tipo = data.erros > 0 ? 'error' : 'success';
            showStatus(
                'inativar-status',
                `✅ Concluído! Inativados: ${data.ok} | Erros: ${data.erros} | Total: ${data.total}`,
                tipo
            );
            _lastResultados = data;
            renderResultadosInativar(data);
            if (data.resultados && data.resultados.length > 0) {
                downloadBtn.classList.add('visible');
            }
        } else {
            showStatus('inativar-status', `❌ ${data.mensagem}`, 'error');
        }

    } catch (err) {
        clearInterval(progInterval);
        progressBar.style.width = '0%';
        showStatus('inativar-status', `❌ Erro de conexão: ${err.message}`, 'error');
    } finally {
        setTimeout(() => {
            progressWrap.classList.remove('visible');
            progressBar.style.width = '0%';
        }, 800);

        btn.disabled = false;
        btn.innerHTML = '🚫 Iniciar Inativação em Lote';
    }
}

// ──────────────────────────────────────────────
// Renderização de resultados
// ──────────────────────────────────────────────
function renderResultadosInativar(data) {
    const section = document.getElementById('results-section-inativar');
    const tbody = document.getElementById('results-body-inativar');
    const summaryEl = document.getElementById('results-summary-inativar');

    if (!data.resultados || data.resultados.length === 0) {
        section.className = 'results-section';
        return;
    }

    const inativados = data.resultados.filter(r =>
        r.status && r.status.toLowerCase().includes('inativado')
    ).length;
    const naoEncontrados = data.resultados.filter(r =>
        r.status && r.status.toLowerCase().includes('encontrado')
    ).length;
    const erros = data.resultados.filter(r =>
        r.status && (r.status.toLowerCase().includes('erro') || r.status.toLowerCase().includes('api'))
    ).length;

    summaryEl.innerHTML = `
        <span class="summary-badge total">📄 Total: ${data.total}</span>
        <span class="summary-badge inativado">🚫 Inativados: ${inativados}</span>
        <span class="summary-badge ok">✅ OK: ${data.ok}</span>
        <span class="summary-badge err">❌ Erros: ${data.erros}</span>
    `;

    tbody.innerHTML = data.resultados.map(r => {
        const statusLower = (r.status || '').toLowerCase();
        let badgeClass = 'err';
        if (statusLower.includes('inativado')) badgeClass = 'inativado';
        else if (statusLower === 'ok' || statusLower === 'sucesso') badgeClass = 'ok';

        return `
        <tr>
            <td>${r.linha}</td>
            <td>${escapeHtml(r.nome_aluno || '')}</td>
            <td>${escapeHtml(r.nome_curso || '')}</td>
            <td class="col-matricula">${r.matricula_id || '—'}</td>
            <td><span class="status-badge ${badgeClass}">${escapeHtml(r.status || '')}</span></td>
            <td>${escapeHtml(r.mensagem || '')}</td>
        </tr>
        `;
    }).join('');

    section.className = 'results-section visible';
}

function limparResultados() {
    document.getElementById('results-section-inativar').className = 'results-section';
    document.getElementById('results-body-inativar').innerHTML = '';
    document.getElementById('results-summary-inativar').innerHTML = '';
}

// ──────────────────────────────────────────────
// Download do relatório Excel
// ──────────────────────────────────────────────
async function downloadRelatorio() {
    if (!_pendingFile) return;

    const btn = document.getElementById('btn-download');
    btn.textContent = '⏳ Gerando relatório...';
    btn.disabled = true;

    const formData = new FormData();
    formData.append('file', _pendingFile);

    try {
        const resp = await fetch('/api/inativar-lote/download', {
            method: 'POST',
            body: formData,
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ mensagem: resp.statusText }));
            showStatus('inativar-status', `❌ Erro ao gerar relatório: ${err.mensagem || resp.statusText}`, 'error');
            return;
        }

        // Obtém nome do arquivo do header Content-Disposition
        const disposition = resp.headers.get('Content-Disposition') || '';
        let filename = 'resultado_inativacao.xlsx';
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match) filename = match[1];

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        showStatus('inativar-status', `❌ Erro ao baixar relatório: ${err.message}`, 'error');
    } finally {
        btn.innerHTML = '⬇️ Baixar Relatório (.xlsx)';
        btn.disabled = false;
    }
}

// ──────────────────────────────────────────────
// Utilitário
// ──────────────────────────────────────────────
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
