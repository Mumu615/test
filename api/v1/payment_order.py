from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional
from dependencies import get_db, get_current_user, get_current_admin_user, require_permission
from schemas.payment_order import (
    PaymentOrderAdmin, PaymentOrderFilter, 
    PaymentOrderAdminPaginatedResponse, PaymentOrderListResponse
)
from schemas.common import success
from crud.payment_order import get_admin_payment_orders, get_payment_order_statistics
from models.user import User
from core.permissions import Permission

router = APIRouter(tags=["管理员-支付订单管理"])

@router.get("/payment-orders", response_model=PaymentOrderListResponse)
def get_payment_orders(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(None, description="按用户ID精确筛选"),
    user_search: Optional[str] = Query(None, description="按用户昵称/邮箱模糊搜索"),
    out_trade_no: Optional[str] = Query(None, description="按商户订单号精确搜索"),
    trade_no: Optional[str] = Query(None, description="按ZPAY订单号精确搜索"),
    type: Optional[str] = Query(None, description="按支付方式筛选 (alipay/wxpay)"),
    status: Optional[int] = Query(None, ge=0, le=2, description="按订单状态筛选 (0/1/2)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TRANSACTIONS))
):
    """
    [管理员-支付订单] 获取支付订单列表，支持多种筛选条件
    
    - **权限**: 管理员
    - **分页**: 支持页码和每页数量
    - **筛选**: 支持用户ID、用户搜索、订单号、支付方式、状态筛选
    - **排序**: 默认按创建时间降序排列
    """
    # 构建筛选条件
    filters = PaymentOrderFilter(
        user_id=user_id,
        user_search=user_search,
        out_trade_no=out_trade_no,
        trade_no=trade_no,
        type=type,
        status=status
    )
    
    # 计算偏移量
    skip = (page - 1) * size
    
    # 查询数据
    orders, total = get_admin_payment_orders(db, filters, skip, size)
    
    # 转换数据格式
    items = []
    for order, user in orders:
        # 构建用户信息
        user_info = {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
        
        # 构建订单信息
        item = PaymentOrderAdmin(
            id=order.id,
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
            trade_no=order.trade_no,
            status=order.status,
            trade_status=order.trade_status,
            buyer=order.buyer,
            addtime=order.addtime,
            endtime=order.endtime,
            unique_pending_flag=order.unique_pending_flag,
            created_at=order.created_at,
            updated_at=order.updated_at,
            user=user_info
        )
        items.append(item)
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    # 构建分页响应
    paginated_response = PaymentOrderAdminPaginatedResponse(
        total=total,
        items=items,
        page=page,
        size=size,
        pages=pages
    )
    
    # 返回统一响应格式
    return PaymentOrderListResponse(
        code=200,
        message="Success",
        data=paginated_response
    )

@router.get("/payment-orders/statistics")
def get_payment_order_statistics_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TRANSACTIONS))
):
    """
    [管理员-支付订单] 获取支付订单统计信息
    
    - **权限**: 管理员
    - **返回**: 总订单数、待支付数、支付成功数、已关闭数、总交易额
    """
    statistics = get_payment_order_statistics(db)
    return success(data=statistics, message="获取统计信息成功")

@router.get("/payment-orders/{order_id}", response_model=PaymentOrderAdmin)
def get_payment_order_detail(
    order_id: int = Path(..., description="订单ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TRANSACTIONS))
):
    """
    [管理员-支付订单] 获取支付订单详情
    
    - **权限**: 管理员
    - **返回**: 包含用户信息的完整订单详情
    """
    from crud.payment_order import get_payment_order_by_id
    
    order = get_payment_order_by_id(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    # 获取用户信息
    user = db.query(User).filter(User.id == order.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单关联用户不存在"
        )
    
    # 构建用户信息
    user_info = {
        "id": user.id,
        "username": user.username,
        "email": user.email
    }
    
    # 构建订单信息
    order_detail = PaymentOrderAdmin(
        id=order.id,
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
        trade_no=order.trade_no,
        status=order.status,
        trade_status=order.trade_status,
        buyer=order.buyer,
        addtime=order.addtime,
        endtime=order.endtime,
        unique_pending_flag=order.unique_pending_flag,
        created_at=order.created_at,
        updated_at=order.updated_at,
        user=user_info
    )
    
    return order_detail