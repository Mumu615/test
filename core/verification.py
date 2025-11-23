import random
from core.redis_client import redis_client

def generate_code() -> str:
    return str(random.randint(100000, 999999))

def store_code(email: str, code: str, purpose: str, expires_in: int = 300):
    """存储验证码到 Redis，key: verification_code:{purpose}:{email}"""
    key = f"verification_code:{purpose}:{email}"
    # 使用列表存储验证码，新的验证码添加到列表头部
    redis_client.lpush(key, code)
    # 设置整个列表的过期时间
    redis_client.expire(key, expires_in)
    # 清空之前的尝试次数记录
    attempts_key = f"{key}:attempts"
    redis_client.delete(attempts_key)

def verify_code(email: str, code: str, purpose: str) -> bool:
    """验证并删除验证码，支持失败尝试次数限制，只验证最近一次发送的验证码"""
    key = f"verification_code:{purpose}:{email}"
    attempts_key = f"{key}:attempts"
    
    # 获取最近一次发送的验证码（列表的第一个元素）
    stored_codes = redis_client.lrange(key, 0, 0)
    
    # 检查验证码是否存在
    if not stored_codes:
        return False
    
    stored_code = stored_codes[0].decode('utf-8') if isinstance(stored_codes[0], bytes) else stored_codes[0]
    
    # 获取当前尝试次数
    current_attempts = redis_client.get(attempts_key)
    if current_attempts is None:
        current_attempts = 0
    else:
        current_attempts = int(current_attempts)
    
    # 增加尝试次数
    current_attempts += 1
    redis_client.setex(attempts_key, 300, str(current_attempts))  # 5分钟过期
    
    # 验证码正确
    if stored_code == code:
        redis_client.delete(key)  # 删除验证码列表
        redis_client.delete(attempts_key)  # 删除尝试次数记录
        return True
    
    # 验证码错误，检查是否超过最大尝试次数
    if current_attempts >= 3:
        redis_client.delete(key)  # 删除验证码列表
        redis_client.delete(attempts_key)  # 删除尝试次数记录
    
    return False

def get_remaining_attempts(email: str, purpose: str) -> int:
    """获取验证码的剩余尝试次数"""
    key = f"verification_code:{purpose}:{email}"
    attempts_key = f"{key}:attempts"
    
    # 检查验证码列表是否存在
    if not redis_client.exists(key):
        return 0
    
    # 获取当前尝试次数
    current_attempts = redis_client.get(attempts_key)
    if current_attempts is None:
        return 3  # 默认3次尝试机会
    
    current_attempts = int(current_attempts)
    remaining = max(0, 3 - current_attempts)
    
    # 如果剩余尝试次数为0，删除验证码列表和尝试记录
    if remaining == 0:
        redis_client.delete(key)
        redis_client.delete(attempts_key)
    
    return remaining

def check_rate_limit(email: str) -> bool:
    """检查发送频率限制，返回True表示可以发送，False表示被限制"""
    cooldown_key = f"cooldown:verify:{email}"
    return not redis_client.exists(cooldown_key)

def set_send_cooldown(email: str, cooldown_seconds: int = 60):
    """设置发送冷却标记"""
    cooldown_key = f"cooldown:verify:{email}"
    redis_client.setex(cooldown_key, cooldown_seconds, "1")
