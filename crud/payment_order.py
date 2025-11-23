from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from models.payment_order import PaymentOrder
from models.user import User
from schemas.payment_order import PaymentOrderCreate, PaymentOrderUpdate, PaymentOrderFilter
from typing import List, Optional, Tuple
from core.payment_utils import generate_order_no, generate_md5_sign

def get_payment_order_by_id(db: Session, order_id: int):
    """根据ID获取支付订单"""
    return db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()

def get_payment_order_by_out_trade_no(db: Session, out_trade_no: str):
    """根据商户订单号获取支付订单"""
    return db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == out_trade_no).first()

def get_payment_order_by_trade_no(db: Session, trade_no: str):
    """根据ZPAY订单号获取支付订单"""
    return db.query(PaymentOrder).filter(PaymentOrder.trade_no == trade_no).first()

def create_payment_order(db: Session, order: PaymentOrderCreate):
    """创建支付订单"""
    # 导入PaymentOrderStatus枚举
    from models.payment_order import PaymentOrderStatus
    
    # 设置unique_pending_flag
    unique_pending_flag = 0 if order.status == PaymentOrderStatus.PENDING.value else None
    
    db_order = PaymentOrder(
        user_id=order.user_id,
        out_trade_no=order.out_trade_no,
        pid=order.pid,
        cid=order.cid,
        type=order.type,
        notify_url=order.notify_url,
        name=order.name,
        money=order.money,
        clientip=order.clientip,
        param=order.param,
        sign=order.sign,
        sign_type=order.sign_type,
        status=order.status,  # 添加status字段
        unique_pending_flag=unique_pending_flag  # 添加unique_pending_flag字段
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # 如果不是待支付状态，需要更新unique_pending_flag为订单ID
    if order.status != PaymentOrderStatus.PENDING.value:
        db_order.unique_pending_flag = db_order.id
        db.commit()
        db.refresh(db_order)
    
    return db_order

def update_payment_order(db: Session, order_id: int, order_update: PaymentOrderUpdate, commit: bool = True):
    """更新支付订单"""
    # 导入PaymentOrderStatus枚举
    from models.payment_order import PaymentOrderStatus
    
    db_order = get_payment_order_by_id(db, order_id)
    if not db_order:
        return None
    
    # 记录原始状态
    original_status = db_order.status
    
    # 处理Pydantic模型和字典两种情况
    if hasattr(order_update, 'dict'):
        update_data = order_update.dict(exclude_unset=True)
    else:
        # 如果是字典，直接使用
        update_data = order_update
    
    for field, value in update_data.items():
        setattr(db_order, field, value)
    
    # 如果状态发生变化，更新unique_pending_flag
    if "status" in update_data and update_data["status"] != original_status:
        new_status = update_data["status"]
        if new_status == PaymentOrderStatus.PENDING.value:
            db_order.unique_pending_flag = 0
        else:
            db_order.unique_pending_flag = db_order.id
    
    # 只有在commit参数为True时才提交，以便在事务上下文中使用
    if commit:
        db.commit()
        db.refresh(db_order)
    
    return db_order

def get_admin_payment_orders(
    db: Session, 
    filters: PaymentOrderFilter,
    skip: int = 0, 
    limit: int = 20
) -> Tuple[List[PaymentOrder], int]:
    """
    管理员获取支付订单列表（分页）
    
    Args:
        db: 数据库会话
        filters: 筛选条件
        skip: 跳过记录数
        limit: 返回记录数
        
    Returns:
        Tuple[List[PaymentOrder], int]: 支付订单列表和总数
    """
    # 构建基础查询，关联用户表
    query = db.query(PaymentOrder, User).join(User, PaymentOrder.user_id == User.id)
    
    # 应用筛选条件
    if filters.user_id:
        query = query.filter(PaymentOrder.user_id == filters.user_id)
    
    if filters.user_search:
        # 按用户昵称/邮箱模糊搜索
        search_filter = or_(
            func.lower(User.username).contains(func.lower(filters.user_search)),
            func.lower(User.email).contains(func.lower(filters.user_search))
        )
        query = query.filter(search_filter)
    
    if filters.out_trade_no:
        query = query.filter(PaymentOrder.out_trade_no == filters.out_trade_no)
    
    if filters.trade_no:
        query = query.filter(PaymentOrder.trade_no == filters.trade_no)
    
    if filters.type:
        query = query.filter(PaymentOrder.type == filters.type)
    
    if filters.status is not None:
        query = query.filter(PaymentOrder.status == filters.status)
    
    # 获取总数（使用相同的筛选条件）
    total = query.count()
    
    # 应用排序和分页
    orders = query.order_by(PaymentOrder.created_at.desc()).offset(skip).limit(limit).all()
    
    return orders, total

def get_user_payment_orders(
    db: Session, 
    user_id: int,
    skip: int = 0, 
    limit: int = 20
) -> Tuple[List[PaymentOrder], int]:
    """
    获取用户支付订单列表（分页）
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        skip: 跳过记录数
        limit: 返回记录数
        
    Returns:
        Tuple[List[PaymentOrder], int]: 支付订单列表和总数
    """
    # 构建基础查询
    query = db.query(PaymentOrder).filter(PaymentOrder.user_id == user_id)
    
    # 获取总数
    total = query.count()
    
    # 应用排序和分页
    orders = query.order_by(PaymentOrder.created_at.desc()).offset(skip).limit(limit).all()
    
    return orders, total

def count_payment_orders_by_status(db: Session, status: int) -> int:
    """统计指定状态的订单数量"""
    return db.query(PaymentOrder).filter(PaymentOrder.status == status).count()

def get_payment_order_statistics(db: Session) -> dict:
    """获取支付订单统计信息"""
    total_orders = db.query(PaymentOrder).count()
    pending_orders = count_payment_orders_by_status(db, 0)
    success_orders = count_payment_orders_by_status(db, 1)
    closed_orders = count_payment_orders_by_status(db, 2)
    
    # 计算总交易额（仅成功订单）
    total_amount = db.query(func.sum(PaymentOrder.money)).filter(PaymentOrder.status == 1).scalar() or 0
    
    return {
        "total": total_orders,
        "pending": pending_orders,
        "success": success_orders,
        "closed": closed_orders,
        "totalAmount": float(total_amount)
    }

def delete_pending_payment_orders(db: Session) -> int:
    """
    删除所有待支付状态的订单
    
    Args:
        db: 数据库会话
        
    Returns:
        int: 删除的订单数量
    """
    # 导入PaymentOrderStatus枚举
    from models.payment_order import PaymentOrderStatus
    
    # 查询所有待支付状态的订单
    pending_orders = db.query(PaymentOrder).filter(
        PaymentOrder.status == PaymentOrderStatus.PENDING.value
    ).all()
    
    # 记录要删除的订单数量
    deleted_count = len(pending_orders)
    
    # 删除这些订单
    for order in pending_orders:
        db.delete(order)
    
    # 提交更改
    db.commit()
    
    return deleted_count

def create_payment_order_with_sign(
    db: Session, 
    user_id: int,
    name: str,
    money: float,
    payment_type: str,
    clientip: str,
    merchant_id: str,
    notify_url: str,
    merchant_key: str,
    param: Optional[str] = None
) -> PaymentOrder:
    """
    创建支付订单并生成签名
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        name: 商品名称
        money: 订单金额
        payment_type: 支付方式
        clientip: 客户端IP
        merchant_id: 商户ID
        notify_url: 异步通知地址
        merchant_key: 商户密钥
        param: 业务扩展参数
        
    Returns:
        PaymentOrder: 创建的支付订单
        
    Raises:
        ValueError: 如果用户在5分钟内已经创建了支付订单
    """
    # 导入PaymentOrderStatus枚举
    from models.payment_order import PaymentOrderStatus
    
    try:
        # 检查用户在5分钟内是否已经创建了支付订单
        from datetime import datetime, timedelta
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        
        recent_order = db.query(PaymentOrder).filter(
            PaymentOrder.user_id == user_id,
            PaymentOrder.created_at >= five_minutes_ago,
            PaymentOrder.status == PaymentOrderStatus.PENDING.value  # 只检查待支付状态的订单
        ).first()
        
        if recent_order:
            # 计算剩余等待时间
            elapsed_seconds = (datetime.now() - recent_order.created_at).total_seconds()
            remaining_seconds = 300 - int(elapsed_seconds)  # 5分钟 = 300秒
            remaining_minutes = remaining_seconds // 60
            remaining_secs = remaining_seconds % 60
            
            raise ValueError(f"您有待支付订单，需在历史订单中取消订单重新购买。订单号: {recent_order.out_trade_no}")
        
        # 生成唯一的商户订单号
        out_trade_no = generate_order_no()
        
        # 准备签名参数
        sign_params = {
            'pid': merchant_id,
            'type': payment_type,
            'out_trade_no': out_trade_no,
            'notify_url': notify_url,
            'name': name,
            'money': str(money),
            'clientip': clientip
        }
        
        # 如果有业务参数，添加到签名参数中
        if param:
            sign_params['param'] = param
        
        # 生成签名
        sign = generate_md5_sign(sign_params, merchant_key)
        
        # 创建订单对象
        order = PaymentOrderCreate(
            user_id=user_id,
            out_trade_no=out_trade_no,
            pid=merchant_id,
            type=payment_type,
            notify_url=notify_url,
            name=name,
            money=money,
            clientip=clientip,
            param=param,
            sign=sign,
            sign_type="MD5",  # 添加签名类型
            status=PaymentOrderStatus.PENDING.value  # 使用枚举的整数值
        )
        
        # 保存到数据库
        result = create_payment_order(db, order)
        return result
        
    except ValueError as ve:
        # 重新抛出业务异常
        raise ve
    except Exception as e:
        # 捕获数据库唯一约束违反错误，处理并发请求情况
        db.rollback()
        # 检查是否是唯一约束违反错误
        error_msg = str(e).lower()
        if "duplicate" in error_msg or "unique" in error_msg:
            raise ValueError("您有待支付订单，需在历史订单中取消订单重新购买")
        # 其他异常重新抛出
        raise e