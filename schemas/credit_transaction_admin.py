from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from schemas.common import PaginatedResponse

class CreditTransactionAdminBase(BaseModel):
    """管理员积分流水基础模型"""
    amount: int
    balance_after: int
    source: str
    source_id: Optional[int] = None

class CreditTransactionAdmin(CreditTransactionAdminBase):
    """管理员积分流水响应模型，包含用户信息"""
    id: int
    user_id: int
    username: str
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CreditTransactionFilter(BaseModel):
    """积分流水筛选参数模型"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

# 管理员积分流水分页响应类型
CreditTransactionAdminPaginatedResponse = PaginatedResponse[CreditTransactionAdmin]