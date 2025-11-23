from sqlalchemy.orm import Session
from models.admin_operation_log import AdminOperationLog
from schemas.admin_operation_log import AdminOperationLogCreate
from typing import Optional, List
import json

def create_admin_operation_log(
    db: Session, 
    log: AdminOperationLogCreate,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """创建管理员操作日志
    
    Note:
        此函数不提交事务，由调用方控制事务提交
    """
    db_log = AdminOperationLog(
        admin_id=log.admin_id,
        target_user_id=log.target_user_id,
        operation_type=log.operation_type,
        operation_detail=log.operation_detail,
        before_data=log.before_data,
        after_data=log.after_data,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(db_log)
    # 不提交事务，由调用方控制
    db.flush()
    return db_log

def get_admin_operation_logs(
    db: Session,
    admin_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    operation_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[AdminOperationLog]:
    """获取管理员操作日志列表"""
    query = db.query(AdminOperationLog)
    
    if admin_id:
        query = query.filter(AdminOperationLog.admin_id == admin_id)
    
    if target_user_id:
        query = query.filter(AdminOperationLog.target_user_id == target_user_id)
    
    if operation_type:
        query = query.filter(AdminOperationLog.operation_type == operation_type)
    
    return query.order_by(AdminOperationLog.created_at.desc()).offset(skip).limit(limit).all()

def count_admin_operation_logs(
    db: Session,
    admin_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    operation_type: Optional[str] = None
) -> int:
    """统计管理员操作日志数量"""
    query = db.query(AdminOperationLog)
    
    if admin_id:
        query = query.filter(AdminOperationLog.admin_id == admin_id)
    
    if target_user_id:
        query = query.filter(AdminOperationLog.target_user_id == target_user_id)
    
    if operation_type:
        query = query.filter(AdminOperationLog.operation_type == operation_type)
    
    return query.count()

def log_user_asset_update(
    db: Session,
    admin_id: int,
    target_user_id: int,
    before_data: dict,
    after_data: dict,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """记录用户资产更新操作日志"""
    log = AdminOperationLogCreate(
        admin_id=admin_id,
        target_user_id=target_user_id,
        operation_type="asset_update",
        operation_detail="更新用户资产信息",
        before_data=json.dumps(before_data, ensure_ascii=False),
        after_data=json.dumps(after_data, ensure_ascii=False)
    )
    
    return create_admin_operation_log(
        db=db,
        log=log,
        ip_address=ip_address,
        user_agent=user_agent
    )