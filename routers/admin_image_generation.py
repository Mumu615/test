from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from dependencies import get_db, get_current_user
from core.permissions import require_permission, Permission, require_any_permission
from models.user import User
from schemas.image_generation_admin import (
    ImageGenerationTaskFilter,
    ImageGenerationTaskAdmin,
    ImageGenerationTaskDetail,
    UserImageGenerationHistory,
    UserImageGenerationStats,
    ImageGenerationTaskPaginatedResponse,
    UserImageGenerationHistoryPaginatedResponse
)
from services.image_generation_admin import ImageGenerationAdminService
from schemas.common import SuccessResponse

router = APIRouter()

@router.get("/tasks", response_model=ImageGenerationTaskPaginatedResponse)
async def get_image_generation_tasks(
    status: Optional[str] = Query(None, description="任务状态"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    model: Optional[str] = Query(None, description="模型名称"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取图片生成任务列表
    
    需要权限: MANAGE_USERS 或 VIEW_ALL_TRANSACTIONS
    """
    # 权限检查
    require_any_permission([Permission.MANAGE_USERS, Permission.VIEW_ALL_TRANSACTIONS])(current_user)
    
    # 构建筛选条件
    filters = ImageGenerationTaskFilter(
        status=status,
        user_id=user_id,
        model=model,
        start_date=start_date,
        end_date=end_date
    )
    
    # 获取任务列表
    tasks, total = ImageGenerationAdminService.get_tasks(db, filters, page, size)
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    return ImageGenerationTaskPaginatedResponse(
        total=total,
        items=tasks,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/tasks/{task_id}", response_model=ImageGenerationTaskDetail)
async def get_image_generation_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取图片生成任务详情
    
    需要权限: MANAGE_USERS 或 VIEW_ALL_TRANSACTIONS
    """
    # 权限检查
    require_any_permission([Permission.MANAGE_USERS, Permission.VIEW_ALL_TRANSACTIONS])(current_user)
    
    # 获取任务详情
    return ImageGenerationAdminService.get_task_detail(db, task_id)

@router.delete("/tasks/{task_id}", response_model=SuccessResponse)
async def delete_image_generation_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除图片生成任务
    
    需要权限: MANAGE_USERS
    """
    # 权限检查
    require_permission(Permission.MANAGE_USERS)(current_user)
    
    # 删除任务
    success = ImageGenerationAdminService.delete_task(db, task_id, current_user.id)
    
    if success:
        return SuccessResponse(message="图片生成任务删除成功")
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除图片生成任务失败"
        )

@router.get("/users/{user_id}/history", response_model=UserImageGenerationHistoryPaginatedResponse)
async def get_user_image_generation_history(
    user_id: int,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户图片生成历史
    
    需要权限: MANAGE_USERS 或 VIEW_ALL_TRANSACTIONS
    """
    # 权限检查
    require_any_permission([Permission.MANAGE_USERS, Permission.VIEW_ALL_TRANSACTIONS])(current_user)
    
    # 获取用户历史记录
    history, total = ImageGenerationAdminService.get_user_history(db, user_id, page, size)
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    return UserImageGenerationHistoryPaginatedResponse(
        total=total,
        items=history,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/users/{user_id}/stats", response_model=UserImageGenerationStats)
async def get_user_image_generation_stats(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户图片生成统计
    
    需要权限: MANAGE_USERS 或 VIEW_ALL_TRANSACTIONS
    """
    # 权限检查
    require_any_permission([Permission.MANAGE_USERS, Permission.VIEW_ALL_TRANSACTIONS])(current_user)
    
    # 获取用户统计信息
    return ImageGenerationAdminService.get_user_stats(db, user_id)