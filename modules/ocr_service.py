"""
OCR 服务模块
"""
__all__ = [
    '_call_baidu_ocr', '_call_qwen_vl', '_classify_image', '_merge_information',
    'BAIDU_API_KEY', 'BAIDU_SECRET_KEY', 'QWEN_VL_API_KEY', 'QWEN_VL_BASE_URL',
    'HAS_PADDLE', 'PADDLE_OCR', '_init_paddle_ocr'
]

import os
import json
import base64
import io
import urllib.request
import urllib.parse
import asyncio
import httpx
from datetime import datetime

# ============ 从 config 导入配置 ============
from modules.config import (
    BASE_DIR,
    PORT_FILE,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_TIMEOUT,
    DEEPSEEK_CONNECT_TIMEOUT,
    MODEL_TEMPERATURE,
    MODEL_TOP_P,
    MODEL_MAX_TOKENS,
    SYSTEM_ROLE,
    BAIDU_API_KEY,
    BAIDU_SECRET_KEY,
    QWEN_VL_API_KEY,
    QWEN_VL_BASE_URL,
)

# ============ DeepSeek API 配置（从 config 导入，此处保留为兼容） ============
# 注意：以下变量已从 config 导入，不需要重新定义
# DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT, DEEPSEEK_CONNECT_TIMEOUT
# MODEL_TEMPERATURE, MODEL_TOP_P, MODEL_MAX_TOKENS, SYSTEM_ROLE
# BAIDU_API_KEY, BAIDU_SECRET_KEY, QWEN_VL_API_KEY, QWEN_VL_BASE_URL

# ============ 本地配置 ============
_baidu_access_token = None
PADDLE_OCR_TIMEOUT = 60
PADDLE_OCR = None
HAS_PADDLE = False


def _init_paddle_ocr():
    """初始化PaddleOCR"""
    global PADDLE_OCR, HAS_PADDLE
    if PADDLE_OCR is not None:
        return True
    try:
        # 环境变量应在导入前设置
        os.environ['FLAGS_use_mkldnn'] = '0'
        os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
        from paddleocr import PaddleOCR
        print('[OCR] 正在初始化 PaddleOCR...')
        PADDLE_OCR = PaddleOCR(lang='ch')
        HAS_PADDLE = True
        print('[OCR] PaddleOCR 初始化成功')
        return True
    except Exception as e:
        print(f'[OCR] PaddleOCR 初始化失败: {e}')
        PADDLE_OCR = None
        HAS_PADDLE = False
        return False


if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
    print('[WARNING] OCR API Key 未配置')
else:
    print('[INFO] OCR API Key 已配置')


def _get_baidu_token() -> str:
    """获取百度OCR Token"""
    global _baidu_access_token
    if _baidu_access_token:
        return _baidu_access_token

    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        raise ValueError("OCR API Key 未配置")

    token_url = "https://aip.baidubce.com/oauth/2.0/token"
    params_str = f"grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"

    try:
        url = f"{token_url}?{params_str}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            _baidu_access_token = data["access_token"]
            print(f'[OCR] 获取百度 OCR Token 成功')
            return _baidu_access_token
    except Exception as e:
        print(f'[OCR] 获取Token失败: {e}')
        raise


def _call_baidu_ocr(image_base64: str) -> dict:
    """调用百度OCR API - 通用文字识别（高精度版）"""
    token = _get_baidu_token()
    ocr_url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={token}"

    try:
        post_data = f"image={urllib.parse.quote(image_base64)}".encode('utf-8')
        req = urllib.request.Request(ocr_url, data=post_data, method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            result_data = json.loads(resp.read().decode('utf-8'))
            return {"status": 200, "data": result_data}
    except Exception as e:
        print(f'[OCR] 调用百度 OCR API 失败: {e}')
        raise


async def _call_qwen_vl(image_base64: str, mode: str = 'ocr') -> str:
    """调用Qwen-VL视觉模型
    Args:
        image_base64: base64编码的图片
        mode: 'ocr' - 精准文字提取, 'describe' - 图片描述
    """
    try:
        headers = {
            "Authorization": f"Bearer {QWEN_VL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        if mode == 'ocr':
            prompt = "请仔细、完整地提取这张图片中所有可见的文字内容。按原文顺序逐字输出，不要添加任何描述、解释或额外的文字。如果图片中有多个文字区域，请按从上到下、从左到右的顺序输出。"
        else:
            prompt = "请详细描述这张图片的内容，包括文字、场景、人物、物品等所有可见信息。"
        
        payload = {
            "model": "qwen-vl-plus",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{QWEN_VL_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            if data and "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            return None
    except Exception as e:
        print(f'[Qwen-VL] 调用失败: {e}')
        return None


def _classify_image(image_base64: str) -> str:
    """简单图像分类 - 判断是文字型还是视觉型"""
    try:
        from PIL import Image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        gray_image = image.convert('L')
        width, height = gray_image.size

        high_contrast_count = 0
        total_pixels = width * height

        for y in range(0, height, 10):
            for x in range(0, width, 10):
                pixel = gray_image.getpixel((x, y))
                if pixel < 30 or pixel > 225:
                    high_contrast_count += 1

        contrast_ratio = high_contrast_count / ((width // 10) * (height // 10))
        if contrast_ratio > 0.3:
            return "text"
        else:
            return "visual"
    except Exception as e:
        print(f'[Image Classify] 分类失败: {e}')
        return "text"


def _merge_information(
    investigation_content: dict = None,
    ocr_text: str = "",
    visual_descriptions: str = "",
    paddle_text: str = ""
) -> str:
    """合并多源信息"""
    merged = []

    if investigation_content:
        if investigation_content.get('scene_investigation'):
            merged.append(f"\n{investigation_content['scene_investigation']}")
        if investigation_content.get('police_station_record'):
            merged.append(f"\n{investigation_content['police_station_record']}")
        if investigation_content.get('traffic_police_record'):
            merged.append(f"\n{investigation_content['traffic_police_record']}")
        if investigation_content.get('hospital_diagnosis'):
            merged.append(f"\n{investigation_content['hospital_diagnosis']}")

    if ocr_text and ocr_text.strip():
        merged.append(f"\nOCR\n{ocr_text}")

    if visual_descriptions and visual_descriptions.strip():
        merged.append(f"\n{visual_descriptions}")

    if paddle_text and paddle_text.strip():
        merged.append(f"\n{paddle_text}")

    return "\n".join(merged)