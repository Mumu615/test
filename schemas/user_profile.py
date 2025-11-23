from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from schemas.common import PaginatedResponse

class UserProfileBase(BaseModel):
    credits: int = 0
    free_model1_usages: int = 5
    free_model2_usages: int = 3
    membership_type: int = 0  # 0-普通, 1-高级, 2-专业
    membership_expires_at: Optional[datetime] = None

class UserProfileCreate(UserProfileBase):
    user_id: int

class UserProfileUpdate(BaseModel):
    credits: Optional[int] = None
    free_model1_usages: Optional[int] = None
    free_model2_usages: Optional[int] = None
    membership_type: Optional[int] = None
    membership_expires_at: Optional[datetime] = None

class UserProfileInDBBase(UserProfileBase):
    user_id: int
    updated_at: datetime

    class Config:
        from_attributes = True

class UserProfile(UserProfileInDBBase):
    pass

class CreditTransactionBase(BaseModel):
    amount: int
    balance_after: int
    source: str
    source_id: Optional[int] = None

class CreditTransactionCreate(CreditTransactionBase):
    user_id: int

class CreditTransactionInDBBase(CreditTransactionBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CreditTransaction(CreditTransactionInDBBase):
    pass

class CreditChange(BaseModel):
    """积分变动请求模型"""
    amount: int
    source: str
    source_id: Optional[int] = None
    description: Optional[str] = None

class MembershipUpgrade(BaseModel):
    """会员升级请求模型"""
    membership_type: int  # 0-普通, 1-高级, 2-专业
    days: int  # 升级天数

class MembershipStatus(BaseModel):
    """会员状态响应模型"""
    membership_type: int
    expires_at: Optional[datetime]
    is_valid: bool

# 管理员接口新增模型
class AdminCreditAdjustment(BaseModel):
    """管理员积分调整请求模型"""
    amount: int  # 正数为增加，负数为减少
    reason: str  # 调整原因
    description: Optional[str] = None  # 详细描述

class AdminMembershipUpdate(BaseModel):
    """管理员会员状态更新请求模型"""
    membership_type: int  # 0-普通, 1-高级, 2-专业
    days: Optional[int] = None  # 升级天数，如果为None则直接设置会员类型而不考虑到期时间
    expires_at: Optional[datetime] = None  # 直接设置到期时间

class UserProfileWithUsername(UserProfile):
    """包含用户名的用户档案模型"""
    username: Optional[str] = None
    email: Optional[str] = None

class TransactionSource(BaseModel):
    """积分来源/消耗类型模型"""
    source: str
    description: Optional[str] = None
    is_income: bool  # True为收入，False为支出

class UserAsset(BaseModel):
    """用户资产模型"""
    user_id: int
    username: str
    email: str
    credits: int
    membership_type: int
    membership_expires_at: Optional[datetime]
    free_model1_usages: int
    free_model2_usages: int
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 用户资产分页响应类型
UserAssetPaginatedResponse = PaginatedResponse[UserAsset]

class UserAssetUpdate(BaseModel):
    """用户资产更新请求模型"""
    credits: Optional[int] = None
    membership_type: Optional[int] = None
    membership_expires_at: Optional[datetime] = None
    free_model1_usages: Optional[int] = None
    free_model2_usages: Optional[int] = None

# 用户积分流水相关模型
class UserCreditTransactionFilter(BaseModel):
    """用户积分流水筛选条件"""
    source: Optional[str] = None  # 积分来源/消耗原因
    min_amount: Optional[int] = None  # 最小积分变动数量
    max_amount: Optional[int] = None  # 最大积分变动数量
    start_date: Optional[datetime] = None  # 开始日期
    end_date: Optional[datetime] = None  # 结束日期

class UserCreditTransaction(BaseModel):
    """用户积分流水响应模型"""
    id: int
    amount: int
    balance_after: int
    source: str
    source_id: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# 用户积分流水分页响应类型
UserCreditTransactionPaginatedResponse = PaginatedResponse[UserCreditTransaction]