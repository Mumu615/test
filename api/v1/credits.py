from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List, Optional
from datetime import datetime
from dependencies import get_db, get_current_user
from schemas.user_profile import CreditTransaction, TransactionSource, UserCreditTransactionFilter, UserCreditTransactionPaginatedResponse
from crud.credit_transaction import get_credit_transactions, get_credit_transaction, get_user_credit_transactions
from crud.user_profile import get_user_profile_or_create
from models.user import User
from models.credit_transaction import CreditTransaction as CreditTransactionModel

router = APIRouter(tags=["个人信息-资产管理"])

# 用户获取自己的积分流水
@router.get("/user/transactions", response_model=UserCreditTransactionPaginatedResponse)
async def get_my_credit_transactions(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    source: Optional[str] = Query(None, description="积分来源/消耗原因"),
    min_amount: Optional[int] = Query(None, description="最小积分变动数量"),
    max_amount: Optional[int] = Query(None, description="最大积分变动数量"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    用户获取自己的积分流水列表（支持分页和搜索）
    """
    # 构建筛选条件
    filters = UserCreditTransactionFilter(
        source=source,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date
    )
    
    # 计算跳过的记录数
    skip = (page - 1) * size
    
    # 获取积分流水列表和总数
    transactions, total = get_user_credit_transactions(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=size
    )
    
    # 计算总页数
    pages = (total + size - 1) // size if total > 0 else 0
    
    # 构建响应
    response = UserCreditTransactionPaginatedResponse(
        items=transactions,
        total=total,
        page=page,
        size=size,
        pages=pages
    )
    
    return response