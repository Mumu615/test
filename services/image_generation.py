import json
import httpx
import asyncio
import os
import base64
from typing import Optional, Dict, Any, List
from functools import lru_cache
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models.image_generation_task import ImageGenerationTask, TaskStatus
from schemas.drawing import ImageGenerationRequest, ImageGenerationTaskCreate, ReferenceImage
from crud.image_generation_task import create_image_generation_task, update_task_status
from crud.credit_transaction import consume_credits, add_credits
from crud.user_profile import get_user_profile_or_create
from models.user import User
import logging

logger = logging.getLogger(__name__)

# 使用缓存避免每次请求都读取文件
@lru_cache()
def load_models_config():
    try:
        with open('config/image_models.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("模型配置文件 config/image_models.json 未找到")
        return {}
    except json.JSONDecodeError:
        logger.error("模型配置文件格式错误")
        return {}

class ImageGenerationService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """获取模型配置"""
        models = load_models_config()
        
        if not models:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统配置错误：无法加载模型配置"
            )

        if model_name not in models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的模型: {model_name}"
            )
        
        return models[model_name]
    
    def validate_request(self, request: ImageGenerationRequest, user: User) -> Dict[str, Any]:
        """验证请求参数"""
        # 获取模型配置
        model_config = self.get_model_config(request.model)
        
        # 获取支持的尺寸和比例
        size_map = model_config.get("sizeMap", {})
        supported_ratios = model_config.get("supportedRatios", [])
        
        # 确定模型类型：支持比例选择还是尺寸选择
        is_ratio_based = not bool(size_map) and bool(supported_ratios)
        
        final_size = None

        if is_ratio_based:
            # 比例选择模式（如 nanobanana）
            if request.size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"模型 {request.model} 仅支持比例选择，不支持尺寸选择，请使用 aspect_ratio 参数"
                )
            
            # 验证比例是否在支持的比例列表中
            if request.aspect_ratio not in supported_ratios:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"模型 {request.model} 不支持比例 {request.aspect_ratio}，支持的比例: {supported_ratios}"
                )
            
            final_size = request.aspect_ratio  # 对于比例选择模型，直接存储比例
            
        else:
            # 尺寸选择模式（如 seedream-4）
            final_size = request.size
            if final_size is None and request.aspect_ratio:
                # 如果没有提供尺寸但提供了比例，使用比例对应的默认尺寸
                if request.aspect_ratio in size_map:
                    final_size = size_map[request.aspect_ratio]
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"模型 {request.model} 不支持比例 {request.aspect_ratio}，支持的比例: {supported_ratios}"
                    )
            elif final_size is not None:
                # 如果提供了尺寸，验证是否在支持的尺寸列表中
                if final_size not in size_map.values():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"模型 {request.model} 不支持尺寸 {final_size}，支持的尺寸: {list(size_map.values())}"
                    )
            else:
                # 如果既没有提供尺寸也没有提供比例，使用默认比例1:1
                if "1:1" in size_map:
                    final_size = size_map["1:1"]
                else:
                    # 如果1:1不可用，使用第一个可用的尺寸
                    if size_map:
                        final_size = list(size_map.values())[0]
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"模型 {request.model} 没有可用的尺寸配置"
                        )
        
        # 验证参考图数量是否超限
        max_ref_images = model_config.get("maxRefImages", 0)
        if request.reference_images and len(request.reference_images) > max_ref_images:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模型 {request.model} 最多支持 {max_ref_images} 张参考图"
            )
        
        # 获取用户积分余额
        profile = get_user_profile_or_create(self.db, user.id)
        credits_needed = model_config.get("credits", 0)
        
        if profile.credits < credits_needed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"积分不足，当前积分: {profile.credits}，需要积分: {credits_needed}"
            )
        
        # 确保 final_size 不为 None，防止后续 Pydantic 验证失败
        if final_size is None:
            final_size = request.aspect_ratio or "1024x1024"

        return {
            "model_config": model_config,
            "credits_needed": credits_needed,
            "current_credits": profile.credits,
            "final_size": final_size,
            "is_ratio_based": is_ratio_based
        }
    
    def create_task_with_transaction(
        self, 
        request: ImageGenerationRequest, 
        user: User
    ) -> ImageGenerationTask:
        """创建图片生成任务（包含积分扣减的事务处理）"""
        # 验证请求
        validation_result = self.validate_request(request, user)
        model_config = validation_result["model_config"]
        credits_needed = validation_result["credits_needed"]
        final_size = validation_result["final_size"]
        
        # 【修复】转换参考图格式
        # request.reference_images 是 List[str] (Pydantic model definition)
        # ImageGenerationTaskCreate.reference_images 需要 List[Dict]
        formatted_ref_images = []
        if request.reference_images:
            for img_url in request.reference_images:
                # 简单的构造字典，确保符合 Schema
                formatted_ref_images.append({"url": img_url, "name": "reference_image"})
        
        try:
            # 开始事务
            # 1. 扣除积分 - 【关键修复】传入 commit=False
            consume_credits(
                db=self.db,
                user_id=user.id,
                amount=credits_needed,
                source="drawing_generation",
                commit=False  # 不要立即提交，等待任务创建成功
            )
            
            # 2. 创建任务
            task_create = ImageGenerationTaskCreate(
                user_id=user.id,
                model=request.model,
                prompt=request.prompt,
                size=str(final_size), # 【修复】确保是字符串
                credits_used=credits_needed,
                reference_images=formatted_ref_images, # 【修复】使用转换后的列表
                meta_data={"webhook_url": model_config.get("webhookUrl")}
            )
            
            # 注意：create_image_generation_task 内部可能也执行了 commit，
            # 如果可以，最好也让它支持 commit=False，或者依靠下面的 update 来提交
            task = create_image_generation_task(self.db, task_create)
            
            # 3. 更新任务状态为处理中
            # 这里会触发 commit，提交之前的积分扣减和任务创建
            update_task_status(self.db, task.id, TaskStatus.PROCESSING)
            
            return task
            
        except Exception as e:
            # 如果事务失败，回滚（包括积分扣减）
            self.db.rollback()
            logger.error(f"创建任务失败，事务回滚: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建任务失败: {str(e)}"
            )
    
    async def call_webhook(self, task_id: str, webhook_url: str) -> bool:
        """异步调用Webhook接口"""
        try:
            # 获取任务详情
            task = self.db.query(ImageGenerationTask).filter(
                ImageGenerationTask.id == task_id
            ).first()
            
            if not task:
                return False
            
            # 获取模型配置
            model_config = self.get_model_config(task.model)
            size_map = model_config.get("sizeMap", {})
            supported_ratios = model_config.get("supportedRatios", [])
            
            # 确定模型类型：支持比例选择还是尺寸选择
            is_ratio_based = not bool(size_map) and bool(supported_ratios)
            
            # 准备请求数据
            payload = {
                "task_id": task.id,
                "model": task.model,
                "prompt": task.prompt,
                "reference_images": [img["url"] for img in task.reference_images] if task.reference_images else []
            }
            
            # 根据模型类型添加不同的参数
            if is_ratio_based:
                # 比例选择模型，传递比例
                payload["aspect_ratio"] = task.size
            else:
                # 尺寸选择模型，传递尺寸
                payload["size"] = task.size
            
            # 发送请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return True
                else:
                    # 如果调用失败，更新任务状态为失败并退还积分
                    await self.handle_task_failure(
                        task_id, 
                        f"Webhook调用失败: {response.status_code} {response.text}"
                    )
                    return False
                    
        except Exception as e:
            # 如果调用失败，更新任务状态为失败并退还积分
            await self.handle_task_failure(
                task_id, 
                f"Webhook调用异常: {str(e)}"
            )
            return False
    
    async def handle_task_success(self, task_id: str, image_url: str = None, image_base64: str = None) -> bool:
        """处理任务成功回调"""
        try:
            # 获取任务信息
            task = self.db.query(ImageGenerationTask).filter(
                ImageGenerationTask.id == task_id
            ).first()
            
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            # 获取模型配置
            try:
                model_config = self.get_model_config(task.model)
                size_map = model_config.get("sizeMap", {})
                supported_ratios = model_config.get("supportedRatios", [])
                # 确定模型类型：支持比例选择还是尺寸选择
                is_ratio_based = not bool(size_map) and bool(supported_ratios)
            except:
                # 如果获取配置失败，默认当作普通处理
                is_ratio_based = False
            
            # 处理图片数据
            final_image_url = image_url
            error_message = None
            
            if image_url:
                # 对于所有模型，如果提供了URL，都将图片上传到第三方服务
                try:
                    logger.info(f"开始下载并上传图片，原始URL: {image_url}")
                    # 调用上传接口
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        # 下载原始图片
                        image_response = await client.get(image_url)
                        if image_response.status_code == 200:
                            image_data = image_response.content
                            # 生成文件名
                            filename = f"{task.model}_{task_id}.jpg"
                            
                            # 上传到第三方服务
                            files = {
                                'file': (filename, image_data, 'image/jpeg')
                            }
                            upload_response = await client.post(
                                "http://localhost:8000/api/v1/upload-image/",
                                files=files
                            )
                            
                            if upload_response.status_code == 200:
                                result = upload_response.json()
                                if result.get("success"):
                                    # 获取上传后的 URL
                                    final_image_url = result.get("data", {}).get("url")
                                    logger.info(f"图片上传成功，新URL: {final_image_url}")
                                else:
                                    error_message = f"上传失败: {result.get('message', '未知错误')}"
                                    logger.error(error_message)
                            else:
                                error_message = f"上传请求失败: {upload_response.status_code} {upload_response.text}"
                                logger.error(error_message)
                        else:
                            error_message = f"下载原始图片失败: {image_response.status_code}"
                            logger.error(error_message)
                            
                except Exception as e:
                    error_message = f"下载并上传图片异常: {str(e)}"
                    logger.error(error_message)
                    # 如果上传失败，仍然使用原始的 image_url
                    pass
            elif is_ratio_based and image_base64:
                # 对于比例选择模型，如果提供了 base64 数据
                try:
                    logger.info(f"开始处理base64图片数据，任务ID: {task_id}")
                    # 移除可能的数据前缀
                    if "base64," in image_base64:
                        image_base64 = image_base64.split("base64,")[1]
                    
                    # 解码 base64 数据
                    image_data = base64.b64decode(image_base64)
                    
                    # 生成文件名
                    filename = f"{task.model}_{task_id}.jpg"
                    
                    # 调用上传接口
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        files = {
                            'file': (filename, image_data, 'image/jpeg')
                        }
                        response = await client.post(
                            "http://localhost:8000/api/v1/upload-image/",
                            files=files
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                # 获取上传后的 URL
                                final_image_url = result.get("data", {}).get("url")
                                logger.info(f"base64图片上传成功，新URL: {final_image_url}")
                            else:
                                error_message = f"上传失败: {result.get('message', '未知错误')}"
                                logger.error(error_message)
                        else:
                            error_message = f"上传请求失败: {response.status_code} {response.text}"
                            logger.error(error_message)
                            
                except Exception as e:
                    error_message = f"上传 base64 图片异常: {str(e)}"
                    logger.error(error_message)
                    pass
            
            # 更新任务状态
            if error_message:
                # 如果有错误，但仍有原始URL，标记为成功但记录错误信息
                if final_image_url:
                    task = update_task_status(
                        self.db, 
                        task_id, 
                        TaskStatus.SUCCESS, 
                        image_url=final_image_url
                    )
                    # 更新错误信息
                    task.error_message = error_message
                    self.db.commit()
                    logger.warning(f"任务完成但有警告，任务ID: {task_id}, 警告信息: {error_message}")
                else:
                    # 如果没有可用的URL，标记为失败
                    task = update_task_status(
                        self.db, 
                        task_id, 
                        TaskStatus.FAILED, 
                        error_message=f"图片处理失败: {error_message}"
                    )
                    # 退还积分
                    add_credits(
                        db=self.db,
                        user_id=task.user_id,
                        amount=task.credits_used,
                        source="generation_refund"
                    )
                    logger.error(f"任务失败，已退还积分，任务ID: {task_id}, 错误信息: {error_message}")
            else:
                # 没有错误，正常更新
                task = update_task_status(
                    self.db, 
                    task_id, 
                    TaskStatus.SUCCESS, 
                    image_url=final_image_url
                )
                logger.info(f"任务成功完成，任务ID: {task_id}, 图片URL: {final_image_url}")
            
            return task is not None
        except Exception as e:
            error_message = f"处理任务成功回调异常: {str(e)}"
            logger.error(error_message)
            # 尝试更新任务状态为失败
            try:
                task = self.db.query(ImageGenerationTask).filter(
                    ImageGenerationTask.id == task_id
                ).first()
                if task:
                    update_task_status(
                        self.db, 
                        task_id, 
                        TaskStatus.FAILED, 
                        error_message=error_message
                    )
                    # 退还积分
                    add_credits(
                        db=self.db,
                        user_id=task.user_id,
                        amount=task.credits_used,
                        source="generation_refund"
                    )
            except:
                pass
            return False
    
    async def handle_task_failure(self, task_id: str, error_message: str) -> bool:
        """处理任务失败回调（退还积分）"""
        try:
            logger.info(f"开始处理任务失败回调，任务ID: {task_id}, 错误信息: {error_message}")
            
            # 获取任务信息
            task = self.db.query(ImageGenerationTask).filter(
                ImageGenerationTask.id == task_id
            ).first()
            
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            logger.info(f"找到任务，用户ID: {task.user_id}, 积分使用量: {task.credits_used}")
            
            # 更新任务状态为失败
            update_task_status(
                self.db, 
                task_id, 
                TaskStatus.FAILED, 
                error_message=error_message
            )
            
            # 退还积分
            add_credits(
                db=self.db,
                user_id=task.user_id,
                amount=task.credits_used,
                source="generation_refund"
            )
            
            logger.info(f"任务失败处理完成，已退还积分，任务ID: {task_id}")
            return True
            
        except Exception as e:
            error_msg = f"处理任务失败回调异常: {str(e)}"
            logger.error(error_msg)
            try:
                task = self.db.query(ImageGenerationTask).filter(
                    ImageGenerationTask.id == task_id
                ).first()
                if task:
                    task.error_message = error_msg
                    self.db.commit()
            except:
                pass
            return False