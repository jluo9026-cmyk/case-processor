/**
 * 结案审批表填写工具 - Web 版本
 * 替代原 Electron renderer.js，所有调用改为 HTTP API + 浏览器原生 API
 */

let currentTemplateFile = null;
let currentParsedData = null;

// API 路径
const API_BASE = '';

// Tab切换
const tabs = document.querySelectorAll('.tab');
const tabContents = {
  ai: document.getElementById('tab-ai'),
  manual: document.getElementById('tab-manual')
};

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const tabId = tab.dataset.tab;
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    Object.values(tabContents).forEach(c => c.classList.remove('active'));
    if (tabContents[tabId]) tabContents[tabId].classList.add('active');
  });
});

// 选择模板文件 (AI模式)
document.getElementById('selectTemplateBtn')?.addEventListener('click', () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.xlsx,.xls';
  input.onchange = (e) => {
    const file = e.target.files[0];
    if (file) {
      currentTemplateFile = file;
      document.getElementById('templatePath').value = file.name;
      document.getElementById('templatePath').dataset.path = file.name;
      showStatus('模板已选中: ' + file.name, 'success');
    }
  };
  input.click();
});

// 选择模板文件 (手动模式)
document.getElementById('selectTemplateBtn2')?.addEventListener('click', () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.xlsx,.xls';
  input.onchange = (e) => {
    const file = e.target.files[0];
    if (file) {
      currentTemplateFile = file;
      document.getElementById('templatePath2').value = file.name;
      showStatus('模板已选中: ' + file.name, 'success');
    }
  };
  input.click();
});

// 预览识别 (AI模式) - 客户端本地解析，无需后端
document.getElementById('previewBtn')?.addEventListener('click', async () => {
  const aiInput = document.getElementById('aiInput').value.trim();
  if (!aiInput) {
    showStatus('请输入报告内容', 'error');
    return;
  }

  const result = parseInputLocally(aiInput);

  if (result.success) {
    currentParsedData = result.data;

    const previewGrid = document.getElementById('aiPreviewGrid');
    previewGrid.innerHTML = '';

    const displayFields = [
      { label: '保单号', key: 'policyNo' },
      { label: '投保人', key: 'insured' },
      { label: '被保险人/伤者', key: 'insuredPerson' },
      { label: '保险险种', key: 'insuranceType' },
      { label: '保险期间', key: 'insurancePeriod' },
      { label: '事故性质', key: 'accidentNature' },
      { label: '出险时间', key: 'accidentDate' },
      { label: '出险地点', key: 'accidentLocation' },
      { label: '索赔金额', key: 'claimAmount' },
      { label: '赔付建议', key: 'suggestion' },
      { label: '受案时间', key: 'acceptDate' },
      { label: '结案时间', key: 'closeDate' },
      { label: '调查员', key: 'investigator' }
    ];

    for (const field of displayFields) {
      const value = result.data[field.key];
      if (value) {
        const item = document.createElement('div');
        item.className = 'preview-item';
        item.innerHTML = `<span class="preview-label">${field.label}：</span><span class="preview-value">${escapeHtml(value)}</span>`;
        previewGrid.appendChild(item);
      }
    }

    document.getElementById('aiPreviewArea').style.display = 'block';
    showStatus(`识别到 ${result.fields ? result.fields.length : Object.keys(result.data).length} 个字段`, 'success');
  } else {
    showStatus('解析失败：' + result.error, 'error');
  }
});

// 生成Excel (AI模式)
document.getElementById('fillBtn')?.addEventListener('click', async () => {
  if (!currentTemplateFile) {
    showStatus('请先选择Excel模板文件', 'error');
    return;
  }
  let data = currentParsedData;
  if (!data) {
    const aiInput = document.getElementById('aiInput').value.trim();
    if (!aiInput) { showStatus('请输入报告内容', 'error'); return; }
    const result = parseInputLocally(aiInput);
    if (!result.success) { showStatus('解析失败：' + result.error, 'error'); return; }
    data = result.data;
  }
  await downloadFilledExcel(data);
});

// 生成Excel (手动模式)
document.getElementById('fillManualBtn')?.addEventListener('click', async () => {
  if (!currentTemplateFile) {
    showStatus('请先选择Excel模板文件', 'error');
    return;
  }
  const data = {
    policyNo: document.getElementById('policyNo').value.trim(),
    insuranceType: document.getElementById('insuranceType').value.trim(),
    insured: document.getElementById('insured').value.trim(),
    insuredPerson: document.getElementById('insuredPerson').value.trim(),
    accidentDate: document.getElementById('accidentDate').value.trim(),
    accidentLocation: document.getElementById('accidentLocation').value.trim(),
    claimAmount: document.getElementById('claimAmount').value.trim(),
    suggestion: document.getElementById('suggestion').value.trim(),
    acceptDate: document.getElementById('acceptDate').value.trim(),
    closeDate: document.getElementById('closeDate').value.trim(),
    investigator: document.getElementById('investigator').value.trim()
  };
  await downloadFilledExcel(data);
});

// 下载填充好的Excel（浏览器端利用FileReader读取模板，利用openpyxl仅作提示）
async function downloadFilledExcel(data) {
  if (!currentTemplateFile) {
    showStatus('请先选择Excel模板文件', 'error');
    return;
  }

  try {
    // 将模板文件发送到后端处理
    const formData = new FormData();
    formData.append('template', currentTemplateFile);
    formData.append('data', JSON.stringify(data));

    showStatus('正在生成Excel...', 'info');

    const resp = await fetch('/api/fill-excel', {
      method: 'POST',
      body: formData
    });

    if (!resp.ok) {
      let err = '生成失败';
      try { const e = await resp.json(); err = e.error || err; } catch(e) {}
      throw new Error(err);
    }

    // 下载生成的文件
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const fileName = data.policyNo
      ? `结案审批表_${data.policyNo.slice(-8)}.xlsx`
      : `结案审批表_${new Date().toISOString().slice(0,10)}.xlsx`;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showStatus('✅ Excel文件已生成并下载！', 'success');
    currentParsedData = null;
  } catch (error) {
    showStatus('❌ 生成失败：' + error.message, 'error');
  }
}

// 本地解析输入文本（替代 Electron IPC）
function parseInputLocally(text) {
  if (!text) return { success: false, error: '输入文本为空' };

  const data = {};
  const fields = [];

  const fieldPatterns = [
    { key: 'policyNo', label: '保单号', patterns: [/保单号[：:]\s*([^\s,，\n\r]+)/i, /保单号码[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'insured', label: '投保人', patterns: [/投保人[：:]\s*([^\s,，\n\r]+)/i, /投保人名称[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'insuredPerson', label: '被保险人/伤者', patterns: [/被保险[人人][：:]\s*([^\s,，\n\r]+)/i, /伤[者员][：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'insuranceType', label: '保险险种', patterns: [/保险险种[：:]\s*([^\s,，\n\r]+)/i, /险种[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'accidentDate', label: '出险时间', patterns: [/出险时间[：:]\s*([^\s,，\n\r]+)/i, /事故发生时间[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'accidentLocation', label: '出险地点', patterns: [/出险地点[：:]\s*([^\n\r]+)/i, /案发地点[：:]\s*([^\n\r]+)/i] },
    { key: 'claimAmount', label: '索赔金额', patterns: [/索赔金额[：:]\s*([^\s,，\n\r]+)/i, /理赔金额[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'suggestion', label: '赔付建议', patterns: [/赔付建议[：:]\s*([^\n\r]+)/i, /处理建议[：:]\s*([^\n\r]+)/i] },
    { key: 'acceptDate', label: '受案时间', patterns: [/受案时间[：:]\s*([^\s,，\n\r]+)/i, /受理时间[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'closeDate', label: '结案时间', patterns: [/结案时间[：:]\s*([^\s,，\n\r]+)/i, /完成时间[：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'investigator', label: '调查员', patterns: [/调查[员人][：:]\s*([^\s,，\n\r]+)/i, /查勘[员人][：:]\s*([^\s,，\n\r]+)/i] },
    { key: 'insurancePeriod', label: '保险期间', patterns: [/保险期间[：:]\s*([^\n\r]+)/i, /保险期限[：:]\s*([^\n\r]+)/i] },
    { key: 'accidentNature', label: '事故性质', patterns: [/事故性质[：:]\s*([^\s,，\n\r]+)/i, /事故类型[：:]\s*([^\s,，\n\r]+)/i] },
  ];

  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.match(/^[\|\s\-:]+$/)) continue;
    for (const field of fieldPatterns) {
      if (data[field.key]) continue;
      for (const pattern of field.patterns) {
        const match = trimmed.match(pattern);
        if (match && match[1].trim() && match[1].trim().length < 100) {
          data[field.key] = match[1].trim();
          fields.push({ key: field.key, label: field.label, value: data[field.key] });
          break;
        }
      }
    }
  }

  return { success: true, data, fields: fields.map(f => f.key) };
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>').replace(/"/g, '"');
}

function showStatus(message, type) {
  const status = document.getElementById('status');
  if (!status) return;
  status.textContent = message;
  status.className = 'status ' + type;
  setTimeout(() => { status.className = 'status'; }, 5000);
}