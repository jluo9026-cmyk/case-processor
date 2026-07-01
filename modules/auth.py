"""
案件处理启动器 - 用户认证模块
使用 stdlib 实现，无需外部依赖
"""
import json
import os
import hashlib
import hmac
import base64
import secrets
import time
from pathlib import Path

# ===== 配置 =====
BASE_DIR = Path(__file__).parent.parent.resolve()
USERS_FILE = BASE_DIR / 'users.json'
TOKEN_SECRET = None  # 在 init 时生成或加载
TOKEN_TIMEOUT = 86400 * 7  # token 有效期 7 天


def _get_secret():
    """获取或生成密钥"""
    global TOKEN_SECRET
    if TOKEN_SECRET is not None:
        return TOKEN_SECRET
    secret_file = BASE_DIR / '.auth_secret'
    if secret_file.exists():
        TOKEN_SECRET = secret_file.read_text().strip()
    else:
        TOKEN_SECRET = secrets.token_hex(32)
        secret_file.write_text(TOKEN_SECRET)
    return TOKEN_SECRET


def _hash_password(password: str) -> str:
    """使用 SHA-256 哈希密码（加盐）"""
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f'{salt}${h}'


def _verify_password(password: str, stored: str) -> bool:
    """验证密码"""
    if '$' not in stored:
        return False
    salt, h = stored.split('$', 1)
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest() == h


def _load_users() -> dict:
    """从文件加载用户数据"""
    if not USERS_FILE.exists():
        return {}
    try:
        data = json.loads(USERS_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except:
        return {}


def _save_users(users: dict):
    """保存用户数据到文件"""
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding='utf-8')


def create_token(username: str, company: str) -> str:
    """创建访问令牌"""
    secret = _get_secret()
    payload = {
        'u': username,
        'c': company,
        't': int(time.time()),
        'e': int(time.time()) + TOKEN_TIMEOUT,
        'n': secrets.token_hex(4)
    }
    data = base64.urlsafe_b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    sig = hmac.new(secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f'{data}.{sig}'


def verify_token(token: str) -> dict:
    """验证令牌，返回 {'username': ..., 'company': ..., 'valid': bool}"""
    secret = _get_secret()
    if '.' not in token:
        return {'valid': False, 'reason': '格式错误'}
    data, sig = token.rsplit('.', 1)
    expected_sig = hmac.new(secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        return {'valid': False, 'reason': '签名无效'}
    try:
        payload = json.loads(base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8'))
    except:
        return {'valid': False, 'reason': '解码失败'}
    if payload.get('e', 0) < int(time.time()):
        return {'valid': False, 'reason': '已过期'}
    return {
        'valid': True,
        'username': payload['u'],
        'company': payload['c'],
        'created_at': payload['t'],
        'expires_at': payload['e']
    }


def _is_first_user() -> bool:
    """检查是否是第一个用户"""
    users = _load_users()
    return len(users) == 0


def register_user(username: str, password: str, company: str = 'hengtaicheng', display_name: str = '') -> dict:
    """注册新用户（第一个注册的用户自动成为管理员）"""
    users = _load_users()
    if username in users:
        return {'success': False, 'error': '用户名已存在'}
    if not username or len(username) < 2:
        return {'success': False, 'error': '用户名至少2个字符'}
    if not password or len(password) < 4:
        return {'success': False, 'error': '密码至少4个字符'}
    role = 'admin' if _is_first_user() else 'user'
    users[username] = {
        'password': _hash_password(password),
        'company': company,
        'display_name': display_name or username,
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'role': role
    }
    _save_users(users)
    return {'success': True, 'username': username, 'company': company, 'role': role}


def login_user(username: str, password: str) -> dict:
    """用户登录，成功返回 token"""
    users = _load_users()
    user = users.get(username)
    if not user:
        return {'success': False, 'error': '用户名或密码错误'}
    if not _verify_password(password, user['password']):
        return {'success': False, 'error': '用户名或密码错误'}
    token = create_token(username, user['company'])
    return {
        'success': True,
        'token': token,
        'username': username,
        'company': user['company'],
        'display_name': user.get('display_name', username)
    }


def list_all_users() -> dict:
    """列出所有用户（供管理员API使用）"""
    return _load_users()


def get_user_info(username: str) -> dict:
    """获取用户信息"""
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    return {
        'username': username,
        'company': user['company'],
        'display_name': user.get('display_name', username),
        'role': user.get('role', 'user'),
        'created_at': user.get('created_at', '')
    }