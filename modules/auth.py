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

# 密码验证开关：免费版暂时关闭，付费版设置环境变量 AUTH_REQUIRED=true 开启
AUTH_REQUIRED = os.getenv('AUTH_REQUIRED', '').lower() == 'true'


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
    """用户登录（免费版跳过密码验证，付费版验证密码）"""
    users = _load_users()
    user = users.get(username)
    
    if not user:
        # 用户不存在时自动创建（免费版不验证密码）
        display_name = username
        role = 'admin' if _is_first_user() else 'user'
        users[username] = {
            'password': _hash_password(password or '123456'),
            'company': 'hengtaicheng',
            'display_name': display_name,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'role': role
        }
        _save_users(users)
        user = users[username]
    elif AUTH_REQUIRED:
        # 付费版：验证密码
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


# ===== 活跃会话管理 =====
ACTIVE_SESSIONS = {}  # token_hash -> {username, company, last_active, request_count, created_at}
BLACKLISTED_TOKENS = {}  # token_hash -> reason
SESSION_TIMEOUT = 1800  # 30 分钟无活动视为离线


def _token_hash(token: str) -> str:
    """生成 token 的哈希值用于存储"""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]


def record_request(token: str, now: float = None):
    """记录一次 API 请求，更新活跃会话"""
    if not token:
        return
    th = _token_hash(token)
    if th in BLACKLISTED_TOKENS:
        return False  # token 已被拉黑
    result = verify_token(token)
    if not result['valid']:
        return None
    if now is None:
        now = time.time()
    if th not in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[th] = {
            'username': result['username'],
            'company': result['company'],
            'last_active': now,
            'request_count': 0,
            'created_at': now,
            'token_prefix': token[:12] + '...'
        }
    ACTIVE_SESSIONS[th]['last_active'] = now
    ACTIVE_SESSIONS[th]['request_count'] += 1
    return True


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    th = _token_hash(token)
    return th in BLACKLISTED_TOKENS


def blacklist_token(token: str) -> bool:
    """将 token 加入黑名单（强制下线）"""
    th = _token_hash(token)
    if th in ACTIVE_SESSIONS:
        username = ACTIVE_SESSIONS[th]['username']
        BLACKLISTED_TOKENS[th] = {
            'username': username,
            'reason': f'管理员强制下线 ({time.strftime("%Y-%m-%d %H:%M:%S")})',
            'created_at': time.time()
        }
        del ACTIVE_SESSIONS[th]
        return True
    return False


def blacklist_user_sessions(username: str) -> int:
    """强制某个用户的所有会话下线"""
    count = 0
    for th, session in list(ACTIVE_SESSIONS.items()):
        if session['username'] == username:
            BLACKLISTED_TOKENS[th] = {
                'username': username,
                'reason': f'管理员强制下线 ({time.strftime("%Y-%m-%d %H:%M:%S")})',
                'created_at': time.time()
            }
            del ACTIVE_SESSIONS[th]
            count += 1
    return count


def get_online_sessions() -> list:
    """获取所有在线会话"""
    now = time.time()
    # 清理超时会话
    expired = []
    for th, session in ACTIVE_SESSIONS.items():
        if now - session['last_active'] > SESSION_TIMEOUT:
            expired.append(th)
    for th in expired:
        del ACTIVE_SESSIONS[th]
    
    result = []
    for th, session in ACTIVE_SESSIONS.items():
        online = (now - session['last_active']) < SESSION_TIMEOUT
        if online:
            result.append({
                'username': session['username'],
                'company': session['company'],
                'request_count': session['request_count'],
                'last_active': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session['last_active'])),
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session['created_at'])),
                'online': True
            })
    return result


def get_online_count() -> int:
    """获取在线用户数"""
    return len(get_online_sessions())


def get_total_request_count() -> int:
    """获取总请求次数"""
    total = 0
    for session in ACTIVE_SESSIONS.values():
        total += session['request_count']
    return total


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