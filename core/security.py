from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt
from core.config import settings
from core.redis_client import redis_client
import secrets

# 只使用 bcrypt 作为哈希方案，避免版本兼容性问题
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # 确保密码不超过 72 字节以符合 bcrypt 的长度限制
    if isinstance(plain_password, str):
        plain_password_bytes = plain_password.encode('utf-8')
        if len(plain_password_bytes) > 72:
            # 截断到 72 字节
            plain_password = plain_password_bytes[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    # 确保密码不超过 72 字节以符合 bcrypt 的长度限制
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            # 截断到 72 字节
            password = password_bytes[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    # 添加jti字段用于Token黑名单检查
    import uuid
    to_encode.update({"jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_never_expire_token(data: dict) -> str:
    """创建永不过期的token"""
    to_encode = data.copy()
    # 不设置过期时间，创建永不过期的token
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token() -> str:
    """生成一个随机的refresh_token"""
    return secrets.token_urlsafe(32)

def store_refresh_token(user_id: int, refresh_token: str, expires_in: int = 604800) -> None:
    """存储refresh_token到Redis，默认7天过期"""
    # 存储正向映射：user_id -> refresh_token
    redis_client.setex(f"refresh_token:{user_id}", expires_in, refresh_token)
    # 存储反向映射：refresh_token -> user_id（用于快速查找）
    redis_client.setex(f"refresh_token_lookup:{refresh_token}", expires_in, str(user_id))

def verify_refresh_token(user_id: int, refresh_token: str) -> bool:
    """验证refresh_token是否有效"""
    stored_token = redis_client.get(f"refresh_token:{user_id}")
    return stored_token == refresh_token

def delete_refresh_token(user_id: int) -> None:
    """删除用户的refresh_token"""
    # 获取当前refresh_token
    refresh_token = redis_client.get(f"refresh_token:{user_id}")
    if refresh_token:
        # 删除正向映射
        redis_client.delete(f"refresh_token:{user_id}")
        # 删除反向映射
        redis_client.delete(f"refresh_token_lookup:{refresh_token}")

def add_token_to_blacklist(jti: str, expires_in: int = None) -> None:
    """将Token添加到黑名单"""
    if expires_in is None:
        # 默认设置为24小时过期
        expires_in = 86400
    redis_client.setex(f"blacklist:at:{jti}", expires_in, "1")

def is_token_blacklisted(jti: str) -> bool:
    """检查Token是否在黑名单中"""
    return redis_client.exists(f"blacklist:at:{jti}")

def invalidate_user_tokens(user_id: int) -> None:
    """使用户的所有token失效"""
    # 添加一个标记，表示该用户的所有token都应该失效
    # 设置一个较长的过期时间，确保覆盖所有可能的token
    redis_client.setex(f"user_tokens_invalid:{user_id}", 86400, "1")

def is_user_tokens_invalid(user_id: int) -> bool:
    """检查用户的所有token是否已被标记为无效"""
    return redis_client.exists(f"user_tokens_invalid:{user_id}")

def clear_user_tokens_invalid(user_id: int) -> None:
    """清除用户token失效标记"""
    redis_client.delete(f"user_tokens_invalid:{user_id}")
