import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from dependencies import get_current_user, get_db
from models.user import User
from schemas.drawing import ImageGenerationRequest, ImageGenerationResponse
from services.image_generation import ImageGenerationService
from config.database import SessionLocal

router = APIRouter(prefix="/api/v1/image", tags=["image"])

@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(
    request: ImageGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    生成图片接口
    
    流程：
    1. 验证用户身份和请求参数
    2. 扣除用户积分（事务处理）
    3. 创建图片生成任务
    4. 异步调用模型Webhook接口
    """
    try:
        # 创建服务实例
        service = ImageGenerationService(db)
        
        # 创建任务（包含积分扣减的事务处理）
        task = service.create_task_with_transaction(request, current_user)
        
        # 获取Webhook URL
        webhook_url = task.meta_data.get("webhook_url") if task.meta_data else None
        if not webhook_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="未找到模型的Webhook配置"
            )
        
        # 【关键修改】添加异步任务到后台，不要传递 db 参数
        background_tasks.add_task(
            call_webhook_and_handle_response,
            task.id,
            webhook_url
            # 删掉 db 参数
        )
        
        # 返回任务信息
        return ImageGenerationResponse(
            task_id=task.id,
            status=task.status.value,
            message="任务创建成功，正在处理中"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成图片失败: {str(e)}"
        )

async def call_webhook_and_handle_response(task_id: str, webhook_url: str):
    """后台任务：调用Webhook并处理响应"""
    # 【关键修改】在这里创建新的数据库会话
    db = SessionLocal()
    try:
        service = ImageGenerationService(db)
        await service.call_webhook(task_id, webhook_url)
    finally:
        db.close() # 务必关闭

from pydantic import BaseModel
from typing import Optional

class CallbackRequest(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    error_message: Optional[str] = None

@router.post("/callback/{task_id}")
async def image_generation_callback(
    task_id: str,
    callback_data: CallbackRequest,
    db: Session = Depends(get_db)
):
    """
    图片生成结果回调接口
    
    用于接收模型服务的回调结果，更新任务状态
    """
    try:
        service = ImageGenerationService(db)
        
        if callback_data.success:
            if not callback_data.image_url and not callback_data.image_base64:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="成功回调必须提供image_url或image_base64"
                )
            
            result = await service.handle_task_success(
                task_id, 
                callback_data.image_url, 
                callback_data.image_base64
            )
            if result:
                return {"message": "任务状态更新成功", "status": "success"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )
        else:
            if not callback_data.error_message:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="失败回调必须提供error_message"
                )
            
            result = await service.handle_task_failure(task_id, callback_data.error_message)
            if result:
                return {"message": "任务状态更新成功", "status": "failed"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理回调失败: {str(e)}"
        )

@router.delete("/task/{task_id}")
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除图片生成任务"""
    try:
        from crud.image_generation_task import get_image_generation_task, delete_image_generation_task
        
        task = get_image_generation_task(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 验证任务所有权
        if task.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此任务"
            )
        
        # 删除任务
        success = delete_image_generation_task(db, task_id, current_user.id)
        if success:
            return {"message": "任务删除成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除任务失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败: {str(e)}"
        )

@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取任务状态"""
    try:
        from crud.image_generation_task import get_image_generation_task
        
        task = get_image_generation_task(db, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 验证任务所有权
        if task.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此任务"
            )
        
        return {
            "task_id": task.id,
            "status": task.status.value,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "image_url": task.image_url,
            "error_message": task.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务状态失败: {str(e)}"
        )

@router.get("/history")
async def get_user_generation_history(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的图片生成历史记录"""
    try:
        from crud.image_generation_task import get_user_image_generation_tasks
        
        tasks, total = get_user_image_generation_tasks(
            db, 
            current_user.id, 
            skip=skip, 
            limit=limit
        )
        
        # 转换为响应格式
        history = []
        for task in tasks:
            history.append({
                "id": task.id,
                "model": task.model,
                "prompt": task.prompt,
                "size": task.size,
                "status": task.status.value,
                "image_url": task.image_url,
                "error_message": task.error_message,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "credits_used": task.credits_used
            })
        
        return {
            "history": history,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取创作历史失败: {str(e)}"
        )