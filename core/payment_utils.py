"""
支付相关工具函数
"""
import hashlib
import uuid
from typing import Dict, Any, Optional
import requests
from datetime import datetime
from schemas.payment_order import ZPayResponse
from core.config import settings

# 商户密钥
MERCHANT_KEY = settings.ZPAY_API_KEY or "your_merchant_key_here"


def generate_order_no() -> str:
    """
    生成唯一的商户订单号
    格式: ORD + 年月日时分秒 + 4位随机数
    例如: ORD202310281530221234
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d%H%M%S")
    random_str = str(uuid.uuid4())[:4]
    return f"ORD{date_str}{random_str}"


def generate_md5_sign(params: Dict[str, Any], merchant_key: str) -> str:
    """
    生成MD5签名 - ZPAY签名算法
    
    Args:
        params: 需要签名的参数字典
        merchant_key: 商户密钥
        
    Returns:
        str: MD5签名（小写）
    """
    # 1. 过滤空值参数和sign、sign_type
    filtered_params = {}
    for key, value in params.items():
        if key not in ['sign', 'sign_type'] and value is not None and value != '':
            filtered_params[key] = value
    
    # 2. 按参数名ASCII码从小到大排序（a-z）
    sorted_params = sorted(filtered_params.items(), key=lambda x: x[0])
    
    # 3. 拼接成 key1=value1&key2=value2 的字符串，参数值不进行URL编码
    param_str = '&'.join([f"{key}={value}" for key, value in sorted_params])
    
    # 4. 将拼接好的字符串与商户密钥KEY进行MD5加密
    # 注意：是将字符串与KEY拼接后进行MD5，不是在字符串末尾附加&key=
    sign_str = f"{param_str}{merchant_key}"
    
    # 5. 进行MD5运算，并将结果转为小写
    md5_hash = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    return md5_hash.lower()


def call_zpay_api(
    api_url: str,
    params: Dict[str, Any],
    merchant_key: str,
    timeout: int = 30
) -> tuple[Optional[ZPayResponse], Optional[Dict[str, Any]]]:
    """
    调用ZPAY支付接口
    
    Args:
        api_url: ZPAY支付接口URL
        params: 请求参数
        merchant_key: 商户密钥
        timeout: 请求超时时间（秒）
        
    Returns:
        tuple: (ZPayResponse对象, 原始响应数据)
              成功时返回(ZPayResponse对象, 原始响应数据)
              失败时返回(None, 原始响应数据)或(None, None)
    """
    try:
        # 生成签名
        sign = generate_md5_sign(params, merchant_key)
        params['sign'] = sign
        
        # 发送POST请求，使用form-data格式
        response = requests.post(
            api_url,
            data=params,
            timeout=timeout,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        # 检查响应状态码
        response.raise_for_status()
        
        # 解析响应JSON
        response_data = response.json()
        print(f"ZPAY原始响应: {response_data}")
        
        # 转换为ZPayResponse对象
        if isinstance(response_data, dict):
            # 处理code字段，如果是字符串则转换为整数（如果是数字字符串）
            if 'code' in response_data and isinstance(response_data['code'], str):
                try:
                    response_data['code'] = int(response_data['code'])
                except ValueError:
                    # 如果无法转换为整数，保持原样
                    pass
            
            try:
                # 创建ZPayResponse对象，只使用模型中定义的字段
                filtered_data = {}
                for key in ZPayResponse.__fields__:
                    if key in response_data:
                        filtered_data[key] = response_data[key]
                
                zpay_response = ZPayResponse(**filtered_data)
                return zpay_response, response_data
            except Exception as e:
                print(f"创建ZPayResponse对象失败: {str(e)}, 响应数据: {response_data}")
                # 返回原始响应数据，不返回None
                return None, response_data
        else:
            print(f"ZPAY响应格式异常: {response_data}")
            return None, response_data
        
    except requests.exceptions.RequestException as e:
        print(f"调用ZPAY接口异常: {str(e)}")
        return None, None
    except Exception as e:
        print(f"处理ZPAY响应异常: {str(e)}")
        return None, None


def verify_zpay_callback(params: Dict[str, Any], merchant_key: str) -> bool:
    """
    验证ZPAY回调通知的签名
    
    Args:
        params: 回调参数
        merchant_key: 商户密钥
        
    Returns:
        bool: 签名是否有效
    """
    # 获取回调中的签名
    received_sign = params.get('sign', '')
    if not received_sign:
        return False
    
    # 生成签名
    calculated_sign = generate_md5_sign(params, merchant_key)
    
    # 比较签名
    return received_sign.lower() == calculated_sign.lower()