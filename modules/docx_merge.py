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


def _chapter_number(title):
    """提取章节的编号数字，如 '三、xxx' → 3"""
    cn_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    m = re.match(r'^([一二三四五六七八九十]+)[、．\.]', title)
    if m:
        num_str = m.group(1)
        if num_str in cn_map:
            return cn_map[num_str]
    return None


def _merge_content_into_template(template_doc: Document, source_bytes: bytes, output_path: Path):
    """将上传文档的内容按章节编号一一对应合并到模板中"""
    import zipfile
    import io as _io
    import re as _re  # ✅ 修复：避免局部作用域中的 re 命名冲突
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
    
    # ========== 第三步：解析模板 ==========
    tpl_doc_xml_content = template_files.get('word/document.xml')
    if tpl_doc_xml_content is None:
        raise ValueError("模板文件中缺少 word/document.xml")
    tpl_doc_xml = etree.fromstring(tpl_doc_xml_content)
    body = tpl_doc_xml.find('.//w:body', nsp)
    all_tpl_paras = body.findall('w:p', nsp) if body is not None else []
    
    # 模板：章节编号→{标题, 段落索引列表}
    tpl_chapters = []  # [(number, title_para_index, content_para_indices)]
    tpl_pre_paras_indices = []
    tpl_post_paras_indices = []
    current_num = None
    current_title_idx = None
    current_content = []
    found_any = False
    
    for idx, pe in enumerate(all_tpl_paras):
        texts = pe.findall('.//w:t', nsp)
        para_text = ''.join(t.text or '' for t in texts).strip()
        num = _chapter_number(para_text)
        if num is not None:
            if current_num is not None:
                tpl_chapters.append((current_num, current_title_idx, current_content))
            current_num = num
            current_title_idx = idx
            current_content = []
            found_any = True
        else:
            if not found_any:
                tpl_pre_paras_indices.append(idx)
            else:
                current_content.append(idx)
    if current_num is not None:
        tpl_chapters.append((current_num, current_title_idx, current_content))
    # 收集后置内容：最后一个章节标题之后的所有段落作为后置（声明/签名等）
    if found_any and tpl_chapters:
        last_num, last_title_idx, last_content = tpl_chapters[-1]
        # 将最后一个章节的内容剥离出来作为后置
        # (模板的最后一章通常包含"声明""以上报告仅供参考"等非章节编号的固定内容)
        tpl_post_paras_indices = last_content
        # 最后一个章节的内容置空，只保留标题
        tpl_chapters[-1] = (last_num, last_title_idx, [])
    
    # ========== 第四步：解析上传文档 ==========
    source_doc_xml_content = source_files.get('word/document.xml')
    if source_doc_xml_content is None:
        raise ValueError("上传文档中缺少 word/document.xml")
    source_doc_xml = etree.fromstring(source_doc_xml_content)
    source_body = source_doc_xml.find('.//w:body', nsp)
    
    source_chapters = []  # [(number, content_para_indices)]
    source_pre_indices = []
    all_source_paras = []
    s_current_num = None
    s_content = []
    s_found = False
    
    if source_body is not None:
        all_source_paras = source_body.findall('w:p', nsp)
        for idx, pe in enumerate(all_source_paras):
            texts = pe.findall('.//w:t', nsp)
            para_text = ''.join(t.text or '' for t in texts).strip()
            num = _chapter_number(para_text)
            if num is not None:
                if s_current_num is not None:
                    source_chapters.append((s_current_num, s_content))
                s_current_num = num
                s_content = []
                s_found = True
            else:
                if not s_found:
                    source_pre_indices.append(idx)
                else:
                    s_content.append(idx)
        if s_current_num is not None:
            source_chapters.append((s_current_num, s_content))
    
    chapters_found = len(source_chapters)
    
    # 建立源文档的 编号→内容索引列表 映射
    source_by_num = {}
    for snum, s_indices in source_chapters:
        source_by_num[snum] = s_indices
    
    # 判断段落是否为章节标题（用于格式化）
    def _is_heading_text(para_text):
        if not para_text:
            return False
        return bool(_re.match(r'^[一二三四五六七八九十]+[、．\.]', para_text)) or \
               bool(_re.match(r'^（[一二三四五六七八九十]+）', para_text))

    def _is_only_number_or_empty(text):
        """判断文本是否只包含编号没有正文（此类段落应跳过不输出）"""
        if not text or not text.strip():
            return True
        s = text.strip()
        # 纯数字
        if s.isdigit():
            return True
        # 纯中文数字（一至十三等）
        if _re.match(r'^[一二三四五六七八九十]+$', s):
            return True
        # 各种编号形式，长度<=5个字符，没有中文正文
        lone_number_patterns = [
            r'^\d+[、．\.\s]*$',           # 1、 2. 3
            r'^[(（]\d+[)）]$',            # (1)（2）
            r'^\d+[）)$]',                 # 1）2)
            r'^[①-⑩]$',                  # ①②
            r'^[A-Za-z][、．\.]?$',       # A. B、
            r'^[(（][A-Za-z][)）]$',       # (A)（B）
            r'^[一二三四五六七八九十]+[、．\.\s]*$',  # 一、 二．
            r'^[(（][一二三四五六七八九十]+[)）]$',   # （一）(二)
            r'^第[一二三四五六七八九十]+[、．\.]?$',  # 第一、第二
        ]
        for pat in lone_number_patterns:
            if _re.match(pat, s):
                return True
        # 只有数字+常见编号标点，没有中文汉字
        if not _re.search(r'[\u4e00-\u9fff]', s) and not _re.search(r'[a-zA-Z]{2,}', s):
            cleaned = _re.sub(r'[\d\s、．\.）).(（\d①-⑩A-Za-z]', '', s)
            if not cleaned:
                return True
        return False

    def _strip_source_numbering(text):
        """剥离段落开头的编号，保留纯文本内容"""
        if not text:
            return text
        stripped = text.strip()
        # 匹配并剥离以下编号模式：
        # 一、 二、 三、  ... 十、 (中文数字章节编号)
        # （一）（二）...（十）(中文数字括号编号)
        # 1、2、3、... (数字顿号)
        # 1. 2. 3. ... (数字点号)
        # 1）2）3）... (数字括号)
        # (1)(2)(3)... (圆括号数字)
        # ①②③... (带圈数字)
        patterns = [
            r'^[一二三四五六七八九十]+[、．\.]\s*',        # 一、 二．
            r'^（[一二三四五六七八九十]+）\s*',               # （一）
            r'^[(（]\d+[)）]\s*',                             # (1) （2）
            r'^\d+[）).、．]\s*',                             # 1） 2. 3、
            r'^[①-⑩]\s*',                                   # ①②...
            r'^第[一二三四五六七八九十]+[、．\.]\s*',         # 第一、
            r'^[A-Z][、．\.]\s*',                             # A. B、
        ]
        for pat in patterns:
            m = _re.match(pat, stripped)
            if m:
                stripped = stripped[m.end():].strip()
                # 继续匹配（防止多重编号如 "2、1）"）
                continue
            break
        return stripped

    _auto_number_counter = 0
    _sub_number_active = False
    _sub_number_counter = 0

    def _reset_auto_number():
        nonlocal _auto_number_counter, _sub_number_active, _sub_number_counter
        _auto_number_counter = 0
        _sub_number_active = False
        _sub_number_counter = 0

    def _get_auto_number_str(text_after_clean):
        """根据文本内容决定使用主编号还是二级编号"""
        nonlocal _auto_number_counter, _sub_number_active, _sub_number_counter
        # 判断上一行是否以：或:结尾 → 激活二级编号
        if text_after_clean and (text_after_clean.rstrip().endswith('：') or text_after_clean.rstrip().endswith(':')):
            _sub_number_active = True
            _sub_number_counter = 0
            # 主编号仍然递增
            _auto_number_counter += 1
            return f'{_auto_number_counter}.'
        # 如果二级编号已激活
        if _sub_number_active:
            _sub_number_counter += 1
            return f'（{_sub_number_counter}）'
        # 普通主编号
        _auto_number_counter += 1
        return f'{_auto_number_counter}.'

    def _strip_source_formatting_and_apply_style(para_elem, is_title=False, is_chapter_content=False, add_number=False):
        """清除源段落所有格式（字体+编号），统一应用宋体+指定字号"""
        texts = para_elem.findall('.//w:t', nsp)
        para_text = ''.join(t.text or '' for t in texts).strip()
        if not para_text:
            return False  # BUG FIX: 返回 False 而非 None
        
        # 彻底清除段落格式（pPr）
        pPr = para_elem.find(f'{{{nsp["w"]}}}pPr')
        if pPr is not None:
            jc = pPr.find(f'{{{nsp["w"]}}}jc')
            jc_val = None
            if jc is not None:
                jc_val = jc.get(f'{{{nsp["w"]}}}val')
            para_elem.remove(pPr)
        new_pPr = etree.SubElement(para_elem, f'{{{nsp["w"]}}}pPr')
        if jc_val:
            new_jc = etree.SubElement(new_pPr, f'{{{nsp["w"]}}}jc')
            new_jc.set(f'{{{nsp["w"]}}}val', jc_val)
        
        para_text_stripped = para_text.strip()
        is_report_title = is_title if is_title else False
        is_chapter_title = _is_heading_text(para_text_stripped)
        
        # 设置字号
        if is_report_title:
            font_size = '30'
            bold = True
        elif is_chapter_title:
            font_size = '28'
            bold = True
        else:
            font_size = '28'
            bold = False
        
        # 如果是章节内容段落，清除编号
        clean_text = para_text_stripped
        if is_chapter_content and not is_report_title and not is_chapter_title:
            clean_text = _strip_source_numbering(para_text_stripped)
            # 过滤掉只剩编号/空的内容
            if not clean_text or _is_only_number_or_empty(clean_text):
                return False  # BUG FIX: 返回 False 让调用者跳过
        
        # 如果需要自动编号，在文本前加上 "1." "2." 或 "（1）" "（2）" ...
        if add_number and not is_report_title and not is_chapter_title and clean_text:
            num_str = _get_auto_number_str(clean_text)
            clean_text = num_str + clean_text
            # 添加缩进 1.0 英寸(720 twips)
            ind = etree.SubElement(new_pPr, f'{{{nsp["w"]}}}ind')
            ind.set(f'{{{nsp["w"]}}}left', '720')
        
        # 更新所有 run：文本和格式
        first_run = True
        for r in para_elem.findall(f'{{{nsp["w"]}}}r'):
            rPr = r.find(f'{{{nsp["w"]}}}rPr')
            if rPr is not None:
                r.remove(rPr)
            new_rPr = etree.SubElement(r, f'{{{nsp["w"]}}}rPr')
            rFonts = etree.SubElement(new_rPr, f'{{{nsp["w"]}}}rFonts')
            rFonts.set(f'{{{nsp["w"]}}}ascii', 'SimSun')
            rFonts.set(f'{{{nsp["w"]}}}eastAsia', 'SimSun')
            rFonts.set(f'{{{nsp["w"]}}}hAnsi', 'SimSun')
            sz = etree.SubElement(new_rPr, f'{{{nsp["w"]}}}sz')
            sz.set(f'{{{nsp["w"]}}}val', font_size)
            szCs = etree.SubElement(new_rPr, f'{{{nsp["w"]}}}szCs')
            szCs.set(f'{{{nsp["w"]}}}val', font_size)
            if bold:
                b = etree.SubElement(new_rPr, f'{{{nsp["w"]}}}b')
            t_elem = r.find(f'{{{nsp["w"]}}}t')
            if t_elem is not None:
                if first_run:
                    t_elem.text = clean_text
                    first_run = False
                else:
                    t_elem.text = ''
    
    # ========== 第五步：构建新文档 ==========
    new_doc_xml = deepcopy(tpl_doc_xml)
    new_body = new_doc_xml.find('.//w:body', nsp)
    if new_body is None:
        raise ValueError("模板文档中找不到 body 元素")
    tpl_sectPr = new_body.find('w:sectPr', nsp)
    
    # 清空 body
    for child in list(new_body):
        if child.tag != f'{{{nsp["w"]}}}sectPr':
            new_body.remove(child)
    
    # ====== 1. 前导内容（标题+引言） ======
    if source_pre_indices:
        for pi in source_pre_indices:
            if pi < len(all_source_paras):
                elem = deepcopy(all_source_paras[pi])
                # 第一个前导段落视为报告标题（小三加粗，保留编号），其余剥离编号
                is_first = (pi == source_pre_indices[0])
                result = _strip_source_formatting_and_apply_style(elem, is_title=is_first, is_chapter_content=not is_first)
                if result is not False:
                    new_body.append(elem)
    else:
        for pi in tpl_pre_paras_indices:
            if pi < len(all_tpl_paras):
                new_body.append(deepcopy(all_tpl_paras[pi]))
    
    # 为模板每个章节定义关键词，用于内容→标题的智能匹配
    # （内容中的关键词匹配数越多，越可能属于这个章节）
    TPL_KEYWORDS = {
        1: ['保单', '保额', '保险期限', '被保险人', '险种', '特约', '保险单', '承保', '投保人', 
            '伤亡责任', '医疗费用责任', '免赔', '赔付比例', '伤残评定'],
        2: ['委托', '接案', '转案', '受理', '我司', '委派', '调查核实',
            '秉承', '依法', '独立', '客观', '公正'],
        3: ['调查', '走访', '笔录', '调查员', '前往', '了解', '调取', '附件',
            '门诊病历', '出院记录', '住院', '诊断', '入院', '出院', '劳动合同',
            '身份信息', '身份证', '预缴金'],
        4: ['事故原因', '经过', '事发', '摔伤', '坠落', '受伤', '骨折', '高处摔伤',
            '桡骨远端骨折', '锁骨骨折', '肋骨骨折'],
        5: ['同业排查', '调查重点', '需要解决的问题', '核实', '核查',
            '排查', '特约条款', '安全绳', '安全带', '高处作业'],
        6: ['保险责任', '赔付', '理赔', '理算', '医疗费用', '伤残',
            '住院津贴', '免赔天数', '赔偿', '给付比例', '伤残等级',
            '责任限额', '医疗费', '损失'],
        7: ['结论', '认定', '属实', '属实', '建议', '综上所述',
            '事故属实', '保险期限', '意外伤害', '建议保险公司'],
    }
    
    # 遍历模板章节，用内容关键词智能匹配源文档内容
    used_source_nums = set()
    # 第一步：对每个模板章节，从所有未使用的源章节中找最佳匹配
    for tpl_num, tpl_title_idx, tpl_content_indices in tpl_chapters:
        _reset_auto_number()
        # 输出模板标题
        if tpl_title_idx < len(all_tpl_paras):
            new_body.append(deepcopy(all_tpl_paras[tpl_title_idx]))
        
        # 收集所有源文档的内容段落（已剥离编号的文本）
        source_content_texts = {}  # source_num -> [(para_idx, clean_text)]
        for snum, s_indices in source_chapters:
            if snum in used_source_nums:
                continue
            texts = []
            for si in s_indices:
                if si < len(all_source_paras):
                    pe = all_source_paras[si]
                    t_els = pe.findall('.//w:t', nsp)
                    pt = ''.join(t.text or '' for t in t_els).strip()
                    ct = _strip_source_numbering(pt)
                    if ct and not _is_only_number_or_empty(ct):
                        texts.append((si, ct))
            if texts:
                source_content_texts[snum] = texts
        
        # 如果没有源内容可以匹配，跳过的模板章节（保留模板标题但内容为空）
        if not source_content_texts:
            empty_p = etree.SubElement(new_body, f'{{{nsp["w"]}}}p')
            empty_r = etree.SubElement(empty_p, f'{{{nsp["w"]}}}r')
            empty_t = etree.SubElement(empty_r, f'{{{nsp["w"]}}}t')
            empty_t.text = ''
            continue
        
        # 计算每个源章节对当前模板章节的内容匹配分数
        keywords = TPL_KEYWORDS.get(tpl_num, [])
        best_snum = None
        best_score = -1
        scores = {}
        for snum, texts in source_content_texts.items():
            score = 0
            for pi, ct in texts:
                for kw in keywords:
                    if kw in ct:
                        score += 1
            scores[snum] = score
        
        # 选择分数最高的（且至少匹配了1个关键词）
        for snum, score in scores.items():
            if score > best_score:
                best_score = score
                best_snum = snum
        
        if best_snum is not None and best_score > 0:
            used_source_nums.add(best_snum)
            for si in source_chapters[best_snum - 1][1] if best_snum <= len(source_chapters) else []:
                actual_idx = None
                for idx, (num, _) in enumerate(source_chapters):
                    if num == best_snum:
                        actual_idx = idx
                        break
                if actual_idx is not None:
                    for pi in source_chapters[actual_idx][1]:
                        if pi < len(all_source_paras):
                            elem = deepcopy(all_source_paras[pi])
                            try:
                                result = _strip_source_formatting_and_apply_style(elem, is_chapter_content=True, add_number=True)
                                if result is not False:
                                    new_body.append(elem)
                            except:
                                pass
        else:
            # 没有匹配到 → 留空
            empty_p = etree.SubElement(new_body, f'{{{nsp["w"]}}}p')
            empty_r = etree.SubElement(empty_p, f'{{{nsp["w"]}}}r')
            empty_t = etree.SubElement(empty_r, f'{{{nsp["w"]}}}t')
            empty_t.text = ''
    
    # ====== 3. 源文档中未被使用的内容，用源文档标题追加 ======
    for snum, s_indices in source_chapters:
        if snum not in used_source_nums:
            # 找源文档章节标题
            src_title = ''
            for pi in range(len(all_source_paras)):
                pe = all_source_paras[pi]
                t_els = pe.findall('.//w:t', nsp)
                pt = ''.join(t.text or '' for t in t_els).strip()
                if _is_heading_text(pt):
                    # 检查这个标题后是否跟着当前章节的内容
                    pass
            # 直接输出内容（无标题）
            for si in s_indices:
                if si < len(all_source_paras):
                    elem = deepcopy(all_source_paras[si])
                    try:
                        result = _strip_source_formatting_and_apply_style(elem, is_chapter_content=True)
                        if result is not False:
                            new_body.append(elem)
                    except:
                        pass
    
    # ====== 4. 后置内容（声明等） ======
    for pi in tpl_post_paras_indices:
        if pi < len(all_tpl_paras):
            new_body.append(deepcopy(all_tpl_paras[pi]))
    
    # 恢复页面设置
    if tpl_sectPr is not None:
        new_body.append(deepcopy(tpl_sectPr))
    
    # ========== 第六步：输出 ==========
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
