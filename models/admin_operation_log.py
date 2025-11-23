from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from config.database import Base

class AdminOperationLog(Base):
    __tablename__ = "admin_operation_logs"
    
    id = Column(BigInteger, primary_key=True, index=True)
    admin_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    operation_type = Column(String(100), nullable=False)
    operation_detail = Column(Text, nullable=True)
    before_data = Column(Text, nullable=True)
    after_data = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # 关系
    admin = relationship("User", foreign_keys=[admin_id])
    target_user = relationship("User", foreign_keys=[target_user_id])