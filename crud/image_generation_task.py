from sqlalchemy.orm import Session
from models.image_generation_task import ImageGenerationTask, TaskStatus
from models.user import User
from schemas.drawing import ImageGenerationTaskCreate, ImageGenerationTaskUpdate
from schemas.image_generation_admin import ImageGenerationTaskFilter
from typing import List, Optional, Tuple
import uuid
import json
from datetime import datetime

def generate_task_id() -> str:
    """生成唯一的任务ID"""
    return str(uuid.uuid4())

def create_image_generation_task(db: Session, task: ImageGenerationTaskCreate) -> ImageGenerationTask:
    """创建图片生成任务"""
    db_task = ImageGenerationTask(
        id=generate_task_id(),
        user_id=task.user_id,
        model=task.model,
        prompt=task.prompt,
        size=task.size,
        status=TaskStatus.PENDING,
        credits_used=task.credits_used,
        reference_images=task.reference_images,
        meta_data=task.meta_data
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_image_generation_task(db: Session, task_id: str) -> Optional[ImageGenerationTask]:
    """获取单个图片生成任务"""
    return db.query(ImageGenerationTask).filter(ImageGenerationTask.id == task_id).first()

def get_user_image_generation_tasks(
    db: Session, 
    user_id: int, 
    status: Optional[TaskStatus] = None,
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[ImageGenerationTask], int]:
    """获取用户的图片生成任务列表（分页）"""
    query = db.query(ImageGenerationTask).filter(ImageGenerationTask.user_id == user_id)
    
    if status:
        query = query.filter(ImageGenerationTask.status == status)
    
    total = query.count()
    tasks = query.order_by(ImageGenerationTask.created_at.desc()).offset(skip).limit(limit).all()
    
    return tasks, total

def update_image_generation_task(
    db: Session, 
    task_id: str, 
    task_update: ImageGenerationTaskUpdate
) -> Optional[ImageGenerationTask]:
    """更新图片生成任务"""
    db_task = db.query(ImageGenerationTask).filter(ImageGenerationTask.id == task_id).first()
    if not db_task:
        return None
    
    # 更新字段
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

def update_task_status(
    db: Session, 
    task_id: str, 
    status: TaskStatus,
    image_url: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[ImageGenerationTask]:
    """更新任务状态"""
    db_task = db.query(ImageGenerationTask).filter(ImageGenerationTask.id == task_id).first()
    if not db_task:
        return None
    
    db_task.status = status
    if image_url:
        db_task.image_url = image_url
    if error_message:
        db_task.error_message = error_message
    
    db.commit()
    db.refresh(db_task)
    return db_task

def get_pending_tasks(db: Session, limit: int = 50) -> List[ImageGenerationTask]:
    """获取待处理的任务列表"""
    return db.query(ImageGenerationTask).filter(
        ImageGenerationTask.status == TaskStatus.PENDING
    ).order_by(ImageGenerationTask.created_at.asc()).limit(limit).all()

def delete_image_generation_task(db: Session, task_id: str, user_id: int) -> bool:
    """删除用户的图片生成任务"""
    db_task = db.query(ImageGenerationTask).filter(
        ImageGenerationTask.id == task_id,
        ImageGenerationTask.user_id == user_id
    ).first()
    
    if not db_task:
        return False
    
    db.delete(db_task)
    db.commit()
    return True

# 管理员相关CRUD操作

def get_admin_image_generation_tasks(
    db: Session, 
    filters: ImageGenerationTaskFilter,
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[ImageGenerationTask], int]:
    """管理员获取图片生成任务列表（分页）"""
    query = db.query(ImageGenerationTask).join(User, ImageGenerationTask.user_id == User.id)
    
    # 应用筛选条件
    if filters.status:
        query = query.filter(ImageGenerationTask.status == filters.status)
    
    if filters.user_id:
        query = query.filter(ImageGenerationTask.user_id == filters.user_id)
    
    if filters.model:
        query = query.filter(ImageGenerationTask.model == filters.model)
    
    if filters.start_date:
        query = query.filter(ImageGenerationTask.created_at >= filters.start_date)
    
    if filters.end_date:
        query = query.filter(ImageGenerationTask.created_at <= filters.end_date)
    
    total = query.count()
    tasks = query.order_by(ImageGenerationTask.created_at.desc()).offset(skip).limit(limit).all()
    
    return tasks, total

def get_admin_image_generation_task(db: Session, task_id: str) -> Optional[ImageGenerationTask]:
    """管理员获取单个图片生成任务详情"""
    return db.query(ImageGenerationTask).filter(ImageGenerationTask.id == task_id).first()

def admin_delete_image_generation_task(db: Session, task_id: str) -> bool:
    """管理员删除图片生成任务"""
    db_task = db.query(ImageGenerationTask).filter(ImageGenerationTask.id == task_id).first()
    
    if not db_task:
        return False
    
    db.delete(db_task)
    db.commit()
    return True

def get_user_image_generation_history(
    db: Session, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[ImageGenerationTask], int]:
    """获取用户的图片生成历史记录（管理员视角）"""
    query = db.query(ImageGenerationTask).filter(ImageGenerationTask.user_id == user_id)
    
    total = query.count()
    tasks = query.order_by(ImageGenerationTask.created_at.desc()).offset(skip).limit(limit).all()
    
    return tasks, total

def get_user_image_generation_stats(db: Session, user_id: int) -> dict:
    """获取用户的图片生成统计信息"""
    total_tasks = db.query(ImageGenerationTask).filter(ImageGenerationTask.user_id == user_id).count()
    successful_tasks = db.query(ImageGenerationTask).filter(
        ImageGenerationTask.user_id == user_id,
        ImageGenerationTask.status == TaskStatus.SUCCESS
    ).count()
    failed_tasks = db.query(ImageGenerationTask).filter(
        ImageGenerationTask.user_id == user_id,
        ImageGenerationTask.status == TaskStatus.FAILED
    ).count()
    
    total_credits = db.query(ImageGenerationTask).filter(
        ImageGenerationTask.user_id == user_id
    ).with_entities(ImageGenerationTask.credits_used).all()
    
    total_credits_used = sum([credits[0] for credits in total_credits])
    
    success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return {
        "total_tasks": total_tasks,
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "total_credits_used": total_credits_used,
        "success_rate": success_rate
    }