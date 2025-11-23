from fastapi import APIRouter, File, UploadFile, HTTPException, Form
import httpx
import os
import uuid
from typing import Optional
import urllib.parse

router = APIRouter(tags=["文件上传"])

# 第三方图片上传服务配置
THIRD_PARTY_UPLOAD_URL = "https://s3.mingder.space/api/images/upload"

@router.post("/upload-image/")
async def upload_image(
    file: UploadFile = File(...),
    encodingMethod: Optional[str] = Form(None),
    originalFilename: Optional[str] = Form(None)
):
    """
    使用第三方服务上传图片
    """
    # 1. 检查文件类型（仅允许图片）
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅允许上传图片文件！")

    # 2. 检查文件格式
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(status_code=400, detail="不支持的图片格式！")
    
    # 3. 准备上传到第三方服务的数据
    file_content = await file.read()
    
    # 处理文件名编码问题
    # 使用原始文件名或提供默认值
    raw_filename = originalFilename or file.filename
    
    # 确保文件名是有效的UTF-8编码
    try:
        # 如果文件名已经是字符串，确保它是有效的UTF-8
        if isinstance(raw_filename, str):
            filename = raw_filename
        else:
            # 如果是字节，尝试解码为UTF-8
            filename = raw_filename.decode('utf-8')
    except (UnicodeDecodeError, AttributeError):
        # 如果解码失败，使用UUID作为文件名，保留原始扩展名
        base_ext = os.path.splitext(raw_filename if isinstance(raw_filename, str) else str(raw_filename))[1]
        filename = f"{uuid.uuid4()}{base_ext}"
    
    # 如果文件名为空或只有扩展名，生成一个UUID文件名
    if not filename or filename.startswith('.'):
        base_ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{base_ext}"
    
    # 4. 调用第三方上传服务
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                'image': (filename, file_content, file.content_type)
            }
            
            # 添加可选参数
            data = {}
            if encodingMethod:
                data['encodingMethod'] = encodingMethod
            
            response = await client.post(
                THIRD_PARTY_UPLOAD_URL,
                files=files,
                data=data
            )
            
            # 接受200或201状态码作为成功响应
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"第三方上传服务错误: {response.text}"
                )
            
            result = response.json()
            
            # 5. 检查第三方服务响应
            if not result.get("success"):
                raise HTTPException(
                    status_code=400, 
                    detail=f"上传失败: {result.get('message', '未知错误')}"
                )
            
            # 6. 返回符合当前API格式的响应
            upload_data = result.get("data", {})
            return {
                "success": True,
                "message": "图片上传成功",
                "data": {
                    "id": upload_data.get("id"),
                    "filename": upload_data.get("filename"),
                    "originalName": upload_data.get("originalName"),
                    "url": upload_data.get("url"),
                    "fileSize": upload_data.get("fileSize"),
                    "mimeType": upload_data.get("mimeType"),
                    "uploadTime": upload_data.get("uploadTime"),
                    "isDuplicate": upload_data.get("isDuplicate", False),
                    "base64": upload_data.get("base64")
                }
            }
            
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"上传请求失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传过程中发生错误: {str(e)}")
