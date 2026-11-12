
async function safeJson(res) {
  const rawText = await res.text();
  try {
    return rawText ? JSON.parse(rawText) : {};
  } catch (e) {
    return {};
  }
}

// ==========================================================================
// Gerador Interativo de Legendas com IA
// ==========================================================================
let currentAiTone = 'academia';
let lastGeneratedCaptions = [];

function openAiCaptionModal() {
  const currentVal = document.getElementById('captionInput').value.trim();
  if (currentVal && !document.getElementById('aiTopicInput').value) {
    document.getElementById('aiTopicInput').value = currentVal.substring(0, 100);
  } else if (!document.getElementById('aiTopicInput').value) {
    // Tenta sugerir o tema pelo nome do arquivo enviado (ex: foto_academia, praia.jpg)
    const fileInput = document.getElementById('mediaInput');
    if (fileInput.files && fileInput.files.length > 0) {
      const fileName = fileInput.files[0].name.toLowerCase();
      if (fileName.includes('trein') || fileName.includes('acad') || fileName.includes('gym')) {
        selectAiTone('academia');
      } else if (fileName.includes('praia') || fileName.includes('sol') || fileName.includes('mar') || fileName.includes('piscina')) {
        selectAiTone('praia_piscina');
      }
    }
  }
  document.getElementById('aiCaptionModal').classList.remove('hidden');
}

function closeAiCaptionModal() {
  document.getElementById('aiCaptionModal').classList.add('hidden');
}

function selectAiTone(tone) {
  currentAiTone = tone;
  document.querySelectorAll('.ai-tone-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tone') === tone);
  });
}

async function generateAiCaptions() {
  const topic = document.getElementById('aiTopicInput').value.trim();
  const use_emojis = document.getElementById('aiUseEmojis').checked;
  const include_cta = document.getElementById('aiIncludeCta').checked;
  const use_hashtags = document.getElementById('aiUseHashtags').checked;

  const btn = document.getElementById('btnGenerateAiCaptions');
  const btnText = document.getElementById('btnAiText');
  const spinner = document.getElementById('spinnerAi');

  btn.disabled = true;
  btnText.innerText = 'Criando legendas com IA...';
  spinner.classList.remove('hidden');

  try {
    const scheduledTimeVal = document.getElementById('datetimeInput').value || null;
    const res = await fetch('/api/ai/generate-captions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: topic,
        tone: currentAiTone,
        use_emojis: use_emojis,
        use_hashtags: use_hashtags,
        include_cta: include_cta,
        scheduled_time: scheduledTimeVal
      })
    });

    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.detail || 'Falha ao gerar legendas.');

    lastGeneratedCaptions = data.captions || [];
    renderAiCaptionsList();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btnText.innerText = '✨ Gerar Novas Opções';
    spinner.classList.add('hidden');
  }
}

function renderAiCaptionsList() {
  const container = document.getElementById('aiResultsContainer');
  const list = document.getElementById('aiCardsList');

  if (lastGeneratedCaptions.length === 0) {
    container.classList.add('hidden');
    return;
  }

  container.classList.remove('hidden');
  list.innerHTML = lastGeneratedCaptions.map((caption, index) => {
    // Escapa string para passar de forma segura para função onclick
    const safeCaption = encodeURIComponent(caption);
    return `
      <div class="ai-caption-card">
        <p class="ai-caption-text">${escapeHtml(caption)}</p>
        <div class="ai-caption-footer">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">Opção #${index + 1}</span>
          <div style="display: flex; gap: 0.5rem;">
            <button type="button" class="btn btn-sm btn-ghost" onclick="copyAiCaption('${safeCaption}')" title="Copiar texto">
              📋 Copiar
            </button>
            <button type="button" class="btn btn-sm btn-primary" onclick="useAiCaption('${safeCaption}')">
              ✅ Usar no Story
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function useAiCaption(encodedCaption) {
  const text = decodeURIComponent(encodedCaption);
  const input = document.getElementById('captionInput');
  input.value = text;
  updateCharCount();
  closeAiCaptionModal();
  showToast('Legenda inserida no story com sucesso!', 'success');
  input.focus();
}

function copyAiCaption(encodedCaption) {
  const text = decodeURIComponent(encodedCaption);
  navigator.clipboard.writeText(text).then(() => {
    showToast('Legenda copiada para a área de transferência!', 'info');
  }).catch(() => {
    showToast('Não foi possível copiar automaticamente.', 'error');
  });
}


function openGridConfirmModal() {
  document.getElementById('gridConfirmModal').classList.remove('hidden');
}

function closeGridConfirmModal() {
  document.getElementById('gridConfirmModal').classList.add('hidden');
}

function confirmGridChoice(choice) {
  syncPin(choice);
  closeGridConfirmModal();
  executeScheduleSubmit();
}

async function toggleGridStory(id) {
  try {
    const res = await fetch(`/api/stories/${id}/toggle-grid`, { method: 'POST' });
    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.detail || 'Falha ao alterar grade.');
    showToast(data.pinned ? 'Story adicionado à grade do perfil!' : 'Story removido da grade do perfil.', 'success');
    loadStories();
  } catch (err) {
    showToast(err.message, 'error');
  }
}
/**
 * Telegram Story Scheduler - Frontend Application
 * Interações em tempo real, agendamento de stories e conexão MTProto.
 */

let currentAuthSessionToken = null;
let currentFilter = 'all';
let allStories = [];
let autoRefreshTimer = null;
let currentEditingStoryId = null;

// ==========================================================================
// Inicialização
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initDatetimePicker();
  setupDragAndDrop();
  resetGridChoice();
  
  const accountSelect = document.getElementById('accountSelect');
  if (accountSelect) {
    accountSelect.addEventListener('change', (e) => {
      const newId = Number(e.target.value);
      if (newId) {
        currentSelectedAccountId = newId;
        renderAccountsHeader();
        loadStories();
      }
    });
  }

  checkAccountStatus();

  // Polling automático a cada 10 segundos para manter status e logs sincronizados
  autoRefreshTimer = setInterval(() => {
    loadStories(true);
  }, 10000);
});

// ==========================================================================
// Relógio e Fuso Horário (America/Fortaleza)
// ==========================================================================
function getFortalezaDate() {
  // Converte a hora atual do navegador para o fuso America/Fortaleza
  const now = new Date();
  const options = { timeZone: 'America/Fortaleza', hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' };
  const formatter = new Intl.DateTimeFormat([], options);
  const parts = formatter.formatToParts(now);
  const partMap = {};
  parts.forEach(p => partMap[p.type] = p.value);

  return new Date(`${partMap.year}-${partMap.month}-${partMap.day}T${partMap.hour}:${partMap.minute}:${partMap.second}`);
}

function initClock() {
  const clockEl = document.getElementById('currentClock');
  function updateClock() {
    const d = new Date();
    clockEl.innerText = d.toLocaleTimeString('pt-BR', { timeZone: 'America/Fortaleza' });
  }
  updateClock();
  setInterval(updateClock, 1000);
}

function initDatetimePicker() {
  const dtInput = document.getElementById('datetimeInput');
  const d = getFortalezaDate();

  // Sugere 5 minutos à frente como padrão
  d.setMinutes(d.getMinutes() + 5);

  const pad = n => String(n).padStart(2, '0');
  const currentFormatted = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

  dtInput.value = currentFormatted;

  // Define o mínimo permitido (agora em Fortaleza)
  const nowF = getFortalezaDate();
  const minFormatted = `${nowF.getFullYear()}-${pad(nowF.getMonth() + 1)}-${pad(nowF.getDate())}T${pad(nowF.getHours())}:${pad(nowF.getMinutes())}`;
  dtInput.min = minFormatted;
}

function updateCharCount() {
  const val = document.getElementById('captionInput').value;
  document.getElementById('captionCount').innerText = `${val.length} / 2048`;
}

// ==========================================================================
// Upload e Pré-visualização de Mídia
// ==========================================================================
function setupDragAndDrop() {
  const dropZone = document.getElementById('dropZone');

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
    }, false);
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
  });

  dropZone.addEventListener('drop', e => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      document.getElementById('mediaInput').files = files;
      processSelectedFile(files[0]);
    }
  });
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) {
    processSelectedFile(file);
  }
}

function processSelectedFile(file) {
  const maxBytes = 50 * 1024 * 1024;
  if (file.size > maxBytes) {
    showToast('O arquivo excede o limite máximo permitido de 50MB.', 'error');
    removeMedia();
    return;
  }

  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/quicktime'];
  if (!allowed.includes(file.type)) {
    showToast('Formato inválido. Use JPG, PNG, WEBP ou MP4.', 'error');
    removeMedia();
    return;
  }

  const prompt = document.getElementById('uploadPrompt');
  const previewContainer = document.getElementById('mediaPreviewContainer');
  const imgEl = document.getElementById('imgPreview');
  const videoEl = document.getElementById('videoPreview');

  const fileUrl = URL.createObjectURL(file);

  prompt.classList.add('hidden');
  previewContainer.classList.remove('hidden');

  const audioGroup = document.getElementById('videoAudioGroup');
  const keepAudioRadio = document.getElementById('keepAudioRadio');

  if (file.type.startsWith('image/')) {
    imgEl.src = fileUrl;
    imgEl.classList.remove('hidden');
    videoEl.classList.add('hidden');
    videoEl.pause();
    videoEl.muted = false;
    if (audioGroup) audioGroup.classList.add('hidden');
    if (keepAudioRadio) keepAudioRadio.checked = true;
  } else if (file.type.startsWith('video/')) {
    videoEl.src = fileUrl;
    videoEl.classList.remove('hidden');
    imgEl.classList.add('hidden');
    if (keepAudioRadio) keepAudioRadio.checked = true;
    videoEl.muted = false;
    if (audioGroup) audioGroup.classList.remove('hidden');
  }
}

function syncVideoAudioPreview() {
  const removeAudio = document.getElementById('removeAudioRadio')?.checked === true;
  const videoEl = document.getElementById('videoPreview');
  if (videoEl) {
    videoEl.muted = removeAudio;
  }
}

// Resposta da pergunta "postar na grade?": padrão sempre true (Sim, na grade)
let gridChoice = true;

// Mantém a pergunta do formulário e o botão sobre a foto sempre iguais
function syncPin(on) {
  gridChoice = on;
  document.getElementById('pinnedInput').checked = on;
  document.getElementById('gridYes').checked = on;
  document.getElementById('gridNo').checked = !on;
  document.getElementById('gridQuestion').classList.remove('needs-answer');
  renderPinOverlay();
}

function renderPinOverlay() {
  const on = gridChoice === true;
  document.getElementById('pinOverlayInput').checked = on;
  document.getElementById('pinOverlayText').innerText =
    gridChoice === null ? 'Postar na grade? Escolha' : on ? 'Vai para a grade do perfil' : 'Só nos Stories';
  document.getElementById('mediaPreviewContainer').classList.toggle('is-pinned', on);
}

function resetGridChoice() {
  syncPin(true);
  const p48 = document.querySelector('input[name="period"][value="172800"]');
  if (p48) p48.checked = true;
  const priv = document.getElementById('privacyInput');
  if (priv) priv.value = 'all';
}

function removeMedia(e) {
  if (e) {
    e.stopPropagation();
  }
  renderPinOverlay();
  document.getElementById('mediaInput').value = '';
  document.getElementById('imgPreview').src = '';
  const videoEl = document.getElementById('videoPreview');
  videoEl.src = '';
  videoEl.muted = false;
  document.getElementById('imgPreview').classList.add('hidden');
  videoEl.classList.add('hidden');
  document.getElementById('mediaPreviewContainer').classList.add('hidden');
  document.getElementById('uploadPrompt').classList.remove('hidden');
  const audioGroup = document.getElementById('videoAudioGroup');
  if (audioGroup) audioGroup.classList.add('hidden');
  const keepAudioRadio = document.getElementById('keepAudioRadio');
  if (keepAudioRadio) keepAudioRadio.checked = true;
}

// ==========================================================================
// Status e Conexão da Conta MTProto
// ==========================================================================
let currentSelectedAccountId = null;
let savedAccountsList = [];

function toggleAccountsMenu(event) {
  if (event) event.stopPropagation();
  const wrapper = document.getElementById('accountsDropdownWrapper');
  const menu = document.getElementById('accountsMenu');
  const isOpen = !menu.classList.contains('hidden');
  if (isOpen) {
    closeAccountsMenu();
  } else {
    menu.classList.remove('hidden');
    wrapper.classList.add('open');
  }
}

function closeAccountsMenu() {
  const wrapper = document.getElementById('accountsDropdownWrapper');
  const menu = document.getElementById('accountsMenu');
  if (menu) menu.classList.add('hidden');
  if (wrapper) wrapper.classList.remove('open');
}

// Fecha o menu ao clicar fora
document.addEventListener('click', (e) => {
  const wrapper = document.getElementById('accountsDropdownWrapper');
  if (wrapper && !wrapper.contains(e.target)) {
    closeAccountsMenu();
  }
});

function switchActiveAccount(accId, event) {
  if (event) event.stopPropagation();
  currentSelectedAccountId = accId;
  const select = document.getElementById('accountSelect');
  if (select) select.value = String(accId);
  renderAccountsHeader();
  closeAccountsMenu();
  const acc = savedAccountsList.find(a => a.id === accId);
  if (acc) {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('account_id', String(acc.id));
      url.searchParams.set('phone', acc.phone || '');
      url.searchParams.set('name', acc.first_name || acc.username || '');
      window.history.replaceState({}, '', url.toString());
    } catch (e) {}
    showToast(`Conta ativa alterada para: ${acc.first_name || acc.username || acc.phone}`, 'info');
  }
  loadStories();
}

function renderAvatarHtml(acc) {
  const rawName = (acc.first_name || acc.username || 'C').trim();
  const initials = escapeHtml(rawName.substring(0, 2).toUpperCase());
  const avatarUrl = acc.avatar_url || `/api/auth/avatar/${acc.id}`;
  return `
    <div class="user-avatar">
      <img src="${escapeHtml(avatarUrl)}" alt="${escapeHtml(rawName)}" class="user-avatar-img"
           onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
      <span class="user-avatar-fallback" style="display:none;">${initials}</span>
    </div>
  `;
}

function renderAccountsHeader() {
  const bar = document.getElementById('accountsBar');
  const menuList = document.getElementById('accountsMenuList');
  const btnConnectHeader = document.getElementById('btnConnectHeader');
  const dropdownWrapper = document.getElementById('accountsDropdownWrapper');

  if (savedAccountsList.length === 0) {
    dropdownWrapper.classList.add('hidden');
    btnConnectHeader.classList.remove('hidden');
    return;
  }

  dropdownWrapper.classList.remove('hidden');
  btnConnectHeader.classList.add('hidden');

  // Encontra conta ativa (ou a primeira por padrão)
  let activeAcc = savedAccountsList.find(a => a.id === currentSelectedAccountId);
  if (!activeAcc) {
    activeAcc = savedAccountsList[0];
    currentSelectedAccountId = activeAcc.id;
  }

  const activeName = escapeHtml(activeAcc.first_name || activeAcc.username || 'Conta');
  const otherCount = savedAccountsList.length - 1;

  // Atualiza badge de identificação da conta no Painel de Stories
  const dashBadge = document.getElementById('dashboardAccountBadge');
  if (dashBadge) {
    dashBadge.innerText = activeName;
    dashBadge.classList.remove('hidden');
  }

  // Renderiza pílula principal no topo (com seta e indicador de outras contas salvas)
  bar.innerHTML = `
    <div class="account-pill connected account-pill-clickable" title="Clique para trocar de conta ou ver contas salvas">
      ${renderAvatarHtml(activeAcc)}
      <div class="account-meta">
        <div class="account-name-row">
          <span class="account-name">${activeName}</span>
          ${activeAcc.is_premium ? '<span class="badge-premium">⭐ Premium</span>' : ''}
        </div>
        <span class="account-phone">${escapeHtml(activeAcc.phone)}</span>
      </div>
      <span class="dropdown-arrow">▼</span>
    </div>
  `;

  // Renderiza a lista suspensa com TODAS as contas salvas
  menuList.innerHTML = savedAccountsList.map(a => {
    const isCurrent = a.id === activeAcc.id;
    const name = escapeHtml(a.first_name || a.username || 'Conta');
    return `
      <div class="account-menu-item ${isCurrent ? 'active' : ''}" onclick="switchActiveAccount(${a.id}, event)">
        <div class="account-item-info">
          ${renderAvatarHtml(a)}
          <div class="account-item-meta">
            <span class="account-item-name">
              ${name}
              ${a.is_premium ? '<span class="badge-premium">⭐</span>' : ''}
              ${isCurrent ? '<small style="color: var(--accent-telegram); font-weight:700;">(Ativa)</small>' : ''}
            </span>
            <span class="account-item-phone">${escapeHtml(a.phone)}</span>
          </div>
        </div>
        <button type="button" class="btn-remove-account" onclick="event.stopPropagation(); disconnectAccount(${a.id})" title="Desconectar e remover esta conta">
          ✕
        </button>
      </div>
    `;
  }).join('');
}

async function checkAccountStatus(preferredAccountId = null) {
  const loading = document.getElementById('accountLoading');
  const select = document.getElementById('accountSelect');

  try {
    let res = await fetch('/api/auth/status');
    if (!res.ok) {
      await new Promise(r => setTimeout(r, 1500));
      res = await fetch('/api/auth/status');
    }
    if (!res.ok) {
      loading.classList.add('hidden');
      showToast('Servidor reiniciando ou banco indisponível no momento. Tente atualizar em alguns segundos.', 'error');
      return;
    }
    const data = await safeJson(res);
    loading.classList.add('hidden');

    savedAccountsList = data.accounts || [];

    // Suporte a redirecionamento direto de conta via URL (?account_id=...&phone=...&name=...)
    let urlMatchedId = null;
    if (!window._urlAccountApplied && savedAccountsList.length > 0) {
      const params = new URLSearchParams(window.location.search);
      const urlPhone = params.get('phone');
      const urlAccId = params.get('account_id') || params.get('account');
      const urlName = params.get('name');
      const normPhone = s => String(s || '').replace(/\D/g, '');

      let matched = null;
      if (urlPhone) {
        const np = normPhone(urlPhone);
        matched = savedAccountsList.find(a => normPhone(a.phone) === np || (np.length >= 9 && normPhone(a.phone).endsWith(np.slice(-9))));
      }
      if (!matched && urlAccId) {
        matched = savedAccountsList.find(a => String(a.id) === String(urlAccId));
      }
      if (!matched && urlName) {
        const nn = urlName.trim().toLowerCase();
        matched = savedAccountsList.find(a => (a.first_name || a.username || '').trim().toLowerCase() === nn);
      }
      if (matched) {
        urlMatchedId = matched.id;
        window._urlAccountApplied = true;
        setTimeout(() => {
          showToast(`Conta sincronizada automaticamente: ${matched.first_name || matched.username || matched.phone}`, 'info');
        }, 300);
      }
    }

    // Seletor de conta do formulário
    const prev = urlMatchedId || preferredAccountId || currentSelectedAccountId || (select ? select.value : null);
    if (savedAccountsList.length === 0) {
      if (select) select.innerHTML = '<option value="">Conecte uma conta primeiro</option>';
      currentSelectedAccountId = null;
      const dashBadge = document.getElementById('dashboardAccountBadge');
      if (dashBadge) dashBadge.classList.add('hidden');
    } else {
      if (select) {
        select.innerHTML = savedAccountsList.map(a =>
          `<option value="${a.id}">${escapeHtml(a.first_name || a.username || 'Conta')} (${escapeHtml(a.phone)})</option>`
        ).join('');
      }
      if (prev && savedAccountsList.some(a => String(a.id) === String(prev))) {
        currentSelectedAccountId = Number(prev);
        if (select) select.value = String(currentSelectedAccountId);
      } else {
        currentSelectedAccountId = savedAccountsList[0].id;
        if (select) select.value = String(currentSelectedAccountId);
      }
    }

    renderAccountsHeader();
    loadStories();
  } catch (err) {
    loading.classList.add('hidden');
  }
}

function openLoginModal() {
  document.getElementById('loginModal').classList.remove('hidden');
  showStep(1);
}

function closeLoginModal() {
  ['apiIdInput', 'apiHashInput', 'codeInput', 'password2FAInput'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('loginModal').classList.add('hidden');
  currentAuthSessionToken = null;
  clearErrors();
}

function showStep(step) {
  document.getElementById('loginStep1').classList.toggle('hidden', step !== 1);
  document.getElementById('loginStep2').classList.toggle('hidden', step !== 2);
  document.getElementById('loginStep3').classList.toggle('hidden', step !== 3);
  clearErrors();
}

function backToStep1() {
  showStep(1);
}

function clearErrors() {
  ['step1Error', 'step2Error', 'step3Error'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.innerText = '';
      el.classList.add('hidden');
    }
  });
}

function showError(stepId, msg) {
  const el = document.getElementById(stepId);
  el.innerText = msg;
  el.classList.remove('hidden');
}

async function handleSendCode() {
  const phone = document.getElementById('phoneInput').value.trim();
  if (!phone) {
    showError('step1Error', 'Digite seu número de telefone com código do país (ex: +55...).');
    return;
  }

  const btn = document.getElementById('btnSendCode');
  const spinner = document.getElementById('spinnerStep1');
  btn.disabled = true;
  spinner.classList.remove('hidden');
  clearErrors();

  try {
    const res = await fetch('/api/auth/send-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone,
        api_id: document.getElementById('apiIdInput').value.trim() || null,
        api_hash: document.getElementById('apiHashInput').value.trim() || null
      })
    });
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || 'Falha ao solicitar código.');
    }

    currentAuthSessionToken = data.session_token;
    document.getElementById('sentPhoneDisplay').innerText = data.phone;
    showStep(2);
    showToast('Código enviado para seu Telegram ou SMS!', 'info');
  } catch (err) {
    showError('step1Error', err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add('hidden');
  }
}

async function handleVerifyCode() {
  const code = document.getElementById('codeInput').value.trim();
  if (!code) {
    showError('step2Error', 'Digite o código recebido.');
    return;
  }

  const btn = document.getElementById('btnVerifyCode');
  const spinner = document.getElementById('spinnerStep2');
  btn.disabled = true;
  spinner.classList.remove('hidden');
  clearErrors();

  try {
    const res = await fetch('/api/auth/verify-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_token: currentAuthSessionToken,
        code: code
      })
    });
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || 'Código inválido.');
    }

    if (data.status === '2fa_required') {
      showStep(3);
      showToast('Autenticação de 2 fatores necessária.', 'info');
    } else {
      closeLoginModal();
      showToast('Conta do Telegram conectada com sucesso!', 'success');
      checkAccountStatus(data.id);
    }
  } catch (err) {
    showError('step2Error', err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add('hidden');
  }
}

async function handleVerify2FA() {
  const password = document.getElementById('password2FAInput').value;
  if (!password) {
    showError('step3Error', 'Digite a senha do 2FA.');
    return;
  }

  const btn = document.getElementById('btnVerify2FA');
  const spinner = document.getElementById('spinnerStep3');
  btn.disabled = true;
  spinner.classList.remove('hidden');
  clearErrors();

  try {
    const res = await fetch('/api/auth/verify-2fa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_token: currentAuthSessionToken,
        password: password
      })
    });
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || 'Senha 2FA incorreta.');
    }

    closeLoginModal();
    showToast('Conta conectada com sucesso!', 'success');
    checkAccountStatus();
  } catch (err) {
    showError('step3Error', err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add('hidden');
  }
}

async function disconnectAccount(id) {
  if (!confirm('Deseja realmente desconectar sua conta do Telegram deste painel?')) {
    return;
  }

  try {
    const res = await fetch(`/api/auth/disconnect/${id}`, { method: 'POST' });
    if (res.ok) {
      showToast('Conta desconectada com sucesso.', 'info');
      if (currentSelectedAccountId === id) {
        currentSelectedAccountId = null;
      }
      checkAccountStatus();
    }
  } catch (err) {
    showToast('Erro ao desconectar conta.', 'error');
  }
}

// ==========================================================================
// Agendamento de Stories (Criação)
// ==========================================================================
async function handleScheduleSubmit(e) {
  e.preventDefault();

  const fileInput = document.getElementById('mediaInput');
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast('Selecione uma foto ou vídeo para o story.', 'error');
    return;
  }

  if (gridChoice === null) {
    const q = document.getElementById('gridQuestion');
    q.classList.add('needs-answer');
    q.scrollIntoView({ behavior: 'smooth', block: 'center' });
    showToast('Escolha se o story deve ser postado também na grade do perfil.', 'error');
    return;
  }

  const accountVal = document.getElementById('accountSelect').value;
  if (!accountVal) {
    showToast('Conecte e selecione uma conta do Telegram.', 'error');
    return;
  }

  const dtVal = document.getElementById('datetimeInput').value;
  if (!dtVal) {
    showToast('Defina a data e a hora do agendamento.', 'error');
    return;
  }

  const periodVal = document.querySelector('input[name="period"]:checked').value;
  const pinnedVal = document.getElementById('pinnedInput').checked;
  const privacyVal = document.getElementById('privacyInput').value;
  const captionVal = document.getElementById('captionInput').value;
  const isVideoFile = fileInput.files[0] && fileInput.files[0].type.startsWith('video/');
  const removeAudioVal = isVideoFile && (document.getElementById('removeAudioRadio')?.checked === true);

  const formData = new FormData();
  formData.append('account_id', accountVal);
  formData.append('file', fileInput.files[0]);
  formData.append('scheduled_time', dtVal);
  formData.append('period', periodVal);
  formData.append('pinned', pinnedVal);
  formData.append('privacy', privacyVal);
  formData.append('remove_audio', removeAudioVal ? 'true' : 'false');
  let finalCaption = captionVal || '';
  if (current3DTitleData && current3DTitleData.html) {
    finalCaption = finalCaption.trim() ? `${current3DTitleData.html}\n${finalCaption.trim()}` : current3DTitleData.html;
  }
  if (finalCaption) {
    formData.append('caption', finalCaption);
  }

  const btn = document.getElementById('btnSubmitStory');
  const btnText = document.getElementById('btnSubmitText');
  const spinner = document.getElementById('btnSubmitSpinner');

  btn.disabled = true;
  btnText.innerText = 'Agendando publicação...';
  spinner.classList.remove('hidden');

  try {
    const res = await fetch('/api/stories', {
      method: 'POST',
      body: formData
    });
    const rawText = await res.text();
    let data = {};
    try {
      data = rawText ? JSON.parse(rawText) : {};
    } catch (parseErr) {
      data = {};
    }

    if (!res.ok) {
      throw new Error(data.detail || `Erro no servidor (${res.status}). Tente novamente em alguns segundos.`);
    }

    showToast('Story agendado com sucesso! Será publicado automaticamente.', 'success');

    // Reseta o formulário
    document.getElementById('storyForm').reset();
    resetGridChoice();
    removeMedia();
    remove3DTitle();
    updateCharCount();
    initDatetimePicker();

    // Recarrega stories
    loadStories();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btnText.innerText = 'Agendar Publicação Automática';
    spinner.classList.add('hidden');
  }
}

// ==========================================================================
// Listagem e Painel de Stories
// ==========================================================================
async function loadStories(isBackground = false) {
  try {
    const url = currentSelectedAccountId 
      ? `/api/stories?account_id=${currentSelectedAccountId}` 
      : '/api/stories';
    const res = await fetch(url);
    if (!res.ok) return;

    allStories = await safeJson(res);
    updateCounts();
    renderStoriesFeed();
  } catch (err) {
    if (!isBackground) {
      console.error('Erro ao carregar stories:', err);
    }
  }
}

function updateCounts() {
  const total = allStories.length;
  const scheduled = allStories.filter(s => s.status === 'SCHEDULED' || s.status === 'PUBLISHING').length;
  const published = allStories.filter(s => s.status === 'PUBLISHED').length;
  const failed = allStories.filter(s => s.status === 'FAILED').length;

  document.getElementById('countAll').innerText = total;
  document.getElementById('countScheduled').innerText = scheduled;
  document.getElementById('countPublished').innerText = published;
  document.getElementById('countFailed').innerText = failed;
}

function setFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-filter') === filter);
  });
  renderStoriesFeed();
}

function renderStoriesFeed() {
  const container = document.getElementById('storiesContainer');

  let filtered = allStories;
  if (currentFilter === 'scheduled') {
    filtered = allStories.filter(s => s.status === 'SCHEDULED' || s.status === 'PUBLISHING');
  } else if (currentFilter === 'published') {
    filtered = allStories.filter(s => s.status === 'PUBLISHED');
  } else if (currentFilter === 'failed') {
    filtered = allStories.filter(s => s.status === 'FAILED');
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" fill="none" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <p>Nenhum story encontrado para este filtro.</p>
        <span>Você pode agendar um novo story usando o formulário à esquerda.</span>
      </div>
    `;
    return;
  }

  const privacyMap = {
    all: '🌍 Público',
    contacts: '👥 Contatos',
    close_friends: '⭐ Amigos Próximos'
  };

  const statusMap = {
    SCHEDULED: { label: 'Agendado', class: 'scheduled' },
    PUBLISHING: { label: 'Publicando...', class: 'publishing' },
    PUBLISHED: { label: 'Publicado', class: 'published' },
    FAILED: { label: 'Erro', class: 'failed' },
    CANCELLED: { label: 'Cancelado', class: 'cancelled' }
  };

  container.innerHTML = filtered.map(story => {
    const isVideo = story.media_type === 'video';
    const statusInfo = statusMap[story.status] || { label: story.status, class: 'scheduled' };
    const isPending = story.status === 'SCHEDULED';
    const isFailed = story.status === 'FAILED';

    return `
      <div class="story-card" id="storyCard_${story.id}">
        <!-- Thumbnail -->
        <div class="story-thumb-wrap">
          <span class="pin-badge ${story.pinned ? 'on' : 'off'}">${story.pinned ? '📌 No perfil' : `Expira em ${story.period_hours}h`}</span>
          ${isVideo ? `
            <video src="${story.media_url}" class="story-thumb" preload="metadata" onerror="thumbFallback(this)"></video>
            <span class="video-indicator">▶ Vídeo</span>
          ` : `
            <img src="${story.media_url}" class="story-thumb" alt="" loading="lazy" onerror="thumbFallback(this)">
          `}
        </div>

        <!-- Info & Controls -->
        <div class="story-content">
          <div>
            <div class="story-top-row">
              <span class="status-badge ${statusInfo.class}">
                ● ${statusInfo.label}
              </span>
              <span class="tag-pill">${privacyMap[story.privacy] || story.privacy}</span>
            </div>

            ${(() => {
      const cap = story.caption || '';
      if (cap.includes('<tg-emoji')) {
        const parts = cap.split('\n');
        const firstLine = parts[0];
        const restLines = parts.slice(1).join('\n').trim();
        // Extrai letras
        const matches = [...firstLine.matchAll(/<tg-emoji[^>]*>([^<]+)<\/tg-emoji>/g)].map(m => m[1]);
        const titleStr = matches.length > 0 ? matches.join(' ') : 'Título 3D';
        return `
          <div class="story-3d-badge">💖 ${escapeHtml(titleStr)}</div>
          ${restLines ? `<p class="story-caption">${escapeHtml(restLines)}</p>` : ''}
        `;
      }
      return `<p class="story-caption">${escapeHtml(cap || 'Sem legenda')}</p>`;
    })()}

            <div class="story-tags-row">
              <span class="tag-pill ${story.period_hours === 48 ? 'premium' : ''}">
                ⏱️ ${story.period_hours} Horas ${story.period_hours === 48 ? '⭐' : ''}
              </span>
              ${story.account_label ? `<span class="tag-pill">👤 ${escapeHtml(story.account_label)}</span>` : ''}
              ${story.pinned ? `<span class="tag-pill pinned">📌 Na grade do perfil</span>` : ''}
              ${story.retry_count > 0 ? `<span class="tag-pill">🔄 Tentativas: ${story.retry_count}/3</span>` : ''}
            </div>

            ${story.error_message ? `
              <div class="story-error-snippet">
                <strong>Erro:</strong> ${escapeHtml(story.error_message)}
              </div>
            ` : ''}
          </div>

          <div class="story-bottom-row">
            <span class="story-time-info">
              📅 ${story.status === 'PUBLISHED' ? 'Publicado em' : 'Agendado para'}: <strong>${story.scheduled_time_formatted}</strong>
            </span>

            <div class="story-actions">
              <button class="btn btn-sm btn-ghost" onclick="openLogsModal(${story.id})" title="Ver histórico de tentativas">
                📋 Logs
              </button>
              ${story.status === 'PUBLISHED' ? `
                <button class="btn btn-sm ${story.pinned ? 'btn-warning-ghost' : 'btn-primary-ghost'}" onclick="toggleGridStory(${story.id})" title="${story.pinned ? 'Remover da grade do perfil' : 'Adicionar à grade do perfil'}">
                  ${story.pinned ? '📌 Na Grade' : '➕ Fixar na Grade'}
                </button>
              ` : ''}
              ${isPending ? `
                <button class="btn btn-sm btn-ghost" onclick="openEditModal(${story.id})" title="Editar agendamento">
                  ✏️ Editar
                </button>
                <button class="btn btn-sm btn-ghost" onclick="cancelStory(${story.id})" title="Cancelar agendamento">
                  ⏸ Cancelar
                </button>
              ` : ''}
              <button class="btn btn-sm btn-danger-ghost" onclick="deleteStory(${story.id})" title="Excluir story">
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ==========================================================================
// Ações de Story (Editar, Cancelar, Excluir)
// ==========================================================================
async function cancelStory(id) {
  if (!confirm(`Deseja cancelar o agendamento do Story #${id}?`)) return;

  try {
    const res = await fetch(`/api/stories/${id}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error('Não foi possível cancelar.');
    showToast('Agendamento cancelado com sucesso.', 'info');
    loadStories();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteStory(id) {
  if (!confirm(`Deseja realmente excluir o Story #${id}? O arquivo de mídia será apagado.`)) return;

  try {
    const res = await fetch(`/api/stories/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Falha ao excluir.');
    showToast('Story excluído com sucesso.', 'success');
    loadStories();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openEditModal(id) {
  const story = allStories.find(s => s.id === id);
  if (!story) return;

  currentEditingStoryId = id;
  document.getElementById('editStoryId').innerText = id;
  document.getElementById('editCaptionInput').value = story.caption || '';
  document.getElementById('editPeriodInput').value = String(story.period);
  document.getElementById('editPinnedInput').checked = Boolean(story.pinned);
  document.getElementById('editPrivacyInput').value = story.privacy;

  // Ajusta datetime
  const cleanSt = story.scheduled_time.substring(0, 16);
  document.getElementById('editDatetimeInput').value = cleanSt;

  document.getElementById('editError').classList.add('hidden');
  document.getElementById('editModal').classList.remove('hidden');
}

function closeEditModal() {
  document.getElementById('editModal').classList.add('hidden');
  currentEditingStoryId = null;
}

async function handleEditSubmit(e) {
  e.preventDefault();
  if (!currentEditingStoryId) return;

  const caption = document.getElementById('editCaptionInput').value;
  const scheduled_time = document.getElementById('editDatetimeInput').value;
  const period = parseInt(document.getElementById('editPeriodInput').value);
  const pinned = document.getElementById('editPinnedInput').checked;
  const privacy = document.getElementById('editPrivacyInput').value;

  const payload = { caption, scheduled_time, period, pinned, privacy };

  try {
    const res = await fetch(`/api/stories/${currentEditingStoryId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || 'Falha ao atualizar agendamento.');
    }

    closeEditModal();
    showToast('Agendamento atualizado com sucesso!', 'success');
    loadStories();
  } catch (err) {
    const errEl = document.getElementById('editError');
    errEl.innerText = err.message;
    errEl.classList.remove('hidden');
  }
}

// ==========================================================================
// Modal de Logs & Auditoria
// ==========================================================================
async function openLogsModal(storyId) {
  document.getElementById('logStoryId').innerText = storyId;
  const container = document.getElementById('logsListContainer');
  container.innerHTML = '<p class="helper-text">Carregando logs...</p>';

  document.getElementById('logsModal').classList.remove('hidden');

  try {
    const res = await fetch(`/api/stories/${storyId}/logs`);
    const logs = await safeJson(res);

    if (!logs || logs.length === 0) {
      container.innerHTML = '<p class="helper-text">Nenhum log registrado ainda para este story.</p>';
      return;
    }

    container.innerHTML = logs.map(l => `
      <div class="log-item ${l.status}">
        <div class="log-header">
          <span>Tentativa #${l.attempt_number} • Status: <strong>${l.status}</strong></span>
          <span>${l.created_at_formatted || l.created_at}</span>
        </div>
        <p class="log-message">${escapeHtml(l.message)}</p>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = '<p class="helper-text">Erro ao buscar logs.</p>';
  }
}

function closeLogsModal() {
  document.getElementById('logsModal').classList.add('hidden');
}

// ==========================================================================
// Toasts e Utilitários
// ==========================================================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  // Evita toasts duplicados consecutivos
  const last = container.querySelector('.toast:last-child');
  if (last && last.textContent.includes(message)) {
    return;
  }

  // Mantém no máximo 3 toasts na tela para não cobrir a interface
  while (container.children.length >= 3) {
    container.removeChild(container.firstChild);
  }

  const toast = document.createElement('div');
  toast.className = 'toast ' + type;

  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = '<span><strong>' + icon + '</strong> ' + escapeHtml(message) + '</span>';

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}


// Placeholder criativo quando a mídia não carrega (arquivo removido ou inválido)
function thumbFallback(el) {
  const wrap = el.parentElement;
  const isVideo = el.tagName === 'VIDEO';
  el.remove();
  if (wrap.querySelector('.thumb-fallback')) return;
  const ph = document.createElement('div');
  ph.className = 'thumb-fallback';
  ph.innerHTML = `<span class="thumb-emoji">${isVideo ? '🎬' : '🌅'}</span><span class="thumb-text">${isVideo ? 'Vídeo' : 'Story'}</span>`;
  wrap.prepend(ph);
}


// ==========================================================================
// Letras 3D & Efeitos (Telegram Pro / Custom Emojis)
// ==========================================================================
let current3DFont = 'mfslots';

function open3DFontsModal() {
  const modal = document.getElementById('customFontsModal');
  if (!modal) return;
  modal.classList.remove('hidden');
  const input = document.getElementById('customTitleInput');
  if (input && !input.value) {
    input.value = 'BOA NOITE';
  }
  update3DFontPreview();
  if (input) input.focus();
}

function close3DFontsModal() {
  const modal = document.getElementById('customFontsModal');
  if (modal) modal.classList.add('hidden');
}

function selectQuickTitle(title) {
  const input = document.getElementById('customTitleInput');
  if (input) {
    input.value = title;
    update3DFontPreview();
  }
}

function selectFontStyle(fontId, el) {
  current3DFont = fontId;
  document.querySelectorAll('.font-style-option').forEach(opt => opt.classList.remove('active'));
  if (el) el.classList.add('active');
  const radio = el ? el.querySelector('input[type="radio"]') : null;
  if (radio) radio.checked = true;
  update3DFontPreview();
}

function update3DFontPreview() {
  const input = document.getElementById('customTitleInput');
  const spaced = document.getElementById('fontSpacedInput').checked;
  const previewEl = document.getElementById('font3DPreviewText');
  
  const text = (input && input.value ? input.value : 'BOA NOITE').trim().toUpperCase();
  
  if (spaced) {
    const words = text.split(' ');
    previewEl.innerText = words.map(w => w.split('').join(' ')).join('   ');
  } else {
    previewEl.innerText = text;
  }

  // Aplica a classe CSS exata correspondente ao pack escolhido
  previewEl.className = 'preview-3d-text font-preview-' + current3DFont;
  const realImg = document.getElementById('fontRealPreviewImg');
  if (realImg) {
    realImg.src = '/static/img/fonts/' + current3DFont + '_sample.png?v=2';
  }
  previewEl.style.color = '';
  previewEl.style.textShadow = '';
  previewEl.style.background = '';
  previewEl.style.webkitBackgroundClip = '';
  previewEl.style.webkitTextFillColor = '';
  previewEl.style.filter = '';
}

let current3DTitleData = null;

function remove3DTitle() {
  current3DTitleData = null;
  const card = document.getElementById('active3DTitleCard');
  if (card) card.classList.add('hidden');
}

async function apply3DFontToCaption() {
  const input = document.getElementById('customTitleInput');
  const text = (input && input.value ? input.value : '').trim();
  if (!text) {
    showToast('Digite uma palavra ou título para inserir.', 'error');
    return;
  }

  const spaced = document.getElementById('fontSpacedInput').checked;

  try {
    const res = await fetch('/api/fonts/format', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: text,
        font: current3DFont,
        spaced: spaced
      })
    });

    const data = await safeJson(res);
    if (!res.ok) throw new Error(data.detail || 'Falha ao formatar letras.');

    // Salva o título 3D no estado para envio limpo sem poluir o textarea
    current3DTitleData = {
      text: text,
      font: current3DFont,
      fontLabel: data.font_label,
      preview: data.preview,
      html: data.html
    };

    // Exibe o card visual limpo com a fonte escolhida
    const card = document.getElementById('active3DTitleCard');
    const badgeEl = document.getElementById('active3DFontBadge');
    const textEl = document.getElementById('active3DText');

    if (badgeEl) badgeEl.innerText = data.font_label;
    if (textEl) textEl.innerText = data.preview;
    if (card) card.classList.remove('hidden');

    // Limpa qualquer código <tg-emoji> residual da legenda para manter o campo 100% limpo
    const captionArea = document.getElementById('captionInput');
    if (captionArea) {
      captionArea.value = captionArea.value.replace(/<tg-emoji[^>]*>[^<]*<\/tg-emoji>/g, '').trim();
      updateCharCount();
      captionArea.focus();
    }

    close3DFontsModal();
    showToast(`Título (${data.font_label}) ativado com sucesso!`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}
