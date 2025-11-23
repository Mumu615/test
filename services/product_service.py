"""
产品配置服务
用于根据产品ID查询价格和产品信息
"""

from typing import Dict, Any, Optional
from decimal import Decimal
import json
import os
from fastapi import HTTPException, status

# 产品配置映射表
PRODUCT_CONFIG = {
    "credits_500": {
        "price": Decimal("0.99"),
        "credits": 500,
        "membership": {
            "level": "advanced",
            "days": 30
        },
        "name": "内测专享包",
        "description": "内测用户专享，超值体验高级功能"
    },
    "credits_150": {
        "price": Decimal("2.90"),
        "credits": 150,
        "name": "新手体验包",
        "description": "体验全部高级模型，低门槛开启创作"
    },
    "credits_1200": {
        "price": Decimal("18.90"),
        "credits": 1200,
        "membership": {
            "level": "advanced",
            "days": 30
        },
        "name": "创作入门包",
        "description": "超高性价比，适合轻度创作者"
    },
    "credits_2400": {
        "price": Decimal("29.90"),
        "credits": 2400,
        "membership": {
            "level": "advanced",
            "days": 30
        },
        "name": "轻量月包",
        "description": "月度主力套餐，积分单价更低"
    },
    "credits_5000": {
        "price": Decimal("68.00"),
        "credits": 5000,
        "membership": {
            "level": "professional",
            "days": 30
        },
        "name": "专业月包",
        "description": "重度创作首选，海量额度随心用"
    },
    "credits_16000": {
        "price": Decimal("188.00"),
        "credits": 16000,
        "membership": {
            "level": "professional",
            "days": 90
        },
        "name": "专业季度包",
        "description": "超长有效期，全年最低单价"
    }
}

def get_product_by_id(product_id: str) -> Dict[str, Any]:
    """
    根据产品ID获取产品信息
    
    Args:
        product_id: 产品ID
        
    Returns:
        产品信息字典
        
    Raises:
        HTTPException: 如果产品ID不存在
    """
    product = PRODUCT_CONFIG.get(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的产品ID: {product_id}"
        )
    
    # 返回产品信息的副本，防止外部修改
    return product.copy()

def get_product_price(product_id: str) -> Decimal:
    """
    根据产品ID获取产品价格
    
    Args:
        product_id: 产品ID
        
    Returns:
        产品价格
        
    Raises:
        HTTPException: 如果产品ID不存在
    """
    product = get_product_by_id(product_id)
    return product["price"]

def get_all_products() -> Dict[str, Dict[str, Any]]:
    """
    获取所有产品配置
    
    Returns:
        所有产品配置的字典
    """
    return PRODUCT_CONFIG