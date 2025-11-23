from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from schemas.common import PaginatedResponse, success
from schemas.credit_transaction_admin import CreditTransactionAdmin, CreditTransactionFilter, CreditTransactionAdminPaginatedResponse
from dependencies import get_db, get_current_user, get_current_admin_user, require_permission
from models.user import User
from crud.credit_transaction import get_admin_credit_transactions
from core.permissions import Permission
import logging

router = APIRouter(tags=["管理员-积分流水"])

@router.get("/credit-transactions", response_model=CreditTransactionAdminPaginatedResponse)
def get_credit_transactions(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    username: Optional[str] = Query(None, description="用户名（模糊匹配）"),
    email: Optional[str] = Query(None, description="邮箱（模糊匹配）"),
    source: Optional[str] = Query(None, description="积分来源/消耗原因"),
    min_amount: Optional[int] = Query(None, description="最小积分变动数量"),
    max_amount: Optional[int] = Query(None, description="最大积分变动数量"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ALL_TRANSACTIONS))
):
    """
    [管理员-积分流水] 获取所有积分流水的分页列表，提供强大的筛选和排序功能
    
    - **权限**: 管理员
    - **分页**: 支持页码和每页数量
    - **筛选**: 支持用户ID、用户名、邮箱、来源、积分范围、日期范围筛选
    - **排序**: 默认按创建时间降序排列
    """
    
    # 构建筛选条件
    filters = CreditTransactionFilter(
        user_id=user_id,
        username=username,
        email=email,
        source=source,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date
    )
    
    # 计算偏移量
    skip = (page - 1) * size
    
    # 查询数据
    transactions, total = get_admin_credit_transactions(db, filters, skip, size)
    
    # 转换数据格式
    items = []
    for transaction, user in transactions:
        item = CreditTransactionAdmin(
            id=transaction.id,
            user_id=transaction.user_id,
            username=user.username,
            email=user.email,
            amount=transaction.amount,
            balance_after=transaction.balance_after,
            source=transaction.source,
            source_id=transaction.source_id,
            created_at=transaction.created_at
        )
        items.append(item)
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    # 返回分页结果
    return CreditTransactionAdminPaginatedResponse(
        total=total,
        items=items,
        page=page,
        size=size,
        pages=pages
    )