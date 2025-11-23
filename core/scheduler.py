# 定时任务模块
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from crud.payment_order import delete_pending_payment_orders
from config.database import SessionLocal
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 创建调度器
scheduler = AsyncIOScheduler()

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def delete_pending_orders_task():
    """删除待支付状态订单的定时任务"""
    db = next(get_db())
    try:
        # 删除待支付状态的订单
        deleted_count = delete_pending_payment_orders(db)
        logger.info(f"定时任务执行完成，删除了 {deleted_count} 个待支付状态的订单")
    except Exception as e:
        logger.error(f"删除待支付订单定时任务执行失败: {str(e)}")
    finally:
        db.close()

def init_scheduler():
    """初始化定时任务调度器"""
    # 添加定时任务，每6小时执行一次
    scheduler.add_job(
        delete_pending_orders_task,
        trigger=CronTrigger(hour="*/6", minute=0),  # 每6小时执行一次（0:00, 6:00, 12:00, 18:00）
        id="delete_pending_orders",
        name="删除待支付状态的订单",
        replace_existing=True
    )
    
    # 启动调度器
    scheduler.start()
    logger.info("定时任务调度器已启动，将每6小时删除待支付状态的订单")