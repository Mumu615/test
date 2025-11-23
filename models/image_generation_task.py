from sqlalchemy import Column, String, BigInteger, Text, Enum, DateTime, func, Index, JSON
from config.database import Base
import enum

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class ImageGenerationTask(Base):
    __tablename__ = "image_generation_tasks"
    
    id = Column(String(50), primary_key=True, comment="任务唯一ID，业务生成")
    user_id = Column(BigInteger, nullable=False, comment="提交任务的用户ID")
    model = Column(String(50), nullable=False, comment="使用的模型名称，如sdxl、midjourney等")
    prompt = Column(Text, nullable=False, comment="用户输入的生成提示词")
    size = Column(String(20), nullable=False, comment="生成图片尺寸，如1024x768")
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, comment="任务状态：待处理、处理中、成功、失败")
    image_url = Column(String(500), comment="生成图片的访问地址")
    error_message = Column(Text, comment="失败时的错误信息")
    created_at = Column(DateTime, default=func.now(), comment="任务创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="任务最后更新时间")
    credits_used = Column(BigInteger, nullable=False, comment="本次任务消耗的积分数")
    reference_images = Column(JSON, comment="用户上传的参考图信息，JSON格式")
    meta_data = Column(JSON, comment="扩展字段，存储其他业务元数据")
    
    # 添加索引和表选项
    __table_args__ = (
        Index("idx_image_tasks_user_id", "user_id"),
        Index("idx_image_tasks_status", "status"),
        Index("idx_image_tasks_created_at", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB", "mysql_comment": "图像生成任务表"}
    )