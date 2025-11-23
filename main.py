# main.py
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # ✅ 新增
from api.v1.auth import router as auth_router
from api.v1.admin import router as admin_router
from api.v1.upload import router as upload_router
from api.v1.user_profile import user_router, admin_router as user_profile_admin_router
from api.v1.credits import router as credits_router
from api.v1.user_management import router as user_management_router
from api.v1.payment_order import router as payment_order_router
from api.v1.payment import router as payment_router
from routers.image_generation import router as image_generation_router
from routers.admin_image_generation import router as admin_image_generation_router

from core.config import settings
from core.scheduler import init_scheduler
from core.middleware import PermissionMiddleware  # 添加权限中间件导入

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logging.info(f"Database URL: {settings.DATABASE_URL}")
logging.info(f"Redis Host: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")

app = FastAPI(
    title="Platform Backend",
    description="支持 Bearer Token 认证的用户系统",
    version="1.0.0",
    debug=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加权限中间件
app.add_middleware(PermissionMiddleware)

# ✅ 挂载静态文件（让 /images/xxx 可访问）
app.mount("/images", StaticFiles(directory="uploads/images"), name="uploaded_images")

# 挂载路由
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(user_profile_admin_router, prefix="/api/v1")
app.include_router(credits_router, prefix="/api/v1")
app.include_router(user_management_router, prefix="/api/v1")
app.include_router(payment_order_router, prefix="/api/v1")
app.include_router(payment_router, prefix="/api/v1")
app.include_router(image_generation_router)
app.include_router(admin_image_generation_router, prefix="/api/v1/admin/image-generation")



@app.get("/", tags=["系统"])
def root():
    return {"message": "Swagger UI 已启用 Bearer Token 认证，请查看 /docs"}

@app.on_event("startup")
def startup_event():
    """应用启动时初始化定时任务"""
    init_scheduler()
    
    # 构建服务器基础URL
    if settings.SERVER_DOMAIN:
        base_url = f"http://{settings.SERVER_DOMAIN}"
    else:
        base_url = f"http://{settings.SERVER_HOST}:{settings.SERVER_PORT}"
    
    # 打印回调地址
    logging.info("=" * 60)
    logging.info("应用启动完成，定时任务已初始化")
    logging.info(f"服务器地址: {base_url}")
    logging.info(f"支付回调地址: {base_url}/api/v1/payment/notify")
    logging.info(f"生图回调地址: {base_url}/image-generation/callback/{{task_id}}")
    logging.info("=" * 60)

@app.on_event("shutdown")
def shutdown_event():
    """应用关闭时停止定时任务"""
    from core.scheduler import scheduler
    scheduler.shutdown()
    logging.info("应用关闭，定时任务已停止")