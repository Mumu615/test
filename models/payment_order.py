from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, func, Enum, DECIMAL
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class PaymentType(str, enum.Enum):
    """支付方式枚举"""
    alipay = "alipay"
    wxpay = "wxpay"

class PaymentOrderStatus(int, enum.Enum):
    """订单状态枚举"""
    PENDING = 0  # 待支付
    SUCCESS = 1  # 支付成功
    CLOSED = 2   # 已关闭

class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID，关联users表")
    out_trade_no = Column(String(64), unique=True, nullable=False, comment="商户订单号，系统内唯一")
    pid = Column(String(32), nullable=False, comment="商户ID")
    cid = Column(String(32), nullable=True, comment="支付渠道ID（可选）")
    type = Column(Enum(PaymentType), nullable=False, comment="支付方式: alipay-支付宝, wxpay-微信支付")
    notify_url = Column(String(255), nullable=False, comment="服务器异步通知地址")
    name = Column(String(127), nullable=False, comment="商品名称")
    money = Column(DECIMAL(10, 2), nullable=False, comment="订单金额，单位：元")
    clientip = Column(String(45), nullable=False, comment="用户发起支付的IP地址")
    param = Column(Text, nullable=True, comment="业务扩展参数，支付后原样返回，用于关联具体业务")
    sign = Column(String(32), nullable=False, comment="请求时的签名字符串")
    sign_type = Column(String(10), default="MD5", comment="签名类型")
    trade_no = Column(String(64), nullable=True, comment="ZPAY内部订单号（支付成功后返回）")
    status = Column(Integer, nullable=False, default=PaymentOrderStatus.PENDING, comment="订单状态: 0-待支付, 1-支付成功, 2-已关闭")
    trade_status = Column(String(32), nullable=True, comment="第三方支付状态，如TRADE_SUCCESS")
    buyer = Column(String(100), nullable=True, comment="支付者账号")
    addtime = Column(DateTime, nullable=True, comment="创建订单时间（来自ZPAY）")
    endtime = Column(DateTime, nullable=True, comment="完成交易时间（来自ZPAY）")
    unique_pending_flag = Column(Integer, nullable=False, default=0, comment="用于唯一索引的字段，待支付订单为0，其他为订单ID")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    # 添加索引和表选项
    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_engine": "InnoDB", "mysql_comment": "支付订单表"}
    )