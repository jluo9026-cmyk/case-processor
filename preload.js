const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // 案件数据
  saveCaseData: (data) => ipcRenderer.invoke('save-case-data', data),
  loadCaseData: () => ipcRenderer.invoke('load-case-data'),
  
  // 工具管理
  getToolList: () => ipcRenderer.invoke('get-tool-list'),
  runTool: (options) => ipcRenderer.invoke('run-tool', options),
  runToolsBatch: (toolNames) => ipcRenderer.invoke('run-tools-batch', toolNames),
  
  // 文件操作
  selectFile: (options) => ipcRenderer.invoke('select-file', options),
  saveFile: (options) => {
    // 兼容两种调用方式
    if (typeof options === 'string') {
      return ipcRenderer.invoke('save-file', options);
    }
    // 如果是对象，返回对话框结果对象
    return ipcRenderer.invoke('dialog:saveFile', options);
  },
  openFolder: (path) => ipcRenderer.invoke('open-folder', path),
  



  // ============ 目录模板工具 API ============
  // 文件对话框
  openFile: (options) => ipcRenderer.invoke('dialog:openFile', options),
  saveFileDialog: (options) => ipcRenderer.invoke('dialog:saveFile', options),

  // 文件操作
  readFile: (filePath) => ipcRenderer.invoke('file:read', filePath),
  writeFile: (filePath, base64Data) => ipcRenderer.invoke('file:write', filePath, base64Data),
  fileExists: (filePath) => ipcRenderer.invoke('file:exists', filePath),

  // DOCX 处理
  replaceTable: (base64Data, reportContent, attachments) => ipcRenderer.invoke('docx:replaceTable', base64Data, reportContent, attachments),




  // 结案审批表工具 API
  selectTemplate: () => ipcRenderer.invoke('select-template'),
  selectOutput: (defaultName) => ipcRenderer.invoke('select-output', defaultName),
  parseInput: (text) => ipcRenderer.invoke('parse-input', text),
  fillExcel: (options) => ipcRenderer.invoke('fill-excel', options)
});
