from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from schemas.common import PaginatedResponse, ResponseModel

class UserInfo(BaseModel):
    """用户信息模型"""
    id: int
    username: Optional[str] = None
    email: Optional[str] = None
    
    class Config:
        from_attributes = True

class PaymentOrderBase(BaseModel):
    """支付订单基础模型"""
    out_trade_no: str
    pid: str
    cid: Optional[str] = None
    type: str  # alipay 或 wxpay
    notify_url: str
    name: str
    money: Decimal
    clientip: str
    param: Optional[str] = None
    sign: str
    sign_type: str = "MD5"

class PaymentOrderCreate(PaymentOrderBase):
    """创建支付订单模型"""
    user_id: int
    status: int = 0  # 默认为待支付状态

class PaymentOrderUpdate(BaseModel):
    """更新支付订单模型"""
    trade_no: Optional[str] = None
    status: Optional[int] = None
    trade_status: Optional[str] = None
    buyer: Optional[str] = None
    addtime: Optional[datetime] = None
    endtime: Optional[datetime] = None

class PaymentOrderInDBBase(PaymentOrderBase):
    """数据库中的支付订单基础模型"""
    id: int
    user_id: int
    trade_no: Optional[str] = None
    status: int
    trade_status: Optional[str] = None
    buyer: Optional[str] = None
    addtime: Optional[datetime] = None
    endtime: Optional[datetime] = None
    unique_pending_flag: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PaymentOrder(PaymentOrderInDBBase):
    """支付订单响应模型"""
    user: Optional[UserInfo] = None

class PaymentOrderAdmin(PaymentOrder):
    """管理员支付订单响应模型，包含用户信息"""
    user: UserInfo

class PaymentOrderFilter(BaseModel):
    """支付订单筛选参数模型"""
    user_id: Optional[int] = None
    user_search: Optional[str] = None  # 按用户昵称/邮箱模糊搜索
    out_trade_no: Optional[str] = None  # 按商户订单号精确搜索
    trade_no: Optional[str] = None  # 按ZPAY订单号精确搜索
    type: Optional[str] = None  # 按支付方式筛选 (alipay/wxpay)
    status: Optional[int] = None  # 按订单状态筛选 (0/1/2)

# 管理员支付订单分页响应类型
PaymentOrderAdminPaginatedResponse = PaginatedResponse[PaymentOrderAdmin]

# 统一响应模型
class PaymentOrderListResponse(ResponseModel):
    """支付订单列表响应模型"""
    data: PaymentOrderAdminPaginatedResponse

# 创建支付订单请求模型
class PaymentRequest(BaseModel):
    """创建支付订单请求模型"""
    product_id: str = Field(..., description="产品ID，如 'credits_150', 'credits_1200', 'credits_2400', 'credits_5000', 'credits_16000'")
    type: str = Field(..., pattern="^(alipay|wxpay)$", description="支付方式: alipay-支付宝, wxpay-微信支付")
    clientip: str = Field(..., description="用户发起支付的IP地址")

# ZPAY支付响应模型
class ZPayResponse(BaseModel):
    """ZPAY支付接口响应模型"""
    model_config = {"extra": "allow"}  # 允许任意字段，防止序列化错误
    
    code: Union[int, str] = Field(..., description="响应码: 1-成功, 其他-失败")
    msg: Optional[str] = Field(None, description="响应消息")
    trade_no: Optional[str] = Field(None, description="支付订单号")
    O_id: Optional[str] = Field(None, description="ZPAY内部订单号")
    payurl: Optional[str] = Field(None, description="支付跳转url")
    qrcode: Optional[str] = Field(None, description="二维码链接")
    img: Optional[str] = Field(None, description="二维码图片地址")

# 创建支付订单响应模型
class PaymentResponse(BaseModel):
    """创建支付订单响应模型"""
    model_config = {"extra": "allow"}  # 允许任意字段，防止序列化错误
    
    code: Union[int, str] = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="支付信息")