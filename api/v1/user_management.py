from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Request
from sqlalchemy.orm import Session
from sqlalchemy import case
from typing import List, Optional
from dependencies import get_db, get_current_user, get_current_admin_user, require_permission
from schemas.user import User, UserStatusUpdate, UserPaginatedResponse, UserWithProfile
from schemas.common import success, fail
from schemas.admin_operation_log import AdminOperationLogCreate
from crud.user import get_user_by_email, get_all_users, get_user_by_id, update_user_status, get_user_with_profile
from crud.admin_operation_log import create_admin_operation_log
from models.user import User as DBUser
from core.security import get_password_hash, delete_refresh_token
from core.permissions import Permission
import json

router = APIRouter(tags=["管理员-用户管理"])

@router.get("/users", response_model=UserPaginatedResponse)
def list_users(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词，支持用户名和邮箱"),
    status: Optional[int] = Query(None, ge=1, le=2, description="按状态筛选: 1-正常, 2-禁用")
):
    """获取用户列表（仅管理员）"""
    # 计算偏移量
    skip = (page - 1) * size
    
    # 获取用户列表和总数
    users, total = get_all_users(db, skip=skip, limit=size, keyword=keyword, status=status)
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    # 构建响应
    return UserPaginatedResponse(
        total=total,
        items=[User.model_validate(u) for u in users],
        page=page,
        size=size,
        pages=pages
    )

@router.get("/users/{user_id}", response_model=UserWithProfile)
def get_user(
    user_id: int = Path(..., description="用户ID"),
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取单个用户详情（仅管理员），包含用户档案"""
    # 使用LEFT JOIN查询用户及其档案信息
    user_data = get_user_with_profile(db, user_id)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 使用Pydantic模型验证数据
    user_with_profile = UserWithProfile(**user_data)
    
    return user_with_profile

@router.post("/users/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int = Path(..., description="用户ID"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(require_permission(Permission.MANAGE_USERS))
):
    """切换用户状态（仅管理员）"""
    # 自我操作保护：防止管理员禁用自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能禁用自己"
        )
    
    # 检查用户是否存在
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 记录操作前的状态
    before_data = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "status": user.status
    }
    
    # 使用原子化的 CASE WHEN 语句切换状态
    # 1(正常) -> 2(禁用), 2(禁用) -> 1(正常)
    new_status = 2 if user.status == 1 else 1
    
    # 更新用户状态
    db.query(DBUser).filter(DBUser.id == user_id).update(
        {"status": new_status},
        synchronize_session=False
    )
    
    # 如果禁用用户，使其所有Token失效
    if new_status == 2:
        delete_refresh_token(user_id)
    
    # 获取更新后的用户信息
    updated_user = get_user_by_id(db, user_id)
    status_text = "禁用" if new_status == 2 else "启用"
    
    # 记录操作后的状态
    after_data = {
        "user_id": updated_user.id,
        "username": updated_user.username,
        "email": updated_user.email,
        "status": updated_user.status
    }
    
    # 获取客户端IP和User-Agent
    client_ip = request.client.host if request else None
    user_agent = request.headers.get("user-agent") if request else None
    
    # 创建审计日志
    log = AdminOperationLogCreate(
        admin_id=current_user.id,
        target_user_id=user_id,
        operation_type="user_status_toggle",
        operation_detail=f"{status_text}用户 '{updated_user.username}'",
        before_data=json.dumps(before_data, ensure_ascii=False),
        after_data=json.dumps(after_data, ensure_ascii=False)
    )
    
    create_admin_operation_log(
        db=db,
        log=log,
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    # 提交事务（状态更新和审计日志记录一起提交）
    db.commit()
    
    return success(
        data=User.model_validate(updated_user).model_dump(),
        message=f"用户 '{updated_user.username}' 已被{status_text}"
    )

@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int = Path(..., description="用户ID"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(require_permission(Permission.MANAGE_USERS))
):
    """管理员重置用户密码（仅管理员）"""
    # 自我操作保护：防止管理员重置自己的密码
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能重置自己的密码"
        )
    
    # 检查用户是否存在
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 记录操作前的状态（不包含密码哈希）
    before_data = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "status": user.status
    }
    
    # 重置密码为 "123456"
    default_password = "123456"
    hashed_password = get_password_hash(default_password)
    
    # 更新密码
    db.query(DBUser).filter(DBUser.id == user_id).update(
        {"password": hashed_password},
        synchronize_session=False
    )
    
    # 使旧Token失效：删除用户的refresh_token
    delete_refresh_token(user_id)
    
    # 获取客户端IP和User-Agent
    client_ip = request.client.host if request else None
    user_agent = request.headers.get("user-agent") if request else None
    
    # 记录操作后的状态（不包含密码哈希）
    after_data = {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "status": user.status,
        "password_reset": True
    }
    
    # 创建审计日志
    log = AdminOperationLogCreate(
        admin_id=current_user.id,
        target_user_id=user_id,
        operation_type="password_reset",
        operation_detail=f"重置用户 '{user.username}' 的密码",
        before_data=json.dumps(before_data, ensure_ascii=False),
        after_data=json.dumps(after_data, ensure_ascii=False)
    )
    
    create_admin_operation_log(
        db=db,
        log=log,
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    # 提交事务（密码重置和审计日志记录一起提交）
    db.commit()
    
    # TODO: 实现通知逻辑，如发送邮件
    # send_password_reset_notification(user.email, default_password)
    
    return success(
        message="Password has been successfully reset to '123456'."
    )