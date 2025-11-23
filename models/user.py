from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Enum, func
from config.database import Base
import enum

class UserRole(enum.Enum):
    """用户角色枚举"""
    USER = "USER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=func.now())
