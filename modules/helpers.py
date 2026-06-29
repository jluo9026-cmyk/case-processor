__all__ = [
    'generate_report_with_content', '_call_deepseek_api', '_generate_report_prompt',
    'generate_disclaimer', 'generate_signature'
]

from modules.config import BASE_DIR, PORT_FILE, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT, DEEPSEEK_CONNECT_TIMEOUT, MODEL_TEMPERATURE, MODEL_TOP_P, MODEL_MAX_TOKENS, SYSTEM_ROLE
from datetime import datetime
import httpx

# ============ 辅助函数 ============

def _generate_report_prompt(ocr_text: str, case_info: str, original_text: str) -> str:
    """生成DeepSeek API的提示词"""
    has_ocr = ocr_text and ocr_text.strip()
    has_original = original_text and original_text.strip()

    prompt = f"""=== OCR识别文本 ===
{ocr_text if has_ocr else "无OCR识别文本"}

=== 案件信息 ===
{case_info if case_info.strip() else "无案件信息"}

=== 原始文本 ===
{original_text if has_original else "无原始文本"}
"""
    return prompt


async def _call_deepseek_api(prompt: str) -> str:
    """调用 DeepSeek API 生成报告"""
    try:
        import httpx
        print(f'[DeepSeek] 调用 API，提示词长度: {len(prompt)}')

        timeout_config = httpx.Timeout(
            DEEPSEEK_TIMEOUT,
            connect=DEEPSEEK_CONNECT_TIMEOUT,
            read=DEEPSEEK_TIMEOUT,
            write=60
        )

        async with httpx.AsyncClient(timeout=timeout_config) as client:
            resp = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": SYSTEM_ROLE},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": MODEL_TEMPERATURE,
                    "top_p": MODEL_TOP_P,
                    "max_tokens": MODEL_MAX_TOKENS
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data and "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                print(f'[DeepSeek] API 返回成功，长度: {len(content)}')
                return content

            print(f'[DeepSeek] API 返回异常: {data}')
            return None

    except httpx.TimeoutException:
        print(f'[DeepSeek] API 超时（{DEEPSEEK_TIMEOUT}秒）')
        return None
    except Exception as e:
        print(f'[DeepSeek] API 调用失败: {e}')
        import traceback
        traceback.print_exc()
        return None


def generate_disclaimer():
    """生成免责声明"""
    return """
免责声明：
本报告仅供内部参考使用，不构成任何法律建议。报告中的信息基于提供的材料进行分析，
如有不准确之处，请以原始文件为准。本报告未经授权不得用于任何商业目的。
"""


def generate_signature(surveyor_name=""):
    """生成签名栏"""
    name = surveyor_name if surveyor_name else "________"
    today = datetime.now().strftime("%Y年%m月%d日")
    return f"""
调查员签名：{name}
日期：{today}

（本报告共 X 页）
"""


def generate_report_with_content(combined_text, ocr_text, original_text):
    """生成报告内容（不使用AI时的后备方案）"""
    report = ""
    report += "保险公估调查报告\n"
    report += "=" * 50 + "\n\n"

    report += "一、案件基本信息\n"
    report += "-" * 30 + "\n"
    report += f"报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    report += "二、调查情况\n"
    report += "-" * 30 + "\n"
    if combined_text.strip():
        report += combined_text + "\n\n"
    else:
        report += "无调查信息\n\n"

    report += "三、保险责任分析\n"
    report += "-" * 30 + "\n"
    report += "根据调查情况，正在进行责任分析...\n\n"

    report += "四、调查结论\n"
    report += "-" * 30 + "\n"
    report += "待补充\n\n"

    report += generate_disclaimer()
    report += generate_signature("")

    return report

