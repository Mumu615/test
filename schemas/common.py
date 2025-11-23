# schemas/common.py
from pydantic import BaseModel
from typing import Any, Optional, Generic, TypeVar, List

T = TypeVar('T')

class ResponseModel(BaseModel):
    code: int
    message: str
    data: Any = None

class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应模型"""
    total: int
    items: List[T]
    page: int
    size: int
    pages: int

class SuccessResponse(BaseModel):
    """成功响应模型"""
    message: str
    data: Any = None

# 通用 success/fail（用于其他接口）
def success(data: Any = None, message: str = "操作成功") -> ResponseModel:
    return ResponseModel(code=200, message=message, data=data)

def fail(code: int = 400, message: str = "请求失败", data: Any = None) -> ResponseModel:
    return ResponseModel(code=code, message=message, data=data)

# ✅ 专用于上传接口的响应格式（符合你的 API 文档）
def api_success(
    url: str,
    data: dict = None,
    message: str = "上传成功"
) -> dict:
    return {
        "success": True,
        "url": url,
        "message": message,
        "data": data or {}
    }

def api_fail(message: str) -> dict:
    return {
        "success": False,
        "message": message
    }