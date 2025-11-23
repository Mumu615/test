from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from schemas.common import PaginatedResponse
from schemas.user_profile import UserProfileBase

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    old_password: str
    new_password: str

class UserStatusUpdate(BaseModel):
    user_id: int
    status: int

class VerificationRequest(BaseModel):
    email: EmailStr
    purpose: str  # 'register' 或 'reset_password'

class RegisterWithCodeRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    code: str
    purpose: str = 'register'  # 默认为 'register'

class UserBase(BaseModel):
    username: str
    email: EmailStr

class User(UserBase):
    id: int
    status: int
    created_at: datetime

    class Config:
        from_attributes = True

class TokenData(BaseModel):
    user_id: Optional[int] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str
    purpose: str = 'reset_password'  # 默认为 'reset_password'

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

# 用户分页响应类型
UserPaginatedResponse = PaginatedResponse[User]

# 带有用户档案的完整用户信息
class UserWithProfile(User):
    """包含用户档案的完整用户信息"""
    profile: Optional[UserProfileBase] = None
