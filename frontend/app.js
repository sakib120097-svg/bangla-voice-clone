// =============================================
// BANGLA VOICE CLONE - Frontend App
// =============================================

const API_BASE = 'http://localhost:8000';

const state = {
  uploadedFile: null,
  generatedAudioUrl: null,
  history: JSON.parse(localStorage.getItem('vcHistory') || '[]'),
};

// ── DOM refs ──────────────────────────────────
const els = {
  dropZone: document.getElementById('dropZone'),
  voiceFile: document.getElementById('voiceFile'),
  uploadPreview: document.getElementById('uploadPreview'),
  uploadFileName: document.getElementById('uploadFileName'),
  uploadAudio: document.getElementById('uploadAudio'),
  uploadWave: document.getElementById('uploadWave'),
  banglaText: document.getElementById('banglaText'),
  charCount: document.getElementById('charCount'),
  generateBtn: document.getElementById('generateBtn'),
  progressWrap: document.getElementById('progressWrap'),
  progressText: document.getElementById('progressText'),
  progressPct: document.getElementById('progressPct'),
  progressFill: document.getElementById('progressFill'),
  progressSteps: document.getElementById('progressSteps'),
  resultWrap: document.getElementById('resultWrap'),
  resultAudio: document.getElementById('resultAudio'),
  resultWave: document.getElementById('resultWave'),
  downloadBtn: document.getElementById('downloadBtn'),
  retryBtn: document.getElementById('retryBtn'),
  errorWrap: document.getElementById('errorWrap'),
  errorMsg: document.getElementById('errorMsg'),
  historyGrid: document.getElementById('historyGrid'),
  serverStatus: document.getElementById('serverStatus'),
};

// ── Server health check ────────────────────────
async function checkServer() {
  const s = els.serverStatus;
  s.querySelector('.status-text').textContent = 'সংযোগ করা হচ্ছে...';
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
    const data = await res.json();
    s.className = 'status-pill connected';
    s.querySelector('.status-text').textContent = data.model_loaded ? 'মডেল প্রস্তুত ✓' : 'সার্ভার চালু (মডেল লোড হচ্ছে)';
  } catch {
    s.className = 'status-pill error';
    s.querySelector('.status-text').textContent = 'সার্ভার বন্ধ';
  }
}

// ── Drop zone ──────────────────────────────────
els.dropZone.addEventListener('click', () => els.voiceFile.click());

els.dropZone.addEventListener('dragover', e => {
  e.preventDefault(); els.dropZone.classList.add('dragover');
});

els.dropZone.addEventListener('dragleave', () => {
  els.dropZone.classList.remove('dragover');
});

els.dropZone.addEventListener('drop', e => {
  e.preventDefault(); els.dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleAudioFile(file);
});

els.voiceFile.addEventListener('change', () => {
  if (els.voiceFile.files[0]) handleAudioFile(els.voiceFile.files[0]);
});

function handleAudioFile(file) {
  const valid = ['audio/wav', 'audio/mpeg', 'audio/mp3'];
  if (!valid.some(t => file.type.includes(t.split('/')[1])) && !file.name.match(/\.(wav|mp3)$/i)) {
    showError('শুধু WAV বা MP3 ফাইল গ্রহণযোগ্য।');
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    showError('ফাইলের আকার সর্বোচ্চ 50MB হতে পারে।');
    return;
  }

  state.uploadedFile = file;
  const url = URL.createObjectURL(file);
  els.uploadAudio.src = url;
  els.uploadFileName.textContent = file.name;
  els.uploadPreview.classList.remove('hidden');
  generateWaveform(els.uploadWave, 36);
  updateGenerateBtn();
}

// ── Waveform decoration ────────────────────────
function generateWaveform(container, bars = 32) {
  container.innerHTML = '';
  for (let i = 0; i < bars; i++) {
    const bar = document.createElement('div');
    bar.className = 'bar';
    const h = 15 + Math.random() * 70;
    bar.style.height = h + '%';
    bar.style.animationDelay = (Math.random() * 1.5) + 's';
    bar.style.animationDuration = (1 + Math.random()) + 's';
    container.appendChild(bar);
  }
}

// ── Text input ─────────────────────────────────
els.banglaText.addEventListener('input', () => {
  const len = els.banglaText.value.length;
  els.charCount.textContent = len;
  if (len > 450) els.charCount.style.color = 'var(--red)';
  else if (len > 350) els.charCount.style.color = 'var(--accent)';
  else els.charCount.style.color = 'var(--text-muted)';
  updateGenerateBtn();
});

// Quick phrases
document.querySelectorAll('.phrase-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    els.banglaText.value = btn.dataset.text;
    els.banglaText.dispatchEvent(new Event('input'));
  });
});

// ── Generate button state ──────────────────────
function updateGenerateBtn() {
  els.generateBtn.disabled = !(state.uploadedFile && els.banglaText.value.trim().length > 0);
}

// ── Progress pipeline ──────────────────────────
const STEPS = [
  'অডিও প্রি-প্রসেসিং',
  'ভয়েস এনকোডিং',
  'মডেল ইনফারেন্স',
  'অডিও জেনারেশন',
  'পোস্ট-প্রসেসিং',
];

function setProgress(pct, msg) {
  els.progressFill.style.width = pct + '%';
  els.progressPct.textContent = pct + '%';
  els.progressText.textContent = msg;
}

function renderSteps(activeIdx) {
  els.progressSteps.innerHTML = STEPS.map((s, i) => {
    const cls = i < activeIdx ? 'done' : i === activeIdx ? 'active' : '';
    return `<span class="step-chip ${cls}">${s}</span>`;
  }).join('');
}

// ── Generate voice ─────────────────────────────
els.generateBtn.addEventListener('click', generateVoice);
els.retryBtn.addEventListener('click', generateVoice);

async function generateVoice() {
  if (!state.uploadedFile || !els.banglaText.value.trim()) return;

  // Reset UI
  els.resultWrap.classList.add('hidden');
  els.errorWrap.classList.add('hidden');
  els.progressWrap.classList.remove('hidden');
  els.generateBtn.disabled = true;
  els.generateBtn.classList.add('loading');
  els.generateBtn.querySelector('.btn-text').textContent = 'তৈরি হচ্ছে';

  setProgress(0, 'শুরু হচ্ছে...');
  renderSteps(0);

  try {
    const formData = new FormData();
    formData.append('voice_sample', state.uploadedFile);
    formData.append('text', els.banglaText.value.trim());
    formData.append('language', 'bn');

    // Simulate step progress while waiting
    const stepIntervals = simulateProgress();

    const res = await fetch(`${API_BASE}/clone`, {
      method: 'POST',
      body: formData,
    });

    clearInterval(stepIntervals);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    setProgress(95, 'ফাইল প্রস্তুত হচ্ছে...');
    renderSteps(4);

    const blob = await res.blob();
    const audioUrl = URL.createObjectURL(blob);
    state.generatedAudioUrl = audioUrl;

    setProgress(100, 'সম্পন্ন!');
    renderSteps(5);

    await sleep(400);

    // Show result
    els.progressWrap.classList.add('hidden');
    els.resultWrap.classList.remove('hidden');
    els.resultAudio.src = audioUrl;
    generateWaveform(els.resultWave, 40);

    // Save to history
    addToHistory(els.banglaText.value.trim(), audioUrl);

    // Download button
    els.downloadBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = audioUrl; a.download = `bangla_clone_${Date.now()}.wav`;
      a.click();
    };

  } catch (err) {
    clearProgress();
    showError(err.message || 'সার্ভারের সাথে সংযোগ করা যাচ্ছে না। backend চালু আছে কিনা দেখুন।');
  } finally {
    els.generateBtn.classList.remove('loading');
    els.generateBtn.querySelector('.btn-text').textContent = 'ভয়েস ক্লোন করুন';
    updateGenerateBtn();
  }
}

function simulateProgress() {
  let step = 0;
  const msgs = [
    [5, 'অডিও প্রি-প্রসেসিং...', 0],
    [25, 'ভয়েস স্যাম্পল এনকোড করা হচ্ছে...', 1],
    [50, 'XTTS v2 মডেল রান করছে...', 2],
    [70, 'বাংলা স্পিচ জেনারেট হচ্ছে...', 3],
    [85, 'অডিও পোস্ট-প্রসেস হচ্ছে...', 4],
  ];
  const interval = setInterval(() => {
    if (step < msgs.length) {
      const [pct, msg, stepIdx] = msgs[step];
      setProgress(pct, msg);
      renderSteps(stepIdx);
      step++;
    }
  }, 1800);
  return interval;
}

function clearProgress() {
  els.progressWrap.classList.add('hidden');
}

function showError(msg) {
  els.errorMsg.textContent = msg;
  els.errorWrap.classList.remove('hidden');
  els.progressWrap.classList.add('hidden');
}

// ── History ────────────────────────────────────
function addToHistory(text, audioUrl) {
  const item = {
    id: Date.now(),
    text,
    audioUrl,
    time: new Date().toLocaleString('bn-BD'),
  };
  state.history.unshift(item);
  if (state.history.length > 10) state.history.pop();
  renderHistory();
}

function renderHistory() {
  if (state.history.length === 0) {
    els.historyGrid.innerHTML = '<p class="history-empty">এখনো কোনো ভয়েস তৈরি হয়নি।</p>';
    return;
  }
  els.historyGrid.innerHTML = state.history.map(item => `
    <div class="history-item" data-id="${item.id}">
      <div class="history-meta">
        <span>#${item.id.toString().slice(-4)}</span>
        <span>${item.time}</span>
      </div>
      <div class="history-text">${escapeHtml(item.text)}</div>
      <audio src="${item.audioUrl}" controls></audio>
    </div>
  `).join('');
}

function escapeHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Helpers ────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ───────────────────────────────────────
checkServer();
setInterval(checkServer, 30000);
renderHistory();
updateGenerateBtn();
