/**
 * 合并工作流 - 整合附件映射和Word转换功能
 * 
 * 功能：
 * 1. 映射功能 - 将图片分配到20个附件
 * 2. Markdown生成 - 输出带附件编号和图片的报告
 * 3. Word转换 - 将Markdown转换为Word文档
 */

const mammoth = require('mammoth');
const { Document, Packer, Paragraph, TextRun, ImageRun, AlignmentType, BorderStyle } = require('docx');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');
const tmp = require('tmp');

// ============================================================
// 附件默认名称 - 保险理赔案件的标准附件清单
// ============================================================
const DEFAULT_ATTACHMENT_NAMES = [
  "案卷资料记载（报案记录）及保单",
  "惠州市中拓模塑科技有限公司车间现场照片",
  "大门监控视频截图",
  "刘华妹询问笔录",
  "马少康个体诊所走访记录",
  "走访东莞市松山湖中心医院",
  "走访社保局",
  "黄昭伯身份证",
  "受益人身份证",
  "认定工伤决定书",
  "工亡待遇核定单",
  "死亡证明",
  "附件十三",
  "附件十四",
  "附件十五",
  "附件十六",
  "附件十七",
  "附件十八",
  "附件十九",
  "附件二十"
];

// ============================================================
// 图片索引到附件的默认分配规则 (20个附件)
// ============================================================
const DEFAULT_RANGES = [
  { start: 0, end: 2, idx: 0 },   // 附件一
  { start: 3, end: 18, idx: 1 },  // 附件二
  { start: 19, end: 20, idx: 2 }, // 附件三
  { start: 21, end: 24, idx: 3 }, // 附件四
  { start: 25, end: 25, idx: 4 }, // 附件五
  { start: 26, end: 46, idx: 5 }, // 附件六
  { start: 47, end: 48, idx: 6 }, // 附件七
  { start: 49, end: 49, idx: 7 }, // 附件八
  { start: 50, end: 50, idx: 8 }, // 附件九
  { start: 51, end: 51, idx: 9 }, // 附件十
  { start: 52, end: 52, idx: 10 }, // 附件十一
  { start: 53, end: 53, idx: 11 }, // 附件十二
  { start: 54, end: 54, idx: 12 }, // 附件十三
  { start: 55, end: 55, idx: 13 }, // 附件十四
  { start: 56, end: 56, idx: 14 }, // 附件十五
  { start: 57, end: 57, idx: 15 }, // 附件十六
  { start: 58, end: 58, idx: 16 }, // 附件十七
  { start: 59, end: 59, idx: 17 }, // 附件十八
  { start: 60, end: 60, idx: 18 }, // 附件十九
  { start: 61, end: 61, idx: 19 }  // 附件二十
];

// ============================================================
// 工具函数
// ============================================================

function toChineseNum(n) {
  const units = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];
  if (n <= 10) return units[n];
  if (n < 20) return '十' + units[n - 10];
  if (n < 100) return units[Math.floor(n / 10)] + '十' + (n % 10 ? units[n % 10] : '');
  return n.toString();
}

/**
 * 安全地将输入值转为数组
 */
function toArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') {
    try { return JSON.parse(value); } catch (e) { return [value]; }
  }
  return [];
}

// ============================================================
// 1. 解析附件名称
// ============================================================
function parseAttachmentNames(namesText) {
  const nameLines = (namesText || '')
    .split(/\r?\n/)
    .filter(line => line && line.trim());

  const result = [...DEFAULT_ATTACHMENT_NAMES];

  // 支持丰富格式：附件一/1/①/❶/[1] 等
  const namePattern = /^附件[一二三四五六七八九十\d①②③④⑤⑥⑦⑧⑨⑩]+[：:.]?\s*(.*)/;

  for (let i = 0; i < nameLines.length && i < result.length; i++) {
    const line = nameLines[i].trim();
    const match = line.match(namePattern);
    if (match && match[1]) {
      result[i] = match[1];
    } else if (line && !line.startsWith('附件')) {
      result[i] = line;
    }
  }

  return result;
}

// ============================================================
// 2. 读取DOCX文本和页眉，并提取图片尺寸信息
// ============================================================
async function extractDocxContent(docxBuffer) {
  try {
    // 提取纯文本
    const result = await mammoth.extractRawText({ buffer: docxBuffer });
    
    // 尝试提取页眉信息（使用自定义转换器）
    let headerInfo = { text: '', hasIcon: false };
    try {
      const headerResult = await mammoth.convert({ buffer: docxBuffer }, {
        styleMap: [
          "p[style-name='Header'] => div:fresh"
        ],
        transformDocument: function(element) {
          // 简化处理，返回基本结构
          return element;
        }
      });
      
      // 尝试读取文档中的标题页（通常是第一页包含案件名称和图标）
      // 这里我们从文本中提取案件名称
      const lines = result.value.split('\n');
      let caseName = '';
      for (const line of lines) {
        const trimmed = line.trim();
        // 跳过很短的行和附件相关的行
        if (trimmed.length > 5 && !trimmed.includes('附件') && !trimmed.match(/^\d+$/)) {
          caseName = trimmed;
          break;
        }
      }
      
      headerInfo = {
        text: caseName,
        hasIcon: false // 需要进一步处理图片
      };
    } catch (headerErr) {
      console.log('页眉提取失败，使用默认:', headerErr.message);
    }
    
    // 提取docx中的图片尺寸信息
    let imageSizes = [];
    try {
      const archiver = require('archiver') || null;
      // 使用JSZip来分析docx中的图片
      const JSZip = require('jszip');
      const zip = await JSZip.loadAsync(docxBuffer);
      
      // 查找所有图片文件
      const imageFiles = Object.keys(zip.files).filter(name => 
        name.startsWith('word/media/') && 
        (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.gif'))
      );
      
      // 获取每个图片的尺寸
      for (const imgName of imageFiles) {
        const imgData = await zip.files[imgName].async('nodebuffer');
        const meta = await sharp(imgData).metadata();
        imageSizes.push({
          name: imgName.replace('word/media/', ''),
          width: meta.width,
          height: meta.height,
          size: imgData.length,
          orientation: (meta.height || 0) > (meta.width || 0) ? 'portrait' : 'landscape'
        });
      }
      
      console.log(`从DOCX中提取了 ${imageSizes.length} 张图片的尺寸信息`);
    } catch (imgErr) {
      console.log('提取DOCX图片尺寸失败:', imgErr.message);
    }
    
    return {
      content: result.value,
      title: extractTitleFromContent(result.value),
      header: headerInfo,
      imageSizes: imageSizes
    };
  } catch (err) {
    console.error('DOCX读取失败:', err);
    return { content: '', title: '', header: { text: '', hasIcon: false }, imageSizes: [] };
  }
}

function extractTitleFromContent(content) {
  const lines = content.split('\n').filter(l => l.trim());
  return lines[0] || '未命名文档';
}

// ============================================================
// 3. 处理图片（支持base64和URL）
// ============================================================

/**
 * 根据目标尺寸智能计算JPEG压缩质量
 * 原则：先保证尺寸，在尺寸范围内尽量保证质量
 * @param {number} targetWidth - 目标宽度(px)
 * @param {number} targetHeight - 目标高度(px)
 * @returns {number} 建议的JPEG质量 (1-100)
 */
function calculateSmartQuality(targetWidth, targetHeight) {
  // 全部使用高质量，确保图片清晰
  return 95;
}

/**
 * 根据docx中的图片尺寸计算目标尺寸
 * @param {Array} docxImageSizes - 从docx提取的图片尺寸信息
 * @param {string} orientation - 图片方向 ('portrait' 或 'landscape')
 * @returns {Object} { width, height }
 */
function getTargetDimensionsFromDocx(docxImageSizes, orientation) {
  // 严格使用固定尺寸（用户要求）
  // docx库内部转换: 像素 × 9525 = EMU, 1cm = 360000 EMU
  // 竖图（高 > 宽）：宽14.64cm = 553px, 高19.53cm = 738px
  // 横图（宽 > 高）：宽19.53cm = 738px, 高14.64cm = 553px
  if (orientation === 'portrait') {
    return { width: 553, height: 738 };
  } else {
    return { width: 738, height: 553 };
  }
}

async function processImage(imageData, index, docxImageSizes = []) {
  const tmpFile = tmp.fileSync({ postfix: '.jpg' });
  
  try {
    let buffer;
    
    // 调试日志
    console.log(`处理图片 ${index}:`, {
      hasFilepath: !!imageData.filepath,
      hasDataUrl: !!imageData.dataUrl,
      hasBase64: !!imageData.base64,
      hasUrl: !!imageData.url,
      filepath: imageData.filepath || '',
    });
    
    // 优先从文件路径读取（优化：上传时直接存磁盘，避免base64内存开销）
    if (imageData.filepath && fs.existsSync(imageData.filepath)) {
      // 本地文件 - 直接从磁盘读取
      buffer = fs.readFileSync(imageData.filepath);
    } else if (imageData.dataUrl) {
      // Base64数据 (前端格式: data:image/jpeg;base64,...)
      const base64 = imageData.dataUrl.replace(/^data:image\/\w+;base64,/, '');
      buffer = Buffer.from(base64, 'base64');
    } else if (imageData.base64) {
      // 纯base64字符串
      buffer = Buffer.from(imageData.base64, 'base64');
    } else if (imageData.url && imageData.url.startsWith('data:')) {
      // data URL
      const base64 = imageData.url.replace(/^data:image\/\w+;base64,/, '');
      buffer = Buffer.from(base64, 'base64');
    } else {
      throw new Error('不支持的图片格式: 缺少 filepath/dataUrl/base64/url');
    }
    
    // 获取原始图片元数据
    const meta = await sharp(buffer).metadata();
    const origWidth = meta.width || 0;
    const origHeight = meta.height || 0;
    const ratio = origHeight / origWidth;
    
    // 根据原图宽高比判断类型
    const orientation = ratio > 1 ? 'portrait' : 'landscape';
    
    // 从docx图片尺寸获取目标尺寸
    const targetDims = getTargetDimensionsFromDocx(docxImageSizes, orientation);
    const targetWidth = targetDims.width;
    const targetHeight = targetDims.height;
    
    // 先根据EXIF方向旋转图片，消除方向标记的影响
    let sharpInstance = sharp(buffer).rotate();
    
    // 获取旋转后的实际尺寸（EXIF方向已应用）
    const rotatedMeta = await sharpInstance.metadata();
    const rotatedWidth = rotatedMeta.width || origWidth;
    const rotatedHeight = rotatedMeta.height || origHeight;
    
    // 计算裁剪参数（使用旋转后的尺寸）
    const origRatio = rotatedWidth / rotatedHeight;
    const targetRatio = targetWidth / targetHeight;
    
    if (origRatio > targetRatio) {
      // 原图更宽，需要裁剪宽度
      const newWidth = Math.round(rotatedHeight * targetRatio);
      const left = Math.round((rotatedWidth - newWidth) / 2);
      sharpInstance = sharpInstance.extract({
        left: Math.max(0, left),
        top: 0,
        width: Math.min(newWidth, rotatedWidth),
        height: rotatedHeight
      });
    } else if (origRatio < targetRatio) {
      // 原图更高，需要裁剪高度
      const newHeight = Math.round(rotatedWidth / targetRatio);
      const top = Math.round((rotatedHeight - newHeight) / 2);
      sharpInstance = sharpInstance.extract({
        left: 0,
        top: Math.max(0, top),
        width: rotatedWidth,
        height: Math.min(newHeight, rotatedHeight)
      });
    }
    
    // 缩放到目标尺寸
    sharpInstance = sharpInstance.resize(targetWidth, targetHeight, { fit: 'fill' });
    
    // 计算质量（在保证尺寸的前提下，尽量保证质量）
    const quality = calculateSmartQuality(targetWidth, targetHeight);
    
    // 转为JPEG（去除所有EXIF元数据，避免Word再次旋转）
    const convBuf = await sharpInstance.jpeg({ quality: quality }).withMetadata({}).toBuffer();
    
    fs.writeFileSync(tmpFile.name, convBuf);
    
    return {
      filepath: tmpFile.name,
      success: true,
      originalSize: buffer.length,
      convertedSize: convBuf.length,
      quality: quality,
      dimensions: `${origWidth}x${origHeight}`,
      targetDimensions: `${targetWidth}x${targetHeight}`,
      orientation: orientation
    };
  } catch (err) {
    tmpFile.removeCallback();
    return { filepath: null, success: false, error: err.message };
  }
}

// ============================================================
// 4. 构建附件数据结构
// ============================================================
function buildAttachments(images, attachmentNames, customRanges) {
  const ranges = customRanges || DEFAULT_RANGES;
  
  return ranges.map((range, i) => {
    const imgList = [];
    for (let j = range.start; j <= range.end && j < images.length; j++) {
      imgList.push(images[j]);
    }
    
    const name = attachmentNames[range.idx] || DEFAULT_ATTACHMENT_NAMES[range.idx];
    
    return {
      index: i + 1,
      indexChinese: toChineseNum(i + 1),
      name: name,
      range: `${range.start}-${range.end}`,
      count: imgList.length,
      images: imgList,
      urls: imgList.map(img => img.url || img.dataUrl || img.filepath || '').filter(Boolean)
    };
  });
}

// ============================================================
// 5. 生成Markdown
// ============================================================
function generateMarkdown(docInfo, attachments) {
  const lines = [];
  
  for (const att of attachments) {
    // 添加附件标题：编号右上角，名称在编号下方居中
    lines.push(`<span style="float:right;color:red;font-weight:bold;">附件${att.indexChinese}</span>`);
    lines.push('');
    lines.push(`### <span style="text-align:center;display:block;">${att.name}</span>`);
    lines.push('');
    
    if (att.images.length > 0) {
      for (let i = 0; i < att.images.length; i++) {
        const img = att.images[i];
        // 优先使用url，其次dataUrl，最后将filepath转为可访问的URL
        let imgRef = img.url || img.dataUrl || '';
        if (!imgRef && img.filepath) {
          // 将磁盘路径转为可通过 /temp/ 访问的URL
          const filename = img.filepath.split(/[/\\]/).pop();
          imgRef = `/temp/${filename}`;
        }
        
        if (imgRef) {
          lines.push(`<img src="${imgRef}" width="100%" />`);
          lines.push('');
        }
      }
    }
  }
  
  return lines.join('\n');
}

// ============================================================
// 6. 解析Markdown（提取图片用于Word转换）
// ============================================================
function parseMarkdownForDocx(md) {
  const blocks = [];
  let currentImages = [];
  let currentTexts = [];
  let pendingAttachment = null; // 待处理的附件信息
  
  const lines = md.split('\n');
  
  for (const line of lines) {
    const trimmed = line.trim();
    
    // 处理HTML图片标签 <img src="..." ...>
    const htmlImgMatch = trimmed.match(/<img\s+src=["']([^"']+)["'][^>]*>/i);
    if (htmlImgMatch) {
      if (currentTexts.length > 0) {
        blocks.push({ type: 'text', content: currentTexts.join('\n') });
        currentTexts = [];
      }
      currentImages.push({ alt: '图片', url: htmlImgMatch[1] });
      continue;
    }
    
    // 处理Markdown图片 ![...](...)
    const imgMatch = [...trimmed.matchAll(/!\[([^\]]*)\]\(([^)]+)\)/g)];
    if (imgMatch.length > 0) {
      if (currentTexts.length > 0) {
        blocks.push({ type: 'text', content: currentTexts.join('\n') });
        currentTexts = [];
      }
      for (const m of imgMatch) {
        currentImages.push({ alt: m[1] || '图片', url: m[2] });
      }
      continue;
    }
    
    // 处理HTML span标签（附件编号）- 格式：<span style="float:right;color:red;font-weight:bold;">附件X</span>
    const htmlSpanRightMatch = trimmed.match(/<span\s+style="[^"]*float:\s*right[^"]*"[^>]*>([^<]+)<\/span>/i);
    if (htmlSpanRightMatch) {
      const attMatch = htmlSpanRightMatch[1].match(/附件([一二三四五六七八九十\d]+)/);
      if (attMatch) {
        if (pendingAttachment) {
          pendingAttachment.num = attMatch[1];
        } else {
          pendingAttachment = { num: attMatch[1], name: '' };
        }
      }
      continue;
    }
    
    // 处理HTML span标签（附件名称）- 格式：<span style="...text-align:center...;">名称</span>
    const htmlSpanCenterMatch = trimmed.match(/<span\s+style="[^"]*text-align:\s*center[^"]*"[^>]*>([^<]+)<\/span>/i);
    if (htmlSpanCenterMatch) {
      // 这是附件名称行
      const name = htmlSpanCenterMatch[1];
      
      // 如果有关联的编号，生成附件标题块
      if (pendingAttachment && pendingAttachment.num) {
        // 输出之前的图片
        if (currentImages.length > 0) {
          blocks.push({ type: 'images', images: [...currentImages] });
          currentImages = [];
        }
        // 输出附件标题
        blocks.push({ 
          type: 'heading', 
          level: 3, 
          content: `附件${pendingAttachment.num}：${name}` 
        });
        pendingAttachment = null;
      }
      continue;
    }
    
    // Markdown标题（纯Markdown格式）
    const mdHeading = trimmed.match(/^(#{1,3})\s+(.+)/);
    if (mdHeading) {
      if (currentImages.length > 0) {
        blocks.push({ type: 'images', images: [...currentImages] });
        currentImages = [];
      }
      if (currentTexts.length > 0) {
        blocks.push({ type: 'text', content: currentTexts.join('\n') });
        currentTexts = [];
      }
      blocks.push({ type: 'heading', level: mdHeading[1].length, content: mdHeading[2] });
      continue;
    }
    
    // 分隔线
    if (/^---+\s*$/.test(trimmed)) {
      if (currentImages.length > 0) {
        blocks.push({ type: 'images', images: [...currentImages] });
        currentImages = [];
      }
      if (currentTexts.length > 0) {
        blocks.push({ type: 'text', content: currentTexts.join('\n') });
        currentTexts = [];
      }
      continue;
    }
    
    // 普通文本（跳过空的HTML标签行）
    if (trimmed && !trimmed.match(/^<br\s*\/?>$/i)) {
      currentTexts.push(line);
    }
  }
  
  // 处理剩余内容
  if (currentImages.length > 0) {
    blocks.push({ type: 'images', images: currentImages });
  }
  if (currentTexts.length > 0) {
    blocks.push({ type: 'text', content: currentTexts.join('\n') });
  }
  
  return blocks;
}

// ============================================================
// 7. 生成Word文档 - 参照附件md转docx工具的格式
// ============================================================
async function generateWord(blocks, imageResults, onProgress, options = {}) {
  const children = [];
  let imgIdx = 0;
  let embedCount = 0;
  const totalImages = imageResults.filter(r => r.success).length;
  
  // 页边距设置（根据图片）
  // 上：2.54cm = 1 inch = 1440 twips
  // 下：2.54cm = 1 inch = 1440 twips
  // 左：3.18cm = 3.18/2.54 inch ≈ 1.252 inch ≈ 1803 twips
  // 右：3.18cm = 3.18/2.54 inch ≈ 1.252 inch ≈ 1803 twips
  const marginTop = 1440;    // 2.54 cm
  const marginBottom = 1440; // 2.54 cm
  const marginLeft = 1803;   // 3.18 cm
  const marginRight = 1803;  // 3.18 cm
  
  // 计算内容宽度用于图片自适应
  // A4宽度210mm = 8.27 inch ≈ 595 pt
  // 内容宽度 = 595 - 左右边距(约127pt) ≈ 468 pt
  const contentWidthPt = 468;
  
  for (const block of blocks) {
    // 标题块
    if (block.type === 'heading') {
      let fontSize = 22;
      let spacing = { before: 200, after: 100 };
      
      const headingText = typeof block.content === 'string' ? block.content : '';
      
      // 检查是否是附件标题，格式：附件一：名称
      const attachmentMatch = headingText.match(/^附件([一二三四五六七八九十\d]+)：(.+)/);
      
      if (attachmentMatch) {
        const attNum = attachmentMatch[1];
        const attName = attachmentMatch[2];
        
        // 第一行：附件编号在右上角
        children.push(new Paragraph({
          children: [
            new TextRun({
              text: `附件${attNum}`,
              bold: true,
              size: 22,
              font: 'SimHei',
              color: 'FF0000',
            }),
          ],
          spacing: { before: 200, after: 0 },
          alignment: AlignmentType.RIGHT,
        }));
        
        // 第二行：附件名称居中
        children.push(new Paragraph({
          children: [
            new TextRun({
              text: attName,
              bold: true,
              size: 24,
              font: 'SimHei',
            }),
          ],
          spacing: { before: 100, after: 100 },
          alignment: AlignmentType.CENTER,
        }));
      } else if (headingText) {
        children.push(new Paragraph({
          children: [new TextRun({
            text: headingText,
            bold: true,
            size: fontSize,
            font: 'SimHei',
          })],
          spacing,
          alignment: AlignmentType.LEFT,
        }));
      }
      continue;
    }
    
    // 文本块
    if (block.type === 'text') {
      const content = block.content || '';
      const text = content.replace(/^\s+|\s+$/g, '');
      if (text) {
        // 检查是否是列表项
        const listMatch = text.match(/^(\d+[.、]|[（(]\d+[）)])\s*(.+)/);
        if (listMatch) {
          children.push(new Paragraph({
            children: [new TextRun({ text, size: 21, font: 'SimSun' })],
            spacing: { before: 60, after: 60 },
            indent: { left: 720 },
          }));
        } else {
          children.push(new Paragraph({
            children: [new TextRun({ text, size: 21, font: 'SimSun' })],
            spacing: { before: 100, after: 100 },
          }));
        }
      }
      continue;
    }
    
    // 图片块
    if (block.type === 'images') {
      for (const img of block.images) {
        const result = imageResults[imgIdx];
        imgIdx++;
        
        if (result?.success && result?.filepath) {
          try {
            const imgBuf = fs.readFileSync(result.filepath);
            const meta = await sharp(imgBuf).metadata();
            const w = meta.width || 300;
            const h = meta.height || 500;
            
            // 严格按要求设置图片尺寸，不允许超出页面
            // docx库内部转换: 像素 × 9525 = EMU, 1cm = 360000 EMU
            // 竖图（高 > 宽）：553px宽 × 738px高 → 宽14.64cm × 高19.53cm
            // 横图（宽 > 高）：738px宽 × 553px高 → 宽19.53cm × 高14.64cm
            let width, height;
            
            if (h > w) {
              // 竖图（高 > 宽）：553px宽 × 738px高
              width = 553;
              height = 738;
            } else {
              // 横图（宽 >= 高）：738px宽 × 553px高
              width = 738;
              height = 553;
            }
            
            children.push(new Paragraph({
              children: [new ImageRun({
                data: imgBuf,
                transformation: { width, height },
                type: 'jpeg',
              })],
              alignment: AlignmentType.CENTER,
              spacing: { before: 100, after: 40 },
            }));
            
            embedCount++;
            onProgress?.(embedCount, totalImages);
          } catch (err) {
            children.push(new Paragraph({
              children: [new TextRun({ text: '[图片渲染失败]', italics: true, color: '888888' })],
              alignment: AlignmentType.CENTER,
            }));
          }
        } else {
          children.push(new Paragraph({
            children: [new TextRun({ text: '[图片加载失败]', italics: true, color: '888888' })],
            alignment: AlignmentType.CENTER,
          }));
        }
      }
      
      // 图片后加分隔线
      children.push(new Paragraph({
        children: [new TextRun({ text: '', size: 12 })],
        spacing: { before: 250, after: 150 },
        border: {
          bottom: { style: 'single', size: 4, color: 'AAAAAA', space: 1 },
        },
      }));
    }
  }
  
  // 构建页眉（如果有）
  let headerObj = undefined;
  if (options.headerText) {
    const { Header } = require('docx');
    // 上边距1.50cm ≈ 850 twips
    // 横线下方间距1.75cm ≈ 17 (docx border space单位为pt)
    headerObj = new Header({
      children: [
        new Paragraph({
          children: [
            new TextRun({
              text: options.headerText || '',
              font: 'SimHei',
              size: 20,
            }),
          ],
          alignment: AlignmentType.LEFT,
          spacing: { before: 850, after: 0 }, // 上边距1.50cm
          border: {
            bottom: { style: 'single', size: 6, color: '000000', space: 17 }, // 横线粗6，间距约1.75cm
          },
        }),
      ],
    });
  }
  
  const doc = new Document({
    title: '附件处理报告',
    creator: 'MD2DOCX',
    description: '由 Markdown 自动转换生成',
    styles: {
      default: {
        document: {
          run: { font: 'SimSun', size: 21 },
        },
      },
    },
    sections: [{
      properties: {
        page: {
          margin: {
            top: marginTop,
            right: marginRight,
            bottom: marginBottom,
            left: marginLeft,
          },
        },
      },
      headers: headerObj ? { default: headerObj } : undefined,
      children,
    }],
  });
  
  return await Packer.toBuffer(doc);
}

// ============================================================
// 映射规则管理（参照便携版实现）
// ============================================================

// 当前生效的映射规则（可运行时修改）
let currentRanges = DEFAULT_RANGES.map(r => ({ ...r }));

/**
 * 获取当前映射规则
 */
function getRanges() {
  return currentRanges;
}

/**
 * 更新映射规则
 * @param {Array} newRanges - 新的映射规则数组
 */
function setRanges(newRanges) {
  if (!Array.isArray(newRanges) || newRanges.length === 0) {
    throw new Error('映射规则必须是非空数组');
  }
  for (const r of newRanges) {
    if (typeof r.start !== 'number' || typeof r.end !== 'number' || typeof r.idx !== 'number') {
      throw new Error('每条规则必须包含 start, end, idx 数字字段');
    }
    if (r.start < 0 || r.end < r.start) {
      throw new Error(`无效范围: start=${r.start}, end=${r.end}`);
    }
  }
  currentRanges = newRanges.map(r => ({ ...r }));
  return currentRanges;
}

// ============================================================
// 导出
// ============================================================
module.exports = {
  DEFAULT_ATTACHMENT_NAMES,
  DEFAULT_RANGES,
  toChineseNum,
  parseAttachmentNames,
  extractDocxContent,
  processImage,
  buildAttachments,
  generateMarkdown,
  parseMarkdownForDocx,
  generateWord,
  getRanges,
  setRanges,
};
