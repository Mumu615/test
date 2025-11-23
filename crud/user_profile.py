from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user_profile import UserProfile
from models.user import User
from schemas.user_profile import UserProfileCreate, UserProfileUpdate, UserAssetUpdate
from typing import Tuple, Optional
from datetime import datetime, timedelta
import json
import logging

def get_user_profile(db: Session, user_id: int):
    """获取用户档案"""
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

def get_user_profile_or_create(db: Session, user_id: int):
    """获取用户档案，如果不存在则创建默认档案"""
    profile = get_user_profile(db, user_id)
    if not profile:
        # 创建默认用户档案
        profile = UserProfile(
            user_id=user_id,
            credits=0,
            free_model1_usages=5,
            free_model2_usages=3,
            membership_type=0,
            membership_expires_at=None
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

def create_user_profile(db: Session, profile: UserProfileCreate):
    """创建用户档案"""
    db_profile = UserProfile(
        user_id=profile.user_id,
        credits=profile.credits,
        free_model1_usages=profile.free_model1_usages,
        free_model2_usages=profile.free_model2_usages,
        membership_type=profile.membership_type,
        membership_expires_at=profile.membership_expires_at
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

def update_user_profile(db: Session, user_id: int, profile_update: UserProfileUpdate):
    """更新用户档案"""
    db_profile = get_user_profile(db, user_id)
    if not db_profile:
        return None
    
    update_data = profile_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_profile, key, value)
    
    db.commit()
    db.refresh(db_profile)
    return db_profile

def update_user_credits(db: Session, user_id: int, credits: int, commit: bool = True):
    """更新用户积分"""
    db_profile = get_user_profile(db, user_id)
    if not db_profile:
        return None
    
    db_profile.credits = credits
    
    # 只有在commit参数为True时才提交，以便在事务上下文中使用
    if commit:
        db.commit()
        db.refresh(db_profile)
    
    return db_profile

def decrease_free_usage(db: Session, user_id: int, model_number: int):
    """减少免费使用次数"""
    db_profile = get_user_profile(db, user_id)
    if not db_profile:
        return None
    
    if model_number == 1 and db_profile.free_model1_usages > 0:
        db_profile.free_model1_usages -= 1
    elif model_number == 2 and db_profile.free_model2_usages > 0:
        db_profile.free_model2_usages -= 1
    
    db.commit()
    db.refresh(db_profile)
    return db_profile

def upgrade_membership(db: Session, user_id: int, membership_type: int, days: int):
    """升级会员"""
    db_profile = get_user_profile(db, user_id)
    if not db_profile:
        return None
    
    # 检查当前会员状态
    now = datetime.now()
    current_membership_type = db_profile.membership_type or 0
    current_expires_at = db_profile.membership_expires_at
    
    # 如果当前会员已过期，重置为普通会员
    if current_expires_at and current_expires_at <= now:
        current_membership_type = 0
        current_expires_at = None
    
    # 专业会员(2)是最高级，如果购买低级会员，不进行任何更改
    if current_membership_type == 2 and membership_type < 2:
        # 记录日志但不修改会员状态
        logger = logging.getLogger(__name__)
        logger.info(f"用户{user_id}是专业会员，尝试购买低级会员({membership_type})，不进行降级处理")
        return db_profile
    
    # 计算新的到期时间
    if current_expires_at and current_expires_at > now:
        # 如果当前会员未过期，在现有时间上延长
        new_expires_at = current_expires_at + timedelta(days=days)
    else:
        # 如果当前会员已过期或没有会员，从现在开始计算
        new_expires_at = now + timedelta(days=days)
    
    # 只有当新会员等级高于当前等级，或者当前会员已过期时，才进行升级
    if membership_type > current_membership_type or current_membership_type == 0:
        db_profile.membership_type = membership_type
        db_profile.membership_expires_at = new_expires_at
        
        db.commit()
        db.refresh(db_profile)
        
        # 记录升级日志
        logger = logging.getLogger(__name__)
        logger.info(f"用户{user_id}会员升级成功，从等级{current_membership_type}升级到{membership_type}，有效期至{new_expires_at}")
    # 如果购买同级会员，只延长到期时间
    elif membership_type == current_membership_type:
        db_profile.membership_expires_at = new_expires_at
        
        db.commit()
        db.refresh(db_profile)
        
        # 记录延长日志
        logger = logging.getLogger(__name__)
        logger.info(f"用户{user_id}会员等级{membership_type}有效期延长{days}天，新有效期至{new_expires_at}")
    
    return db_profile

def check_membership_valid(db: Session, user_id: int):
    """检查会员是否有效"""
    db_profile = get_user_profile(db, user_id)
    if not db_profile:
        return False
    
    if db_profile.membership_type == 0:  # 普通会员
        return True
    
    # 检查会员是否过期
    now = datetime.now()
    return db_profile.membership_expires_at and db_profile.membership_expires_at > now

def get_user_assets(
    db: Session, 
    page: int = 1, 
    size: int = 10,
    min_credits: Optional[int] = None,
    max_credits: Optional[int] = None,
    membership_type: Optional[int] = None,
    username: Optional[str] = None
) -> Tuple[list, int]:
    """
    获取用户资产列表和总数
    
    Args:
        db: 数据库会话
        page: 页码，从1开始
        size: 每页数量
        min_credits: 最小积分
        max_credits: 最大积分
        membership_type: 会员类型 (0-普通, 1-高级, 2-专业)
        username: 用户名 (模糊匹配)
        
    Returns:
        Tuple[list, int]: (用户资产列表, 总记录数)
    """
    # 计算偏移量
    skip = (page - 1) * size
    
    # 构建基础查询，使用JOIN连接users和user_profiles表
    query = db.query(
        User.id.label("user_id"),
        User.username,
        User.email,
        UserProfile.credits,
        UserProfile.membership_type,
        UserProfile.membership_expires_at,
        UserProfile.free_model1_usages,
        UserProfile.free_model2_usages,
        UserProfile.updated_at
    ).join(
        UserProfile, User.id == UserProfile.user_id
    )
    
    # 构建计数查询
    count_query = db.query(func.count(User.id)).join(
        UserProfile, User.id == UserProfile.user_id
    )
    
    # 动态添加筛选条件
    if username:
        search_filter = User.username.like(f"%{username}%")
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)
    
    if min_credits is not None:
        query = query.filter(UserProfile.credits >= min_credits)
        count_query = count_query.filter(UserProfile.credits >= min_credits)
    
    if max_credits is not None:
        query = query.filter(UserProfile.credits <= max_credits)
        count_query = count_query.filter(UserProfile.credits <= max_credits)
    
    if membership_type is not None:
        query = query.filter(UserProfile.membership_type == membership_type)
        count_query = count_query.filter(UserProfile.membership_type == membership_type)
    
    # 获取总数
    total = count_query.scalar()
    
    # 排序和分页
    assets = query.order_by(User.id.desc()).offset(skip).limit(size).all()
    
    return assets, total

def update_user_assets_atomic(
    db: Session, 
    user_id: int, 
    asset_update: UserAssetUpdate
) -> Tuple[Optional[UserProfile], Optional[dict], Optional[dict]]:
    """
    原子性更新用户资产信息
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        asset_update: 资产更新数据
        
    Returns:
        Tuple[Optional[UserProfile], Optional[dict], Optional[dict]]: 
        (更新后的用户档案, 更新前的数据, 更新后的数据)
        
    Note:
        此函数不提交事务，由调用方控制事务提交
    """
    # 获取用户档案
    profile = get_user_profile(db, user_id)
    if not profile:
        return None, None, None
    
    # 保存更新前的数据
    before_data = {
        "credits": profile.credits,
        "membership_type": profile.membership_type,
        "membership_expires_at": profile.membership_expires_at.isoformat() if profile.membership_expires_at else None,
        "free_model1_usages": profile.free_model1_usages,
        "free_model2_usages": profile.free_model2_usages
    }
    
    # 获取更新数据
    update_data = asset_update.dict(exclude_unset=True)
    
    # 验证数据有效性
    if "credits" in update_data and update_data["credits"] < 0:
        raise ValueError("积分不能为负数")
    
    if "membership_type" in update_data and update_data["membership_type"] not in [0, 1, 2]:
        raise ValueError("无效的会员类型")
    
    if "free_model1_usages" in update_data and update_data["free_model1_usages"] < 0:
        raise ValueError("模型一免费使用次数不能为负数")
        
    if "free_model2_usages" in update_data and update_data["free_model2_usages"] < 0:
        raise ValueError("模型二免费使用次数不能为负数")
    
    # 检查是否有积分更新
    credits_updated = "credits" in update_data
    old_credits = profile.credits
    new_credits = update_data.get("credits", old_credits)
    
    # 原子性更新所有字段
    for key, value in update_data.items():
        setattr(profile, key, value)
    
    # 刷新对象以获取更新后的值，但不提交事务
    db.flush()
    db.refresh(profile)
    
    # 如果积分有更新，创建积分流水记录
    if credits_updated and old_credits != new_credits:
        from models.credit_transaction import CreditTransaction
        from datetime import datetime
        
        # 计算积分变动量
        amount = new_credits - old_credits
        
        # 创建积分流水记录
        credit_transaction = CreditTransaction(
            user_id=user_id,
            amount=amount,
            balance_after=new_credits,
            source="admin_adjustment",
            source_id=None,
            created_at=datetime.now()
        )
        db.add(credit_transaction)
        
        # 再次刷新以确保流水记录已添加到会话中
        db.flush()
    
    # 保存更新后的数据
    after_data = {
        "credits": profile.credits,
        "membership_type": profile.membership_type,
        "membership_expires_at": profile.membership_expires_at.isoformat() if profile.membership_expires_at else None,
        "free_model1_usages": profile.free_model1_usages,
        "free_model2_usages": profile.free_model2_usages
    }
    
    return profile, before_data, after_data