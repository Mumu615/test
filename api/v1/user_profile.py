from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Request
from sqlalchemy.orm import Session
from typing import Optional
from dependencies import get_db, get_current_user, get_current_admin_user, require_permission
from schemas.user_profile import (
    UserProfileWithUsername,
    UserAsset, UserAssetPaginatedResponse, UserAssetUpdate
)
from crud.user_profile import (
    get_user_profile, get_user_profile_or_create,
    check_membership_valid, get_user_assets, update_user_assets_atomic
)
from crud.user import get_user_by_id
from crud.admin_operation_log import log_user_asset_update
from models.user import User
from models.user_profile import UserProfile as UserProfileModel
from core.permissions import Permission

# 用户路由
user_router = APIRouter(tags=["个人信息-资产管理"])

# 管理员路由
admin_router = APIRouter(prefix="/admin", tags=["管理员-用户档案管理"])

# 用户获取自己的资产信息
@user_router.get("/user/assets", response_model=UserAsset)
def get_my_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的资产信息"""
    # 获取用户档案
    profile = get_user_profile_or_create(db, current_user.id)
    
    # 构建返回数据
    asset_data = {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "credits": profile.credits,
        "membership_type": profile.membership_type,
        "membership_expires_at": profile.membership_expires_at,
        "free_model1_usages": profile.free_model1_usages,
        "free_model2_usages": profile.free_model2_usages,
        "updated_at": profile.updated_at
    }
    
    return UserAsset(**asset_data)

@admin_router.get("/profiles/{user_id}", response_model=UserProfileWithUsername)
def get_user_profile_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取单个用户档案详情"""
    # 获取用户档案和用户信息
    profile = db.query(UserProfileModel).filter(UserProfileModel.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="用户档案未找到")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户未找到")
    
    # 组合结果
    profile_dict = {
        "user_id": profile.user_id,
        "credits": profile.credits,
        "free_model1_usages": profile.free_model1_usages,
        "free_model2_usages": profile.free_model2_usages,
        "membership_type": profile.membership_type,
        "membership_expires_at": profile.membership_expires_at,
        "updated_at": profile.updated_at,
        "username": user.username,
        "email": user.email
    }
    
    return UserProfileWithUsername(**profile_dict)







@admin_router.get("/assets", response_model=UserAssetPaginatedResponse)
def get_user_assets_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    min_credits: Optional[int] = Query(None, ge=0, description="最小积分"),
    max_credits: Optional[int] = Query(None, ge=0, description="最大积分"),
    membership_type: Optional[int] = Query(None, ge=0, le=2, description="会员类型筛选: 0-普通, 1-高级, 2-专业"),
    username: Optional[str] = Query(None, description="用户名 (模糊匹配)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS))
):
    """获取用户资产列表（仅管理员）"""
    # 调用CRUD函数获取用户资产列表和总数
    assets, total = get_user_assets(
        db=db,
        page=page,
        size=size,
        min_credits=min_credits,
        max_credits=max_credits,
        membership_type=membership_type,
        username=username
    )
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    # 将查询结果转换为UserAsset模型
    asset_items = []
    for asset in assets:
        asset_dict = {
            "user_id": asset.user_id,
            "username": asset.username,
            "email": asset.email,
            "credits": asset.credits,
            "membership_type": asset.membership_type,
            "membership_expires_at": asset.membership_expires_at,
            "free_model1_usages": asset.free_model1_usages,
            "free_model2_usages": asset.free_model2_usages,
            "updated_at": asset.updated_at
        }
        asset_items.append(UserAsset(**asset_dict))
    
    # 构建分页响应
    return UserAssetPaginatedResponse(
        total=total,
        items=asset_items,
        page=page,
        size=size,
        pages=pages
    )

@admin_router.put("/assets/{user_id}", response_model=UserAsset)
def update_user_assets(
    user_id: int = Path(..., description="用户ID"),
    asset_update: UserAssetUpdate = ...,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS))
):
    """更新指定用户的资产信息（仅管理员）"""
    # 检查用户是否存在
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户档案是否存在
    profile = get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户档案不存在"
        )
    
    # 获取客户端IP和User-Agent
    client_ip = request.client.host if request else None
    user_agent = request.headers.get("user-agent") if request else None
    
    try:
        # 原子性更新用户资产
        updated_profile, before_data, after_data = update_user_assets_atomic(
            db, user_id, asset_update
        )
        
        if not updated_profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新用户资产失败"
            )
        
        # 记录审计日志
        log_user_asset_update(
            db=db,
            admin_id=current_user.id,
            target_user_id=user_id,
            before_data=before_data,
            after_data=after_data,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        # 提交事务（资产更新和审计日志记录一起提交）
        db.commit()
        
        # 构建返回数据
        asset_data = {
            "user_id": user_id,  # 直接使用user_id而不是从profile获取
            "username": user.username,
            "email": user.email,
            "credits": updated_profile.credits,
            "membership_type": updated_profile.membership_type,
            "membership_expires_at": updated_profile.membership_expires_at,
            "free_model1_usages": updated_profile.free_model1_usages,
            "free_model2_usages": updated_profile.free_model2_usages,
            "updated_at": updated_profile.updated_at
        }
        
        return UserAsset(**asset_data)
    except ValueError as e:
        # 数据验证错误
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # 其他错误
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户资产失败: {str(e)}"
        )