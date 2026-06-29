# 显式导出所有需要被 import * 导入的名称
__all__ = [
    'TEMPLATE_DOCX_MAP', '_merge_content_into_template', '_is_chapter_heading',
    '_chapter_matches'
]

from modules.config import BASE_DIR, PORT_FILE, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT, DEEPSEEK_CONNECT_TIMEOUT, MODEL_TEMPERATURE, MODEL_TOP_P, MODEL_MAX_TOKENS, SYSTEM_ROLE
from datetime import datetime
import httpx
import re  # ✅ 修复1：添加 re 导入
from pathlib import Path  # ✅ 修复2：添加 Path 导入
from docx import Document  # ✅ 修复3：添加 Document 导入

# 预设模板对应的真实 .docx 模板文件路径映射
TEMPLATE_DOCX_MAP = {
    'preset_1': BASE_DIR / 'template_preset_1.docx',
    'preset_2': BASE_DIR / 'template_preset_2.docx',
    'preset_3': BASE_DIR / 'template_preset_3.docx',
}


def _is_chapter_heading(text: str) -> bool:
    """判断段落文本是否为章节标题"""
    if not text:
        return False
    patterns = [
        '第' in text and '章' in text,
        text.startswith('一、'), text.startswith('二、'),
        text.startswith('三、'), text.startswith('四、'),
        text.startswith('五、'), text.startswith('六、'),
        text.startswith('七、'), text.startswith('八、'),
        text.startswith('九、'), text.startswith('十、'),
    ]
    return any(patterns)


def _chapter_matches(title_a: str, title_b: str) -> bool:
    """判断两个章节标题是否匹配（模糊匹配）"""
    a = re.sub(r'[（(].*?[）)]', '', title_a).strip()
    b = re.sub(r'[（(].*?[）)]', '', title_b).strip()
    return a == b or a in b or b in a


def _merge_content_into_template(template_doc: Document, source_bytes: bytes, output_path: Path):
    """将上传文档的内容按章节合并到模板文档中"""
    import zipfile
    import io as _io
    from lxml import etree
    from copy import deepcopy
    
    nsp = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    # ========== 第一步：读取模板文档 ==========
    template_buffer = _io.BytesIO()
    template_doc.save(template_buffer)
    template_zip = zipfile.ZipFile(template_buffer, 'r')
    
    template_files = {}
    for item in template_zip.infolist():
        template_files[item.filename] = template_zip.read(item.filename)
    template_zip.close()
    
    # ========== 第二步：读取上传文档 ==========
    source_zip = zipfile.ZipFile(_io.BytesIO(source_bytes), 'r')
    source_files = {}
    for item in source_zip.infolist():
        source_files[item.filename] = source_zip.read(item.filename)
    source_zip.close()
    
    # ========== 第三步：解析模板章节结构 ==========
    tpl_doc_xml_content = template_files.get('word/document.xml')
    if tpl_doc_xml_content is None:
        raise ValueError("模板文件中缺少 word/document.xml")
    
    tpl_doc_xml = etree.fromstring(tpl_doc_xml_content)
    body = tpl_doc_xml.find('.//w:body', nsp)
    all_tpl_paras = body.findall('w:p', nsp) if body is not None else []
    
    tpl_chapter_indices = []
    for idx, para_elem in enumerate(all_tpl_paras):
        texts = para_elem.findall('.//w:t', nsp)
        para_text = ''.join(t.text or '' for t in texts).strip()
        if _is_chapter_heading(para_text):
            tpl_chapter_indices.append({'index': idx, 'title': para_text})
    
    # ========== 第四步：解析上传文档章节结构 ==========
    source_doc_xml_content = source_files.get('word/document.xml')
    if source_doc_xml_content is None:
        raise ValueError("上传文档中缺少 word/document.xml")
    
    source_doc_xml = etree.fromstring(source_doc_xml_content)
    source_body = source_doc_xml.find('.//w:body', nsp)
    
    source_chapters = []
    current_title = None
    current_indices = []
    all_source_paras = []  # ✅ 修复4：提前定义，避免 UnboundLocalError
    
    if source_body is not None:
        all_source_paras = source_body.findall('w:p', nsp)
        for idx, para_elem in enumerate(all_source_paras):
            texts = para_elem.findall('.//w:t', nsp)
            para_text = ''.join(t.text or '' for t in texts).strip()
            if not para_text:
                continue
            if _is_chapter_heading(para_text):
                if current_title is not None:
                    source_chapters.append((current_title, current_indices))
                current_title = para_text
                current_indices = []
            else:
                current_indices.append(idx)
        if current_title is not None:
            source_chapters.append((current_title, current_indices))
    
    chapters_found = len(source_chapters)
    
    # ========== 第五步：构建新文档 ==========
    new_doc_xml = deepcopy(tpl_doc_xml)
    new_body = new_doc_xml.find('.//w:body', nsp)
    
    if new_body is None:
        raise ValueError("模板文档中找不到 body 元素")
    
    tpl_sectPr = new_body.find('w:sectPr', nsp)
    
    # 保存模板章节间内容
    tpl_chapter_para_indices = {ch['index'] for ch in tpl_chapter_indices}
    tpl_pre_chapter_paras = []
    tpl_post_chapter_paras = []
    tpl_chapter_content = {}
    
    if tpl_chapter_indices:
        first_ch_idx = tpl_chapter_indices[0]['index']
        last_ch_idx = tpl_chapter_indices[-1]['index']
        
        current_ch_title = None
        current_ch_content = []
        for idx, pe in enumerate(all_tpl_paras):
            if idx in tpl_chapter_para_indices:
                if current_ch_title is not None:
                    tpl_chapter_content[current_ch_title] = current_ch_content
                texts = pe.findall('.//w:t', nsp)
                current_ch_title = ''.join(t.text or '' for t in texts).strip()
                current_ch_content = []
            elif idx < first_ch_idx:
                tpl_pre_chapter_paras.append(deepcopy(pe))
            elif idx > last_ch_idx:
                tpl_post_chapter_paras.append(deepcopy(pe))
            else:
                current_ch_content.append(deepcopy(pe))
        if current_ch_title is not None:
            tpl_chapter_content[current_ch_title] = current_ch_content
    else:
        for idx, pe in enumerate(all_tpl_paras):
            if idx not in tpl_chapter_para_indices:
                tpl_pre_chapter_paras.append(deepcopy(pe))
    
    # 清空 body
    children_to_remove = []
    for child in new_body:
        if child.tag != f'{{{nsp["w"]}}}sectPr':
            children_to_remove.append(child)
    for child in children_to_remove:
        new_body.remove(child)
    
    # 重新构建
    matched_source_titles = set()
    
    # 添加前导内容
    for pe in tpl_pre_chapter_paras:
        new_body.append(pe)
    
    for ch_info in tpl_chapter_indices:
        ch_title = ch_info['title']
        ch_para_index = ch_info['index']
        
        tpl_heading_elem = all_tpl_paras[ch_para_index] if ch_para_index < len(all_tpl_paras) else None
        if tpl_heading_elem is not None:
            new_body.append(deepcopy(tpl_heading_elem))
        
        matched = False
        for src_title, src_indices in source_chapters:
            if _chapter_matches(src_title, ch_title):
                matched = True
                matched_source_titles.add(src_title)
                # ✅ 修复5：使用 all_source_paras 而不是 source_all_paras_list
                for pi in src_indices:
                    if all_source_paras and pi < len(all_source_paras):
                        new_body.append(deepcopy(all_source_paras[pi]))
                break
        
        if not matched:
            tpl_content_paras = tpl_chapter_content.get(ch_title, [])
            if tpl_content_paras:
                for pe in tpl_content_paras:
                    new_body.append(pe)
            else:
                empty_p = etree.SubElement(new_body, f'{{{nsp["w"]}}}p')
                empty_r = etree.SubElement(empty_p, f'{{{nsp["w"]}}}r')
                empty_t = etree.SubElement(empty_r, f'{{{nsp["w"]}}}t')
                empty_t.text = '（此章节内容待补充）'
                empty_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    
    # 添加上传文档中额外的章节
    if source_body is not None and all_source_paras:
        for src_title, src_indices in source_chapters:
            if src_title not in matched_source_titles:
                for idx, para_elem in enumerate(all_source_paras):
                    texts = para_elem.findall('.//w:t', nsp)
                    para_text = ''.join(t.text or '' for t in texts).strip()
                    if para_text == src_title:
                        new_body.append(deepcopy(para_elem))
                        break
                for pi in src_indices:
                    if pi < len(all_source_paras):
                        new_body.append(deepcopy(all_source_paras[pi]))
    
    # 添加后置内容
    for pe in tpl_post_chapter_paras:
        new_body.append(pe)
    
    # 恢复页面设置
    if tpl_sectPr is not None:
        new_body.append(deepcopy(tpl_sectPr))
    
    # ========== 第六步：构建输出文档 ==========
    output_buffer = _io.BytesIO()
    
    with zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED) as oz:
        for name, data in template_files.items():
            if name == 'word/document.xml':
                new_data = etree.tostring(
                    new_doc_xml,
                    xml_declaration=True,
                    encoding='UTF-8',
                    standalone=True
                )
                oz.writestr(name, new_data)
            else:
                oz.writestr(name, data)
    
    output_buffer.seek(0)
    with open(str(output_path), 'wb') as f:
        f.write(output_buffer.read())
    
    final_doc = Document(str(output_path))
    return final_doc, chapters_found, chapters_found