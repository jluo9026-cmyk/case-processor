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

// 选中的工具
let selectedTools = new Set();
let toolList = [];

// 初始化
async function init() {
  await loadToolList();
  await loadCaseData();
  setupEventListeners();
}

// 加载工具列表
async function loadToolList() {
  try {
    const tools = await window.electronAPI.getToolList();
    toolList = tools;
    
    toolGrid.innerHTML = tools.map(tool => `
      <div class="tool-btn ${!tool.exists ? 'not-found' : ''}" 
           data-tool="${tool.id}"
           data-exists="${tool.exists}">
        <div class="tool-icon">${tool.icon}</div>
        <div class="tool-name">${tool.name}</div>
        <div class="tool-desc">${tool.exists ? tool.desc : '未找到'}</div>
      </div>
    `).join('');
    
    // 添加工具点击事件
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
  const exists = btn.dataset.exists === 'true';
  
  if (!exists) {
    showStatus('该工具不存在或路径错误', 'error');
    return;
  }
  
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
  // 保存数据
  document.getElementById('saveDataBtn').addEventListener('click', saveCaseData);
  
  // 加载数据
  document.getElementById('loadDataBtn').addEventListener('click', loadCaseData);
  
  // 清空数据
  document.getElementById('clearDataBtn').addEventListener('click', clearCaseData);
  
  // 执行选中工具
  document.getElementById('runSelectedBtn').addEventListener('click', runSelectedTools);
  
  // 一键执行全部
  document.getElementById('runAllBtn').addEventListener('click', runAllTools);
  
  // 打开工具目录
  document.getElementById('openToolsFolderBtn').addEventListener('click', openToolsFolder);
}

// 保存案件数据
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
  
  const result = await window.electronAPI.saveCaseData(data);
  
  if (result.success) {
    lastSaveSpan.textContent = new Date().toLocaleTimeString();
    showStatus('案件数据已保存', 'success');
    addLog('数据已保存到 case-data.json');
  } else {
    showStatus('保存失败: ' + result.error, 'error');
    addLog('保存失败: ' + result.error, 'error');
  }
}

// 加载案件数据
async function loadCaseData() {
  const data = await window.electronAPI.loadCaseData();
  
  if (data && Object.keys(data).length) {
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
    addLog('从 case-data.json 加载数据');
  } else {
    showStatus('无历史数据', 'info');
    addLog('未找到历史数据');
  }
}

// 清空数据
function clearCaseData() {
  caseId.value = '';
  policyNo.value = '';
  insured.value = '';
  injured.value = '';
  thirdParty.value = '';
  accidentDate.value = '';
  accidentLocation.value = '';
  attachments.value = '';
  lastSaveSpan.textContent = '-';
  showStatus('数据已清空', 'info');
  addLog('已清空所有数据');
}

// 执行选中的工具
async function runSelectedTools() {
  if (selectedTools.size === 0) {
    showStatus('请先选择要执行的工具', 'error');
    return;
  }
  
  // 先保存数据
  await saveCaseData();
  
  const tools = Array.from(selectedTools);
  await executeTools(tools);
}

// 执行所有可用工具
async function runAllTools() {
  // 先保存数据
  await saveCaseData();
  
  const availableTools = toolList
    .filter(t => t.exists)
    .map(t => t.id);
  
  await executeTools(availableTools);
}

// 执行工具
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
    
    const result = await window.electronAPI.runTool({ 
      toolName: toolNames[i],
      caseData: getCurrentCaseData()
    });
    
    if (result.success) {
      addLog(`✓ ${tool ? tool.name : toolNames[i]} 已启动`, 'success');
    } else {
      addLog(`✗ ${tool ? tool.name : toolNames[i]} 失败: ${result.error}`, 'error');
    }
    
    // 等待一下，避免程序启动冲突
    await sleep(800);
  }
  
  progressBar.classList.remove('active');
  toolStatus.textContent = '';
  addLog('全部执行完成！', 'success');
  showStatus('所有工具已启动执行', 'success');
}

// 获取当前案件数据
function getCurrentCaseData() {
  return {
    caseId: caseId.value,
    policyNo: policyNo.value,
    insured: insured.value,
    injured: injured.value,
    thirdParty: thirdParty.value,
    accidentDate: accidentDate.value,
    accidentLocation: accidentLocation.value,
    attachments: attachments.value.split('\n').filter(l => l.trim())
  };
}

// 打开工具目录
async function openToolsFolder() {
  const folder = await window.electronAPI.selectFile({ directory: true });
  if (folder) {
    await window.electronAPI.openFolder(folder);
  }
}

// 添加日志
function addLog(message, type = 'info') {
  const time = new Date().toLocaleTimeString();
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;
  
  if (type === 'success') {
    line.style.color = '#38ef7d';
  } else if (type === 'error') {
    line.style.color = '#f5576c';
  }
  
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
