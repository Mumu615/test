from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional, Tuple, List
from models.image_generation_task import ImageGenerationTask, TaskStatus
from models.user import User
from crud.image_generation_task import (
    get_admin_image_generation_tasks,
    get_admin_image_generation_task,
    admin_delete_image_generation_task,
    get_user_image_generation_history,
    get_user_image_generation_stats
)
from schemas.image_generation_admin import (
    ImageGenerationTaskFilter,
    ImageGenerationTaskAdmin,
    ImageGenerationTaskDetail,
    UserImageGenerationHistory,
    UserImageGenerationStats
)
from core.permissions import Permission
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ImageGenerationAdminService:
    """图片生成任务管理服务"""
    
    @staticmethod
    def get_tasks(
        db: Session,
        filters: ImageGenerationTaskFilter,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[ImageGenerationTaskAdmin], int]:
        """获取图片生成任务列表"""
        skip = (page - 1) * size
        tasks, total = get_admin_image_generation_tasks(db, filters, skip, size)
        
        # 转换为管理员视图模型
        admin_tasks = []
        for task in tasks:
            # 获取用户信息
            user = db.query(User).filter(User.id == task.user_id).first()
            username = user.username if user else None
            user_email = user.email if user else None
            
            admin_task = ImageGenerationTaskAdmin(
                id=task.id,
                user_id=task.user_id,
                username=username,
                user_email=user_email,
                model=task.model,
                prompt=task.prompt,
                size=task.size,
                status=task.status,
                image_url=task.image_url,
                error_message=task.error_message,
                created_at=task.created_at,
                updated_at=task.updated_at,
                credits_used=task.credits_used,
                reference_images=task.reference_images,
                meta_data=task.meta_data
            )
            admin_tasks.append(admin_task)
        
        return admin_tasks, total
    
    @staticmethod
    def get_task_detail(db: Session, task_id: str) -> ImageGenerationTaskDetail:
        """获取图片生成任务详情"""
        task = get_admin_image_generation_task(db, task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="图片生成任务不存在"
            )
        
        # 获取用户信息
        user = db.query(User).filter(User.id == task.user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务关联的用户不存在"
            )
        
        return ImageGenerationTaskDetail(
            id=task.id,
            user_id=task.user_id,
            username=user.username,
            user_email=user.email,
            model=task.model,
            prompt=task.prompt,
            size=task.size,
            status=task.status,
            image_url=task.image_url,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
            credits_used=task.credits_used,
            reference_images=task.reference_images,
            meta_data=task.meta_data
        )
    
    @staticmethod
    def delete_task(db: Session, task_id: str, admin_id: int) -> bool:
        """删除图片生成任务"""
        task = get_admin_image_generation_task(db, task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="图片生成任务不存在"
            )
        
        # 记录任务信息用于日志
        task_info = {
            "task_id": task.id,
            "user_id": task.user_id,
            "model": task.model,
            "status": task.status.value,
            "admin_id": admin_id
        }
        
        # 如果任务有图片文件，尝试删除
        if task.image_url:
            try:
                # 这里可以根据实际的图片存储路径来删除文件
                # 例如: os.remove(task.image_url)
                logger.info(f"删除任务图片文件: {task.image_url}")
            except Exception as e:
                logger.warning(f"删除任务图片文件失败: {str(e)}")
        
        # 删除任务记录
        success = admin_delete_image_generation_task(db, task_id)
        
        if success:
            logger.info(f"管理员 {admin_id} 删除了图片生成任务: {task_info}")
            return True
        else:
            logger.error(f"删除图片生成任务失败: {task_id}")
            return False
    
    @staticmethod
    def get_user_history(
        db: Session,
        user_id: int,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[UserImageGenerationHistory], int]:
        """获取用户图片生成历史"""
        # 检查用户是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        skip = (page - 1) * size
        tasks, total = get_user_image_generation_history(db, user_id, skip, size)
        
        # 转换为历史记录模型
        history = []
        for task in tasks:
            history_item = UserImageGenerationHistory(
                id=task.id,
                model=task.model,
                prompt=task.prompt,
                size=task.size,
                status=task.status,
                image_url=task.image_url,
                error_message=task.error_message,
                created_at=task.created_at,
                updated_at=task.updated_at,
                credits_used=task.credits_used
            )
            history.append(history_item)
        
        return history, total
    
    @staticmethod
    def get_user_stats(db: Session, user_id: int) -> UserImageGenerationStats:
        """获取用户图片生成统计"""
        # 检查用户是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        stats_data = get_user_image_generation_stats(db, user_id)
        
        return UserImageGenerationStats(
            total_tasks=stats_data["total_tasks"],
            successful_tasks=stats_data["successful_tasks"],
            failed_tasks=stats_data["failed_tasks"],
            total_credits_used=stats_data["total_credits_used"],
            success_rate=stats_data["success_rate"]
        )