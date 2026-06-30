/**
 * 案件处理启动器 - Web 版本渲染器
 * 替代 Electron renderer.js，所有调用改为 HTTP API
 */

// DOM 元素
const caseId = document.getElementById('caseId');
const policyNo = document.getElementById('policyNo');
const insured = document.getElementById('insured');
const injured = document.getElementById('injured');
const thirdParty = document.getElementById('thirdParty');
const accidentDate = document.getElementById('accidentDate');
const accidentLocation = document.getElementById('accidentLocation');
const attachments = document.getElementById('attachments');
const toolGrid = document.getElementById('toolGrid');
const lastSaveSpan = document.getElementById('lastSave');
const logArea = document.getElementById('logArea');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const toolStatus = document.getElementById('toolStatus');

// API 基础路径
const API = {
  tools: '/api/tools',
  toolsRun: '/api/tools/run',
  caseDataSave: '/api/case-data/save',
  caseDataLoad: '/api/case-data/load',
  caseDataClear: '/api/case-data/clear',
};

// 选中的工具
let selectedTools = new Set();
let toolList = [];

// HTTP 请求工具
async function apiGet(url) {
  const resp = await fetch(url);
  return resp.json();
}

async function apiPost(url, data) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return resp.json();
}

// 初始化
async function init() {
  await loadToolList();
  await loadCaseData();
  setupEventListeners();
}

// 加载工具列表
async function loadToolList() {
  try {
    const result = await apiGet(API.tools);
    if (!result.success) throw new Error(result.error);
    toolList = result.tools;
    
    toolGrid.innerHTML = toolList.map(tool => `
      <div class="tool-btn" 
           data-tool="${tool.id}"
           data-url="${tool.url}">
        <div class="tool-icon">${tool.icon}</div>
        <div class="tool-name">${tool.name}</div>
        <div class="tool-desc">${tool.desc}</div>
      </div>
    `).join('');
    
    document.querySelectorAll('.tool-btn').forEach(btn => {
      btn.addEventListener('click', () => toggleToolSelection(btn));
    });
    
  } catch (error) {
    showStatus('加载工具列表失败: ' + error.message, 'error');
  }
}

// 切换工具选中状态
function toggleToolSelection(btn) {
  const toolId = btn.dataset.tool;
  
  if (selectedTools.has(toolId)) {
    selectedTools.delete(toolId);
    btn.classList.remove('active');
  } else {
    selectedTools.add(toolId);
    btn.classList.add('active');
  }
}

// 设置事件监听
function setupEventListeners() {
  document.getElementById('saveDataBtn').addEventListener('click', saveCaseData);
  document.getElementById('loadDataBtn').addEventListener('click', loadCaseData);
  document.getElementById('clearDataBtn').addEventListener('click', clearCaseData);
  document.getElementById('runSelectedBtn').addEventListener('click', runSelectedTools);
  document.getElementById('runAllBtn').addEventListener('click', runAllTools);
}

// 保存案件数据（存到后端内存）
async function saveCaseData() {
  const data = {
    caseId: caseId.value,
    policyNo: policyNo.value,
    insured: insured.value,
    injured: injured.value,
    thirdParty: thirdParty.value,
    accidentDate: accidentDate.value,
    accidentLocation: accidentLocation.value,
    attachments: attachments.value.split('\n').filter(l => l.trim()),
    lastModified: new Date().toISOString()
  };
  
  const result = await apiPost(API.caseDataSave, data);
  
  if (result.success) {
    lastSaveSpan.textContent = new Date().toLocaleTimeString();
    showStatus('案件数据已保存', 'success');
    addLog('数据已保存');
  } else {
    showStatus('保存失败: ' + result.error, 'error');
    addLog('保存失败: ' + result.error, 'error');
  }
}

// 加载案件数据
async function loadCaseData() {
  const result = await apiGet(API.caseDataLoad);
  
  if (result.success && result.data && Object.keys(result.data).length) {
    const data = result.data;
    caseId.value = data.caseId || '';
    policyNo.value = data.policyNo || '';
    insured.value = data.insured || '';
    injured.value = data.injured || '';
    thirdParty.value = data.thirdParty || '';
    accidentDate.value = data.accidentDate || '';
    accidentLocation.value = data.accidentLocation || '';
    attachments.value = (data.attachments || []).join('\n');
    
    if (data.lastModified) {
      lastSaveSpan.textContent = new Date(data.lastModified).toLocaleString();
    }
    
    showStatus('数据已加载', 'success');
    addLog('数据已加载');
  } else {
    showStatus('无历史数据', 'info');
    addLog('未找到历史数据');
  }
}

// 清空数据
async function clearCaseData() {
  caseId.value = '';
  policyNo.value = '';
  insured.value = '';
  injured.value = '';
  thirdParty.value = '';
  accidentDate.value = '';
  accidentLocation.value = '';
  attachments.value = '';
  lastSaveSpan.textContent = '-';
  await apiPost(API.caseDataClear, {});
  showStatus('数据已清空', 'info');
  addLog('已清空所有数据');
}

// 执行选中的工具
async function runSelectedTools() {
  if (selectedTools.size === 0) {
    showStatus('请先选择要执行的工具', 'error');
    return;
  }
  await saveCaseData();
  const tools = Array.from(selectedTools);
  await executeTools(tools);
}

// 执行所有可用工具
async function runAllTools() {
  await saveCaseData();
  const allTools = toolList.map(t => t.id);
  await executeTools(allTools);
}

// 执行工具（Web 版本：在新标签页或当前窗口打开工具）
async function executeTools(toolNames) {
  progressBar.classList.add('active');
  progressFill.style.width = '0%';
  logArea.classList.add('active');
  logArea.innerHTML = '';
  
  addLog(`开始执行 ${toolNames.length} 个工具...`);
  
  for (let i = 0; i < toolNames.length; i++) {
    const tool = toolList.find(t => t.id === toolNames[i]);
    const progress = ((i + 1) / toolNames.length) * 100;
    
    progressFill.style.width = progress + '%';
    toolStatus.textContent = `正在执行: ${tool ? tool.icon + ' ' + tool.name : toolNames[i]} (${i + 1}/${toolNames.length})`;
    addLog(`执行中: ${tool ? tool.name : toolNames[i]}...`);
    
    // Web 版本直接打开工具页面
    if (tool) {
      window.open(tool.url, '_blank');
      addLog(`✓ ${tool.name} 已打开`, 'success');
    } else {
      addLog(`✗ ${toolNames[i]} 未找到`, 'error');
    }
    
    await sleep(500);
  }
  
  progressBar.classList.remove('active');
  toolStatus.textContent = '';
  addLog('全部执行完成！', 'success');
  showStatus('所有工具已启动执行', 'success');
}

// 添加日志
function addLog(message, type = 'info') {
  const time = new Date().toLocaleTimeString();
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;
  if (type === 'success') line.style.color = '#38ef7d';
  else if (type === 'error') line.style.color = '#f5576c';
  logArea.appendChild(line);
  logArea.scrollTop = logArea.scrollHeight;
}

// 显示状态
function showStatus(msg, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = msg;
  statusDiv.className = `status ${type}`;
  clearTimeout(window.statusTimeout);
  window.statusTimeout = setTimeout(() => {
    statusDiv.className = 'status';
  }, 4000);
}

// 工具函数
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 启动
init();