from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, func, Index
from config.database import Base

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False, comment="积分变动数量，正数为增加，负数为消耗")
    balance_after = Column(Integer, nullable=False, comment="变动后的余额")
    source = Column(String(50), nullable=False, comment="积分来源/消耗原因，如: drawing_generation, purchase, daily_bonus")
    source_id = Column(BigInteger, nullable=True, comment="关联的业务ID")
    created_at = Column(DateTime, default=func.now())
    
    # 添加索引和表选项
    __table_args__ = (
        Index("idx_credit_transactions_user_id", "user_id"),
        Index("idx_credit_transactions_created_at", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB", "mysql_comment": "积分流水记录表"}
    )