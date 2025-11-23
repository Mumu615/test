"""
支付相关API接口
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import Dict, Any
from dependencies import get_db, get_current_user
from schemas.payment_order import PaymentRequest, PaymentResponse, PaymentOrder
from schemas.common import success, fail
from models.user import User
from models.payment_order import PaymentOrder as PaymentOrderModel, PaymentOrderStatus
from crud.payment_order import create_payment_order_with_sign, update_payment_order, get_payment_order_by_out_trade_no, get_payment_order_by_id, get_user_payment_orders
from crud.user import update_user_credits, update_user_role
from crud.credit_transaction import add_credits
from core.payment_utils import call_zpay_api, verify_zpay_callback, MERCHANT_KEY
from core.config import settings
from services.product_service import get_product_by_id
from datetime import datetime
import logging

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(tags=["支付订单"])

# ZPAY配置 - 从环境变量中读取，如果未设置则使用默认值
ZPAY_API_URL = settings.ZPAY_API_URL or "https://zpayz.cn/mapi.php"  # ZPAY支付接口URL
MERCHANT_ID = settings.ZPAY_MERCHANT_ID or "MERCHANT001"  # 商户ID
MERCHANT_KEY = settings.ZPAY_API_KEY or "your_merchant_key_here"  # 商户密钥
NOTIFY_URL = "http://75.127.89.76:880/api/v1/payment/notify"  # 异步通知地址，实际项目中应该使用实际域名

@router.post("/payment/create", response_model=PaymentResponse)
def create_payment_order(
    payment_request: PaymentRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建支付订单
    
    - **权限**: 需要登录
    - **流程**: 
        1. 验证用户身份
        2. 根据产品ID查询产品信息和价格
        3. 检查用户是否在1分钟内已有待支付订单
        4. 生成唯一订单号和签名
        5. 保存订单到数据库
        6. 调用ZPAY支付接口
        7. 返回支付信息给前端
    """
    try:
        # 1. 根据产品ID获取产品信息
        product = get_product_by_id(payment_request.product_id)
        
        # 2. 创建支付订单（包含签名）
        # 将产品ID存储在param字段中，以便在支付回调时使用
        param_data = {"product_id": payment_request.product_id}
        import json
        param_str = json.dumps(param_data)
        
        order = create_payment_order_with_sign(
            db=db,
            user_id=current_user.id,
            name=product["name"],
            money=float(product["price"]),
            payment_type=payment_request.type,
            clientip=payment_request.clientip,
            merchant_id=MERCHANT_ID,
            notify_url=NOTIFY_URL,
            merchant_key=MERCHANT_KEY,
            param=param_str
        )
        
        # 2. 准备调用ZPAY接口的参数
        zpay_params = {
            'pid': order.pid,
            'type': order.type,
            'out_trade_no': order.out_trade_no,
            'notify_url': order.notify_url,
            'name': order.name,
            'money': str(order.money),
            'clientip': order.clientip,
            'sign': order.sign,
            'sign_type': 'MD5'  # 添加签名类型参数
        }
        
        # 3. 调用ZPAY支付接口
        zpay_response, raw_response = call_zpay_api(
            api_url=ZPAY_API_URL,
            params=zpay_params,
            merchant_key=MERCHANT_KEY
        )
        
        # 4. 处理ZPAY响应
        if zpay_response:
            # 将code字段转换为整数进行比较
            response_code = int(zpay_response.code) if isinstance(zpay_response.code, str) else zpay_response.code
            
            if response_code == 1:
                # 支付接口调用成功，更新订单信息
                update_data = {
                    'trade_no': zpay_response.trade_no,
                    'status': 0  # 待支付状态
                }
                update_payment_order(db, order.id, update_data)
                
                # 构建返回数据
                response_data = {
                    'id': order.id,  # 添加订单ID
                    'out_trade_no': order.out_trade_no,  # 添加订单号
                    'trade_no': zpay_response.trade_no  # 添加交易号
                }
                if zpay_response.payurl:
                    response_data['pay_url'] = zpay_response.payurl
                if zpay_response.qrcode:
                    response_data['qrcode_url'] = zpay_response.qrcode
                if zpay_response.img:
                    response_data['qrcode_img'] = zpay_response.img
                    
                # 返回成功响应
                try:
                    return PaymentResponse(
                        code=1,
                        message="success",
                        data=response_data
                    )
                except Exception as response_error:
                    logger.error(f"创建PaymentResponse对象失败: {str(response_error)}")
                    return PaymentResponse(
                        code=1,
                        message="success",
                        data=None
                    )
            else:
                # 支付接口调用失败，记录错误日志
                error_msg = zpay_response.msg if zpay_response.msg else "支付接口返回错误"
                logger.error(f"调用ZPAY接口失败: {error_msg}, 响应码: {zpay_response.code}")
                
                # 更新订单状态为已关闭
                update_data = {'status': 2}  # 已关闭状态
                update_payment_order(db, order.id, update_data)
                
                # 直接返回ZPAY原始错误响应
                try:
                    return PaymentResponse(
                        code=zpay_response.code,
                        message=error_msg,
                        data=raw_response
                    )
                except Exception as response_error:
                    logger.error(f"创建PaymentResponse对象失败: {str(response_error)}")
                    return PaymentResponse(
                        code=zpay_response.code,
                        message=error_msg,
                        data=None
                    )
        elif raw_response:
            # ZPAY返回了响应但无法解析为ZPayResponse对象，或者解析失败
            logger.error(f"ZPAY响应解析失败: {raw_response}")
            
            # 检查是否是成功响应
            response_code = raw_response.get('code')
            if response_code == 1:
                # 即使解析失败，如果是成功响应，也尝试处理
                trade_no = raw_response.get('trade_no')
                if trade_no:
                    update_data = {
                        'trade_no': trade_no,
                        'status': 0  # 待支付状态
                    }
                    update_payment_order(db, order.id, update_data)
                
                # 构建返回数据
                response_data = {}
                if raw_response.get('payurl'):
                    response_data['pay_url'] = raw_response.get('payurl')
                if raw_response.get('qrcode'):
                    response_data['qrcode_url'] = raw_response.get('qrcode')
                if raw_response.get('img'):
                    response_data['qrcode_img'] = raw_response.get('img')
                
                # 返回成功响应
                try:
                    return PaymentResponse(
                        code=1,
                        message="success",
                        data=response_data
                    )
                except Exception as response_error:
                    logger.error(f"创建PaymentResponse对象失败: {str(response_error)}")
                    return PaymentResponse(
                        code=1,
                        message="success",
                        data=None
                    )
            else:
                # 失败响应，更新订单状态为已关闭
                update_data = {'status': 2}  # 已关闭状态
                update_payment_order(db, order.id, update_data)
                
                # 返回错误响应
                try:
                    return PaymentResponse(
                        code=raw_response.get('code', -1),
                        message=raw_response.get('msg', 'ZPAY响应解析失败'),
                        data=raw_response
                    )
                except Exception as response_error:
                    logger.error(f"创建PaymentResponse对象失败: {str(response_error)}")
                    return PaymentResponse(
                        code=raw_response.get('code', -1),
                        message=raw_response.get('msg', 'ZPAY响应解析失败'),
                        data=None
                    )
        else:
            # 支付接口调用失败，记录错误日志
            error_msg = "网络异常，请稍后再试"
            logger.error(f"调用ZPAY接口失败: {error_msg}")
            
            # 更新订单状态为已关闭
            update_data = {'status': 2}  # 已关闭状态
            update_payment_order(db, order.id, update_data)
            
            # 返回错误响应
            return PaymentResponse(
                code=-1,
                message=error_msg
            )
            
    except ValueError as e:
        # 处理1分钟内重复创建订单的异常
        logger.warning(f"用户{current_user.id}尝试重复创建订单: {str(e)}")
        
        # 使用HTTPException返回429状态码
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except Exception as e:
        # 记录异常日志
        logger.error(f"创建支付订单异常: {str(e)}")
        
        # 返回错误响应
        return PaymentResponse(
            code=-1,
            message="系统异常，请稍后再试"
        )

@router.post("/payment/orders/{order_id}/cancel")
def cancel_payment_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    取消支付订单
    
    - **权限**: 需要登录
    - **流程**: 
        1. 验证用户身份
        2. 查询订单并验证权限
        3. 检查订单状态是否为待支付
        4. 更新订单状态为已关闭
    """
    try:
        # 1. 查询订单
        order = get_payment_order_by_id(db, order_id)
        
        # 2. 验证订单是否存在
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在"
            )
        
        # 3. 验证权限：确保请求用户是订单的所有者
        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作此订单"
            )
        
        # 4. 检查订单状态是否为待支付
        if order.status != PaymentOrderStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能取消待支付状态的订单"
            )
        
        # 5. 更新订单状态为已关闭
        update_data = {'status': PaymentOrderStatus.CLOSED.value}
        update_payment_order(db, order_id, update_data)
        
        # 6. 返回成功响应
        return success(message="订单已取消")
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 记录异常日志
        logger.error(f"取消支付订单异常: {str(e)}")
        
        # 返回错误响应
        return fail(message="系统异常，请稍后再试")

@router.get("/payment/orders/{order_id}")
def get_payment_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询支付订单状态
    
    - **权限**: 需要登录
    - **流程**: 
        1. 验证用户身份
        2. 查询订单并验证权限
        3. 返回订单详情（特别是status字段）
    """
    try:
        # 1. 查询订单
        order = get_payment_order_by_id(db, order_id)
        
        # 2. 验证订单是否存在
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在"
            )
        
        # 3. 验证权限：确保请求用户是订单的所有者
        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此订单"
            )
        
        # 4. 构建响应数据
        response_data = {
            "id": order.id,
            "out_trade_no": order.out_trade_no,
            "trade_no": order.trade_no,
            "name": order.name,
            "money": float(order.money),
            "type": order.type.value if hasattr(order.type, 'value') else str(order.type),
            "status": order.status,
            "trade_status": order.trade_status,
            "created_at": order.created_at,
            "updated_at": order.updated_at
        }
        
        # 5. 返回订单详情
        return success(data=response_data, message="查询成功")
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 记录异常日志
        logger.error(f"查询支付订单状态异常: {str(e)}")
        
        # 返回错误响应
        return fail(message="系统异常，请稍后再试")

@router.get("/payment/orders")
def get_user_payment_orders_api(
    page: int = 1,
    size: int = 10,
    status: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户历史支付订单列表
    
    - **权限**: 需要登录
    - **参数**:
        - page: 页码，默认为1
        - size: 每页数量，默认为10
        - status: 订单状态筛选，0-待支付，1-支付成功，2-已关闭
    """
    try:
        # 计算跳过的记录数
        skip = (page - 1) * size
        
        # 构建筛选条件
        filters = {}
        if status is not None:
            filters['status'] = status
        
        # 获取用户订单列表和总数
        orders, total = get_user_payment_orders(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=size
        )
        
        # 如果有状态筛选条件，需要进一步过滤
        if status is not None:
            orders = [order for order in orders if order.status == status]
            total = len(orders)
        
        # 构建响应数据
        response_data = {
            "items": [
                {
                    "id": order.id,
                    "out_trade_no": order.out_trade_no,
                    "trade_no": order.trade_no,
                    "name": order.name,
                    "money": float(order.money),
                    "type": order.type.value if hasattr(order.type, 'value') else str(order.type),
                    "status": order.status,
                    "status_text": "待支付" if order.status == 0 else "支付成功" if order.status == 1 else "已关闭",
                    "trade_status": order.trade_status,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                    "endtime": order.endtime
                }
                for order in orders
            ],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size if total > 0 else 0
        }
        
        # 返回订单列表
        return success(data=response_data, message="查询成功")
        
    except Exception as e:
        # 记录异常日志
        logger.error(f"获取用户历史订单异常: {str(e)}")
        
        # 返回错误响应
        return fail(message="系统异常，请稍后再试")

@router.get("/payment/notify")
def payment_notify(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    支付异步通知接口
    
    - **权限**: 无需认证（公开接口）
    - **请求方法**: GET
    - **处理流程**: 
        1. 获取ZPAY平台发送的回调参数
        2. 验证签名
        3. 查询订单信息
        4. 检查订单状态（幂等性处理）
        5. 验证金额
        6. 更新订单状态
        7. 处理业务逻辑（积分更新、会员升级等）
        8. 返回"success"给ZPAY平台
    """
    try:
        # 1. 获取所有GET参数
        params = dict(request.query_params)
        logger.info(f"收到支付异步通知: {params}")
        
        # 2. 验证必要参数
        required_params = ['pid', 'trade_no', 'out_trade_no', 'type', 'name', 'money', 'trade_status', 'sign', 'sign_type']
        for param in required_params:
            if param not in params:
                logger.error(f"支付异步通知缺少必要参数: {param}")
                return Response(content="fail", media_type="text/plain")  # 返回fail给ZPAY平台
        
        # 3. 验证签名
        is_valid_sign = verify_zpay_callback(params, MERCHANT_KEY)
        if not is_valid_sign:
            logger.error(f"支付异步通知签名验证失败: {params}")
            return Response(content="fail", media_type="text/plain")  # 返回fail给ZPAY平台
        
        # 4. 查询订单信息
        out_trade_no = params.get('out_trade_no')
        order = get_payment_order_by_out_trade_no(db, out_trade_no)
        
        if not order:
            logger.error(f"支付异步通知订单不存在: {out_trade_no}")
            return Response(content="fail", media_type="text/plain")  # 返回fail给ZPAY平台
        
        # 5. 检查订单状态（幂等性处理）
        if order.status == PaymentOrderStatus.SUCCESS.value:
            logger.info(f"订单已处理，跳过重复处理: {out_trade_no}")
            return Response(content="success", media_type="text/plain")  # 返回success给ZPAY平台
        
        # 6. 验证金额
        callback_money = float(params.get('money', '0'))
        order_money = float(order.money)
        
        # 使用四舍五入比较金额，避免浮点数精度问题
        if round(callback_money, 2) != round(order_money, 2):
            logger.error(f"支付异步通知金额不匹配: 订单金额={order_money}, 回调金额={callback_money}")
            return Response(content="fail", media_type="text/plain")  # 返回fail给ZPAY平台
        
        # 7. 检查支付状态
        trade_status = params.get('trade_status')
        if trade_status != 'TRADE_SUCCESS':
            logger.warning(f"支付状态不是成功: {trade_status}")
            return Response(content="success", media_type="text/plain")  # 非成功状态也返回success，避免重复通知
        
        # 8. 使用数据库事务处理订单状态更新和业务逻辑
        # 开始事务
        with db.begin():
            # 更新订单状态
            update_data = {
                'trade_no': params.get('trade_no'),
                'trade_status': trade_status,
                'status': PaymentOrderStatus.SUCCESS.value,
                'endtime': datetime.now()
            }
            update_payment_order(db, order.id, update_data, commit=False)
            
            # 获取订单所属用户
            user = db.query(User).filter(User.id == order.user_id).first()
            if not user:
                logger.error(f"订单用户不存在: {order.user_id}")
                raise ValueError(f"订单用户不存在: {order.user_id}")
            
            # 根据订单名称或参数处理业务逻辑
            # 先尝试从param参数中获取产品ID
            product_id = None
            if order.param:
                try:
                    import json
                    param_data = json.loads(order.param)
                    product_id = param_data.get('product_id')
                except:
                    pass
            
            # 如果没有从param中获取到产品ID，尝试从产品服务中查找
            if not product_id:
                # 尝试根据订单名称匹配产品
                from services.product_service import PRODUCT_CONFIG
                for pid, product in PRODUCT_CONFIG.items():
                    if product.get("name") == order.name:
                        product_id = pid
                        break
            
            if product_id:
                # 根据产品ID处理业务逻辑
                try:
                    product = get_product_by_id(product_id)
                    
                    # 添加积分
                    credits_to_add = product.get("credits", 0)
                    if credits_to_add > 0:
                        add_credits(
                            db=db,
                            user_id=user.id,
                            amount=credits_to_add,
                            source="recharge",
                            source_id=order.id,
                            commit=False
                        )
                        logger.info(f"用户{user.id}购买产品{product_id}成功，增加{credits_to_add}积分")
                    
                    # 处理会员权益
                    membership = product.get("membership")
                    if membership:
                        level = membership.get("level")
                        days = membership.get("days")
                        if level and days:
                            update_user_role(db, user.id, level, days, commit=False)
                            logger.info(f"用户{user.id}购买产品{product_id}成功，升级为{level}会员，有效期{days}天")
                
                except Exception as product_error:
                    logger.error(f"处理产品{product_id}业务逻辑失败: {str(product_error)}")
                    # 产品处理失败不影响订单状态更新
            else:
                # 兼容旧的业务逻辑
                if order.name == "积分充值":
                    # 积分充值：增加用户积分
                    credits_to_add = int(order_money * 10)  # 假设1元=10积分
                    
                    # 记录积分流水
                    add_credits(
                        db=db,
                        user_id=user.id,
                        amount=credits_to_add,
                        source="recharge",
                        source_id=order.id,
                        commit=False
                    )
                    logger.info(f"用户{user.id}积分充值成功，增加{credits_to_add}积分")
                    
                elif order.name == "会员升级":
                    # 会员升级：更新用户角色
                    update_user_role(db, user.id, "premium", commit=False)  # 升级为高级会员
                    logger.info(f"用户{user.id}会员升级成功")
        
        # 事务自动提交成功
        logger.info(f"支付异步通知处理成功: {out_trade_no}")
        return Response(content="success", media_type="text/plain")  # 返回success给ZPAY平台
        
    except Exception as e:
        # 事务自动回滚
        logger.error(f"支付回调事务处理失败: {str(e)}")
        return Response(content="fail", media_type="text/plain")  # 返回fail给ZPAY平台
