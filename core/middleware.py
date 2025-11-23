from fastapi import Request, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Callable, List
from functools import wraps
import logging

from core.security import is_token_blacklisted
from core.config import settings
from core.permissions import check_user_permission, Permission
from dependencies import get_db
from models.user import User

logger = logging.getLogger(__name__)

class PermissionMiddleware:
    """权限控制中间件类"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # 获取请求路径和方法
            path = request.url.path
            method = request.method
            
            # 检查是否需要权限验证的路径
            if self._requires_permission_check(path):
                try:
                    # 获取Authorization头
                    authorization = request.headers.get("authorization")
                    if not authorization:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="未提供认证令牌",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    
                    # 解析Bearer token
                    if not authorization.startswith("Bearer "):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="无效的认证令牌格式",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    
                    token = authorization.split(" ")[1]
                    
                    # 检查token是否在黑名单中
                    if is_token_blacklisted(token):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="令牌已失效",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    
                    # 解码JWT获取用户信息
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                    user_id: int = payload.get("sub")
                    if user_id is None:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="无效的认证令牌",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    
                    # 获取数据库会话
                    db = next(get_db())
                    
                    try:
                        # 获取用户信息
                        user = db.query(User).filter(User.id == user_id).first()
                        if user is None:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="用户不存在",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
                        
                        # 检查用户状态
                        if user.status != 1:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="用户账户已被禁用",
                            )
                        
                        # 获取路径所需的权限
                        required_permissions = self._get_required_permissions(path, method)
                        
                        # 检查用户权限
                        if required_permissions and not check_user_permission(user, required_permissions):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="权限不足",
                            )
                        
                        # 将用户信息添加到请求状态
                        request.state.user = user
                    finally:
                        db.close()
                    
                except JWTError:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="无效的认证令牌",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                except HTTPException:
                    # 重新抛出HTTPException，不包装
                    raise
                except Exception as e:
                    # 记录详细错误信息用于调试
                    logger.error(f"权限验证失败: {str(e)}", exc_info=True)
                    
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="权限验证失败",
                    )
        
        # 调用下一个中间件或路由处理器
        await self.app(scope, receive, send)
    
    def _requires_permission_check(self, path: str) -> bool:
        """检查路径是否需要权限验证"""
        # 不需要权限验证的路径
        public_paths = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/favicon.ico",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/verification/send",
            "/api/v1/verification/verify",
            "/api/v1/payment/notify",  # 支付回调接口
            "/api/v1/payment/query",   # 支付查询接口
        ]
        
        # 检查是否为公共路径
        for public_path in public_paths:
            if path.startswith(public_path):
                return False
        
        # 检查是否为静态文件
        if path.startswith("/static/") or path.startswith("/media/") or path.startswith("/images/"):
            return False
        
        # 其他路径都需要权限验证
        return True
    
    def _get_required_permissions(self, path: str, method: str) -> List[Permission]:
        """获取路径所需的权限"""
        # 管理员路径权限映射
        admin_paths = {
            "/api/v1/admin/": [Permission.VIEW_ALL_USERS],
            "/api/v1/users/": [Permission.MANAGE_USERS],
            "/api/v1/user_management/": [Permission.MANAGE_USERS],
            "/api/v1/payment_order/": [Permission.VIEW_ALL_TRANSACTIONS],
            "/api/v1/credits/": [Permission.VIEW_ALL_TRANSACTIONS],
        }
        
        # 检查是否为管理员路径
        for admin_path, permissions in admin_paths.items():
            if path.startswith(admin_path):
                return permissions
        
        # 默认不需要特殊权限，只需要登录验证
        return []

def require_permissions(permissions: List[Permission]):
    """权限装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取请求对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # 尝试从kwargs中获取
                request = kwargs.get("request")
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="无法获取请求对象",
                )
            
            # 获取用户信息
            user = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # 检查权限
            if not check_user_permission(user, permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="权限不足",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator