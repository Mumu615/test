"""
权限控制模块
实现基于角色的访问控制(RBAC)系统
"""
from enum import Enum
from typing import List, Optional, Set
from fastapi import HTTPException, status, Depends
from models.user import User, UserRole

class Permission(Enum):
    """权限枚举"""
    # 用户权限
    READ_OWN_PROFILE = "read_own_profile"
    UPDATE_OWN_PROFILE = "update_own_profile"
    CHANGE_OWN_PASSWORD = "change_own_password"
    VIEW_OWN_TRANSACTIONS = "view_own_transactions"
    VIEW_OWN_PAYMENT_ORDERS = "view_own_payment_orders"
    GENERATE_IMAGES = "generate_images"
    
    # 管理员权限
    MANAGE_USERS = "manage_users"  # 管理用户（启用/禁用、重置密码等）
    VIEW_ALL_USERS = "view_all_users"  # 查看所有用户列表
    VIEW_ALL_TRANSACTIONS = "view_all_transactions"  # 查看所有用户积分流水
    MANAGE_PAYMENT_ORDERS = "manage_payment_orders"  # 管理支付订单
    MANAGE_USER_ASSETS = "manage_user_assets"  # 管理用户资产（积分、会员等）
    VIEW_ADMIN_LOGS = "view_admin_logs"  # 查看管理员操作日志

class Role(Enum):
    """角色枚举"""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

# 角色权限映射
ROLE_PERMISSIONS = {
    Role.USER: {
        Permission.READ_OWN_PROFILE,
        Permission.UPDATE_OWN_PROFILE,
        Permission.CHANGE_OWN_PASSWORD,
        Permission.VIEW_OWN_TRANSACTIONS,
        Permission.VIEW_OWN_PAYMENT_ORDERS,
        Permission.GENERATE_IMAGES,
    },
    Role.ADMIN: {
        Permission.READ_OWN_PROFILE,
        Permission.UPDATE_OWN_PROFILE,
        Permission.CHANGE_OWN_PASSWORD,
        Permission.VIEW_OWN_TRANSACTIONS,
        Permission.VIEW_OWN_PAYMENT_ORDERS,
        Permission.GENERATE_IMAGES,
        Permission.MANAGE_USERS,
        Permission.VIEW_ALL_USERS,
        Permission.VIEW_ALL_TRANSACTIONS,
        Permission.MANAGE_PAYMENT_ORDERS,
        Permission.MANAGE_USER_ASSETS,
    },
    Role.SUPER_ADMIN: {
        # 超级管理员拥有所有权限
        Permission.READ_OWN_PROFILE,
        Permission.UPDATE_OWN_PROFILE,
        Permission.CHANGE_OWN_PASSWORD,
        Permission.VIEW_OWN_TRANSACTIONS,
        Permission.VIEW_OWN_PAYMENT_ORDERS,
        Permission.GENERATE_IMAGES,
        Permission.MANAGE_USERS,
        Permission.VIEW_ALL_USERS,
        Permission.VIEW_ALL_TRANSACTIONS,
        Permission.MANAGE_PAYMENT_ORDERS,
        Permission.MANAGE_USER_ASSETS,
        Permission.VIEW_ADMIN_LOGS,
    }
}

def get_user_role(user: User) -> Role:
    """获取用户角色"""
    # 兼容旧版本：如果用户没有role字段，则根据用户ID判断
    if not hasattr(user, 'role') or user.role is None:
        return Role.ADMIN if user.id == 1 else Role.USER
    
    # 新版本：根据role字段判断
    try:
        # 处理两种不同的枚举类型
        if hasattr(user.role, 'value'):
            # 如果是枚举类型，获取其值
            role_value = user.role.value
        else:
            # 如果是字符串，直接使用
            role_value = str(user.role)
        
        # 将值转换为大写，然后匹配Role枚举
        role_value_upper = role_value.upper()
        
        if role_value_upper == "USER":
            return Role.USER
        elif role_value_upper == "ADMIN":
            return Role.ADMIN
        elif role_value_upper == "SUPER_ADMIN":
            return Role.SUPER_ADMIN
        else:
            # 如果角色值无效，默认为普通用户
            return Role.USER
    except Exception:
        # 如果转换过程中出现任何异常，默认为普通用户
        return Role.USER

def has_permission(user: User, permission: Permission) -> bool:
    """检查用户是否具有指定权限"""
    user_role = get_user_role(user)
    return permission in ROLE_PERMISSIONS.get(user_role, set())

def has_any_permission(user: User, permissions: List[Permission]) -> bool:
    """检查用户是否具有任意一个指定权限"""
    user_role = get_user_role(user)
    user_permissions = ROLE_PERMISSIONS.get(user_role, set())
    return any(permission in user_permissions for permission in permissions)

def has_all_permissions(user: User, permissions: List[Permission]) -> bool:
    """检查用户是否具有所有指定权限"""
    user_role = get_user_role(user)
    user_permissions = ROLE_PERMISSIONS.get(user_role, set())
    return all(permission in user_permissions for permission in permissions)

def require_permission(permission: Permission):
    """权限检查依赖装饰器"""
    def permission_checker(current_user):
        # 这里不使用Depends，而是接受一个用户对象作为参数
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {permission.value}"
            )
        return current_user
    return permission_checker

def require_any_permission(permissions: List[Permission]):
    """需要任意一个权限的依赖装饰器"""
    def permission_checker(current_user):
        # 这里不使用Depends，而是接受一个用户对象作为参数
        if not has_any_permission(current_user, permissions):
            permission_names = [p.value for p in permissions]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要以下权限之一: {', '.join(permission_names)}"
            )
        return current_user
    return permission_checker

def require_all_permissions(permissions: List[Permission]):
    """需要所有权限的依赖装饰器"""
    def permission_checker(current_user):
        # 这里不使用Depends，而是接受一个用户对象作为参数
        if not has_all_permissions(current_user, permissions):
            permission_names = [p.value for p in permissions]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要以下所有权限: {', '.join(permission_names)}"
            )
        return current_user
    return permission_checker

# 常用权限检查函数
def check_user_permission(user: User, required_permissions: List[Permission]) -> bool:
    """检查用户是否具有所需权限"""
    return has_all_permissions(user, required_permissions)

def get_user_permissions(user: User) -> Set[Permission]:
    """获取用户的所有权限"""
    user_role = get_user_role(user)
    return ROLE_PERMISSIONS.get(user_role, set())

# 创建可以直接与FastAPI Depends一起使用的权限检查函数
def create_admin_permission_checker():
    """创建管理员权限检查函数"""
    async def admin_checker(current_user: User):
        from fastapi import HTTPException, status
        if not has_permission(current_user, Permission.MANAGE_USERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {Permission.MANAGE_USERS.value}"
            )
        return current_user
    return admin_checker

def create_payment_admin_permission_checker():
    """创建支付管理员权限检查函数"""
    async def payment_admin_checker(current_user: User):
        from fastapi import HTTPException, status
        if not has_permission(current_user, Permission.MANAGE_PAYMENT_ORDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {Permission.MANAGE_PAYMENT_ORDERS.value}"
            )
        return current_user
    return payment_admin_checker

def create_asset_admin_permission_checker():
    """创建资产管理员权限检查函数"""
    async def asset_admin_checker(current_user: User):
        from fastapi import HTTPException, status
        if not has_permission(current_user, Permission.MANAGE_USER_ASSETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {Permission.MANAGE_USER_ASSETS.value}"
            )
        return current_user
    return asset_admin_checker

def create_transaction_admin_permission_checker():
    """创建交易管理员权限检查函数"""
    async def transaction_admin_checker(current_user: User):
        from fastapi import HTTPException, status
        if not has_permission(current_user, Permission.VIEW_ALL_TRANSACTIONS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {Permission.VIEW_ALL_TRANSACTIONS.value}"
            )
        return current_user
    return transaction_admin_checker

def create_logs_admin_permission_checker():
    """创建日志管理员权限检查函数"""
    async def logs_admin_checker(current_user: User):
        from fastapi import HTTPException, status
        if not has_permission(current_user, Permission.VIEW_ADMIN_LOGS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {Permission.VIEW_ADMIN_LOGS.value}"
            )
        return current_user
    return logs_admin_checker

# 路径权限映射
PATH_PERMISSIONS = {
    # 管理员接口
    "/api/v1/admin": Permission.VIEW_ALL_TRANSACTIONS,
    "/api/v1/user-management": Permission.MANAGE_USERS,
    "/api/v1/user-profile/admin": Permission.MANAGE_USER_ASSETS,
    "/api/v1/payment-order": Permission.MANAGE_PAYMENT_ORDERS,
}

def get_required_permission_for_path(path: str) -> Optional[Permission]:
    """根据路径获取所需权限"""
    for path_prefix, permission in PATH_PERMISSIONS.items():
        if path.startswith(path_prefix):
            return permission
    return None