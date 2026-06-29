/**
 * 附件处理器合并版 - 服务器
 * 
 * 整合附件映射、Markdown生成和Word转换功能
 * 支持一键连续流程 + SSE实时进度推送
 * 
 * 优化：上传图片直接存为临时文件，避免base64在内存中反复拷贝
 */

const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const wf = require('./workflow');

const app = express();
const PORT = 3000;

// ============================================================
// SSE 客户端管理
// ============================================================
const sseClients = new Set();

/**
 * 向所有连接的SSE客户端广播进度消息
 */
function broadcastProgress(data) {
  const msg = `data: ${JSON.stringify(data)}\n\n`;
  for (const client of sseClients) {
    try {
      client.write(msg);
    } catch (e) {
      sseClients.delete(client);
    }
  }
}

/**
 * 发送SSE进度事件
 */
function sseSend(client, data) {
  try {
    client.write(`data: ${JSON.stringify(data)}\n\n`);
  } catch (e) {
    sseClients.delete(client);
  }
}

// 确保临时目录存在
const tmpDir = path.join(__dirname, 'temp');
if (!fs.existsSync(tmpDir)) {
  fs.mkdirSync(tmpDir, { recursive: true });
}

// 配置文件上传 - 使用磁盘存储，避免内存占用
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, tmpDir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname) || '.jpg';
    cb(null, `upload_${Date.now()}_${Math.random().toString(36).slice(2, 8)}${ext}`);
  }
});
const upload = multer({ storage, limits: { fileSize: 200 * 1024 * 1024 } });

// 请求体限制 - 文件夹上传可能包含base64图片数据，需要更大的限制
app.use(express.json({ limit: '200mb', extended: true }));
app.use(express.urlencoded({ extended: true, limit: '200mb' }));
app.use(express.static(__dirname));

// 提供temp目录的静态文件访问（用于缩略图显示）
app.use('/temp', express.static(tmpDir));

// ============================================================
// API 接口
// ============================================================

/**
 * SSE 实时进度推送端点
 * 前端通过 EventSource 连接此端点接收实时进度
 */
app.get('/api/progress', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
  });

  // 发送初始连接成功消息
  res.write(`data: ${JSON.stringify({ type: 'connected', message: 'SSE连接已建立' })}\n\n`);

  sseClients.add(res);

  // 客户端断开时清理
  req.on('close', () => {
    sseClients.delete(res);
  });
});

/**
 * 获取默认附件名称
 */
app.get('/api/default-names', (req, res) => {
  res.json({
    names: wf.DEFAULT_ATTACHMENT_NAMES,
    ranges: wf.DEFAULT_RANGES
  });
});

/**
 * 上传DOCX模板
 */
app.post('/api/upload-docx', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: '请上传DOCX文件' });
    }
    
    broadcastProgress({ type: 'docx', status: 'processing', message: '正在解析DOCX模板...' });
    const result = await wf.extractDocxContent(req.file.buffer);
    broadcastProgress({ type: 'docx', status: 'done', message: `DOCX解析完成：${result.title || '未命名'}` });
    
    res.json({
      success: true,
      content: result.content,
      title: result.title,
      header: result.header,
      imageSizes: result.imageSizes || []
    });
  } catch (err) {
    broadcastProgress({ type: 'docx', status: 'error', message: `DOCX解析失败：${err.message}` });
    console.error('DOCX处理失败:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * 上传图片 - 直接存为临时文件，返回文件路径而非base64
 */
app.post('/api/upload-images', upload.array('files', 100), async (req, res) => {
  try {
    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ error: '请上传图片文件' });
    }
    
    const images = req.files.map((file, index) => ({
      index,
      name: file.originalname,
      size: file.size,
      filepath: file.path  // 直接返回磁盘文件路径，不再转base64
    }));
    
    broadcastProgress({ type: 'images', status: 'uploaded', count: images.length, message: `已上传 ${images.length} 张图片` });
    
    res.json({
      success: true,
      count: images.length,
      images
    });
  } catch (err) {
    broadcastProgress({ type: 'images', status: 'error', message: `图片上传失败：${err.message}` });
    console.error('图片上传失败:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * 上传文件夹结构 - 通过FormData直接上传文件（避免base64内存问题）
 * 前端发送FormData:
 *   - files: 所有图片文件（multer处理）
 *   - folderMapping: JSON字符串，格式 [{folderName:"附件一", fileIndexes:[0,1]}, ...]
 * 后端解析文件与文件夹的对应关系，自动生成映射规则
 */
app.post('/api/upload-folder', upload.array('files', 500), async (req, res) => {
  try {
    let folderMapping = [];
    try {
      folderMapping = JSON.parse(req.body.folderMapping || '[]');
    } catch (e) {
      return res.status(400).json({ error: '文件夹映射数据格式错误' });
    }
    
    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ error: '请上传图片文件' });
    }
    
    broadcastProgress({ type: 'folder', status: 'processing', message: `正在处理 ${folderMapping.length} 个附件文件夹...` });
    
    // 按文件夹映射关系，将multer处理好的文件分组
    const processedFolders = [];
    let totalImages = 0;
    
    for (const folder of folderMapping) {
      const folderFiles = [];
      for (const idx of (folder.fileIndexes || [])) {
        const file = req.files[idx];
        if (file) {
          folderFiles.push({
            name: file.originalname,
            size: file.size,
            filepath: file.path
          });
        }
      }
      if (folderFiles.length > 0) {
        processedFolders.push({
          folderName: folder.folderName,
          files: folderFiles
        });
        totalImages += folderFiles.length;
      }
    }
    
    // 使用workflow的文件夹解析函数，自动生成映射规则和扁平化图片列表
    const { images, ranges } = wf.parseFolderStructure(processedFolders);
    
    broadcastProgress({ 
      type: 'folder', status: 'done', 
      message: `✅ 已识别 ${processedFolders.length} 个附件文件夹，共 ${totalImages} 张图片`,
      folders: processedFolders.length,
      images: totalImages
    });
    
    res.json({
      success: true,
      folders: processedFolders.length,
      totalImages,
      images,
      ranges,
      hasAutoMapping: ranges.length > 0
    });
  } catch (err) {
    broadcastProgress({ type: 'folder', status: 'error', message: `文件夹上传失败：${err.message}` });
    console.error('文件夹上传失败:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * 生成Markdown
 */
app.post('/api/generate-markdown', async (req, res) => {
  try {
    const { docContent, docTitle, attachmentNames, customRanges, images, header } = req.body;
    
    broadcastProgress({ type: 'markdown', status: 'processing', message: '正在生成Markdown...' });
    
    // 解析附件名称
    const names = wf.parseAttachmentNames(attachmentNames || '');
    
    // 构建附件数据
    const attachments = wf.buildAttachments(images || [], names, customRanges);
    
    // 生成Markdown（带进度回调）
    const markdown = wf.generateMarkdown(
      { content: docContent, title: docTitle },
      attachments,
      (current, total, detail) => {
        broadcastProgress({ 
          type: 'markdown', 
          status: 'progress', 
          current, total, 
          progress: Math.round((current / total) * 100),
          message: detail || `Markdown生成中 ${current}/${total}`
        });
      }
    );
    
    broadcastProgress({ type: 'markdown', status: 'done', message: 'Markdown生成完成' });
    
    res.json({
      success: true,
      markdown,
      attachments,
      header
    });
  } catch (err) {
    broadcastProgress({ type: 'markdown', status: 'error', message: `Markdown生成失败：${err.message}` });
    console.error('Markdown生成失败:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * 转换为Word - 直接从临时文件读取图片，无需base64传输
 */
app.post('/api/convert-word', async (req, res) => {
  try {
    const { markdown, images, header, docxImageSizes } = req.body;
    
    if (!markdown) {
      return res.status(400).json({ error: '请提供Markdown内容' });
    }
    
    broadcastProgress({ type: 'word', status: 'processing', message: '正在解析Markdown结构...' });
    
    // 解析Markdown
    const blocks = wf.parseMarkdownForDocx(markdown);
    
    // 处理图片 - 直接从磁盘文件读取
    const imageResults = [];
    const allImageUrls = [];
    
    // 收集所有图片URL
    for (const block of blocks) {
      if (block.type === 'images' && block.images) {
        for (const img of block.images) {
          if (img.url && !img.url.startsWith('data:')) {
            allImageUrls.push(img.url);
          }
        }
      }
    }
    
    // 处理图片（来自上传的临时文件），传入docx中的图片尺寸作为参考
    if (images && images.length > 0) {
      broadcastProgress({ type: 'word', status: 'processing', message: `正在处理 ${images.length} 张图片...` });
      
      for (let i = 0; i < images.length; i++) {
        try {
          const result = await wf.processImage(images[i], i, docxImageSizes || []);
          imageResults.push(result);
          
          const pct = Math.round(((i + 1) / images.length) * 50);
          broadcastProgress({ type: 'word', status: 'progress', current: i + 1, total: images.length, progress: pct, message: `图片处理中 ${i + 1}/${images.length}` });
        } catch (imgErr) {
          console.error(`图片 ${i} 处理失败:`, imgErr.message);
          imageResults.push({ success: false, filepath: null, error: imgErr.message });
        }
      }
    } else {
      for (let i = 0; i < allImageUrls.length; i++) {
        imageResults.push({ success: false, filepath: null });
      }
    }
    
    broadcastProgress({ type: 'word', status: 'processing', message: '正在生成Word文档...' });
    
    // 生成Word
    const docBuffer = await wf.generateWord(blocks, imageResults, (current, total) => {
      const pct = 50 + Math.round((current / total) * 50);
      broadcastProgress({ type: 'word', status: 'progress', current, total, progress: pct, message: `Word构建中 ${current}/${total}` });
    }, {
      headerText: header?.text || ''
    });
    
    // 保存到临时文件
    const outputPath = path.join(tmpDir, `output_${Date.now()}.docx`);
    fs.writeFileSync(outputPath, docBuffer);
    
    broadcastProgress({ type: 'word', status: 'done', message: 'Word文档生成完成！', outputPath: outputPath.split(/[/\\]/).pop() });
    
    res.json({
      success: true,
      outputPath,
      size: docBuffer.length
    });
  } catch (err) {
    broadcastProgress({ type: 'word', status: 'error', message: `Word转换失败：${err.message}` });
    console.error('Word转换失败:', err);
    res.status(500).json({ error: err.message, stack: err.stack });
  }
});

/**
 * 一键连续流程：上传图片 → 生成Markdown → 生成Word（带SSE进度推送）
 * 接收已上传好的数据（图片列表、附件配置等），自动完成全流程
 */
app.post('/api/one-click', async (req, res) => {
  try {
    const { 
      images,        // 已上传的图片列表 [{filepath, name, size, index}]
      attachmentNames, // 附件名称清单（可选）
      customRanges,    // 自定义映射规则（可选）
      header,          // 页眉信息（可选）
      docxImageSizes   // DOCX图片尺寸（可选）
    } = req.body;
    
    if (!images || images.length === 0) {
      return res.status(400).json({ error: '请先上传图片' });
    }
    
    // ====== 阶段1：构建附件 ======
    broadcastProgress({ type: 'oneclick', phase: 'build', status: 'processing', progress: 0, message: '正在构建附件映射...' });
    const names = wf.parseAttachmentNames(attachmentNames || '');
    const attachments = wf.buildAttachments(images, names, customRanges);
    
    await sleep(100);
    
    // ====== 阶段2：生成Markdown ======
    broadcastProgress({ type: 'oneclick', phase: 'markdown', status: 'processing', progress: 15, message: '正在生成Markdown...' });
    
    const markdown = wf.generateMarkdown(
      { content: '', title: '附件处理报告' },
      attachments,
      (current, total, detail) => {
        const pct = 15 + Math.round((current / total) * 25);
        broadcastProgress({ 
          type: 'oneclick', phase: 'markdown', status: 'progress', 
          current, total, progress: pct,
          message: detail || `Markdown生成中 ${current}/${total}`
        });
      }
    );
    
    await sleep(100);
    
    // ====== 阶段3：解析Markdown ======
    broadcastProgress({ type: 'oneclick', phase: 'parse', status: 'processing', progress: 42, message: '正在解析Markdown结构...' });
    const blocks = wf.parseMarkdownForDocx(markdown);
    
    await sleep(100);
    
    // ====== 阶段4：处理图片 ======
    broadcastProgress({ type: 'oneclick', phase: 'images', status: 'processing', progress: 45, message: `正在处理 ${images.length} 张图片...` });
    const imageResults = [];
    
    for (let i = 0; i < images.length; i++) {
      try {
        const result = await wf.processImage(images[i], i, docxImageSizes || []);
        imageResults.push(result);
        
        const pct = 45 + Math.round(((i + 1) / images.length) * 30);
        broadcastProgress({ 
          type: 'oneclick', phase: 'images', status: 'progress', 
          current: i + 1, total: images.length, progress: pct,
          message: `图片处理中 ${i + 1}/${images.length}`
        });
      } catch (imgErr) {
        console.error(`图片 ${i} 处理失败:`, imgErr.message);
        imageResults.push({ success: false, filepath: null, error: imgErr.message });
      }
    }
    
    await sleep(100);
    
    // ====== 阶段5：生成Word ======
    broadcastProgress({ type: 'oneclick', phase: 'word', status: 'processing', progress: 78, message: '正在生成Word文档...' });
    
    const docBuffer = await wf.generateWord(blocks, imageResults, (current, total) => {
      const pct = 78 + Math.round((current / total) * 20);
      broadcastProgress({ 
        type: 'oneclick', phase: 'word', status: 'progress', 
        current, total, progress: pct,
        message: `Word构建中 ${current}/${total}`
      });
    }, {
      headerText: header?.text || ''
    });
    
    // 保存到临时文件
    const outputPath = path.join(tmpDir, `output_${Date.now()}.docx`);
    fs.writeFileSync(outputPath, docBuffer);
    const filename = outputPath.split(/[/\\]/).pop();
    
    broadcastProgress({ 
      type: 'oneclick', phase: 'done', status: 'success', 
      progress: 100, 
      message: '🎉 全流程完成！Word文档已生成',
      outputPath: filename,
      stats: {
        images: images.length,
        attachments: attachments.length,
        size: docBuffer.length
      }
    });
    
    res.json({
      success: true,
      markdown,
      attachments,
      outputPath,
      filename,
      size: docBuffer.length
    });
  } catch (err) {
    broadcastProgress({ type: 'oneclick', phase: 'error', status: 'error', message: `全流程失败：${err.message}` });
    console.error('一键生成失败:', err);
    res.status(500).json({ error: err.message, stack: err.stack });
  }
});

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 下载生成的Word文档
 */
app.get('/api/download/:filename', (req, res) => {
  const filename = req.params.filename;
  const filepath = path.join(tmpDir, filename);
  
  if (!fs.existsSync(filepath)) {
    return res.status(404).json({ error: '文件不存在' });
  }
  
  res.download(filepath, `附件处理报告_${Date.now()}.docx`, (err) => {
    if (err) {
      console.error('下载失败:', err);
    }
    // 下载完成后删除临时文件
    try {
      fs.unlinkSync(filepath);
    } catch (e) {
      // 忽略删除错误
    }
  });
});

/**
 * 获取当前映射规则
 */
app.get('/api/ranges', (req, res) => {
  try {
    const ranges = wf.getRanges();
    res.json({ ranges });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * 更新映射规则
 */
app.put('/api/ranges', (req, res) => {
  try {
    const { ranges } = req.body;
    if (!ranges) {
      return res.status(400).json({ error: '请提供映射规则数据' });
    }
    const updated = wf.setRanges(ranges);
    res.json({ success: true, ranges: updated });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

/**
 * 重置映射规则为默认值
 */
app.post('/api/ranges/reset', (req, res) => {
  try {
    const updated = wf.setRanges(wf.DEFAULT_RANGES);
    res.json({ success: true, ranges: updated });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * 清理临时文件
 */
app.post('/api/cleanup', (req, res) => {
  try {
    const files = fs.readdirSync(tmpDir);
    const now = Date.now();
    let cleaned = 0;
    
    for (const file of files) {
      const filepath = path.join(tmpDir, file);
      const stat = fs.statSync(filepath);
      // 删除1小时前的文件
      if (now - stat.mtimeMs > 3600000) {
        fs.unlinkSync(filepath);
        cleaned++;
      }
    }
    
    res.json({ success: true, cleaned });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ============================================================
// 启动服务器
// ============================================================
app.listen(PORT, () => {
  console.log(`附件处理器合并版已启动: http://localhost:${PORT}`);
  console.log('支持一键连续流程 + SSE实时进度推送');
  console.log('按 Ctrl+C 停止服务器');
});