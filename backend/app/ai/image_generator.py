# backend/app/ai/image_generator.py
"""
图片生成模块

使用 Seedream API 生成图片，支持同步处理。
"""

import logging
from typing import Dict, Any, Optional, List

from backend.app.ai.client import client

logger = logging.getLogger(__name__)


def generate_image(
    prompt: str, 
    model: str = "doubao-seedream-4-5-251128",
    size: str = "2K",
    response_format: str = "url",
    watermark: bool = True,
    sequential_image_generation: str = "disabled",
    image: Optional[str] = None  # 以图生图：图片URL或Base64
) -> Dict[str, Any]:
    """
    使用 Seedream API 生成图片（同步处理），支持以图生图
    
    Args:
        prompt: 图片生成提示词
        model: 图片生成模型，默认为 doubao-seedream-4-5-251128
        size: 图片尺寸，可选值: "2K", "1024x1024", "512x512" 等
        response_format: 响应格式，"url" 或 "b64_json"
        watermark: 是否添加水印
        sequential_image_generation: 顺序图片生成，"enabled" 或 "disabled"
        image: 以图生图的源图片URL或Base64字符串（可选）
    
    Returns:
        Dict包含:
            - success: 是否成功
            - image_url: 图片URL（如果成功且response_format="url"）
            - image_urls: 图片URL列表（如果生成多张图片）
            - image_data: 完整的响应数据
            - error: 错误信息（如果失败）
    """
    logger.info(f"[图片生成] [IMAGE] ========== 开始生成图片 ==========")
    logger.debug(f"[图片生成] [IMAGE] 提示词: {prompt[:100]}...")
    logger.debug(f"[图片生成] [IMAGE] 模型: {model}, 尺寸: {size}, 水印: {watermark}")
    if image:
        logger.info(f"[图片生成] [IMAGE] 以图生图模式，源图片: {image[:100]}...")
    
    try:
        # 使用 SDK 方法调用图片生成 API
        logger.debug(f"[图片生成] [IMAGE] 调用client.images.generate")
        
        # 构建API调用参数
        api_params = {
            "model": model,
            "prompt": prompt,
            "sequential_image_generation": sequential_image_generation,
            "response_format": response_format,
            "size": size,
            "stream": False,  # 同步处理，不使用流式
            "watermark": watermark
        }
        
        # 如果提供了图片，添加image参数（以图生图）
        if image:
            api_params["image"] = image
            logger.debug(f"[图片生成] [IMAGE] 添加image参数，以图生图模式")
        
        images_response = client.images.generate(**api_params)
        
        logger.info(f"[图片生成] [IMAGE] ✅ 生成成功")
        logger.debug(f"[图片生成] [IMAGE] 响应类型: {type(images_response)}")
        
        # 解析响应
        if hasattr(images_response, 'data') and len(images_response.data) > 0:
            logger.debug(f"[图片生成] [IMAGE] 响应包含 {len(images_response.data)} 个数据项")
            # 提取所有图片URL
            image_urls = []
            for index, item in enumerate(images_response.data):
                if hasattr(item, 'url') and item.url:
                    image_urls.append(item.url)
                    logger.debug(f"[图片生成] [IMAGE] 图片 {index} URL: {item.url[:100]}...")
            
            if image_urls:
                logger.info(f"[图片生成] [IMAGE] ✅ 成功提取 {len(image_urls)} 张图片URL")
                
                return {
                    "success": True,
                    "image_url": image_urls[0] if len(image_urls) == 1 else None,  # 单张图片时提供image_url
                    "image_urls": image_urls,  # 所有图片URL列表
                    "image_data": images_response.data,
                    "raw_response": str(images_response)
                }
            else:
                logger.warning(f"[图片生成] [IMAGE] ⚠️ 响应中未找到图片URL")
                return {
                    "success": False,
                    "error": "响应中未找到图片URL",
                    "raw_response": str(images_response)
                }
        else:
            logger.warning(f"[图片生成] [IMAGE] ⚠️ 响应中未找到图片数据")
            return {
                "success": False,
                "error": "响应中未找到图片数据",
                "raw_response": str(images_response)
            }
            
    except Exception as e:
        logger.error(f"[图片生成] [IMAGE] ❌ 生成失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "raw_response": None
        }


def generate_image_from_user_message(
    user_message: str,
    model: str = "doubao-seedream-4-5-251128",
    size: str = "2K",
    watermark: bool = True,
    image: Optional[str] = None  # 以图生图：图片URL或Base64
) -> Dict[str, Any]:
    """
    从用户消息中提取提示词并生成图片，支持以图生图
    
    这是一个便捷函数，直接使用用户消息作为图片生成提示词。
    在实际使用中，可能需要进一步处理用户消息（如提取关键词、优化提示词等）。
    
    Args:
        user_message: 用户消息文本
        model: 图片生成模型
        size: 图片尺寸
        watermark: 是否添加水印
        image: 以图生图的源图片URL或Base64字符串（可选）
    
    Returns:
        与 generate_image 相同的返回格式
    """
    # 简单处理：直接使用用户消息作为提示词
    # 可以后续优化：提取关键词、去除无关词汇等
    prompt = user_message.strip()
    
    # 移除常见的请求词汇，保留核心描述
    prompt = prompt.replace("生成", "").replace("画", "").replace("创建", "").replace("一张", "").replace("图片", "").strip()
    
    logger.info(f"[图片生成] 从用户消息提取提示词: {prompt[:50]}...")
    if image:
        logger.info(f"[图片生成] 以图生图模式，使用源图片")
    
    return generate_image(
        prompt=prompt,
        model=model,
        size=size,
        watermark=watermark,
        image=image
    )

