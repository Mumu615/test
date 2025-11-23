from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from typing import Optional

from core.config import settings
from core.security import verify_password, is_token_blacklisted
from crud.user import get_user_by_id
from config.database import get_db
from models.user import User as DBUser, UserRole
from schemas.user import User

security = HTTPBearer()

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")  # 获取JWT ID
        if user_id is None:
            raise credentials_exception
        
        # 检查Token是否在黑名单中
        from core.security import is_token_blacklisted
        if jti and is_token_blacklisted(jti):
            raise credentials_exception
        
        # 检查用户的所有token是否已被标记为无效
        from core.security import is_user_tokens_invalid
        if is_user_tokens_invalid(int(user_id)):
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_id(db, user_id=int(user_id))
    if user is None:
        raise credentials_exception
    
    # 将用户信息添加到请求状态，供中间件使用
    request.state.user = user
    
    return user

# 权限检查依赖
async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    return current_user

# 管理员权限检查
async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前管理员用户"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限"
        )
    return current_user

# 超级管理员权限检查
async def get_current_super_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前超级管理员用户"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要超级管理员权限"
        )
    return current_user

# 自定义权限检查
async def get_current_user_with_permissions(
    required_permissions: list,
    current_user: User = Depends(get_current_user)
) -> User:
    """获取具有特定权限的当前用户"""
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(current_user)
    
    for permission in required_permissions:
        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {permission.value}"
            )
    
    return current_user

# 创建权限检查函数
def require_permission(permission):
    """创建需要特定权限的依赖函数"""
    async def permission_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        from core.permissions import has_permission
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {permission.value}"
            )
        return current_user
    
    return permission_dependency

# 创建多权限检查函数
def require_permissions(permissions):
    """创建需要多个权限的依赖函数"""
    async def permissions_dependency(
        current_user: User = Depends(get_current_user)
    ) -> User:
        from core.permissions import has_all_permissions
        if not has_all_permissions(current_user, permissions):
            required_names = [p.value for p in permissions]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {', '.join(required_names)}"
            )
        return current_user
    
    return permissions_dependency

__all__ = [
    "get_current_user", 
    "get_current_active_user",
    "get_current_admin_user",
    "get_current_super_admin_user",
    "get_current_user_with_permissions",
    "require_permission",
    "require_permissions",
    "get_db"
]