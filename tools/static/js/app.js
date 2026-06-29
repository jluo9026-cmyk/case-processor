/**
 * Universal Docx Formatter - Frontend JavaScript
 */

// 全局变量
let selectedTemplateId = null;
let selectedPresetId = null;

document.addEventListener('DOMContentLoaded', function() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const selectFileBtn = document.getElementById('selectFileBtn');
    const fileInfo = document.getElementById('fileInfo');
    const actionsSection = document.getElementById('actionsSection');
    const progressSection = document.getElementById('progressSection');
    const resultSection = document.getElementById('resultSection');
    const errorSection = document.getElementById('errorSection');
    const convertBtn = document.getElementById('convertBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const resetBtn = document.getElementById('resetBtn');
    const retryBtn = document.getElementById('retryBtn');

    // 模板相关元素
    const templateUploadArea = document.getElementById('templateUploadArea');
    const templateFileInput = document.getElementById('templateFileInput');
    const selectTemplateBtn = document.getElementById('selectTemplateBtn');
    const templateList = document.getElementById('templateList');
    const optionStandard = document.getElementById('optionStandard');
    const optionPreset1 = document.getElementById('optionPreset1');
    const optionPreset2 = document.getElementById('optionPreset2');
    const optionPreset3 = document.getElementById('optionPreset3');
    const optionWithTemplate = document.getElementById('optionWithTemplate');
    const templateBadge = document.getElementById('templateBadge');
    const presetBadge = document.getElementById('presetBadge');

    let currentFile = null;
    let analysisResult = null;
    let currentConvertMode = 'standard';

    // API 基础路径 - 通过代理
    const API_BASE = '/api';

    // ========== 模板相关功能 ==========
    
    // 加载模板列表
    loadTemplates();

    // 选择模板文件按钮
    selectTemplateBtn.addEventListener('click', () => templateFileInput.click());
    templateFileInput.addEventListener('change', handleTemplateSelect);

    // 拖拽上传
    templateUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        templateUploadArea.classList.add('dragover');
    });
    templateUploadArea.addEventListener('dragleave', () => {
        templateUploadArea.classList.remove('dragover');
    });
    templateUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        templateUploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].name.endsWith('.docx')) {
            uploadTemplate(files[0]);
        }
    });

    // 转换方式选择
    optionStandard.addEventListener('click', () => selectConvertMode('standard'));
    optionPreset1.addEventListener('click', () => selectConvertMode('preset_1'));
    optionPreset2.addEventListener('click', () => selectConvertMode('preset_2'));
    optionPreset3.addEventListener('click', () => selectConvertMode('preset_3'));
    optionWithTemplate.addEventListener('click', () => selectConvertMode('with_template'));

    // 文件选择
    selectFileBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);
    
    // 拖拽
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
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // 按钮事件
    convertBtn.addEventListener('click', startConversion);
    downloadBtn.addEventListener('click', downloadFile);
    resetBtn.addEventListener('click', resetForm);
    retryBtn.addEventListener('click', resetForm);

    // ========== 模板函数 ==========

    async function loadTemplates() {
        try {
            const response = await fetch(API_BASE + '/templates');
            const data = await response.json();
            if (data.success) {
                renderTemplateList(data.templates);
            }
        } catch (error) {
            console.error('加载模板失败:', error);
        }
    }

    function renderTemplateList(templates) {
        if (!templates || templates.length === 0) {
            templateList.innerHTML = '<p style="text-align: center; opacity: 0.7; padding: 20px;">暂无模板，请上传标准模板</p>';
            return;
        }

        templateList.innerHTML = templates.map(t => `
            <div class="template-item ${selectedTemplateId === t.id ? 'selected' : ''}" data-id="${t.id}">
                <div class="template-info">
                    <div class="template-name">📄 ${t.name}</div>
                    <div class="template-meta">
                        ${t.sections_count || t.structure_info?.heading_count || 0} 个章节 · ${t.paragraphs_count || t.structure_info?.paragraph_count || 0} 个段落 · ${formatTime(t.upload_time)}
                    </div>
                </div>
                <div class="template-actions">
                    <button class="btn-sm ${selectedTemplateId === t.id ? 'btn-select selected' : 'btn-select'}" onclick="toggleTemplate('${t.id}', '${t.name}')">
                        ${selectedTemplateId === t.id ? '✓ 已选择' : '选择'}
                    </button>
                    <button class="btn-sm btn-delete" onclick="deleteTemplate('${t.id}')">删除</button>
                </div>
            </div>
        `).join('');
    }

    function formatTime(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleString('zh-CN');
    }

    function handleTemplateSelect(e) {
        const file = e.target.files[0];
        if (file) {
            uploadTemplate(file);
        }
    }

    async function uploadTemplate(file) {
        const formData = new FormData();
        formData.append('template', file);

        try {
            const response = await fetch(API_BASE + '/template/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.success) {
                alert('模板上传成功！');
                loadTemplates();
                // 自动选中刚上传的模板
                selectedTemplateId = data.template_id;
                updateTemplateBadge();
            } else {
                alert('上传失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            alert('上传失败: ' + error.message);
        }
    }

    window.toggleTemplate = function(id, name) {
        if (selectedTemplateId === id) {
            selectedTemplateId = null;
        } else {
            selectedTemplateId = id;
        }
        loadTemplates();
        updateTemplateBadge();
    };

    window.deleteTemplate = async function(id) {
        if (!confirm('确定要删除这个模板吗？')) return;
        
        try {
            const response = await fetch(API_BASE + '/template/' + id, {
                method: 'DELETE'
            });
            const data = await response.json();
            
            if (data.success) {
                if (selectedTemplateId === id) {
                    selectedTemplateId = null;
                }
                loadTemplates();
                updateTemplateBadge();
            } else {
                alert('删除失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            alert('删除失败: ' + error.message);
        }
    };

    function selectConvertMode(mode) {
        currentConvertMode = mode;
        optionStandard.classList.toggle('selected', mode === 'standard');
        optionPreset1.classList.toggle('selected', mode === 'preset_1');
        optionPreset2.classList.toggle('selected', mode === 'preset_2');
        optionPreset3.classList.toggle('selected', mode === 'preset_3');
        optionWithTemplate.classList.toggle('selected', mode === 'with_template');
        
        // 如果选择了模板模式但没有选择模板，提示用户
        if (mode === 'with_template' && !selectedTemplateId) {
            alert('请先选择一个模板！');
            selectConvertMode('standard');
            return;
        }
        
        updateTemplateBadge();
    }

    function updateTemplateBadge() {
        // 自定义模板徽章
        if (selectedTemplateId) {
            templateBadge.style.display = 'inline-block';
        } else {
            templateBadge.style.display = 'none';
        }
        // 预设模板标记 - 显示对应模板的"已选择"徽章
        const presetBadge1 = document.getElementById('presetBadge1');
        const presetBadge2 = document.getElementById('presetBadge2');
        const presetBadge3 = document.getElementById('presetBadge3');
        if (presetBadge1) presetBadge1.style.display = currentConvertMode === 'preset_1' ? 'inline-block' : 'none';
        if (presetBadge2) presetBadge2.style.display = currentConvertMode === 'preset_2' ? 'inline-block' : 'none';
        if (presetBadge3) presetBadge3.style.display = currentConvertMode === 'preset_3' ? 'inline-block' : 'none';
    }


    // ========== 文件处理函数 ==========

    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            handleFile(file);
        }
    }

    function handleFile(file) {
        if (!file.name.endsWith('.docx')) {
            showError('只支持 .docx 格式的文件');
            return;
        }
        
        currentFile = file;
        analyzeFile(file);
    }

    async function analyzeFile(file) {
        showProgress('正在分析文档...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch(API_BASE + '/analyze', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                analysisResult = data;
                showFileInfo(file.name, data);
                hideProgress();
                showActions();
            } else {
                showError(data.error || '分析失败');
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        }
    }

    function showFileInfo(filename, data) {
        document.getElementById('fileName').textContent = filename;
        document.getElementById('originalTitle').textContent = data.structure.main_title || '未检测到';
        
        const chapters = data.structure.chapters || [];
        document.getElementById('detectedChapters').textContent = 
            chapters.length > 0 ? chapters.length + ' 个章节' : '未检测到';
        
        const keyInfo = data.structure.key_info || {};
        const keyInfoText = Object.entries(keyInfo)
            .map(([k, v]) => `${k}: ${v}`)
            .join(' | ');
        document.getElementById('keyInfo').textContent = keyInfoText || '无';
        
        fileInfo.style.display = 'block';
        
        if (data.preview) {
            document.getElementById('previewContent').textContent = data.preview;
            document.getElementById('previewSection').style.display = 'block';
        }
    }

    function showActions() {
        actionsSection.style.display = 'block';
    }

    async function startConversion() {
        if (!currentFile) {
            showError('请先选择文件');
            return;
        }
        
        if (currentConvertMode === 'with_template' && !selectedTemplateId) {
            showError('请先选择一个模板');
            return;
        }
        
        const isPresetMode = currentConvertMode && currentConvertMode.startsWith('preset_');
        showProgress(isPresetMode ? '正在使用预设模板转换...' : currentConvertMode === 'with_template' ? '正在使用模板格式转换...' : '正在转换文档...');
        actionsSection.style.display = 'none';
        
        if (currentConvertMode === 'with_template') {
            // 使用自定义模板转换
            await convertWithTemplate();
        } else {
            // 标准转换或预设模板转换
            await convertStandard();
        }
    }

    async function convertStandard() {
        const formData = new FormData();
        formData.append('file', currentFile);
        
        // 如果选择了预设模板，传递 template_id
        const isPresetMode = currentConvertMode && currentConvertMode.startsWith('preset_');
        if (isPresetMode) {
            formData.append('template_id', currentConvertMode);
        }
        
        try {
            const response = await fetch(API_BASE + '/convert', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                hideProgress();
                showResult(data);
            } else {
                showError(data.error || '转换失败');
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        }
    }


    async function convertWithTemplate() {
        const formData = new FormData();
        formData.append('file', currentFile);
        
        try {
            const response = await fetch(API_BASE + '/template/' + selectedTemplateId + '/apply', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                hideProgress();
                showResult(data, true);
            } else {
                showError(data.error || '转换失败');
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        }
    }

    function showResult(data, usedTemplate = false) {
        document.getElementById('outputFileName').textContent = data.output_file;
        document.getElementById('summaryChapters').textContent = 
            data.summary.chapters_found + ' 个章节';
        document.getElementById('summaryAutoGenerated').textContent = 
            data.summary.chapters_auto_generated > 0 
                ? data.summary.chapters_auto_generated + ' 个自动补全'
                : '无需补全';
        
        if (data.template_name) {
            document.getElementById('templateUsed').textContent = data.template_name;
            document.getElementById('templateUsedItem').style.display = 'flex';
        } else {
            document.getElementById('templateUsedItem').style.display = 'none';
        }

        
        downloadBtn.href = API_BASE + '/download/' + encodeURIComponent(data.report_id || data.output_file);
        downloadBtn.download = data.output_file;
        
        resultSection.style.display = 'block';
        fileInfo.style.display = 'none';
        document.getElementById('previewSection').style.display = 'none';
    }

    function downloadFile() {
        window.location.href = downloadBtn.href;
    }

    function showProgress(message) {
        document.getElementById('progressStatus').textContent = message;
        progressSection.style.display = 'block';
    }

    function hideProgress() {
        progressSection.style.display = 'none';
    }

    function showError(message) {
        document.getElementById('errorMessage').textContent = message;
        hideProgress();
        errorSection.style.display = 'block';
        actionsSection.style.display = 'none';
        fileInfo.style.display = 'none';
    }

    function resetForm() {
        currentFile = null;
        analysisResult = null;
        fileInput.value = '';
        fileInfo.style.display = 'none';
        actionsSection.style.display = 'none';
        progressSection.style.display = 'none';
        resultSection.style.display = 'none';
        errorSection.style.display = 'none';
        document.getElementById('previewSection').style.display = 'none';
        currentConvertMode = 'standard';
        selectConvertMode('standard');
    }
});
