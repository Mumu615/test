from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AdminOperationLogBase(BaseModel):
    operation_type: str
    operation_detail: Optional[str] = None
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AdminOperationLogCreate(AdminOperationLogBase):
    admin_id: int
    target_user_id: Optional[int] = None

class AdminOperationLogInDBBase(AdminOperationLogBase):
    id: int
    admin_id: int
    target_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AdminOperationLog(AdminOperationLogInDBBase):
    pass

class AdminOperationLogWithAdmin(AdminOperationLog):
    """包含管理员信息的操作日志"""
    admin_username: Optional[str] = None
    target_username: Optional[str] = None