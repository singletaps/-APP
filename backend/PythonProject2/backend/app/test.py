# test.py
"""
测试脚本：测试意图识别 API 和图片生成 API

意图识别模型：doubao-seed-1-6-lite-251015
图片生成模型：doubao-seedream-4-5-251128

使用方法：
1. 确保已安装依赖：
   pip install volcenginesdkarkruntime

2. 确保 backend/app/ai/client.py 中配置了正确的 API Key 和 Base URL

3. 运行测试：
   cd E:\PythonProject2\backend\app
   python test.py

测试内容：
- 测试1: 意图识别功能 - 测试各种用户消息的意图识别准确性
- 测试2: 图片生成功能 - 测试图片生成 API 的调用
- 测试3: 集成流程 - 测试完整的意图识别 -> 图片生成流程
"""

import json
import logging
from typing import Dict, Any, Optional
from backend.app.ai.client import client

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 意图类型枚举
class IntentType:
    FILE_PARSE = "FILE_PARSE"
    IMAGE_GENERATE = "IMAGE_GENERATE"
    NORMAL_CHAT = "NORMAL_CHAT"


def detect_intent(user_message: str, has_files: bool = False) -> Dict[str, Any]:
    """
    使用轻量模型快速识别用户意图
    
    Args:
        user_message: 用户消息文本
        has_files: 是否包含文件上传
    
    Returns:
        Dict包含:
            - intent: 意图类型 (FILE_PARSE, IMAGE_GENERATE, NORMAL_CHAT)
            - reason: 判断理由
            - raw_response: 原始响应（用于调试）
    """
    logger.info(f"[意图识别] 开始识别用户意图: {user_message[:50]}...")
    
    # 意图识别的系统提示词
    intent_system_prompt = """你是一个意图识别助手。你的任务是快速分析用户消息，判断用户的意图。

可能的意图类型：
1. FILE_PARSE - 用户想要解析文件（如：上传文档、解析PDF、分析文件内容等）
2. IMAGE_GENERATE - 用户想要生成图片（如：生成图片、画一张图、创建图像等）
3. NORMAL_CHAT - 普通对话（其他所有情况）

请只返回JSON格式，格式如下：
{
    "intent": "FILE_PARSE" | "IMAGE_GENERATE" | "NORMAL_CHAT",
    "reason": "简要说明判断理由"
}

只返回JSON，不要其他内容。"""

    # 如果用户上传了文件，优先判断为文件解析
    if has_files:
        logger.info("[意图识别] 检测到文件上传，直接判断为文件解析")
        return {
            "intent": IntentType.FILE_PARSE,
            "reason": "检测到文件上传",
            "raw_response": None
        }
    
    try:
        # 使用轻量模型进行意图识别（关闭深度思考，快速响应）
        messages = [
            {"role": "system", "content": intent_system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-lite-251015",
            messages=messages,
            thinking={"type": "disabled"},  # 关闭深度思考，快速响应
            max_tokens=200,  # 意图识别不需要太多token
            temperature=0.1,  # 低温度，更确定性的输出
        )
        
        response_text = completion.choices[0].message.content.strip()
        logger.info(f"[意图识别] 模型原始响应: {response_text}")
        
        # 尝试解析JSON响应
        try:
            # 提取JSON部分（可能包含markdown代码块）
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            intent_result = json.loads(response_text)
            intent = intent_result.get("intent", IntentType.NORMAL_CHAT)
            reason = intent_result.get("reason", "")
            
            logger.info(f"[意图识别] ✅ 识别结果: {intent}, 理由: {reason}")
            
            return {
                "intent": intent,
                "reason": reason,
                "raw_response": response_text
            }
        except json.JSONDecodeError:
            # JSON解析失败，尝试从文本中提取意图关键词
            logger.warning(f"[意图识别] JSON解析失败，尝试关键词匹配: {response_text}")
            response_lower = response_text.lower()
            
            if "file_parse" in response_lower or "文件" in response_text or "解析" in response_text:
                intent = IntentType.FILE_PARSE
            elif "image_generate" in response_lower or "图片" in response_text or "生成" in response_text:
                intent = IntentType.IMAGE_GENERATE
            else:
                intent = IntentType.NORMAL_CHAT
            
            logger.info(f"[意图识别] ✅ 关键词匹配结果: {intent}")
            return {
                "intent": intent,
                "reason": "关键词匹配",
                "raw_response": response_text
            }
            
    except Exception as e:
        logger.error(f"[意图识别] ❌ 识别失败: {e}", exc_info=True)
        # 失败时降级为普通对话
        return {
            "intent": IntentType.NORMAL_CHAT,
            "reason": f"识别失败，降级为普通对话: {str(e)}",
            "raw_response": None
        }


def generate_image(
    prompt: str, 
    model: str = "doubao-seedream-4-5-251128",
    size: str = "2K",
    response_format: str = "url",
    watermark: bool = True
) -> Dict[str, Any]:
    """
    使用 Seedream API 生成图片（使用正确的 SDK 方法）
    
    Args:
        prompt: 图片生成提示词
        model: 图片生成模型，默认为 doubao-seedream-4-5-251128
        size: 图片尺寸，可选值: "2K", "1024x1024", "512x512" 等
        response_format: 响应格式，"url" 或 "b64_json"
        watermark: 是否添加水印
    
    Returns:
        Dict包含:
            - success: 是否成功
            - image_url: 图片URL（如果成功）
            - image_data: 完整的响应数据
            - error: 错误信息（如果失败）
    """
    logger.info(f"[图片生成] 开始生成图片，提示词: {prompt[:50]}...")
    
    try:
        # 使用正确的 SDK 方法调用图片生成 API
        images_response = client.images.generate(
            model=model,
            prompt=prompt,
            sequential_image_generation="disabled",
            response_format=response_format,
            size=size,
            stream=False,
            watermark=watermark
        )
        
        logger.info(f"[图片生成] ✅ 生成成功")
        logger.info(f"[图片生成] 响应类型: {type(images_response)}")
        
        # 解析响应
        if hasattr(images_response, 'data') and len(images_response.data) > 0:
            image_url = images_response.data[0].url
            logger.info(f"[图片生成] 图片URL: {image_url}")
            
            return {
                "success": True,
                "image_url": image_url,
                "image_data": images_response.data[0],
                "raw_response": str(images_response)
            }
        else:
            logger.warning(f"[图片生成] 响应中未找到图片数据")
            return {
                "success": False,
                "error": "响应中未找到图片数据",
                "raw_response": str(images_response)
            }
            
    except Exception as e:
        logger.error(f"[图片生成] ❌ 生成失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "raw_response": None
        }


def test_intent_detection():
    """测试意图识别功能"""
    print("\n" + "="*60)
    print("测试1: 意图识别功能")
    print("="*60)
    
    test_cases = [
        ("请帮我解析这个PDF文件", False),
        ("生成一张日落的图片", False),
        ("上传文档并分析内容", False),
        ("画一张猫的图片", False),
        ("今天天气怎么样？", False),
        ("你好", False),
    ]
    
    for user_message, has_files in test_cases:
        print(f"\n用户消息: {user_message}")
        result = detect_intent(user_message, has_files)
        print(f"识别结果: {result['intent']}")
        print(f"判断理由: {result.get('reason', 'N/A')}")
        print("-" * 60)


def test_image_generation():
    """测试图片生成功能"""
    print("\n" + "="*60)
    print("测试2: 图片生成功能")
    print("="*60)
    
    test_prompts = [
        "一只可爱的小猫坐在窗台上",
        "美丽的日落风景，有山有海",
    ]
    
    for prompt in test_prompts:
        print(f"\n生成提示词: {prompt}")
        print("正在生成图片，请耐心等待...")
        
        result = generate_image(prompt)
        
        if result["success"]:
            print(f"✅ 生成成功!")
            print(f"图片URL: {result.get('image_url', 'N/A')}")
        else:
            print(f"❌ 生成失败: {result.get('error', '未知错误')}")
        
        print("-" * 60)


def test_integrated_flow():
    """测试集成流程：意图识别 -> 图片生成"""
    print("\n" + "="*60)
    print("测试3: 集成流程（意图识别 -> 图片生成）")
    print("="*60)
    
    test_messages = [
        "请生成一张日落的图片",
        "画一只可爱的小猫",
        "今天天气怎么样？",  # 这个应该识别为普通对话
    ]
    
    for user_message in test_messages:
        print(f"\n用户消息: {user_message}")
        
        # 步骤1: 意图识别
        intent_result = detect_intent(user_message)
        intent = intent_result["intent"]
        print(f"意图识别结果: {intent}")
        
        # 步骤2: 根据意图路由
        if intent == IntentType.IMAGE_GENERATE:
            print("→ 检测到图片生成意图，调用图片生成API...")
            print("正在生成图片，请耐心等待...")
            image_result = generate_image(user_message)
            
            if image_result["success"]:
                print(f"✅ 图片生成成功!")
                print(f"图片URL: {image_result.get('image_url', 'N/A')}")
            else:
                print(f"❌ 图片生成失败: {image_result.get('error', '未知错误')}")
        elif intent == IntentType.FILE_PARSE:
            print("→ 检测到文件解析意图，应调用文件解析API（未实现）")
        else:
            print("→ 检测到普通对话意图，应调用Chat API（现有逻辑）")
        
        print("-" * 60)


if __name__ == "__main__":
    print("="*60)
    print("意图识别与图片生成 API 测试")
    print("="*60)
    
    try:
        # 测试1: 意图识别
        test_intent_detection()
        
        # 测试2: 图片生成
        test_image_generation()
        
        # 测试3: 集成流程
        test_integrated_flow()
        
        print("\n" + "="*60)
        print("所有测试完成!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)
        print(f"\n❌ 测试失败: {e}")
