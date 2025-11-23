from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from models.user import User, UserRole
from models.user_profile import UserProfile
from core.security import get_password_hash
from typing import Tuple, Optional, Dict, Any

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def validate_user_role(role: str) -> UserRole:
    """
    验证并返回有效的用户角色枚举值
    
    Args:
        role: 角色字符串值
        
    Returns:
        UserRole: 有效的用户角色枚举值
        
    Raises:
        ValueError: 如果角色值无效
    """
    # 将输入转换为大写，以匹配枚举定义
    role_upper = role.upper() if role else None
    
    # 验证角色值是否有效
    try:
        if role_upper is None:
            # 默认返回USER角色
            return UserRole.USER
        return UserRole(role_upper)
    except ValueError:
        # 如果角色值无效，抛出明确的错误
        valid_roles = [r.value for r in UserRole]
        raise ValueError(f"无效的用户角色: {role}. 有效角色为: {valid_roles}")

def create_user(db: Session, user_create):
    if get_user_by_email(db, user_create.email):
        return None
    hashed_password = get_password_hash(user_create.password)
    
    # 确保使用正确的枚举值作为默认角色
    user_role = UserRole.USER
    
    # 如果user_create对象包含role属性，验证它
    if hasattr(user_create, 'role') and user_create.role:
        try:
            user_role = validate_user_role(user_create.role)
        except ValueError as e:
            raise ValueError(f"用户角色验证失败: {str(e)}")
    
    db_user = User(
        username=user_create.username,
        email=user_create.email,
        password=hashed_password,
        role=user_role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_password(db: Session, user: User, new_hashed_password: str):
    user.password = new_hashed_password
    db.commit()
    db.refresh(user)
    return user

def update_user_status(db: Session, user_id: int, status: int):
    user = get_user_by_id(db, user_id)
    if user:
        user.status = status
        db.commit()
        db.refresh(user)
    return user

def get_all_users(db: Session, skip: int = 0, limit: int = 100, keyword: Optional[str] = None, status: Optional[int] = None) -> Tuple[list, int]:
    """
    获取用户列表和总数
    
    Args:
        db: 数据库会话
        skip: 跳过的记录数
        limit: 返回的记录数
        keyword: 搜索关键词，支持用户名和邮箱
        status: 用户状态筛选
        
    Returns:
        Tuple[list, int]: (用户列表, 总记录数)
    """
    # 构建基础查询
    query = db.query(
        User.id,
        User.username,
        User.email,
        User.status,
        User.created_at
    )
    
    # 构建计数查询
    count_query = db.query(func.count(User.id))
    
    # 动态筛选条件
    filters = []
    
    # 关键词搜索（不区分大小写）
    if keyword:
        search_filter = or_(
            func.lower(User.username).contains(func.lower(keyword)),
            func.lower(User.email).contains(func.lower(keyword))
        )
        filters.append(search_filter)
    
    # 状态筛选
    if status is not None:
        filters.append(User.status == status)
    
    # 应用筛选条件
    for f in filters:
        query = query.filter(f)
        count_query = count_query.filter(f)
    
    # 获取总数
    total = count_query.scalar()
    
    # 排序和分页
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    return users, total

def get_user_with_profile(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    """
    使用LEFT JOIN获取用户及其档案信息
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        Dict[str, Any]: 包含用户和档案信息的字典，如果用户不存在则返回None
    """
    # 使用LEFT JOIN查询用户及其档案信息
    result = db.query(
        User.id,
        User.username,
        User.email,
        User.status,
        User.created_at,
        UserProfile.user_id.label("profile_user_id"),
        UserProfile.credits,
        UserProfile.membership_type,
        UserProfile.membership_expires_at,
        UserProfile.free_model1_usages,
        UserProfile.free_model2_usages,
        UserProfile.updated_at.label("profile_updated_at")
    ).outerjoin(
        UserProfile, User.id == UserProfile.user_id
    ).filter(
        User.id == user_id
    ).first()
    
    if not result:
        return None
    
    # 构建符合UserWithProfile模型的数据结构
    user_data = {
        "id": result.id,
        "username": result.username,
        "email": result.email,
        "status": result.status,
        "created_at": result.created_at,
        "profile": None
    }
    
    # 如果有档案信息，添加到profile字段
    if result.profile_user_id is not None:
        user_data["profile"] = {
            "user_id": result.profile_user_id,
            "credits": result.credits,
            "membership_type": result.membership_type,
            "membership_expires_at": result.membership_expires_at,
            "free_model1_usages": result.free_model1_usages,
            "free_model2_usages": result.free_model2_usages,
            "updated_at": result.profile_updated_at
        }
    
    return user_data

def update_user_credits(db: Session, user_id: int, credits_to_add: int, commit: bool = True) -> bool:
    """
    更新用户积分
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        credits_to_add: 要增加的积分数量（可以是负数）
        commit: 是否自动提交更改，默认为True
        
    Returns:
        bool: 是否更新成功
    """
    try:
        # 查询用户档案
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        
        if profile:
            # 更新现有档案的积分
            profile.credits += credits_to_add
        else:
            # 创建新的用户档案
            profile = UserProfile(
                user_id=user_id,
                credits=credits_to_add
            )
            db.add(profile)
        
        # 只有在commit参数为True时才提交，以便在事务上下文中使用
        if commit:
            db.commit()
        return True
    except Exception as e:
        # 只有在commit参数为True时才回滚，以便在事务上下文中使用
        if commit:
            db.rollback()
        print(f"更新用户积分失败: {str(e)}")
        return False

def update_user_role(db: Session, user_id: int, role: str, commit: bool = True) -> bool:
    """
    更新用户角色
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        role: 新角色
        commit: 是否自动提交更改，默认为True
        
    Returns:
        bool: 是否更新成功
    """
    try:
        # 验证角色
        user_role = validate_user_role(role)
        
        # 查询用户
        user = get_user_by_id(db, user_id)
        if not user:
            return False
        
        # 更新用户角色
        user.role = user_role
        
        # 如果是升级为高级会员，更新会员档案
        if role == "premium":
            profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if profile:
                from datetime import datetime, timedelta
                # 设置会员到期时间为一年后
                profile.membership_type = "premium"
                profile.membership_expires_at = datetime.now() + timedelta(days=365)
            else:
                # 创建新的用户档案
                from datetime import datetime, timedelta
                profile = UserProfile(
                    user_id=user_id,
                    membership_type="premium",
                    membership_expires_at=datetime.now() + timedelta(days=365)
                )
                db.add(profile)
        
        # 只有在commit参数为True时才提交，以便在事务上下文中使用
        if commit:
            db.commit()
        return True
    except Exception as e:
        # 只有在commit参数为True时才回滚，以便在事务上下文中使用
        if commit:
            db.rollback()
        print(f"更新用户角色失败: {str(e)}")
        return False
