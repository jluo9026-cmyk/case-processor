const state = {
  uploadedFiles: [],
  uploadedStatementFiles: [],
  selectedPresetId: null,
  currentReportMarkdown: null,
  backendReady: false,
  formatSummary: null,  // 格式化摘要
  docxPath: null,       // 格式化DOCX下载路径
};

// ========== 通用错误解析工具 ==========
async function parseApiError(resp) {
  let errorMsg = `请求失败: ${resp.status}`;
  try {
    const err = await resp.json();
    errorMsg = err?.error || err?.detail || JSON.stringify(err);
  } catch {
    try {
      const text = await resp.text();
      if (text) errorMsg = text;
    } catch {}
  }
  return new Error(errorMsg);
}

const api = {
  async checkStatus() {
    const resp = await fetch('/backend-status');
    if (!resp.ok) throw new Error('无法获取后端状态');
    return resp.json();
  },

  async listPresetTemplates() {
    const resp = await fetch('/api/template/presets');
    if (!resp.ok) throw new Error('获取预设模板列表失败');
    return resp.json();
  },

  async getPresetTemplateDetail(templateId) {
    const resp = await fetch(`/api/template/preset/${templateId}`);
    if (!resp.ok) throw new Error('获取预设模板详情失败');
    return resp.json();
  },

  async runReportWithPreset(formData) {
    try {
      const resp = await fetch('/api/run-with-preset', { method: 'POST', body: formData });
      if (!resp.ok) throw await parseApiError(resp);
      return resp.json();
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('网络请求失败，请检查后端服务是否正常运行');
      }
      throw error;
    }
  },

  async runReport(formData) {
    const resp = await fetch('/api/run', { method: 'POST', body: formData });
    if (!resp.ok) throw await parseApiError(resp);
    return resp.json();
  },

  async getJobStatus(jobId) {
    const resp = await fetch(`/api/run/${jobId}`);
    if (!resp.ok) throw await parseApiError(resp);
    return resp.json();
  },

  // 修复：generateDocx 先获取 JSON 拿到 report_id，再通过下载端点获取 Blob
  async generateDocx(formData) {
    const resp = await fetch('/api/generate-docx', { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json().catch(() => null);
      throw new Error(err?.error || `DOCX 生成失败: ${resp.status}`);
    }
    const data = await resp.json();
    if (!data.success || !data.report_id) {
      throw new Error(data.error || 'DOCX 生成失败：未获取到报告ID');
    }
    // 通过下载端点获取实际文件 Blob
    const downloadResp = await fetch(`/api/download/${data.report_id}`);
    if (!downloadResp.ok) throw new Error('下载 DOCX 文件失败');
    return downloadResp.blob();
  }
};

const elements = {
  statusBar: document.getElementById('backendStatusBar'),
  statusText: document.getElementById('backendStatusText'),
  dropZone: document.getElementById('dropZone'),
  fileInput: document.getElementById('fileInput'),
  fileList: document.getElementById('fileList'),
  btnRun: document.getElementById('btnRun'),
  btnClear: document.getElementById('btnClear'),
  progressCard: document.getElementById('progressCard'),
  progressFill: document.getElementById('progressFill'),
  progressText: document.getElementById('progressText'),
  resultContent: document.getElementById('resultContent'),
  errorBox: document.getElementById('errorBox'),
  btnCopy: document.getElementById('btnCopy'),
  imageStats: document.getElementById('imageStats'),
  imgCount: document.getElementById('imgCount'),
  resultStats: document.getElementById('resultStats'),
  resultImages: document.getElementById('resultImages'),
  resultOcrLen: document.getElementById('resultOcrLen'),
  downloadSection: document.getElementById('downloadSection'),
  btnDownloadDocx: document.getElementById('btnDownloadDocx'),
  statementDropZone: document.getElementById('statementDropZone'),
  statementFileInput: document.getElementById('statementFileInput'),
  statementFileList: document.getElementById('statementFileList'),
  statementStats: document.getElementById('statementStats'),
  statementCount: document.getElementById('statementCount'),
  tabs: document.querySelectorAll('.tab'),
  presetTemplateList: document.getElementById('presetTemplateList'),
  selectedPresetInfo: document.getElementById('selectedPresetInfo'),
  selectedPresetName: document.getElementById('selectedPresetName'),
};

function setStatus(ready, message) {
  state.backendReady = ready;
  elements.statusBar.className = `backend-status ${ready ? 'connected' : 'disconnected'}`;
  elements.statusText.textContent = message;
  updateBtnState();
}

async function checkBackendStatus() {
  try {
    const data = await api.checkStatus();
    setStatus(data.ready, data.ready ? `✅ 后端已就绪（端口 ${data.port || '未知'}）` : data.message || '❌ 后端尚未就绪，请稍候重试');
  } catch (error) {
    setStatus(false, '❌ 后端服务未连接 - 请刷新或重启应用');
  }
}

function updateBtnState() {
  const hasFiles = state.uploadedFiles.length > 0 || state.uploadedStatementFiles.length > 0;
  const sceneInvestigationInput = document.getElementById('sceneInvestigation');
  const policeStationRecordInput = document.getElementById('policeStationRecord');
  const trafficPoliceRecordInput = document.getElementById('trafficPoliceRecord');
  const hospitalRecordInput = document.getElementById('hospitalRecord');
  const hasInvestigationContent = (sceneInvestigationInput && sceneInvestigationInput.value.trim()) ||
                                  (policeStationRecordInput && policeStationRecordInput.value.trim()) ||
                                  (trafficPoliceRecordInput && trafficPoliceRecordInput.value.trim()) ||
                                  (hospitalRecordInput && hospitalRecordInput.value.trim());
  const hasContent = hasFiles || hasInvestigationContent;
  // 模板为可选，不再强制要求选择模板
  elements.btnRun.disabled = !(hasContent && state.backendReady);
}


function selectPresetTemplate(presetId) {
  document.querySelectorAll('.preset-template-item').forEach(item => {
    item.classList.toggle('selected', item.dataset.templateId === presetId);
  });
  state.selectedPresetId = presetId;
  elements.selectedPresetInfo.style.display = 'flex';
  elements.selectedPresetName.textContent = document.querySelector(`[data-template-id="${presetId}"] .preset-template-name`).textContent;
  updateBtnState();
}

window.selectPresetTemplate = selectPresetTemplate;

function clearPresetSelection() {
  document.querySelectorAll('.preset-template-item').forEach(item => {
    item.classList.remove('selected');
  });
  state.selectedPresetId = null;
  elements.selectedPresetInfo.style.display = 'none';
  updateBtnState();
}

window.clearPresetSelection = clearPresetSelection;

// ========== 通用下载工具 ==========
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function transformUploadedFiles(files) {
  const items = [];
  const warnings = [];
  for (const f of files) {
    if (!f.type.startsWith('image/')) {
      warnings.push(`"${f.name}" 不是图片文件，已跳过`);
      continue;
    }
    if (f.size > 5 * 1024 * 1024) {
      warnings.push(`"${f.name}" 超过 5MB 限制（文件大小: ${(f.size / 1024 / 1024).toFixed(1)}MB），已跳过`);
      continue;
    }
    items.push(f);
  }
  if (warnings.length > 0) {
    const msg = warnings.join('\n');
    console.warn('[文件过滤]', msg);
    // 已有 errorBox 展示错误，用 showError 展示警告
    showError(msg);
    // 3秒后自动隐藏警告
    setTimeout(() => {
      if (elements.errorBox.textContent === msg) {
        elements.errorBox.style.display = 'none';
      }
    }, 5000);
  }
  return items;
}

function renderFileList() {
  elements.fileList.innerHTML = state.uploadedFiles.map((file, idx) =>
    `<span class="file-tag">🖼️ ${file.name} <span class="remove" data-idx="${idx}">×</span></span>`
  ).join('');
  elements.fileList.querySelectorAll('.remove').forEach(el => {
    el.addEventListener('click', () => {
      state.uploadedFiles.splice(+el.dataset.idx, 1);
      renderFileList();
      updateBtnState();
    });
  });
  if (state.uploadedFiles.length) {
    elements.imageStats.style.display = 'flex';
    elements.imgCount.textContent = state.uploadedFiles.length;
  } else {
    elements.imageStats.style.display = 'none';
  }
}

function renderStatementFileList() {
  elements.statementFileList.innerHTML = state.uploadedStatementFiles.map((file, idx) =>
    `<span class="file-tag" style="background:#fff3e0;border-color:#e67e22;color:#e67e22;">📋 ${file.name} <span class="remove" data-idx="${idx}">×</span></span>`
  ).join('');
  elements.statementFileList.querySelectorAll('.remove').forEach(el => {
    el.addEventListener('click', () => {
      state.uploadedStatementFiles.splice(+el.dataset.idx, 1);
      renderStatementFileList();
      updateBtnState();
    });
  });
  if (state.uploadedStatementFiles.length) {
    elements.statementStats.style.display = 'flex';
    elements.statementCount.textContent = state.uploadedStatementFiles.length;
  } else {
    elements.statementStats.style.display = 'none';
  }
}

async function handleFiles(fileList) {
  const files = transformUploadedFiles(fileList);
  state.uploadedFiles.push(...files);
  renderFileList();
  updateBtnState();
}

async function handleStatementFiles(fileList) {
  const files = transformUploadedFiles(fileList);
  state.uploadedStatementFiles.push(...files);
  renderStatementFileList();
  updateBtnState();
}

const TEXTAREA_IDS = ['sceneInvestigation', 'policeStationRecord', 'trafficPoliceRecord', 'hospitalRecord'];

function resetView() {
  state.uploadedFiles = [];
  state.uploadedStatementFiles = [];
  state.currentReportMarkdown = null;
  state.selectedPresetId = null;
  state.currentResult = null;
  
  // 清空文件列表
  elements.fileList.innerHTML = '';
  elements.statementFileList.innerHTML = '';
  elements.imageStats.style.display = 'none';
  elements.statementStats.style.display = 'none';
  
  // 清空结果区
  elements.resultContent.textContent = '';
  elements.errorBox.style.display = 'none';
  elements.resultStats.style.display = 'none';
  elements.progressCard.style.display = 'none';
  elements.downloadSection.classList.remove('show');
  
  // 清空模板选择
  elements.selectedPresetInfo.style.display = 'none';
  document.querySelectorAll('.preset-template-item').forEach(item => {
    item.classList.remove('selected');
  });
  
  // 清空所有文本域
  TEXTAREA_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  
  updateBtnState();
}

function showError(message) {
  // 确保消息是字符串，防止 [object Object] 错误
  const errorText = typeof message === 'string' ? message : JSON.stringify(message);
  elements.errorBox.textContent = errorText;
  elements.errorBox.style.display = 'block';
}

function renderResult(data) {
  state.currentResult = data;
  state.currentReportMarkdown = data.final_report || data.report_content;
  state.formatSummary = data.summary || null;
  state.docxPath = data.docx_path || null;
  
  elements.resultStats.style.display = 'flex';
  elements.resultImages.textContent = data.total_images || 0;
  elements.resultOcrLen.textContent = (data.combined_text || '').length;
  elements.downloadSection.classList.add('show');
  elements.btnDownloadDocx.disabled = false;
  
  // 如果有标准化DOCX下载路径，直接使用；否则使用原生成方式
  if (data.docx_path) {
    elements.btnDownloadDocx.onclick = () => {
      window.open(data.docx_path, '_blank');
    };
    elements.btnDownloadDocx.textContent = '📄 下载标准格式DOCX';
  } else {
    elements.btnDownloadDocx.onclick = downloadDocx;
    elements.btnDownloadDocx.textContent = '📄 下载 Word 文档';
  }
  
  switchTab('final');
  elements.resultContent.textContent = data.final_report || data.report_content || data.combined_text || '（无报告内容）';
  
  // 渲染格式化摘要
  renderFormatSummary(data);
}


function renderFormatSummary(data) {
  const container = document.getElementById('formatSummary');
  if (!container) return;
  
  const summary = data.summary;
  if (!summary) {
    container.style.display = 'none';
    return;
  }
  
  container.style.display = 'block';
  
  // 填充模板名称
  const templateNameEl = document.getElementById('formatTemplateName');
  if (templateNameEl) templateNameEl.textContent = data.template_name || '未知模板';
  
  // 填充公司名称
  const companyNameEl = document.getElementById('formatCompanyName');
  if (companyNameEl) companyNameEl.textContent = summary.company_name || summary.main_title || '未知公司';
  
  // 填充章节统计
  const chaptersFoundEl = document.getElementById('formatChaptersFound');
  if (chaptersFoundEl) chaptersFoundEl.textContent = summary.chapters_found || 0;
  
  const chaptersAutoEl = document.getElementById('formatChaptersAuto');
  if (chaptersAutoEl) chaptersAutoEl.textContent = summary.chapters_auto_generated || 0;
  
  // 填充关键信息
  const keyFieldsContainer = document.getElementById('formatKeyFields');
  if (keyFieldsContainer && summary.key_fields) {
    const fields = summary.key_fields;
    const fieldKeys = Object.keys(fields);
    if (fieldKeys.length > 0) {
      keyFieldsContainer.innerHTML = fieldKeys.map(key => 
        `<div class="format-key-field">
          <span class="format-key-label">${key}</span>
          <span class="format-key-value">${fields[key] || '-'}</span>
        </div>`
      ).join('');
      keyFieldsContainer.style.display = 'grid';
    } else {
      keyFieldsContainer.innerHTML = '<div class="format-key-field"><span class="format-key-value" style="color:#999;">暂无提取信息</span></div>';
    }
  }
  
  // 填充章节列表
  const chaptersList = document.getElementById('formatChaptersList');
  if (chaptersList && summary.chapters) {
    chaptersList.innerHTML = summary.chapters.map((ch, idx) => 
      `<li>${ch}</li>`
    ).join('');
  } else if (chaptersList) {
    // 如果没有chapters列表，从main_title显示
    chaptersList.innerHTML = `<li>${summary.main_title || '标准六章节格式'}</li>`;
  }
  
  // 设置下载链接
  const downloadLink = document.getElementById('formatDownloadLink');
  if (downloadLink && data.docx_path) {
    downloadLink.href = data.docx_path;
    downloadLink.style.display = 'inline-block';
  } else if (downloadLink) {
    downloadLink.style.display = 'none';
  }
}


function switchTab(tabName) {
  if (!state.currentReportMarkdown || !state.currentResult) return;
  elements.tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabName));
  const content = tabName === 'ocr'
    ? (state.currentResult?.combined_text || '（无OCR内容）')
    : (state.currentResult?.final_report || state.currentResult?.report_content || '（无报告内容）');
  elements.resultContent.textContent = content;
}

async function downloadDocx() {
  if (!state.currentReportMarkdown) return;
  const btn = elements.btnDownloadDocx;
  const originalText = btn.textContent;
  btn.textContent = '⏳ 生成中...';
  btn.disabled = true;

  try {
    const formData = new FormData();
    formData.append('markdown_report', state.currentReportMarkdown);
    formData.append('output_name', `调查报告_${new Date().toISOString().slice(0,10)}`);
    const blob = await api.generateDocx(formData);
    downloadBlob(blob, `调查报告_${new Date().toISOString().slice(0,10)}.docx`);
  } catch (error) {
    showError(error.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

function bindEvents() {
  elements.dropZone.addEventListener('click', () => elements.fileInput.click());
  elements.dropZone.addEventListener('dragover', e => { e.preventDefault(); elements.dropZone.classList.add('dragover'); });
  elements.dropZone.addEventListener('dragleave', () => elements.dropZone.classList.remove('dragover'));
  elements.dropZone.addEventListener('drop', e => {
    e.preventDefault();
    elements.dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
  });
  elements.fileInput.addEventListener('change', () => { handleFiles(elements.fileInput.files); elements.fileInput.value = ''; });

  elements.statementDropZone.addEventListener('click', () => elements.statementFileInput.click());
  elements.statementDropZone.addEventListener('dragover', e => { e.preventDefault(); elements.statementDropZone.classList.add('dragover'); });
  elements.statementDropZone.addEventListener('dragleave', () => elements.statementDropZone.classList.remove('dragover'));
  elements.statementDropZone.addEventListener('drop', e => {
    e.preventDefault();
    elements.statementDropZone.classList.remove('dragover');
    handleStatementFiles(e.dataTransfer.files);
  });
  elements.statementFileInput.addEventListener('change', () => { handleStatementFiles(elements.statementFileInput.files); elements.statementFileInput.value = ''; });

  const sceneInvestigationInput = document.getElementById('sceneInvestigation');
  const policeStationRecordInput = document.getElementById('policeStationRecord');
  const trafficPoliceRecordInput = document.getElementById('trafficPoliceRecord');
  const hospitalRecordInput = document.getElementById('hospitalRecord');
  
  if (sceneInvestigationInput) {
    sceneInvestigationInput.addEventListener('input', updateBtnState);
  }
  if (policeStationRecordInput) {
    policeStationRecordInput.addEventListener('input', updateBtnState);
  }
  if (trafficPoliceRecordInput) {
    trafficPoliceRecordInput.addEventListener('input', updateBtnState);
  }
  if (hospitalRecordInput) {
    hospitalRecordInput.addEventListener('input', updateBtnState);
  }

  elements.btnClear.addEventListener('click', resetView);
  elements.btnRun.addEventListener('click', onRunClicked);
  elements.btnCopy.addEventListener('click', async () => {
    await navigator.clipboard.writeText(elements.resultContent.textContent);
    elements.btnCopy.textContent = '✅ 已复制';
    setTimeout(() => { elements.btnCopy.textContent = '📋 复制报告'; }, 2000);
  });
  elements.btnDownloadDocx.addEventListener('click', downloadDocx);

  elements.tabs.forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
}

async function onRunClicked() {
  if (!state.backendReady) {
    alert('后端服务未连接，请先等待后端就绪');
    return;
  }

  elements.resultContent.textContent = '';
  elements.errorBox.style.display = 'none';
  elements.progressCard.style.display = 'block';
  elements.progressFill.style.width = '0%';
  elements.progressText.textContent = '准备中...';
  elements.btnRun.disabled = true;

  await runWithPresetTemplate();
}


async function runWithPresetTemplate() {
  const formData = new FormData();
  formData.append('template_id', state.selectedPresetId);

  console.log('[前端] 上传图片数量:', state.uploadedFiles.length);
  state.uploadedFiles.forEach((file, idx) => {
    console.log(`[前端] 添加第${idx+1}张图片:`, file.name, file.size, 'bytes');
    formData.append('images', file);
  });

  console.log('[前端] 上传笔录数量:', state.uploadedStatementFiles.length);
  state.uploadedStatementFiles.forEach((file, idx) => {
    console.log(`[前端] 添加第${idx+1}张笔录:`, file.name, file.size, 'bytes');
    formData.append('statement_images', file);
  });

  const sceneInvestigationInput = document.getElementById('sceneInvestigation');
  const policeStationRecordInput = document.getElementById('policeStationRecord');
  const trafficPoliceRecordInput = document.getElementById('trafficPoliceRecord');
  const hospitalRecordInput = document.getElementById('hospitalRecord');
  
  if (sceneInvestigationInput && sceneInvestigationInput.value.trim()) {
    formData.append('sceneInvestigation', sceneInvestigationInput.value.trim());
  }
  if (policeStationRecordInput && policeStationRecordInput.value.trim()) {
    formData.append('policeStationRecord', policeStationRecordInput.value.trim());
  }
  if (trafficPoliceRecordInput && trafficPoliceRecordInput.value.trim()) {
    formData.append('trafficPoliceRecord', trafficPoliceRecordInput.value.trim());
  }
  if (hospitalRecordInput && hospitalRecordInput.value.trim()) {
    formData.append('hospitalRecord', hospitalRecordInput.value.trim());
  }

  let progress = 0;
  const startTime = Date.now();
  const progressInterval = setInterval(() => {
    // 超时检测：超过 300 秒则重置进度条
    if (Date.now() - startTime > 300000) {
      clearInterval(progressInterval);
      elements.progressFill.style.width = '0%';
      elements.progressText.textContent = '⏰ 处理超时（超过5分钟）';
      showError('处理超时，请检查后端状态后重试');
      elements.btnRun.disabled = false;
      return;
    }
    if (progress < 90) {
      progress += Math.random() * 10;
      progress = Math.min(progress, 90);
      elements.progressFill.style.width = `${progress}%`;
    }
  }, 1000);

  try {
    elements.progressText.textContent = '正在使用预设模板生成报告...';
    const data = await api.runReportWithPreset(formData);
    
    if (data.success) {
      elements.progressFill.style.width = '100%';
      elements.progressText.textContent = '✅ 完成！';
      state.currentResult = data;
      state.currentReportMarkdown = data.report_content;
      renderResult(data);
    } else {
      throw new Error(data.error || data.detail || '生成失败');
    }
  } catch (error) {
    elements.progressText.textContent = '❌ 处理失败';
    let errorMsg = '未知错误';
    if (error instanceof Error) {
      errorMsg = error.message;
    } else if (typeof error === 'string') {
      errorMsg = error;
    } else if (typeof error === 'object') {
      errorMsg = JSON.stringify(error, null, 2);
    } else {
      errorMsg = String(error);
    }
    console.error('报告生成错误:', error);
    showError(errorMsg);
  } finally {
    clearInterval(progressInterval);
    elements.btnRun.disabled = false;
  }
}

async function loadPresetTemplates() {
  try {
    const data = await api.listPresetTemplates();
    if (data.success && data.presets && data.presets.length > 0) {
      renderPresetTemplates(data.presets);
    }
  } catch (error) {
    console.error('加载预设模板列表失败:', error);
  }
}

function renderPresetTemplates(presets) {
  const container = document.getElementById('presetTemplateList');
  if (!container) return;

  // 保留第一个"不使用模板"选项，移除旧的动态模板项
  const noneItem = container.querySelector('.preset-template-none');
  container.innerHTML = '';
  if (noneItem) container.appendChild(noneItem);

  // 动态渲染预设模板
  presets.forEach(preset => {
    const item = document.createElement('div');
    item.className = 'preset-template-item';
    item.dataset.templateId = preset.id;
    item.onclick = () => selectPresetTemplate(preset.id);

    // 根据模板名称选择图标
    let icon = '📋';
    if (preset.name.includes('二') || preset.name.includes('2') || preset.name.includes('DE')) {
      icon = '📊';
    } else if (preset.name.includes('三') || preset.name.includes('3') || preset.name.includes('XU')) {
      icon = '📋';
    }

    item.innerHTML = `
      <div class="preset-template-icon">${icon}</div>
      <div class="preset-template-info">
        <div class="preset-template-name">${preset.name}</div>
        ${preset.description ? `<div class="preset-template-desc">${preset.description}</div>` : ''}
      </div>
      <div class="preset-template-check">✓</div>
    `;

    container.appendChild(item);
  });
}

// ============================================================
// DOCX 转换功能（上传待转换报告 → 按模板转换）
// ============================================================
const convertState = {
  file: null,
  outputFilename: null,
  reportId: null,
};

let convertElements = null;

function getConvertElements() {
  if (convertElements) return convertElements;
  convertElements = {
    dropZone: document.getElementById('convertDropZone'),
    fileInput: document.getElementById('convertFileInput'),
    fileInfo: document.getElementById('convertFileInfo'),
    fileName: document.getElementById('convertFileName'),
    fileRemove: document.getElementById('convertFileRemove'),
    btnConvert: document.getElementById('btnConvertDocx'),
    btnDownload: document.getElementById('btnDownloadConverted'),
    progress: document.getElementById('convertProgress'),
    progressFill: document.getElementById('convertProgressFill'),
    progressText: document.getElementById('convertProgressText'),
    errorBox: document.getElementById('convertErrorBox'),
  };
  return convertElements;
}

async function handleConvertFile(file) {
  const el = getConvertElements();
  if (!file) return;
  
  // 验证格式
  if (!file.name.toLowerCase().endsWith('.docx')) {
    el.errorBox.textContent = '请上传 .docx 格式的文件';
    el.errorBox.style.display = 'block';
    return;
  }
  
  convertState.file = file;
  convertState.outputFilename = null;
  
  el.fileName.textContent = file.name;
  el.fileInfo.style.display = 'flex';
  el.btnConvert.disabled = false;
  el.btnDownload.style.display = 'none';
  el.errorBox.style.display = 'none';
  el.progress.style.display = 'none';
}

async function startConvertDocx() {
  const el = getConvertElements();
  
  if (!convertState.file) {
    el.errorBox.textContent = '请先上传 .docx 文件';
    el.errorBox.style.display = 'block';
    return;
  }
  
  // 如果没有选择模板，使用 'standard' 通用格式
  const templateId = state.selectedPresetId || 'standard';
  
  el.btnConvert.disabled = true;
  el.errorBox.style.display = 'none';
  el.progress.style.display = 'block';
  el.progressFill.style.width = '10%';
  el.progressText.textContent = '正在上传并转换文档...';
  
  try {
    const formData = new FormData();
    formData.append('file', convertState.file);
    formData.append('template_id', templateId);
    
    el.progressFill.style.width = '30%';
    el.progressText.textContent = '正在处理...';
    
    const resp = await fetch('/api/convert', {
      method: 'POST',
      body: formData,
    });
    
    if (!resp.ok) {
      let errMsg = `转换失败: ${resp.status}`;
      try { const err = await resp.json(); errMsg = err.detail || err.error || errMsg; } catch(e) {}
      throw new Error(errMsg);
    }
    
    el.progressFill.style.width = '80%';
    el.progressText.textContent = '转换完成，准备下载...';
    
    const result = await resp.json();
    
    if (result.success) {
      convertState.outputFilename = result.output_file;
      convertState.reportId = result.report_id;
      
      el.progressFill.style.width = '100%';
      
      // 显示转换摘要
      const summary = result.summary || {};
      const templateName = result.template_name || '通用格式';
      const chaptersFound = summary.chapters_found || 0;
      const chaptersAuto = summary.chapters_auto_generated || 0;
      
      el.progressText.textContent = `✅ 转换完成！模板：${templateName}，识别章节：${chaptersFound}章，自动补全：${chaptersAuto}章`;
      el.btnConvert.disabled = false;
      
      // 显示下载按钮
      el.btnDownload.style.display = 'inline-flex';
      el.btnDownload.onclick = () => downloadConvertedDocx();
      
      // 自动下载
      setTimeout(() => downloadConvertedDocx(), 500);
    } else {
      throw new Error(result.error || '转换失败');
    }
  } catch (error) {
    el.progressFill.style.width = '0%';
    el.progressText.textContent = '❌ 转换失败';
    el.errorBox.textContent = error.message;
    el.errorBox.style.display = 'block';
    el.btnConvert.disabled = false;
  }
}

async function downloadConvertedDocx() {
  if (!convertState.outputFilename) return;
  if (!convertState.reportId) {
    console.error('下载失败: 缺少 report_id');
    return;
  }
  
  const el = getConvertElements();
  const downloadUrl = `/api/download/${convertState.reportId}`;
  
  try {
    const resp = await fetch(downloadUrl);
    if (!resp.ok) throw new Error('下载失败');
    
    const blob = await resp.blob();
    downloadBlob(blob, `转换报告_${new Date().toISOString().slice(0,10)}.docx`);
  } catch (error) {
    el.errorBox.textContent = '下载失败: ' + error.message;
    el.errorBox.style.display = 'block';
  }
}

function resetConvertFile() {
  convertState.file = null;
  convertState.outputFilename = null;
  convertState.reportId = null;
  const el = getConvertElements();
  el.fileInfo.style.display = 'none';
  el.btnConvert.disabled = true;
  el.btnDownload.style.display = 'none';
  el.errorBox.style.display = 'none';
  el.progress.style.display = 'none';
  el.fileInput.value = '';
}

function bindConvertEvents() {
  const el = getConvertElements();
  
  el.dropZone.addEventListener('click', () => el.fileInput.click());
  el.dropZone.addEventListener('dragover', e => { e.preventDefault(); el.dropZone.classList.add('dragover'); });
  el.dropZone.addEventListener('dragleave', () => el.dropZone.classList.remove('dragover'));
  el.dropZone.addEventListener('drop', e => {
    e.preventDefault();
    el.dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) handleConvertFile(e.dataTransfer.files[0]);
  });
  el.fileInput.addEventListener('change', () => {
    if (el.fileInput.files.length > 0) handleConvertFile(el.fileInput.files[0]);
    el.fileInput.value = '';
  });
  el.fileRemove.addEventListener('click', resetConvertFile);
  el.btnConvert.addEventListener('click', startConvertDocx);
}

async function init() {
  bindEvents();
  bindConvertEvents();
  await checkBackendStatus();
  await loadPresetTemplates();
  setInterval(checkBackendStatus, 5000);
  updateBtnState();
}

init();
