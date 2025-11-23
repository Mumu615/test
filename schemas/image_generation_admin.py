from pydantic import BaseModel, Field
from typing import Optional, List
from models.image_generation_task import TaskStatus
from datetime import datetime
from schemas.common import PaginatedResponse

# 图片生成任务管理相关Schema

class ImageGenerationTaskFilter(BaseModel):
    """图片生成任务筛选条件"""
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    user_id: Optional[int] = Field(None, description="用户ID")
    model: Optional[str] = Field(None, description="模型名称")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")

class ImageGenerationTaskAdmin(BaseModel):
    """管理员视角的图片生成任务信息"""
    id: str
    user_id: int
    username: Optional[str] = None
    user_email: Optional[str] = None
    model: str
    prompt: str
    size: str
    status: TaskStatus
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    credits_used: int
    reference_images: Optional[List[dict]] = None
    meta_data: Optional[dict] = None
    
    class Config:
        from_attributes = True

class ImageGenerationTaskDetail(BaseModel):
    """图片生成任务详情"""
    id: str
    user_id: int
    username: str
    user_email: str
    model: str
    prompt: str
    size: str
    status: TaskStatus
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    credits_used: int
    reference_images: Optional[List[dict]] = None
    meta_data: Optional[dict] = None
    
    class Config:
        from_attributes = True

class UserImageGenerationHistory(BaseModel):
    """用户图片生成历史"""
    id: str
    model: str
    prompt: str
    size: str
    status: TaskStatus
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    credits_used: int
    
    class Config:
        from_attributes = True

class UserImageGenerationStats(BaseModel):
    """用户图片生成统计"""
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    total_credits_used: int
    success_rate: float

# 分页响应类型
ImageGenerationTaskPaginatedResponse = PaginatedResponse[ImageGenerationTaskAdmin]
UserImageGenerationHistoryPaginatedResponse = PaginatedResponse[UserImageGenerationHistory]