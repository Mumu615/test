from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from models.image_generation_task import TaskStatus
from datetime import datetime

class DrawingRequest(BaseModel):
    prompt: str
    image_url: Optional[str] = None  # 用于图像编辑
    size: Optional[str] = None  # 图像尺寸，如 "1024x1024"
    aspect_ratio: Optional[str] = "1:1"  # 图像比例
    seed: Optional[int] = None  # 随机种子
    steps: Optional[int] = None  # 推理步数
    guidance: Optional[float] = None  # 引导强度
    negative_prompt: Optional[str] = None  # 负面提示词

class ImageInfo(BaseModel):
    url: str
    filename: str

class DrawingResponse(BaseModel):
    success: bool
    images: List[ImageInfo]
    message: str

class ReferenceImage(BaseModel):
    url: str
    name: Optional[str] = None

class ImageGenerationTaskCreate(BaseModel):
    user_id: int = Field(..., description="用户ID")
    model: str = Field(..., description="使用的模型名称")
    prompt: str = Field(..., min_length=1, max_length=2000, description="生成提示词")
    size: str = Field(..., description="图片尺寸，如1024x768或比例16:9")
    credits_used: int = Field(..., gt=0, description="消耗的积分数")
    reference_images: Optional[List[Dict[str, Any]]] = Field(default=[], description="参考图片列表")
    meta_data: Optional[Dict[str, Any]] = Field(default={}, description="扩展元数据")
    
    @validator('size')
    def validate_size(cls, v):
        """验证尺寸格式，支持'宽度x高度'或'宽:高'比例格式"""
        # 尝试解析为比例格式（宽:高）
        if ':' in v:
            try:
                ratio_parts = v.split(':')
                if len(ratio_parts) != 2:
                    raise ValueError("比例格式不正确，应为'宽:高'，如'16:9'")
                w, h = int(ratio_parts[0]), int(ratio_parts[1])
                if w <= 0 or h <= 0:
                    raise ValueError("比例值必须为正整数")
                # 比例格式验证通过
                return v
            except ValueError:
                raise ValueError("比例格式不正确，应为'宽:高'，如'16:9'")
        
        # 尝试解析为尺寸格式（宽度x高度）
        if 'x' in v:
            try:
                width, height = v.split('x')
                w, h = int(width), int(height)
                if w < 64 or h < 64 or w > 4096 or h > 4096:
                    raise ValueError("图片尺寸必须在64x64到4096x4096之间")
                # 尺寸格式验证通过
                return v
            except ValueError:
                raise ValueError("尺寸格式不正确，应为'宽度x高度'，如'1024x768'")
        
        # 既不是比例也不是尺寸格式
        raise ValueError("尺寸格式不正确，应为'宽度x高度'（如1024x768）或'宽:高'比例（如16:9）")

class ImageGenerationTaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None

class ImageGenerationTaskResponse(BaseModel):
    id: str
    user_id: int
    model: str
    prompt: str
    size: str
    status: TaskStatus
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    credits_used: int
    reference_images: Optional[List[Dict[str, Any]]] = None
    meta_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class ImageGenerationRequest(BaseModel):
    model: str = Field(..., description="使用的模型名称")
    prompt: str = Field(..., min_length=1, max_length=2000, description="生成提示词")
    size: Optional[str] = Field(None, description="图片尺寸，如1024x768（仅支持像素尺寸的模型可用）")
    aspect_ratio: str = Field(..., description="图片比例，如1:1, 16:9等（必填）")
    reference_images: Optional[List[str]] = Field(default=[], description="参考图片URL列表")
    
    @validator('size')
    def validate_size(cls, v, values):
        """验证尺寸格式"""
        if v is not None:
            try:
                width, height = v.split('x')
                w, h = int(width), int(height)
                if w < 64 or h < 64 or w > 4096 or h > 4096:
                    raise ValueError("图片尺寸必须在64x64到4096x4096之间")
            except ValueError:
                raise ValueError("尺寸格式不正确，应为'宽度x高度'，如'1024x768'")
        return v
    
    @validator('aspect_ratio')
    def validate_aspect_ratio(cls, v, values):
        """验证比例格式"""
        if v is not None:
            try:
                ratio_parts = v.split(':')
                if len(ratio_parts) != 2:
                    raise ValueError("比例格式不正确，应为'宽:高'，如'16:9'")
                w, h = int(ratio_parts[0]), int(ratio_parts[1])
                if w <= 0 or h <= 0:
                    raise ValueError("比例值必须为正整数")
            except ValueError:
                raise ValueError("比例格式不正确，应为'宽:高'，如'16:9'")
        return v

class ImageGenerationResponse(BaseModel):
    task_id: str
    status: str
    message: str

class WebhookPayload(BaseModel):
    task_id: str
    status: TaskStatus
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
