from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey, func
from config.database import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    credits = Column(Integer, default=0, nullable=False, comment="当前积分余额")
    free_model1_usages = Column(Integer, default=5, nullable=False, comment="模型一的剩余免费使用次数")
    free_model2_usages = Column(Integer, default=3, nullable=False, comment="模型二的剩余免费使用次数")
    membership_type = Column(Integer, default=0, nullable=False, comment="会员类型: 0-普通, 1-高级, 2-专业")
    membership_expires_at = Column(DateTime, nullable=True, comment="会员到期时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 添加索引和表选项
    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB", "mysql_comment": "用户档案与权益表"}
    )