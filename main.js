const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');

// ============ 常量定义 ============
const TIMEOUTS = {
  HEALTH_CHECK: 15000,
  PROXY_REQUEST: 300000,
  PORT_CHECK: 3000,
  BACKEND_STARTUP: 30000,
  PORT_VERIFY_INTERVAL: 800,
  TOOL_WINDOW_DELAY: 300,
  ATTACHMENT_PROCESSOR_PORT: 3000,
};

const MAX_PORT_RETRIES = 10;

const TOOL_TITLES = {
  'reportGenerate': '报告生成',

  'catalogTool': '目录工具',

  'approvalForm': '结案审批表',

  'attachmentProcessor': '附件处理器',
};

const TOOL_HTML_MAP = {
  'reportGenerate': 'report_generate/index.html',

  'catalogTool': 'index4.html',

  'approvalForm': 'index3.html',

  'attachmentProcessor': '附件处理器-合并版/index.html',
};

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

const CACHE_CONTROL_HEADERS = {
  'Cache-Control': 'no-cache, no-store, must-revalidate',
  'Pragma': 'no-cache',
};

// ============ 应用状态管理 ============
class AppState {
  constructor() {
    this.mainWindow = null;
    this.httpServer = null;
    this.httpPort = 8765;
    this.combinedBackend = null;
    this.backendPort = null;
    this.backendReady = false;
    this.portVerificationInProgress = false;
    this.backendStarting = false;
    this._portRetryCount = 0;
    this.attachmentProcessorProcess = null;  // 附件处理器 Node.js 子进程
  }

  getBackendScriptPath() {
    return path.join(__dirname, 'combined_backend.py');
  }

  getPortFilePath() {
    return path.join(__dirname, '.backend_port');
  }

  getToolsDir() {
    return path.join(__dirname, 'tools');
  }

  getTemplatesDir() {
    return path.join(__dirname, 'templates');
  }

  getStaticDir() {
    return path.join(__dirname, 'static');
  }

  incrementPortRetry() {
    this._portRetryCount++;
  }

  resetPortRetry() {
    this._portRetryCount = 0;
  }

  hasExceededPortRetry() {
    return this._portRetryCount >= MAX_PORT_RETRIES;
  }
}

const appState = new AppState();

// ============ 路径安全检查 ============
function isPathSafe(baseDir, targetPath) {
  const resolved = path.resolve(targetPath);
  return resolved.startsWith(path.resolve(baseDir));
}

// ============ 后端端口管理 ============
function readBackendPort() {
  try {
    const portFile = appState.getPortFilePath();
    if (fs.existsSync(portFile)) {
      const raw = fs.readFileSync(portFile, 'utf-8').trim();
      const port = parseInt(raw, 10);
      if (port > 0) return port;
    }
  } catch (e) {
    console.warn('读取端口文件失败:', e.message);
  }
  return null;
}

function clearBackendPortFile() {
  try {
    const portFile = appState.getPortFilePath();
    if (fs.existsSync(portFile)) {
      fs.unlinkSync(portFile);
    }
  } catch (e) {
    console.warn('清除端口文件失败:', e.message);
  }
}

function verifyBackendPort(port) {
  return new Promise((resolve) => {
    if (!port || typeof port !== 'number') {
      resolve(false);
      return;
    }

    const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
      if (res.statusCode === 200) {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            const data = JSON.parse(body);
            resolve(data.status === 'ok' && data.modules?.report_generate);
          } catch {
            resolve(false);
          }
        });
      } else {
        resolve(false);
      }
    });

    req.on('error', () => resolve(false));
    req.setTimeout(TIMEOUTS.HEALTH_CHECK, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function resolveBackendPort() {
  while (appState.portVerificationInProgress) {
    await new Promise(r => setTimeout(r, 100));
  }

  appState.portVerificationInProgress = true;
  try {
    if (appState.backendPort) {
      const ok = await verifyBackendPort(appState.backendPort);
      if (ok) {
        appState.backendReady = true;
        return appState.backendPort;
      }
      appState.backendPort = null;
      appState.backendReady = false;
    }

    const filePort = readBackendPort();
    if (filePort) {
      const ok = await verifyBackendPort(filePort);
      if (ok) {
        appState.backendPort = filePort;
        appState.backendReady = true;
        return filePort;
      }
      clearBackendPortFile();
    }

    appState.backendReady = false;
    return null;
  } finally {
    appState.portVerificationInProgress = false;
  }
}

async function getBackendStatus() {
  const port = await resolveBackendPort();
  const message = appState.backendReady
    ? `后端已就绪（端口 ${port || '未知'}）`
    : appState.backendStarting
      ? '后端正在启动中，请稍候...'
      : '后端尚未就绪';

  return {
    ready: appState.backendReady,
    port: port || null,
    message,
  };
}

// ============ 工具信息管理 ============
function getToolTitle(toolName) {
  return TOOL_TITLES[toolName] || toolName;
}

function getToolPath(toolName) {
  const htmlFile = TOOL_HTML_MAP[toolName];
  if (htmlFile) {
    const toolPath = path.join(__dirname, 'tools', htmlFile);
    if (fs.existsSync(toolPath)) {
      return { toolName, htmlFile };
    }
  }
  return null;
}

// ============ 后端启动 ============
function waitForBackendReady() {
  return new Promise((readyResolve) => {
    const startTime = Date.now();
    const timeoutMs = TIMEOUTS.BACKEND_STARTUP;

    const check = () => {
      if (Date.now() - startTime >= timeoutMs) {
        readyResolve(false);
        return;
      }

      const port = readBackendPort();
      if (port > 0) {
        const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
          if (res.statusCode === 200) {
            appState.backendPort = port;
            console.log(`✅ 合并后端健康检查通过，端口: ${port}`);
            readyResolve(true);
          } else {
            setTimeout(check, TIMEOUTS.PORT_VERIFY_INTERVAL);
          }
        });

        req.on('error', () => setTimeout(check, TIMEOUTS.PORT_VERIFY_INTERVAL));
        req.setTimeout(TIMEOUTS.HEALTH_CHECK, () => {
          req.destroy();
          setTimeout(check, TIMEOUTS.PORT_VERIFY_INTERVAL);
        });
      } else {
        setTimeout(check, TIMEOUTS.PORT_VERIFY_INTERVAL);
      }
    };

    check();
  });
}

function startBackendProcess(pythonCmd) {
  return new Promise((resolve, reject) => {
    const backendScript = appState.getBackendScriptPath();
    console.log(`启动后端: ${pythonCmd} ${backendScript}`);

    appState.combinedBackend = spawn(pythonCmd, [backendScript], {
      cwd: __dirname,
      stdio: ['inherit', 'inherit', 'inherit'],
      shell: true,
      windowsHide: false,
    });

    appState.combinedBackend.on('error', (err) => {
      console.error('❌ 启动合并后端失败:', err.message);
      appState.combinedBackend = null;
      reject(err);
    });

    appState.combinedBackend.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        console.error(`合并后端异常退出，代码: ${code}`);
      }
      appState.combinedBackend = null;
    });

    resolve();
  });
}

function startCombinedBackend() {
  return new Promise((resolve) => {
    if (appState.backendStarting) {
      const check = () => {
        if (!appState.backendStarting) {
          resolve(appState.backendReady);
        } else {
          setTimeout(check, 200);
        }
      };
      check();
      return;
    }

    appState.backendStarting = true;
    console.log('正在启动合并 Python 后端...');

    const backendScript = appState.getBackendScriptPath();
    if (!fs.existsSync(backendScript)) {
      console.warn('合并后端脚本不存在:', backendScript);
      appState.backendStarting = false;
      resolve(false);
      return;
    }

    // 先检查是否已在运行
    const existingPort = readBackendPort();
    if (existingPort && existingPort > 0) {
      verifyBackendPort(existingPort).then((ok) => {
        if (ok) {
          appState.backendPort = existingPort;
          appState.backendReady = true;
          appState.backendStarting = false;
          console.log(`合并后端已在运行于端口 ${existingPort}`);
          resolve(true);
        } else {
          console.warn(`已有端口 ${existingPort} 不可用，重新启动后端`);
          clearBackendPortFile();
          attemptStartBackend(resolve);
        }
      });
    } else {
      attemptStartBackend(resolve);
    }
  });
}

function attemptStartBackend(resolve) {
  const pythonCandidates = process.platform === 'win32'
    ? ['py', 'python']
    : ['python', 'py'];

  let index = 0;

  function tryNext() {
    if (index >= pythonCandidates.length) {
      console.error('❌ 无法找到可用的 Python 命令，请检查 Python 是否已安装');
      appState.backendStarting = false;
      resolve(false);
      return;
    }

    const pythonCmd = pythonCandidates[index];
    index++;

    startBackendProcess(pythonCmd)
      .then(() => {
        waitForBackendReady().then((ready) => {
          appState.backendStarting = false;
          if (!ready) {
            console.warn('⚠️ 合并后端启动超时或健康检查失败，继续运行...');
            resolve(false);
          } else {
            resolve(true);
          }
        });
      })
      .catch(() => {
        console.warn(`未找到命令 ${pythonCmd}，尝试下一个可用 Python 命令...`);
        tryNext();
      });
  }

  tryNext();
}

// ============ HTTP 代理 ============
async function proxyToBackend(req, res) {
  let port = await resolveBackendPort();

  if (!port) {
    const filePort = readBackendPort();
    if (filePort) {
      console.log('[代理] 尝试直接使用端口文件中的端口:', filePort);
      port = filePort;
    }
  }

  if (!port) {
    console.error('[代理] 无效的端口:', port);
    res.writeHead(503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      success: false,
      error: '后端服务端口不可用，请稍候重试。',
      debug_port: port,
      backendPort: appState.backendPort,
    }));
    return;
  }

  const chunks = [];
  req.on('data', (chunk) => chunks.push(chunk));
  req.on('end', () => {
    const bodyBuffer = Buffer.concat(chunks);

    const options = {
      hostname: '127.0.0.1',
      port: port,
      path: req.url,
      method: req.method,
      headers: Object.assign({}, req.headers, {
        'content-length': Buffer.byteLength(bodyBuffer),
      }),
      timeout: TIMEOUTS.PROXY_REQUEST,
    };

    const proxyReq = http.request(options, (proxyRes) => {
      const responseChunks = [];
      proxyRes.on('data', (chunk) => responseChunks.push(chunk));
      proxyRes.on('end', () => {
        const responseBody = Buffer.concat(responseChunks);
        const contentType = proxyRes.headers['content-type'] || '';
        const statusCode = proxyRes.statusCode || 500;
        const bodyStr = responseBody.toString('utf-8');

        const isJsonResponse = contentType.includes('application/json') || contentType.includes('text/json');

        if (isJsonResponse) {
          try {
            JSON.parse(bodyStr);
            res.writeHead(statusCode, proxyRes.headers);
            res.end(responseBody);
          } catch (e) {
            console.error('[代理] 后端返回了无效的 JSON:', bodyStr.substring(0, 500));
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              success: false,
              error: '后端服务返回了无效的响应格式',
              debug_response: bodyStr.substring(0, 200),
            }));
          }
        } else if (statusCode >= 400) {
          console.error('[代理] 后端返回错误:', statusCode, bodyStr.substring(0, 500));
          res.writeHead(statusCode, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            success: false,
            error: bodyStr.substring(0, 500) || `后端服务错误 (${statusCode})`,
            status_code: statusCode,
          }));
        } else {
          res.writeHead(statusCode, proxyRes.headers);
          res.end(responseBody);
        }
      });
    });

    proxyReq.setTimeout(TIMEOUTS.PROXY_REQUEST);
    proxyReq.on('error', (err) => {
      console.error(`[代理错误] 无法连接到后端 http://127.0.0.1:${port}:`, err.message);
      res.writeHead(503, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: false,
        error: `后端服务未启动或无法连接（尝试端口 ${port}）。请检查后端是否正在运行。`,
        debug_port: port,
        debug_error: err.message,
      }));
    });

    proxyReq.on('timeout', () => {
      console.error(`[代理] 后端请求超时 (${port})`);
      proxyReq.destroy();
      res.writeHead(504, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: false,
        error: `后端服务响应超时（端口 ${port}）`,
      }));
    });

    proxyReq.write(bodyBuffer);
    proxyReq.end();
  });
}

// ============ API 路由处理 ============
async function handleApiRequest(req, res) {
  const url = req.url.split('?')[0];
  const method = req.method;

  // 设置 CORS 头
  Object.entries(CORS_HEADERS).forEach(([key, value]) => {
    res.setHeader(key, value);
  });

  if (method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  if (url === '/backend-status') {
    const status = await getBackendStatus();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      success: status.ready,
      ready: status.ready,
      port: status.port,
      message: status.message,
    }));
    return;
  }

  if (url.startsWith('/api/')) {
    await proxyToBackend(req, res);
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'API not found' }));
}

// ============ HTTP 服务器 ============
function startHttpServer() {
  return new Promise((resolve, reject) => {
    if (appState.hasExceededPortRetry()) {
      reject(new Error('端口重试次数超过限制'));
      return;
    }

    const server = http.createServer(async (req, res) => {
      let filePath = req.url.split('?')[0];

      // 设置通用响应头
      Object.entries(CORS_HEADERS).forEach(([key, value]) => {
        res.setHeader(key, value);
      });
      Object.entries(CACHE_CONTROL_HEADERS).forEach(([key, value]) => {
        res.setHeader(key, value);
      });

      // API 请求处理
      if (filePath === '/backend-status' || filePath.startsWith('/api/')) {
        try {
          await handleApiRequest(req, res);
        } catch (err) {
          console.error('API 处理错误:', err);
          if (!res.headersSent) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
          }
          res.end(JSON.stringify({ success: false, error: '内部服务器错误' }));
        }
        return;
      }

      // 静态文件请求
      if (filePath.startsWith('/static/')) {
        await serveStaticFile(req, res, filePath);
        return;
      }

      // 处理主页面请求
      filePath = filePath === '/' ? '/index.html' : filePath;

      // 检查是否是报告标准化工具页面
      if (filePath === '/report-standard' || filePath === '/tools/index.html') {
        await serveTemplatePage(req, res);
        return;
      }

      await serveToolFile(req, res, filePath);
    });

    server.listen(appState.httpPort, '127.0.0.1', () => {
      console.log(`✅ HTTP Server running at http://127.0.0.1:${appState.httpPort}`);
      appState.httpServer = server;
      appState.resetPortRetry();
      resolve();
    });

    server.on('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        console.log(`端口 ${appState.httpPort} 被占用，尝试 ${appState.httpPort + 1}...`);
        appState.httpPort++;
        appState.incrementPortRetry();
        startHttpServer().then(resolve).catch(reject);
      } else {
        reject(err);
      }
    });
  });
}

async function serveStaticFile(req, res, filePath) {
  const staticDir = appState.getStaticDir();
  const staticFile = filePath.substring(8);
  const fullPath = path.join(staticDir, staticFile);

  // 路径安全检查
  if (!isPathSafe(staticDir, fullPath)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  const ext = path.extname(fullPath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  try {
    const content = await fs.promises.readFile(fullPath);
    res.setHeader('Content-Type', contentType);
    res.writeHead(200);
    res.end(content);
  } catch (err) {
    res.writeHead(404);
    res.end('Not Found');
  }
}

async function serveTemplatePage(req, res) {
  const templatePath = path.join(appState.getTemplatesDir(), 'index.html');

  // 路径安全检查
  if (!isPathSafe(appState.getTemplatesDir(), templatePath)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  try {
    const content = await fs.promises.readFile(templatePath, 'utf-8');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.writeHead(200);
    res.end(content);
  } catch (err) {
    res.writeHead(404);
    res.end('Not Found');
  }
}

async function serveToolFile(req, res, filePath) {
  const toolsDir = appState.getToolsDir();
  const fullPath = path.join(toolsDir, filePath);

  // 路径安全检查
  if (!isPathSafe(toolsDir, fullPath)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  const ext = path.extname(fullPath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  try {
    const content = await fs.promises.readFile(fullPath);
    res.setHeader('Content-Type', contentType);
    res.writeHead(200);
    res.end(content);
  } catch (err) {
    if (err.code === 'ENOENT') {
      // 文件不存在，返回 index.html
      try {
        const indexContent = await fs.promises.readFile(path.join(toolsDir, 'index.html'));
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        res.writeHead(200);
        res.end(indexContent);
      } catch {
        res.writeHead(404);
        res.end('Not Found');
      }
    } else {
      res.writeHead(500);
      res.end('Server Error');
    }
  }
}

// ============ 窗口管理 ============
function createWindow() {
  appState.mainWindow = new BrowserWindow({
    width: 1000,
    height: 750,
    minWidth: 900,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: '案件处理启动器',
    autoHideMenuBar: true,
  });

  appState.mainWindow.loadFile('index.html');
}

function createToolWindow(toolName, htmlFile) {
  const toolWin = new BrowserWindow({
    width: 1000,
    height: 750,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: getToolTitle(toolName),
    autoHideMenuBar: true,
  });

  toolWin.loadURL(`http://127.0.0.1:${appState.httpPort}/${htmlFile}`);
  toolWin.on('closed', () => {
    console.log(`工具窗口已关闭: ${toolName}`);
  });
}

// ============ 应用初始化 ============
async function initApp() {
  try {
    await startHttpServer();
    createWindow();
    console.log('案件处理启动器已就绪');
    console.log(`工具页面访问地址: http://127.0.0.1:${appState.httpPort}`);

    console.log('正在初始化后端服务（报告生成 + 报告标准化）...');
    const backendStarted = await startCombinedBackend();
    appState.backendReady = backendStarted;

    if (backendStarted) {
      console.log(`✅ 后端服务已就绪（端口: ${appState.backendPort}）`);
    } else {
      console.log('⚠️ 后端服务未就绪，部分功能可能不可用');
    }
  } catch (err) {
    console.error('启动失败:', err);
    app.quit();
  }
}

// ============ App 生命周期 ============
app.whenReady().then(initApp);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (appState.httpServer) {
      appState.httpServer.close();
    }
    if (appState.combinedBackend) {
      appState.combinedBackend.kill('SIGTERM');
    }
    if (appState.attachmentProcessorProcess) {
      appState.attachmentProcessorProcess.kill('SIGTERM');
    }
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// ============ IPC 处理器 ============

// 案件数据
ipcMain.handle('save-case-data', async (event, data) => {
  try {
    const filePath = path.join(__dirname, 'case-data.json');
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('load-case-data', async () => {
  try {
    const filePath = path.join(__dirname, 'case-data.json');
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    }
    return {};
  } catch (error) {
    return {};
  }
});

// 工具管理
ipcMain.handle('get-tool-list', async () => {
  const tools = [
    { id: 'reportGenerate', name: '报告生成', icon: '📝', desc: '上传图片+笔录→自动生成勘查报告' },

    { id: 'catalogTool', name: '目录工具', icon: '📑', desc: '生成附件清单Word表格' },

    { id: 'approvalForm', name: '结案审批表', icon: '✅', desc: '填写结案审批表' },

    { id: 'attachmentProcessor', name: '附件处理器', icon: '🖼️', desc: '图片附件→Markdown→Word文档' },
  ];

  return tools.map(tool => {
    const toolInfo = getToolPath(tool.id);
    return {
      ...tool,
      exists: toolInfo !== null,
      path: toolInfo ? `http://127.0.0.1:${appState.httpPort}/${toolInfo.htmlFile}` : '',
    };
  });
});

ipcMain.handle('run-tool', async (event, { toolName }) => {
  // 附件处理器特殊处理：需要启动独立的 Node.js Express 服务器
  if (toolName === 'attachmentProcessor') {
    try {
      // 如果已经启动，直接打开窗口
      const toolWin = new BrowserWindow({
        width: 1300,
        height: 800,
        minWidth: 1000,
        minHeight: 700,
        webPreferences: {
          preload: path.join(__dirname, 'preload.js'),
          contextIsolation: true,
          nodeIntegration: false,
        },
        title: '附件处理器',
        autoHideMenuBar: true,
      });

      toolWin.loadURL(`http://127.0.0.1:${TIMEOUTS.ATTACHMENT_PROCESSOR_PORT}`);
      toolWin.on('closed', () => {
        console.log('附件处理器窗口已关闭');
      });
      
      // 检查Node.js进程是否已启动
      if (!appState.attachmentProcessorProcess) {
        const serverPath = path.join(__dirname, 'tools', '附件处理器-合并版', 'server.js');
        if (fs.existsSync(serverPath)) {
          console.log('正在启动附件处理器 Node.js 后端...');
          appState.attachmentProcessorProcess = spawn('node', [serverPath], {
            cwd: path.join(__dirname, 'tools', '附件处理器-合并版'),
            stdio: 'pipe',
            shell: true,
            windowsHide: false,
          });
          
          appState.attachmentProcessorProcess.stdout.on('data', (data) => {
            console.log(`[附件处理器] ${data.toString().trim()}`);
          });
          
          appState.attachmentProcessorProcess.stderr.on('data', (data) => {
            console.error(`[附件处理器] ${data.toString().trim()}`);
          });
          
          appState.attachmentProcessorProcess.on('exit', (code) => {
            console.log(`附件处理器退出，代码: ${code}`);
            appState.attachmentProcessorProcess = null;
          });
        } else {
          console.warn('附件处理器 server.js 不存在:', serverPath);
        }
      }
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
  
  // 其他工具通过 Electron HTTP 代理加载
  const toolInfo = getToolPath(toolName);
  if (!toolInfo) {
    return { success: false, error: `工具不存在: ${toolName}` };
  }
  try {
    createToolWindow(toolName, toolInfo.htmlFile);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('run-tools-batch', async (event, toolNames) => {
  const results = [];
  for (const toolName of toolNames) {
    const toolInfo = getToolPath(toolName);
    if (!toolInfo) {
      results.push({ tool: toolName, success: false, error: '工具不存在' });
      continue;
    }
    try {
      createToolWindow(toolName, toolInfo.htmlFile);
      results.push({ tool: toolName, success: true });
    } catch (error) {
      results.push({ tool: toolName, success: false, error: error.message });
    }
    await new Promise(r => setTimeout(r, TIMEOUTS.TOOL_WINDOW_DELAY));
  }
  return results;
});

// 文件对话框
ipcMain.handle('select-file', async (event, options) => {
  const result = await dialog.showOpenDialog({
    properties: options && options.directory ? ['openDirectory'] : ['openFile'],
    filters: options && options.filters || [{ name: '所有文件', extensions: ['*'] }],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('save-file', async (event, options) => {
  let defaultPath = 'output';
  let title = '保存文件';

  if (typeof options === 'string') {
    defaultPath = options;
  } else if (options && typeof options === 'object') {
    title = options.title || title;
    defaultPath = options.defaultPath || defaultPath;
  }

  const result = await dialog.showSaveDialog({
    title,
    defaultPath,
  });
  return result.canceled ? null : result.filePath;
});

ipcMain.handle('open-folder', async (event, folderPath) => {
  const { shell } = require('electron');
  return shell.openPath(folderPath);
});

ipcMain.handle('save-docx-file', async (event, { content, defaultName }) => {
  try {
    const result = await dialog.showSaveDialog({
      defaultPath: defaultName || 'document.docx',
      filters: [
        { name: 'Word 文档', extensions: ['docx'] },
        { name: '所有文件', extensions: ['*'] },
      ],
    });

    if (result.canceled || !result.filePath) {
      return { success: false, error: '用户取消保存' };
    }

    const buffer = Buffer.from(content, 'base64');
    fs.writeFileSync(result.filePath, buffer);
    return { success: true, filePath: result.filePath };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// ============ 目录模板工具 IPC ============
ipcMain.handle('dialog:openFile', async (event, options) => {
  const result = await dialog.showOpenDialog({
    title: (options && options.title) || '选择文件',
    filters: (options && options.filters) || [
      { name: 'Word文档', extensions: ['docx'] },
      { name: '所有文件', extensions: ['*'] },
    ],
    properties: ['openFile'],
  });
  return result;
});

ipcMain.handle('dialog:saveFile', async (event, options) => {
  const result = await dialog.showSaveDialog({
    title: (options && options.title) || '保存文件',
    defaultPath: (options && options.defaultPath) || '目录.docx',
    filters: (options && options.filters) || [
      { name: 'Word文档', extensions: ['docx'] },
    ],
  });
  return result;
});

ipcMain.handle('file:read', async (event, filePath) => {
  try {
    const buffer = fs.readFileSync(filePath);
    return { success: true, data: buffer.toString('base64') };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('file:write', async (event, filePath, base64Data) => {
  try {
    const buffer = Buffer.from(base64Data, 'base64');
    fs.writeFileSync(filePath, buffer);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('file:exists', async (event, filePath) => {
  return fs.existsSync(filePath);
});

// DOCX 表格处理
ipcMain.handle('docx:replaceTable', async (event, base64Data, reportContent, attachments) => {
  try {
    const JSZip = require('jszip');
    const arrayBuffer = Buffer.from(base64Data, 'base64');
    console.log('=== 开始处理 DOCX ===');

    const zip = await JSZip.loadAsync(arrayBuffer);
    let xml = await zip.file('word/document.xml').async('string');

    const allTables = xml.match(/<w:tbl[\s\S]*?<\/w:tbl>/g);
    console.log('找到表格数量:', allTables ? allTables.length : 0);

    if (!allTables || allTables.length === 0) {
      return { success: false, error: '未在文档中找到目录表格' };
    }

    const lastTableXml = allTables[allTables.length - 1];

    const catalogData = {
      reportContent: reportContent || [],
      attachments: attachments || [],
    };

    const newTableXml = generateCompleteCatalogXml(catalogData, lastTableXml);
    console.log('生成的新表格行数:', (newTableXml.match(/<w:tr[\s>]/g) || []).length);

    xml = xml.replace(lastTableXml, newTableXml);
    zip.file('word/document.xml', xml);

    const newDocx = await zip.generateAsync({ type: 'base64', compression: 'DEFLATE' });
    return { success: true, data: newDocx };
  } catch (error) {
    console.error('处理错误:', error);
    return { success: false, error: error.message };
  }
});

// ============ 结案审批表工具 IPC ============

// 选择Excel模板文件
ipcMain.handle('select-template', async () => {
  try {
    const result = await dialog.showOpenDialog({
      title: '选择Excel模板文件',
      filters: [
        { name: 'Excel文件', extensions: ['xlsx', 'xls'] },
        { name: '所有文件', extensions: ['*'] },
      ],
      properties: ['openFile'],
    });
    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  } catch (error) {
    console.error('选择模板文件失败:', error);
    return null;
  }
});

// 选择输出路径
ipcMain.handle('select-output', async (event, defaultName) => {
  try {
    const result = await dialog.showSaveDialog({
      title: '保存Excel文件',
      defaultPath: defaultName || '结案审批表.xlsx',
      filters: [
        { name: 'Excel文件', extensions: ['xlsx'] },
        { name: '所有文件', extensions: ['*'] },
      ],
    });
    if (result.canceled || !result.filePath) {
      return null;
    }
    return result.filePath;
  } catch (error) {
    console.error('选择输出路径失败:', error);
    return null;
  }
});

// 解析输入文本（从AI报告文本中提取案件字段）
ipcMain.handle('parse-input', async (event, text) => {
  try {
    if (!text) {
      return { success: false, error: '输入文本为空' };
    }
    
    const data = {};
    const fields = [];
    
    // 定义要提取的字段及其正则模式
    const fieldPatterns = [
      { key: 'policyNo', label: '保单号', patterns: [
          /保单号[：:]\s*([^\s,，\n\r]+)/i,
          /保单号码[：:]\s*([^\s,，\n\r]+)/i,
          /policy\s*(?:no|number)[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'insured', label: '投保人', patterns: [
          /投保人[：:]\s*([^\s,，\n\r]+)/i,
          /投保人名称[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'insuredPerson', label: '被保险人/伤者', patterns: [
          /被保险[人人][：:]\s*([^\s,，\n\r]+)/i,
          /伤[者员][：:]\s*([^\s,，\n\r]+)/i,
          /受伤[人人][员员][：:]\s*([^\s,，\n\r]+)/i,
          /出险[人人][员员][：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'insuranceType', label: '保险险种', patterns: [
          /保险险种[：:]\s*([^\s,，\n\r]+)/i,
          /险种[：:]\s*([^\s,，\n\r]+)/i,
          /险别[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'accidentDate', label: '出险时间', patterns: [
          /出险时间[：:]\s*([^\s,，\n\r]+)/i,
          /事故发生时间[：:]\s*([^\s,，\n\r]+)/i,
          /案发时间[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'accidentLocation', label: '出险地点', patterns: [
          /出险地点[：:]\s*([^\n\r]+)/i,
          /事故发生地点[：:]\s*([^\n\r]+)/i,
          /案发地点[：:]\s*([^\n\r]+)/i,
          /地点[：:]\s*([^\n\r]+)/i,
        ] },
      { key: 'claimAmount', label: '索赔金额', patterns: [
          /索赔金额[：:]\s*([^\s,，\n\r]+)/i,
          /理赔金额[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'suggestion', label: '赔付建议', patterns: [
          /赔付建议[：:]\s*([^\n\r]+)/i,
          /处理建议[：:]\s*([^\n\r]+)/i,
          /建议[：:]\s*([^\n\r]+)/i,
        ] },
      { key: 'acceptDate', label: '受案时间', patterns: [
          /受案时间[：:]\s*([^\s,，\n\r]+)/i,
          /受理时间[：:]\s*([^\s,，\n\r]+)/i,
          /立案时间[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'closeDate', label: '结案时间', patterns: [
          /结案时间[：:]\s*([^\s,，\n\r]+)/i,
          /完成时间[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'insurancePeriod', label: '保险期间', patterns: [
          /保险期间[：:]\s*([^\n\r]+)/i,
          /保险期限[：:]\s*([^\n\r]+)/i,
        ] },
      { key: 'accidentNature', label: '事故性质', patterns: [
          /事故性质[：:]\s*([^\s,，\n\r]+)/i,
          /事故类型[：:]\s*([^\s,，\n\r]+)/i,
        ] },
      { key: 'investigator', label: '调查员', patterns: [
          /调查[员人][：:]\s*([^\s,，\n\r]+)/i,
          /查勘[员人][：:]\s*([^\s,，\n\r]+)/i,
          /经办[人人][：:]\s*([^\s,，\n\r]+)/i,
        ] },
    ];
    
    // 按行提取（兼容Markdown表格和键值对）
    const lines = text.split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      
      // 跳过Markdown表格分隔行
      if (trimmed.match(/^[\|\s\-:]+$/)) continue;
      
      for (const field of fieldPatterns) {
        if (data[field.key]) continue; // 已找到
        for (const pattern of field.patterns) {
          const match = trimmed.match(pattern);
          if (match) {
            const value = match[1].trim();
            if (value && value.length < 100) { // 避免提取过长文本
              data[field.key] = value;
              fields.push({ key: field.key, label: field.label, value });
              break;
            }
          }
        }
      }
    }
    
    // 如果没提取到，再尝试全文匹配（用于跨行匹配）
    if (!data.accidentLocation || !data.suggestion) {
      for (const field of fieldPatterns) {
        if (data[field.key]) continue;
        for (const pattern of field.patterns) {
          const match = text.match(pattern);
          if (match) {
            const value = match[1].trim();
            if (value && value.length < 100) {
              data[field.key] = value;
              fields.push({ key: field.key, label: field.label, value });
              break;
            }
          }
        }
      }
    }
    
    return { success: true, data, fields: fields.map(f => f.key) };
  } catch (error) {
    console.error('解析输入失败:', error);
    return { success: false, error: error.message };
  }
});

// 填充Excel模板
ipcMain.handle('fill-excel', async (event, options) => {
  try {
    const { templatePath, outputPath, caseData } = options;
    
    if (!templatePath) {
      return { success: false, error: '未指定模板路径' };
    }
    if (!outputPath) {
      return { success: false, error: '未指定输出路径' };
    }
    if (!caseData) {
      return { success: false, error: '未提供案件数据' };
    }
    
    // 使用 python 脚本处理 Excel (通过子进程调用)
    const { spawnSync } = require('child_process');
    
    const scriptContent = `
import sys, json, os
try:
    import openpyxl
    wb = openpyxl.load_workbook(r"${templatePath.replace(/\\/g, '\\\\')}")
    ws = wb.active
    
    data = json.loads(r'''${JSON.stringify(caseData).replace(/'/g, "\\'")}''')
    
    # 定义映射：字段 -> 单元格中的关键词
    field_keywords = {
        'policyNo': ['保单号', '保单号码'],
        'insuranceType': ['保险险种', '险种', '险别'],
        'insured': ['投保人', '投保'],
        'insuredPerson': ['被保险人', '伤者', '受伤人员', '出险人员'],
        'accidentDate': ['出险时间', '出险日期', '事故发生时间', '事故日期'],
        'accidentLocation': ['出险地点', '事故地点', '案发地点', '地点'],
        'claimAmount': ['索赔金额', '理赔金额'],
        'suggestion': ['赔付建议', '处理建议'],
        'acceptDate': ['受案时间', '受理时间', '立案时间'],
        'closeDate': ['结案时间', '完成时间'],
        'investigator': ['调查员', '查勘员', '经办人'],
        'insurancePeriod': ['保险期间', '保险期限'],
        'accidentNature': ['事故性质', '事故类型'],
    }
    
    # 辅助函数：安全写入单元格（处理合并单元格）
    def safe_set_cell_value(ws, row, col, value):
        # 检查单元格是否在合并区域中
        for merged_range in ws.merged_cells.ranges:
            if merged_range.min_row <= row <= merged_range.max_row and merged_range.min_col <= col <= merged_range.max_col:
                if row == merged_range.min_row and col == merged_range.min_col:
                    # 是合并区域的左上角，可以直接写入
                    ws.cell(row=row, column=col).value = value
                    return True
                else:
                    # 在合并区域中但不是左上角 → 写入左上角
                    ws.cell(row=merged_range.min_row, column=merged_range.min_col).value = value
                    return True
        # 非合并单元格，直接写入
        ws.cell(row=row, column=col).value = value
        return True
    
    filled = 0
    
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell_text = str(cell.value).strip()
                for field, keywords in field_keywords.items():
                    if field in data and data[field]:
                        for kw in keywords:
                            if kw in cell_text:
                                # 找到匹配的关键词，将数据填入右边的单元格
                                # 使用 safe_set_cell_value 处理合并单元格
                                if safe_set_cell_value(ws, cell.row, cell.column + 1, data[field]):
                                    filled += 1
                                break
    
    wb.save(r"${outputPath.replace(/\\/g, '\\\\')}")
    print(json.dumps({"success": True, "filled": filled, "path": "${outputPath.replace(/\\/g, '\\\\')}"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
`;
    
    // 写入临时脚本文件
    const tmpScriptPath = path.join(__dirname, 'temp_fill_excel.py');
    fs.writeFileSync(tmpScriptPath, scriptContent, 'utf-8');
    
    const pythonCandidates = process.platform === 'win32' ? ['py', 'python'] : ['python', 'py'];
    let result = null;
    
    for (const pythonCmd of pythonCandidates) {
      result = spawnSync(pythonCmd, [tmpScriptPath], {
        cwd: __dirname,
        timeout: 30000,
        encoding: 'utf-8',
      });
      if (result.status === 0 || result.stdout) break;
    }
    
    // 清理临时脚本
    try { fs.unlinkSync(tmpScriptPath); } catch(e) {}
    
    if (result && result.stdout) {
      // 找到最后一行JSON输出
      const lines = result.stdout.trim().split('\n');
      const lastLine = lines[lines.length - 1].trim();
      try {
        const parsed = JSON.parse(lastLine);
        if (parsed.success) {
          return { success: true, path: parsed.path };
        } else {
          return { success: false, error: parsed.error || '填充失败' };
        }
      } catch (e) {
        return { success: false, error: '解析Python输出失败: ' + result.stdout.substring(0, 200) };
      }
    } else {
      return { success: false, error: result ? (result.stderr || '进程执行失败') : '无法找到Python' };
    }
  } catch (error) {
    console.error('填充Excel失败:', error);
    return { success: false, error: error.message };
  }
});

// ============ 目录表格生成函数 ============
function extractRowTemplate(tableXml) {
  const rowRegex = /<w:tr[\s\S]*?<\/w:tr>/g;
  const rows = [];
  let m;
  while ((m = rowRegex.exec(tableXml)) !== null) {
    rows.push(m[0]);
  }
  if (rows.length < 2) {
    console.log('警告：表格行数不足，无法提取数据行模板');
    return null;
  }
  return rows[1];
}

function randomParaId() {
  return Math.floor(Math.random() * 0xFFFFFFFF).toString(16).toUpperCase().padStart(8, '0');
}

function escapeXml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function cloneRowWithTextSafe(templateRow, numText, nameText) {
  let result = templateRow.replace(/w14:paraId="[^"]+"/g, () => {
    return 'w14:paraId="' + randomParaId() + '"';
  });

  const tcRegex = /(<w:tc>[\s\S]*?<\/w:tc>)/g;
  const tcs = [];
  let mm;
  while ((mm = tcRegex.exec(result)) !== null) {
    tcs.push(mm[1]);
  }

  if (tcs.length < 2) {
    console.log('警告：模板行单元格不足2个，直接返回');
    return result;
  }

  const tc0 = tcs[0].replace(/(<w:t>)[^<]*(<\/w:t>)/, (m, open, close) => {
    return open + escapeXml(numText) + close;
  });
  const tc1 = tcs[1].replace(/(<w:t>)[^<]*(<\/w:t>)/, (m, open, close) => {
    return open + escapeXml(nameText) + close;
  });

  result = result.replace(tcs[0], tc0);
  result = result.replace(tcs[1], tc1);
  return result;
}

function extractTableStructure(tableXml) {
  const tblPr = tableXml.match(/<w:tblPr>[\s\S]*?<\/w:tblPr>/);
  const tblGrid = tableXml.match(/<w:tblGrid>[\s\S]*?<\/w:tblGrid>/);
  const allRows = tableXml.match(/<w:tr[\s\S]*?<\/w:tr>/g) || [];

  let headerRow = null;
  for (let i = 0; i < allRows.length; i++) {
    const row = allRows[i];
    if (row.includes('<w:tblHeader') || row.includes('<w:trHeader')) {
      headerRow = row;
      break;
    }
  }

  if (!headerRow) {
    for (let i = 0; i < allRows.length; i++) {
      const row = allRows[i];
      if (row.includes('序号') || row.includes('目录') || row.includes('资料名称')) {
        headerRow = row;
        break;
      }
    }
  }

  if (!headerRow && allRows.length > 0) {
    headerRow = allRows[0];
  }

  return {
    tblPr: tblPr ? tblPr[0] : '',
    tblGrid: tblGrid ? tblGrid[0] : '',
    headerRow: headerRow || '',
  };
}

function generateCompleteCatalogXml(catalogData, oldTableXml) {
  const attachments = catalogData.attachments || [];
  const structure = extractTableStructure(oldTableXml);
  const rowTemplate = extractRowTemplate(oldTableXml);

  if (!rowTemplate) {
    console.log('警告：无法提取数据行模板，返回原表格');
    return oldTableXml;
  }

  // 生成所有数据行
  const dataRows = attachments.map((item, index) => {
    const num = String(index + 1);
    const name = item.name || item.fileName || item.description || '';
    return cloneRowWithTextSafe(rowTemplate, num, name);
  });

  // 重建完整表格
  const headerRow = structure.headerRow || '';
  const newTableXml = `<w:tbl>${structure.tblPr}${structure.tblGrid}${headerRow}${dataRows.join('')}</w:tbl>`;

  return newTableXml;
}
