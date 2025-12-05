# backend/app/ai/intent_detector.py
"""
意图识别模块

使用轻量模型快速识别用户意图，支持：
- FILE_PARSE: 文件解析意图
- IMAGE_GENERATE: 图片生成意图
- NORMAL_CHAT: 普通对话意图
"""

import json
import logging
from typing import Dict, Any

from backend.app.ai.client import client

logger = logging.getLogger(__name__)


# 意图类型枚举
class IntentType:
    FILE_PARSE = "FILE_PARSE"
    IMAGE_GENERATE = "IMAGE_GENERATE"
    NORMAL_CHAT = "NORMAL_CHAT"


# 意图识别的系统提示词
INTENT_SYSTEM_PROMPT = """你是一个意图识别助手。你的任务是快速分析用户消息，判断用户的意图。

可能的意图类型：
1. FILE_PARSE - 用户想要解析文件（如：上传文档、解析PDF、分析文件内容等）
2. IMAGE_GENERATE - 用户想要生成图片或修改图片，包括：
   - 生成新图片（如：生成图片、画一张图、创建图像等）
   - 修改图片（如：改图、改背景、改颜色、继续改图、将图片改成...等）
   - 以图生图（如：根据这张图生成...、基于图片生成...等）
   - 任何涉及图片生成、图片修改、图片变换的请求
3. NORMAL_CHAT - 普通对话（其他所有情况），包括：
   - 询问图片内容（如：这张图片上面是什么、这是什么、分析这张图片等）
   - 问答、聊天、咨询等
   - 不涉及文件解析或图片生成/修改的对话

重要提示：
- 如果用户消息包含"改图"、"改背景"、"改颜色"、"继续改"、"将图片改成"等修改图片的词汇，应识别为 IMAGE_GENERATE
- 如果用户消息包含"生成图片"、"画图"、"创建图像"等生成图片的词汇，应识别为 IMAGE_GENERATE
- 如果用户消息只是询问图片内容（如："这张图片上面是什么"、"这是什么"、"分析这张图片"等），应识别为 NORMAL_CHAT（这是使用Chat API的视觉能力来分析图片，不是生成图片）
- 如果用户消息只是普通对话（如：询问、回答、聊天），应识别为 NORMAL_CHAT

请只返回JSON格式，格式如下：
{
    "intent": "FILE_PARSE" | "IMAGE_GENERATE" | "NORMAL_CHAT",
    "reason": "简要说明判断理由"
}

只返回JSON，不要其他内容。"""


def detect_intent(
    user_message: str, 
    has_files: bool = False,
    model: str = "doubao-seed-1-6-lite-251015",
    max_tokens: int = 200,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    使用轻量模型快速识别用户意图
    
    Args:
        user_message: 用户消息文本
        has_files: 是否包含文件上传（可能是图片）
        model: 意图识别模型名称，默认为轻量模型
        max_tokens: 最大token数，默认200
        temperature: 温度参数，默认0.1（低温度，更确定性的输出）
    
    Returns:
        Dict包含:
            - intent: 意图类型 (FILE_PARSE, IMAGE_GENERATE, NORMAL_CHAT)
            - reason: 判断理由
            - raw_response: 原始响应（用于调试）
    """
    logger.info(f"[意图识别] 开始识别用户意图: {user_message[:50]}...")
    
    # 如果用户上传了文件，需要判断是文件解析、以图生图还是普通对话（询问图片内容）
    if has_files:
        message_lower = user_message.lower()
        
        # 检查是否是询问图片内容的意图（应该使用Chat API的视觉能力）
        # 询问类关键词：什么、如何、为什么、分析、描述、识别、解释等
        inquiry_keywords = ["什么", "如何", "为什么", "分析", "描述", "识别", "解释", "这是", "上面", "里面", "包含", "显示"]
        has_inquiry_keyword = any(keyword in message_lower for keyword in inquiry_keywords)
        
        # 检查是否是图片生成/修改意图（需要明确的生成/修改动词）
        # 生成/修改类关键词：生成、画、创建、改、修改、变成、改为、改成、变换、制作
        image_generate_keywords = ["生成", "画", "创建", "改", "修改", "变成", "改为", "改成", "变换", "制作", "设计", "绘制"]
        has_image_generate_keyword = any(keyword in message_lower for keyword in image_generate_keywords)
        
        if has_inquiry_keyword and not has_image_generate_keyword:
            # 用户上传图片并询问内容，应该使用Chat API分析图片
            logger.info("[意图识别] 检测到文件上传且包含询问关键词，判断为普通对话（使用Chat API分析图片）")
            return {
                "intent": IntentType.NORMAL_CHAT,
                "reason": "检测到文件上传且包含询问关键词，用户想要分析图片内容",
                "raw_response": None
            }
        elif has_image_generate_keyword:
            # 用户上传图片并要求生成/修改图片，是以图生图
            logger.info("[意图识别] 检测到文件上传且包含图片生成关键词，判断为图片生成（以图生图）")
            return {
                "intent": IntentType.IMAGE_GENERATE,
                "reason": "检测到文件上传且包含图片生成关键词，可能是以图生图",
                "raw_response": None
            }
        else:
            # 默认判断为文件解析（可能是文档等）
            logger.info("[意图识别] 检测到文件上传，判断为文件解析")
            return {
                "intent": IntentType.FILE_PARSE,
                "reason": "检测到文件上传",
                "raw_response": None
            }
    
    try:
        # 使用轻量模型进行意图识别（关闭深度思考，快速响应）
        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            thinking={"type": "disabled"},  # 关闭深度思考，快速响应
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        response_text = completion.choices[0].message.content.strip()
        logger.debug(f"[意图识别] 模型原始响应: {response_text}")
        
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
            message_lower = user_message.lower()
            
            # 检查文件解析关键词
            if "file_parse" in response_lower or "文件" in response_text or "解析" in response_text:
                intent = IntentType.FILE_PARSE
            # 检查图片生成/修改关键词（包括用户消息中的关键词）
            elif ("image_generate" in response_lower or 
                  "图片" in response_text or 
                  "生成" in response_text or
                  "画" in message_lower or
                  "改图" in message_lower or
                  "改背景" in message_lower or
                  "改颜色" in message_lower or
                  "继续改" in message_lower or
                  "将图片" in message_lower or
                  "改成" in message_lower or
                  "改为" in message_lower):
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
        # 失败时降级为普通对话，确保系统稳定性
        return {
            "intent": IntentType.NORMAL_CHAT,
            "reason": f"识别失败，降级为普通对话: {str(e)}",
            "raw_response": None
        }


