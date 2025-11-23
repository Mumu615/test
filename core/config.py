# core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 1天
    DEBUG: bool = False
    
    # 邮件
    EMAIL_ADDRESS: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: int = 587
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # ImgBB API
    IMGBB_API_KEY: str
    
    # ZPAY配置
    ZPAY_API_URL: Optional[str] = None
    ZPAY_MERCHANT_ID: Optional[str] = None
    ZPAY_API_KEY: Optional[str] = None
    
    # 服务器配置
    SERVER_HOST: str = "http://75.127.89.76"
    SERVER_PORT: int = 8880
    SERVER_DOMAIN: Optional[str] = None  # 如果设置，则使用此域名，否则使用 HOST:PORT

    class Config:
        env_file = ".env"
        extra = "allow"  # 允许额外的配置项

settings = Settings()