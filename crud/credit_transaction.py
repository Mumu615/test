from sqlalchemy.orm import Session
from models.credit_transaction import CreditTransaction
from models.user import User
from schemas.user_profile import CreditTransactionCreate, UserCreditTransactionFilter
from schemas.credit_transaction_admin import CreditTransactionFilter
from crud.user_profile import get_user_profile_or_create, update_user_credits
from typing import List, Optional, Tuple

def create_credit_transaction(db: Session, transaction: CreditTransactionCreate):
    """创建积分流水记录"""
    db_transaction = CreditTransaction(
        user_id=transaction.user_id,
        amount=transaction.amount,
        balance_after=transaction.balance_after,
        source=transaction.source,
        source_id=transaction.source_id
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def get_credit_transaction(db: Session, transaction_id: int):
    """获取单个积分流水记录"""
    return db.query(CreditTransaction).filter(CreditTransaction.id == transaction_id).first()

def get_credit_transactions(db: Session, user_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    """获取积分流水记录列表"""
    query = db.query(CreditTransaction)
    if user_id:
        query = query.filter(CreditTransaction.user_id == user_id)
    return query.order_by(CreditTransaction.created_at.desc()).offset(skip).limit(limit).all()

def add_credits(db: Session, user_id: int, amount: int, source: str, source_id: Optional[int] = None, commit: bool = True):
    """增加用户积分并创建流水记录"""
    # 获取或创建用户档案
    profile = get_user_profile_or_create(db, user_id)
    
    # 计算新的积分余额
    new_balance = profile.credits + amount
    
    # 更新用户积分，传递commit=False以避免在事务中自动提交
    update_user_credits(db, user_id, amount, commit=False)
    
    # 创建积分流水记录
    transaction = CreditTransactionCreate(
        user_id=user_id,
        amount=amount,
        balance_after=new_balance,
        source=source,
        source_id=source_id
    )
    
    # 创建积分流水记录，但不自动提交
    db_transaction = CreditTransaction(
        user_id=transaction.user_id,
        amount=transaction.amount,
        balance_after=transaction.balance_after,
        source=transaction.source,
        source_id=transaction.source_id
    )
    db.add(db_transaction)
    
    # 只有在commit参数为True时才提交，以便在事务上下文中使用
    if commit:
        db.commit()
        db.refresh(db_transaction)
    
    return db_transaction


def consume_credits(db: Session, user_id: int, amount: int, source: str, source_id: Optional[int] = None, commit: bool = True):
    """消耗用户积分并创建流水记录"""
    # 获取用户档案
    profile = get_user_profile_or_create(db, user_id)
    
    # 检查积分是否足够
    if profile.credits < amount:
        raise ValueError(f"积分不足，当前积分: {profile.credits}，需要积分: {amount}")
    
    # 计算新的积分余额
    new_balance = profile.credits - amount
    
    # 更新用户积分，传递commit=False以避免在事务中自动提交
    update_user_credits(db, user_id, new_balance, commit=False)
    
    # 创建积分流水记录（消耗积分为负数）
    transaction = CreditTransactionCreate(
        user_id=user_id,
        amount=-amount,  # 消耗积分为负数
        balance_after=new_balance,
        source=source,
        source_id=source_id
    )
    
    # 创建积分流水记录，但不自动提交
    db_transaction = CreditTransaction(
        user_id=transaction.user_id,
        amount=transaction.amount,
        balance_after=transaction.balance_after,
        source=transaction.source,
        source_id=transaction.source_id
    )
    db.add(db_transaction)
    
    # 【关键修改】只有 commit 为 True 时才提交
    if commit:
        db.commit()
        db.refresh(db_transaction)
    else:
        db.flush() # 否则只 flush，确保在当前事务中可见
    
    return db_transaction

def get_user_credit_balance(db: Session, user_id: int):
    """获取用户当前积分余额"""
    profile = get_user_profile_or_create(db, user_id)
    return profile.credits

def get_credit_transactions_by_source(db: Session, user_id: int, source: str, skip: int = 0, limit: int = 100):
    """根据来源获取用户积分流水记录"""
    return db.query(CreditTransaction).filter(
        CreditTransaction.user_id == user_id,
        CreditTransaction.source == source
    ).order_by(CreditTransaction.created_at.desc()).offset(skip).limit(limit).all()

def get_admin_credit_transactions(
    db: Session, 
    filters: CreditTransactionFilter,
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[CreditTransaction], int]:
    """
    管理员获取积分流水列表（分页）
    
    Args:
        db: 数据库会话
        filters: 筛选条件
        skip: 跳过记录数
        limit: 返回记录数
        
    Returns:
        Tuple[List[CreditTransaction], int]: 积分流水列表和总数
    """
    # 构建基础查询，关联用户表
    query = db.query(CreditTransaction, User).join(User, CreditTransaction.user_id == User.id)
    
    # 应用筛选条件
    if filters.user_id:
        query = query.filter(CreditTransaction.user_id == filters.user_id)
    
    if filters.username:
        query = query.filter(User.username.like(f"%{filters.username}%"))
    
    if filters.email:
        query = query.filter(User.email.like(f"%{filters.email}%"))
    
    if filters.source:
        query = query.filter(CreditTransaction.source == filters.source)
    
    if filters.min_amount is not None:
        query = query.filter(CreditTransaction.amount >= filters.min_amount)
    
    if filters.max_amount is not None:
        query = query.filter(CreditTransaction.amount <= filters.max_amount)
    
    if filters.start_date:
        query = query.filter(CreditTransaction.created_at >= filters.start_date)
    
    if filters.end_date:
        query = query.filter(CreditTransaction.created_at <= filters.end_date)
    
    # 获取总数（使用相同的筛选条件）
    total = query.count()
    
    # 应用排序和分页
    transactions = query.order_by(CreditTransaction.created_at.desc()).offset(skip).limit(limit).all()
    
    return transactions, total

def get_user_credit_transactions(
    db: Session, 
    user_id: int,
    filters: Optional[UserCreditTransactionFilter] = None,
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[CreditTransaction], int]:
    """
    获取用户积分流水列表（分页）
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        filters: 筛选条件
        skip: 跳过记录数
        limit: 返回记录数
        
    Returns:
        Tuple[List[CreditTransaction], int]: 积分流水列表和总数
    """
    # 构建基础查询
    query = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id)
    
    # 应用筛选条件
    if filters:
        if filters.source:
            query = query.filter(CreditTransaction.source == filters.source)
        
        if filters.min_amount is not None:
            query = query.filter(CreditTransaction.amount >= filters.min_amount)
        
        if filters.max_amount is not None:
            query = query.filter(CreditTransaction.amount <= filters.max_amount)
        
        if filters.start_date:
            query = query.filter(CreditTransaction.created_at >= filters.start_date)
        
        if filters.end_date:
            query = query.filter(CreditTransaction.created_at <= filters.end_date)
    
    # 获取总数（使用相同的筛选条件）
    total = query.count()
    
    # 应用排序和分页
    transactions = query.order_by(CreditTransaction.created_at.desc()).offset(skip).limit(limit).all()
    
    return transactions, total