// 结案审批表填写工具 - 渲染进程

let currentTemplatePath = null;
let currentParsedData = null;

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
    tabContents[tabId].classList.add('active');
  });
});

// 选择模板文件 (AI模式)
document.getElementById('selectTemplateBtn')?.addEventListener('click', async () => {
  const filePath = await window.electronAPI.selectTemplate();
  if (filePath) {
    currentTemplatePath = filePath;
    document.getElementById('templatePath').value = filePath;
    showStatus('模板已选中', 'success');
  }
});

// 选择模板文件 (手动模式)
document.getElementById('selectTemplateBtn2')?.addEventListener('click', async () => {
  const filePath = await window.electronAPI.selectTemplate();
  if (filePath) {
    currentTemplatePath = filePath;
    document.getElementById('templatePath2').value = filePath;
    showStatus('模板已选中', 'success');
  }
});

// 预览识别 (AI模式)
document.getElementById('previewBtn')?.addEventListener('click', async () => {
  const aiInput = document.getElementById('aiInput').value.trim();
  if (!aiInput) {
    showStatus('请输入报告内容', 'error');
    return;
  }
  
  const result = await window.electronAPI.parseInput(aiInput);
  
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
    showStatus(`识别到 ${result.fields.length} 个字段`, 'success');
  } else {
    showStatus('解析失败：' + result.error, 'error');
  }
});

// 生成Excel (AI模式)
document.getElementById('fillBtn')?.addEventListener('click', async () => {
  if (!currentTemplatePath) {
    showStatus('请先选择Excel模板文件', 'error');
    return;
  }
  
  let data = currentParsedData;
  if (!data) {
    const aiInput = document.getElementById('aiInput').value.trim();
    if (!aiInput) {
      showStatus('请输入报告内容', 'error');
      return;
    }
    const result = await window.electronAPI.parseInput(aiInput);
    if (!result.success) {
      showStatus('解析失败：' + result.error, 'error');
      return;
    }
    data = result.data;
  }
  
  await generateExcel(data);
});

// 生成Excel (手动模式)
document.getElementById('fillManualBtn')?.addEventListener('click', async () => {
  if (!currentTemplatePath) {
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
  
  await generateExcel(data);
});

// 生成Excel核心函数
async function generateExcel(data) {
  // 选择保存路径
  const defaultName = data.policyNo 
    ? `结案审批表_${data.policyNo.slice(-10)}_${new Date().toISOString().slice(0,10)}.xlsx`
    : `结案审批表_${new Date().toISOString().slice(0,10)}.xlsx`;
  
  const savePath = await window.electronAPI.selectOutput(defaultName);
  if (!savePath) return;
  
  // 执行填充
  const result = await window.electronAPI.fillExcel({
    templatePath: currentTemplatePath,
    outputPath: savePath,
    caseData: data
  });
  
  if (result.success) {
    showStatus('✅ Excel文件已生成：' + result.path, 'success');
    currentParsedData = null; // 清空已填充的数据
  } else {
    showStatus('❌ 生成失败：' + result.error, 'error');
  }
}

// HTML转义
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// 显示状态
function showStatus(message, type) {
  const status = document.getElementById('status');
  status.textContent = message;
  status.className = 'status ' + type;
  setTimeout(() => {
    status.className = 'status';
  }, 5000);
}
