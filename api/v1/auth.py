from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import jwt, JWTError
from core.config import settings
from core.security import verify_password, create_access_token, get_password_hash, create_refresh_token, store_refresh_token, verify_refresh_token, delete_refresh_token, add_token_to_blacklist
from core.email import send_verification_code, send_verification_code_async
from core.verification import generate_code, store_code, verify_code, check_rate_limit, set_send_cooldown, get_remaining_attempts
from crud.user import get_user_by_email, create_user, update_user_password, get_user_by_id, validate_user_role
from crud.user_profile import get_user_profile_or_create
from config.database import get_db
from schemas.common import success, fail
from schemas.user import (
    UserCreate,
    LoginRequest,
    User,
    TokenData,
    RefreshTokenRequest,
    VerificationRequest,
    RegisterWithCodeRequest,
    PasswordResetRequest,
    PasswordChangeRequest
)
from dependencies import get_current_user
from models.user import User as DBUser, UserRole


router = APIRouter(tags=["用户认证"])

@router.post("/login")
def login_for_access_token(login_request: LoginRequest, db: Session = Depends(get_db)):
    # 状态值：1-正常，2-禁用
    user = get_user_by_email(db, login_request.email)
    if not user or not verify_password(login_request.password, user.password) or user.status != 1:
        return fail(code=4001, message="邮箱或密码错误")
    
    # 清除用户token失效标记（如果存在）
    from core.security import clear_user_tokens_invalid
    clear_user_tokens_invalid(user.id)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "user_id": user.id},
        expires_delta=access_token_expires
    )
    
    # 生成并存储refresh_token
    refresh_token = create_refresh_token()
    store_refresh_token(user.id, refresh_token)
    
    return success(
        data={
            "user": User.model_validate(user).model_dump(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        },
        message="登录成功"
    )

@router.post("/send-verification-code")
async def send_code(request: VerificationRequest, db: Session = Depends(get_db)):
    """发送验证码（用于注册或找回密码）"""
    # 输入验证
    if request.purpose not in ['register', 'reset_password']:
        return fail(code=400, message="验证码用途无效")
    
    # 频率限制检查
    if not check_rate_limit(request.email):
        return fail(code=429, message="发送过于频繁，请稍后再试")
    
    # 如果是找回密码，检查邮箱是否存在
    if request.purpose == 'reset_password':
        user = get_user_by_email(db, request.email)
        if not user:
            # 防止邮箱枚举，仍返回成功
            return success(message="如果邮箱存在，验证码已发送")
    
    # 如果是注册，检查邮箱是否已存在
    elif request.purpose == 'register':
        if get_user_by_email(db, request.email):
            return fail(code=4002, message="邮箱已存在")
    
    # 生成验证码
    code = generate_code()
    
    # 存储验证码（5分钟过期）
    store_code(request.email, code, request.purpose, 300)
    
    # 设置发送冷却（1分钟）
    set_send_cooldown(request.email, 60)
    
    # 发送邮件
    await send_verification_code_async(request.email, code)
    
    if settings.DEBUG:
        return success(message=f"【开发模式】验证码：{code}")
    return success(message="验证码已发送，请查收邮箱")

@router.post("/register-with-code")
def register_with_code(request: RegisterWithCodeRequest, db: Session = Depends(get_db)):
    """使用验证码注册"""
    if request.purpose != 'register':
        return fail(code=400, message="验证码用途不匹配")
    if len(request.username) < 2:
        return fail(code=400, message="用户名长度至少2位")
    if len(request.password) < 6:
        return fail(code=400, message="密码长度至少6位")
    if not verify_code(request.email, request.code, request.purpose):
        remaining_attempts = get_remaining_attempts(request.email, request.purpose)
        if remaining_attempts > 0:
            return fail(code=4003, message=f"验证码错误，还有{remaining_attempts}次尝试机会")
        else:
            return fail(code=4003, message="验证码错误次数过多，请重新获取验证码")
    if get_user_by_email(db, request.email):
        return fail(code=4002, message="邮箱已存在")
    hashed_password = get_password_hash(request.password)
    
    # 使用验证函数确保角色值正确
    try:
        user_role = validate_user_role("USER")  # 注册用户默认为USER角色
    except ValueError as e:
        return fail(code=400, message=f"角色验证失败: {str(e)}")
    
    db_user = DBUser(
        username=request.username,
        email=request.email,
        password=hashed_password,
        role=user_role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # 创建用户档案
    get_user_profile_or_create(db, db_user.id)
    
    # 清除用户token失效标记（如果存在）
    from core.security import clear_user_tokens_invalid
    clear_user_tokens_invalid(db_user.id)
    
    # 生成access_token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(db_user.id), "user_id": db_user.id},
        expires_delta=access_token_expires
    )
    
    # 生成并存储refresh_token
    refresh_token = create_refresh_token()
    store_refresh_token(db_user.id, refresh_token)
    
    return success(
        data={
            "user": User.model_validate(db_user).model_dump(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        },
        message="注册成功"
    )

@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """使用refresh_token获取新的access_token"""
    # 从Redis中查找用户ID
    from core.redis_client import redis_client
    
    try:
        # 使用refresh_token作为Key，直接查找对应的user_id
        user_id_str = redis_client.get(f"refresh_token_lookup:{request.refresh_token}")
        
        if user_id_str is None:
            return fail(code=401, message="refresh_token已过期或无效")
        
        # 将字符串转换为整数
        user_id = int(user_id_str)
        
        # 获取用户信息
        user = get_user_by_id(db, user_id)
        # 状态值：1-正常，2-禁用
        if not user or user.status != 1:
            return fail(code=401, message="用户不存在或已被禁用")
        
        # 生成新的access_token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "user_id": user.id},
            expires_delta=access_token_expires
        )
        
        return success(
            data={
                "access_token": access_token,
                "token_type": "bearer"
            },
            message="刷新token成功"
        )
    except redis.RedisError:
        return fail(code=500, message="服务器内部错误")

@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: DBUser = Depends(get_current_user)
):
    """登出，删除refresh_token并将Token添加到黑名单"""
    delete_refresh_token(current_user.id)
    
    # 将Token添加到黑名单
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        if jti:
            # 计算Token剩余有效时间
            exp = payload.get("exp")
            if exp:
                from datetime import datetime
                now = datetime.now().timestamp()
                expires_in = int(exp - now)
                if expires_in > 0:
                    add_token_to_blacklist(jti, expires_in)
    except JWTError:
        pass  # 如果Token无效，忽略错误
    
    return success(message="登出成功")

@router.post("/forgot-password")
def reset_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """忘记密码 - 重置密码"""
    # 输入验证
    if len(request.new_password) < 6:
        return fail(code=400, message="密码长度至少6位")
    
    # 验证码校验
    if not verify_code(request.email, request.code, request.purpose):
        remaining_attempts = get_remaining_attempts(request.email, request.purpose)
        if remaining_attempts > 0:
            return fail(code=4003, message=f"验证码错误，还有{remaining_attempts}次尝试机会")
        else:
            return fail(code=4003, message="验证码错误次数过多，请重新获取验证码")
    
    # 用户查找
    user = get_user_by_email(db, request.email)
    if not user:
        return fail(code=4004, message="用户不存在")
    
    # 密码加密
    hashed_password = get_password_hash(request.new_password)
    
    # 更新密码
    user.password = hashed_password
    db.commit()
    
    # 使旧Token失效
    delete_refresh_token(user.id)
    
    # 使用户的所有token失效
    from core.security import invalidate_user_tokens
    invalidate_user_tokens(user.id)
    
    return success(message="密码修改成功，请重新登录")

@router.post("/change-password")
def change_password(
    request: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """修改密码（已登录状态）"""
    # 输入验证
    if len(request.new_password) < 6:
        return fail(code=400, message="新密码长度至少6位")
    
    # 获取并验证旧密码
    if not verify_password(request.old_password, current_user.password):
        return fail(code=4005, message="原密码错误")
    
    # 密码加密
    hashed_password = get_password_hash(request.new_password)
    
    # 更新密码
    current_user.password = hashed_password
    db.commit()
    
    # 使旧Token失效
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        if jti:
            # 计算Token剩余有效时间
            exp = payload.get("exp")
            if exp:
                from datetime import datetime
                now = datetime.now().timestamp()
                expires_in = int(exp - now)
                if expires_in > 0:
                    add_token_to_blacklist(jti, expires_in)
    except JWTError:
        pass  # 如果Token无效，忽略错误
    
    # 删除该用户的RT
    delete_refresh_token(current_user.id)
    
    return success(message="密码修改成功，请重新登录")

@router.get("/me")
def read_users_me(current_user: DBUser = Depends(get_current_user)):
    return success(
        data=User.model_validate(current_user).model_dump(),
        message="获取用户信息成功"
    )
