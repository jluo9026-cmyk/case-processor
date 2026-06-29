/**
 * 附件处理器合并版 - 服务器
 * 
 * 整合附件映射、Markdown生成和Word转换功能
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

// 请求体限制降低，因为不再传输base64大图片数据
app.use(express.json({ limit: '10mb', extended: true }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(express.static(__dirname));

// 提供temp目录的静态文件访问（用于缩略图显示）
app.use('/temp', express.static(tmpDir));

// ============================================================
// API 接口
// ============================================================

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
    
    const result = await wf.extractDocxContent(req.file.buffer);
    
    res.json({
      success: true,
      content: result.content,
      title: result.title,
      header: result.header,
      imageSizes: result.imageSizes || []
    });
  } catch (err) {
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
    
    res.json({
      success: true,
      count: images.length,
      images
    });
  } catch (err) {
    console.error('图片上传失败:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * 生成Markdown
 */
app.post('/api/generate-markdown', async (req, res) => {
  try {
    const { docContent, docTitle, attachmentNames, customRanges, images, header } = req.body;
    
    // 解析附件名称
    const names = wf.parseAttachmentNames(attachmentNames || '');
    
    // 构建附件数据
    const attachments = wf.buildAttachments(images || [], names, customRanges);
    
    // 生成Markdown
    const markdown = wf.generateMarkdown(
      { content: docContent, title: docTitle },
      attachments
    );
    
    res.json({
      success: true,
      markdown,
      attachments,
      header
    });
  } catch (err) {
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
      for (let i = 0; i < images.length; i++) {
        try {
          const result = await wf.processImage(images[i], i, docxImageSizes || []);
          imageResults.push(result);
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
    
    // 生成Word
    const docBuffer = await wf.generateWord(blocks, imageResults, (current, total) => {
      console.log(`Word生成进度: ${current}/${total}`);
    }, {
      headerText: header?.text || ''
    });
    
    // 保存到临时文件
    const outputPath = path.join(tmpDir, `output_${Date.now()}.docx`);
    fs.writeFileSync(outputPath, docBuffer);
    
    res.json({
      success: true,
      outputPath,
      size: docBuffer.length
    });
  } catch (err) {
    console.error('Word转换失败:', err);
    res.status(500).json({ error: err.message, stack: err.stack });
  }
});

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
  console.log('按 Ctrl+C 停止服务器');
});
