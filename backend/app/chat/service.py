# backend/app/chat/service.py
from typing import List, Tuple, Optional, Iterator
import logging

from sqlalchemy.orm import Session

from backend.app.models.chat import ChatSession, ChatMessage
from backend.app.models.user import User
from backend.app.ai.service import (
    ask_bot,
    ask_bot_stream,
    ask_with_messages,
    ask_with_messages_stream,
    DEFAULT_SYSTEM_PROMPT,
)
from backend.app.ai.intent_detector import detect_intent, IntentType
from backend.app.ai.image_generator import generate_image_from_user_message

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def _find_latest_image(
    db: Session,
    session_id: int
) -> Optional[str]:
    """
    查找会话中最近的图片（包括用户上传的图片和助手生成的图片）
    按照时间顺序从最新到最旧查找，不区分用户上传还是助手生成
    
    Args:
        db: 数据库会话
        session_id: 会话ID
    
    Returns:
        最近的图片URL或Base64字符串，如果没有则返回None
        按照时间顺序返回最新的图片（无论是用户上传的还是助手生成的）
    """
    try:
        logger.debug(f"[Chat Service] [IMAGE] ========== 开始查找最近的图片 ==========")
        logger.debug(f"[Chat Service] [IMAGE] 会话ID: {session_id}")
        
        # 查询所有消息（包括用户和助手消息），按时间倒序排列
        all_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .all()
        )
        
        logger.debug(f"[Chat Service] [IMAGE] 找到 {len(all_messages)} 条消息，按时间倒序查找图片...")
        
        # 按照时间顺序从最新到最旧查找，不区分用户上传还是助手生成
        for msg in all_messages:
            logger.debug(f"[Chat Service] [IMAGE] 检查消息ID: {msg.id}, role: {msg.role}, created_at: {msg.created_at}")
            logger.debug(f"[Chat Service] [IMAGE] 消息内容预览: {msg.content[:50] if msg.content else 'None'}...")
            
            # 先检查助手生成的图片
            if msg.role == "assistant" and msg.generated_images is not None:
                logger.debug(f"[Chat Service] [IMAGE] 助手消息，generated_images类型: {type(msg.generated_images)}, 值: {msg.generated_images}")
                
                if isinstance(msg.generated_images, list) and len(msg.generated_images) > 0:
                    image_url = msg.generated_images[0]
                    if image_url:
                        logger.info(f"[Chat Service] [IMAGE] ✅ 找到最近的图片（助手消息ID: {msg.id}），图片URL: {image_url[:100]}...")
                        return image_url
                elif not isinstance(msg.generated_images, list):
                    logger.warning(f"[Chat Service] [IMAGE] ⚠️ 消息ID {msg.id} 的 generated_images 不是列表类型: {type(msg.generated_images)}")
            
            # 再检查用户上传的图片
            elif msg.role == "user" and msg.images is not None:
                logger.debug(f"[Chat Service] [IMAGE] 用户消息，images类型: {type(msg.images)}, 值: {msg.images}")
                
                if isinstance(msg.images, list) and len(msg.images) > 0:
                    image_base64 = msg.images[0]
                    if image_base64:
                        logger.info(f"[Chat Service] [IMAGE] ✅ 找到最近的图片（用户消息ID: {msg.id}），图片Base64长度: {len(image_base64)} 字符")
                        return image_base64
                elif not isinstance(msg.images, list):
                    logger.warning(f"[Chat Service] [IMAGE] ⚠️ 消息ID {msg.id} 的 images 不是列表类型: {type(msg.images)}")
        
        logger.warning(f"[Chat Service] [IMAGE] ⚠️ 未找到任何图片（检查了 {len(all_messages)} 条消息）")
        return None
    except Exception as e:
        logger.error(f"[Chat Service] [IMAGE] ❌ 查找最近图片时出错: {e}", exc_info=True)
        return None


def _should_use_previous_image(user_message: str) -> bool:
    """
    判断用户消息是否提到要使用上一张生成的图片
    
    Args:
        user_message: 用户消息文本
    
    Returns:
        如果提到使用上一张图，返回True
    """
    message_lower = user_message.lower()
    keywords = [
        "上一张", "上一张图", "上一张图片", "上一张生成的", "上一张生成的图",
        "刚才", "刚才的", "刚才生成的", "刚才生成的图",
        "之前", "之前的", "之前生成的", "之前生成的图",
        "这张", "这张图", "这张图片", "生成的图", "生成的图片",
        "继续", "继续改", "继续修改", "继续生成", "继续画",  # 新增：继续相关关键词
        "改", "改成", "改为", "修改", "改变",  # 新增：修改相关关键词（当没有上传图片时，可能是指修改上一张图）
    ]
    return any(keyword in message_lower for keyword in keywords)


def _generate_title(question: str) -> str:
    question = (question or "").strip()
    if not question:
        return "新的对话"
    # 简单截断前 20 个字符
    return question[:20]


def create_session_and_ask(
    db: Session,
    user: User,
    question: str,
    title: Optional[str] = None,
    thinking: str = "disabled",
    images: Optional[List[str]] = None,
) -> Tuple[ChatSession, List[ChatMessage]]:

    if not title:
        title = _generate_title(question)

    session = ChatSession(
        user_id=user.id,
        title=title,
    )
    db.add(session)
    db.flush()  # 先拿到 session.id

    # 保存用户问题
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=question,
        images=images if images else None,  # 保存图片Base64列表
    )
    db.add(user_msg)

    answer_text = ask_bot(question, thinking=thinking, images=images)

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_text,
        generated_images=None,  # 普通对话不生成图片
    )
    db.add(assistant_msg)

    db.commit()
    db.refresh(session)
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return session, [user_msg, assistant_msg]


def create_session_and_ask_stream(
    db: Session,
    user: User,
    question: str,
    title: Optional[str] = None,
    thinking: str = "disabled",
    images: Optional[List[str]] = None,
) -> Iterator[Tuple[str, dict]]:
    """
    创建会话并流式返回 AI 回答。
    
    返回格式：(event_type, data)
    - event_type: 'session_created' | 'user_msg_created' | 'chunk' | 'complete' | 'error'
    - data: 包含事件相关数据的字典
      - session_created: {'session_id': int, 'title': str}
      - user_msg_created: {'message_id': int, 'content': str}
      - chunk: {'content': str}  # 实际的文本块
      - complete: {'session_id': int, 'user_msg_id': int, 'assistant_msg_id': int}
      - error: {'error': str}
    """
    session = None
    user_msg = None
    assistant_msg = None
    full_answer = ""
    reasoning_content = None
    
    try:
        # 1. 创建会话
        if not title:
            title = _generate_title(question)
        
        session = ChatSession(
            user_id=user.id,
            title=title,
        )
        db.add(session)
        db.flush()
        yield ("session_created", {"session_id": session.id, "title": session.title})
        
        # 2. 保存用户问题
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=question,
            images=images if images else None,  # 保存图片Base64列表
        )
        db.add(user_msg)
        db.flush()
        yield ("user_msg_created", {"message_id": user_msg.id, "content": user_msg.content})
        
        # 2.5. 意图识别（快速判断用户意图）
        has_files = bool(images)
        logger.debug(f"[Chat Service] [IMAGE] ========== 开始意图识别 ==========")
        logger.debug(f"[Chat Service] [IMAGE] 用户消息: {question[:50]}...")
        logger.debug(f"[Chat Service] [IMAGE] 是否有文件: {has_files}")
        
        intent_result = detect_intent(question, has_files=has_files)
        intent = intent_result["intent"]
        logger.info(f"[Chat Service] [IMAGE] 意图识别结果: {intent}, 理由: {intent_result.get('reason', 'N/A')}")
        
        # 3. 根据意图进行路由分发
        if intent == IntentType.IMAGE_GENERATE:
            # 图片生成意图，调用图片生成API
            logger.info(f"[Chat Service] [IMAGE] ========== 检测到图片生成意图，调用图片生成API ==========")
            logger.debug(f"[Chat Service] [IMAGE] 发送image_generating事件")
            yield ("image_generating", {"status": "generating", "message": "正在生成图片，请稍候..."})
            
            # 确定以图生图的源图片
            source_image = None
            if images and len(images) > 0:
                # 用户上传了图片，使用第一张图片作为源图片
                source_image = images[0]
                logger.info(f"[Chat Service] [IMAGE] 使用用户上传的图片作为源图片（以图生图）")
                logger.debug(f"[Chat Service] [IMAGE] 源图片长度: {len(source_image)} 字符")
            else:
                # 用户没有上传图片，检查历史消息中是否有最近生成的图片
                logger.debug(f"[Chat Service] [IMAGE] 用户未上传图片，检查历史消息中的生成图片")
                # 注意：新会话没有历史消息，所以这里不需要查找
                logger.debug(f"[Chat Service] [IMAGE] 新会话，无历史消息，使用纯文本生成")
            
            logger.debug(f"[Chat Service] [IMAGE] 调用generate_image_from_user_message")
            image_result = generate_image_from_user_message(
                question,
                image=source_image  # 传入源图片（如果有）
            )
            logger.debug(f"[Chat Service] [IMAGE] 图片生成结果: success={image_result.get('success')}")
            
            if image_result["success"]:
                image_urls = image_result.get("image_urls", [])
                if image_urls:
                    logger.info(f"[Chat Service] [IMAGE] ✅ 图片生成成功，共 {len(image_urls)} 张")
                    for index, url in enumerate(image_urls):
                        logger.debug(f"[Chat Service] [IMAGE] 图片 {index}: {url[:100]}...")
                    
                    # 发送图片生成完成事件
                    logger.debug(f"[Chat Service] [IMAGE] 发送image_generated事件，包含 {len(image_urls)} 张图片")
                    yield ("image_generated", {
                        "image_urls": image_urls,
                        "image_url": image_urls[0] if len(image_urls) == 1 else None
                    })
                    
                    # 使用ChatAPI生成图片描述
                    logger.info(f"[Chat Service] [IMAGE] ========== 开始生成图片描述 ==========")
                    logger.debug(f"[Chat Service] [IMAGE] 使用ChatAPI生成图片描述")
                    image_description = f"已为您生成图片：{question}"  # 默认描述
                    
                    try:
                        image_description_prompt = f"请用简洁优美的中文描述这张图片，描述应该生动有趣，不超过50字。图片是根据用户需求'{question}'生成的。"
                        logger.debug(f"[Chat Service] [IMAGE] 图片描述提示词: {image_description_prompt[:100]}...")
                        
                        # 构建多模态消息，包含图片URL
                        from backend.app.ai.service import build_multimodal_content
                        logger.debug(f"[Chat Service] [IMAGE] 构建多模态内容，图片URL数量: {len(image_urls)}")
                        image_description_content = build_multimodal_content(
                            image_description_prompt,
                            image_urls  # 传入图片URL列表
                        )
                        logger.debug(f"[Chat Service] [IMAGE] 多模态内容构建完成")
                        
                        description_messages = [
                            {"role": "system", "content": "你是一个专业的图片描述助手，擅长用简洁优美的语言描述图片内容。"},
                            {"role": "user", "content": image_description_content}
                        ]
                        
                        logger.debug(f"[Chat Service] [IMAGE] 调用ask_with_messages生成图片描述...")
                        image_description = ask_with_messages(description_messages, thinking="disabled")
                        logger.info(f"[Chat Service] [IMAGE] ✅ 图片描述生成成功: {image_description[:50]}...")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 图片描述生成失败: {e}", exc_info=True)
                        logger.warning(f"[Chat Service] [IMAGE] ⚠️ 使用默认描述")
                        image_description = f"已为您生成图片：{question}"
                    
                    # 先发送content_update事件，更新前端显示的描述内容
                    try:
                        logger.info(f"[Chat Service] [IMAGE] ========== 发送content_update事件 ==========")
                        logger.debug(f"[Chat Service] [IMAGE] 发送content_update事件，更新图片描述")
                        yield ("content_update", {
                            "content": image_description,
                            "message_id": None  # 此时消息还未保存，使用None
                        })
                        logger.debug(f"[Chat Service] [IMAGE] ✅ content_update事件已发送")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 发送content_update事件失败: {e}", exc_info=True)
                    
                    # 保存 AI 回复（包含生成的图片URL和描述）
                    try:
                        logger.info(f"[Chat Service] [IMAGE] ========== 保存AI回复到数据库 ==========")
                        logger.debug(f"[Chat Service] [IMAGE] 保存AI回复到数据库，包含 {len(image_urls)} 张图片URL")
                        assistant_msg = ChatMessage(
                            session_id=session.id,
                            role="assistant",
                            content=image_description,  # 使用ChatAPI生成的图片描述
                            generated_images=image_urls,  # 保存生成的图片URL列表
                        )
                        db.add(assistant_msg)
                        db.commit()
                        db.refresh(assistant_msg)
                        logger.info(f"[Chat Service] [IMAGE] ✅ AI回复已保存，消息ID: {assistant_msg.id}")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 保存AI回复到数据库失败: {e}", exc_info=True)
                        db.rollback()
                        # 即使保存失败，也创建一个临时消息对象用于complete事件
                        # 注意：这里不能直接设置id，因为id是数据库自动生成的
                        # 我们使用None来表示未保存的消息
                        assistant_msg = None
                    
                    # 发送complete事件
                    try:
                        logger.info(f"[Chat Service] [IMAGE] ========== 发送complete事件 ==========")
                        yield ("complete", {
                            "session_id": session.id,
                            "user_msg_id": user_msg.id,
                            "assistant_msg_id": assistant_msg.id if assistant_msg else None
                        })
                        logger.info(f"[Chat Service] [IMAGE] ✅ 图片生成流程完成")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 发送complete事件失败: {e}", exc_info=True)
                    
                    return
                else:
                    logger.warning(f"[Chat Service] [IMAGE] ⚠️ 图片生成成功但未获取到URL，降级为普通对话")
                    # 降级为普通对话
            else:
                error_msg = image_result.get("error", "图片生成失败")
                logger.error(f"[Chat Service] [IMAGE] ❌ 图片生成失败: {error_msg}")
                yield ("error", {"error": f"图片生成失败: {error_msg}"})
                return
        
        # 普通对话或文件解析（使用现有逻辑）
        # DEBUG 2: 确认传递给AI service的thinking参数
        logger.debug(f"[Chat Service] ========== 开始调用AI服务 ==========")
        logger.debug(f"[Chat Service] 问题: {question[:50]}...")
        logger.debug(f"[Chat Service] thinking参数: {thinking}")
        logger.debug(f"[Chat Service] thinking类型: {type(thinking)}")
        logger.debug(f"[Chat Service] 图片数量: {len(images) if images else 0}")
        
        # 3. 流式返回 AI 回答
        chunk_count = 0
        reasoning_content_parts = []  # 用于累积reasoning_content（用于数据库存储）
        
        for chunk_data in ask_bot_stream(question, thinking=thinking, images=images):
            chunk_count += 1
            chunk_content = chunk_data.get("content", "")
            chunk_reasoning = chunk_data.get("reasoning_content")
            
            logger.debug(f"[Chat Service] 收到chunk #{chunk_count}: content长度={len(chunk_content)}, reasoning_content={'有' if chunk_reasoning else '无'}")
            
            # 流式发送content片段
            if chunk_content:
                full_answer += chunk_content
                yield ("chunk", {"content": chunk_content})
            
            # 流式发送reasoning_content片段（每个片段都立即发送给客户端，让前端实时显示）
            if chunk_reasoning:
                reasoning_content_parts.append(chunk_reasoning)
                logger.debug(f"[Chat Service] ⭐ 发送reasoning_content片段，长度: {len(chunk_reasoning)}")
                # 立即发送给客户端，让前端实时显示
                yield ("reasoning", {"reasoning_content": chunk_reasoning})
        
        # 合并完整的reasoning_content用于后续数据库存储
        reasoning_content = "".join(reasoning_content_parts) if reasoning_content_parts else None
        logger.debug(f"[Chat Service] 流式调用完成，共处理 {chunk_count} 个chunk，reasoning_content={'有' if reasoning_content else '无'}")
        
        # 4. 保存 AI 回复
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=full_answer,
            reasoning_content=reasoning_content,  # 保存深度思考内容
            generated_images=None,  # 普通对话不生成图片
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(session)
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        
        yield ("complete", {
            "session_id": session.id,
            "user_msg_id": user_msg.id,
            "assistant_msg_id": assistant_msg.id
        })
        
    except Exception as e:
        if session:
            db.rollback()
        yield ("error", {"error": str(e)})


def list_sessions_for_user(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 20,
) -> List[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_session_for_user(
    db: Session,
    user: User,
    session_id: int,
) -> Optional[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
        .first()
    )


def get_session_with_messages_for_user(
    db: Session,
    user: User,
    session_id: int,
) -> Tuple[Optional[ChatSession], List[ChatMessage]]:
    session = get_session_for_user(db, user, session_id)
    if not session:
        return None, []

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return session, messages


def send_message_in_session(
    db: Session,
    user: User,
    session_id: int,
    question: str,
    thinking: str = "disabled",
    images: Optional[List[str]] = None,
) -> List[ChatMessage]:
    """
    在已有会话中继续提问：
    1. 检查会话归属
    2. 读取历史消息，构造 messages 作为上下文
    3. 调用 AI
    4. 保存用户问题和 AI 回复
    """
    session = get_session_for_user(db, user, session_id)
    if not session:
        raise ValueError("session_not_found")

    # 先保存用户这条问题（为了记录）
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=question,
    )
    db.add(user_msg)

    # 获取历史消息（不包括当前这条）
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    # 构造 Ark 所需 messages
    from backend.app.ai.service import build_multimodal_content
    
    messages_payload = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
    ]
    for msg in history:
        # 构建消息内容，包含图片（如果有）
        # 根据消息角色决定使用哪种图片
        # user消息：使用images（用户上传的Base64图片）
        # assistant消息：使用generated_images（模型生成的图片URL）
        msg_images = None
        if msg.role == "user" and msg.images:
            msg_images = msg.images
            logger.debug(f"[Chat Service] [IMAGE] 历史消息（用户）包含 {len(msg_images)} 张上传的图片")
        elif msg.role == "assistant" and msg.generated_images:
            msg_images = msg.generated_images
            logger.debug(f"[Chat Service] [IMAGE] 历史消息（助手）包含 {len(msg_images)} 张生成的图片")
        
        # 构建多模态内容（包含图片）
        msg_content = build_multimodal_content(msg.content, msg_images)
        messages_payload.append(
            {"role": msg.role, "content": msg_content}
        )
    # 再把当前问题也加上（支持多模态）
    user_content = build_multimodal_content(question, images)
    messages_payload.append({"role": "user", "content": user_content})

    # 带历史上下文调用 AI
    answer_text = ask_with_messages(messages_payload, thinking=thinking)

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_text,
        generated_images=None,  # 普通对话不生成图片
    )
    db.add(assistant_msg)

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return [user_msg, assistant_msg]


def delete_session_for_user(
    db: Session,
    user: User,
    session_id: int,
) -> bool:
    """
    删除指定用户的会话（级联删除消息）。
    返回 True 如果删除成功，False 如果会话不存在。
    """
    session = get_session_for_user(db, user, session_id)
    if not session:
        return False
    
    db.delete(session)
    db.commit()
    return True


def update_session_title_for_user(
    db: Session,
    user: User,
    session_id: int,
    new_title: str,
) -> Optional[ChatSession]:
    """
    更新指定用户的会话标题。
    返回更新后的会话，如果会话不存在则返回 None。
    """
    session = get_session_for_user(db, user, session_id)
    if not session:
        return None
    
    session.title = new_title
    db.commit()
    db.refresh(session)
    return session


def send_message_in_session_stream(
    db: Session,
    user: User,
    session_id: int,
    question: str,
    thinking: str = "disabled",
    images: Optional[List[str]] = None,
) -> Iterator[Tuple[str, dict]]:
    """
    在已有会话中流式发送消息。
    
    返回格式：(event_type, data)
    - event_type: 'user_msg_created' | 'chunk' | 'complete' | 'error'
    - data: 包含事件相关数据的字典
      - user_msg_created: {'message_id': int, 'content': str}
      - chunk: {'content': str}  # 实际的文本块
      - complete: {'user_msg_id': int, 'assistant_msg_id': int}
      - error: {'error': str}
    """
    user_msg = None
    assistant_msg = None
    full_answer = ""
    reasoning_content = None
    
    try:
        session = get_session_for_user(db, user, session_id)
        if not session:
            yield ("error", {"error": "session_not_found"})
            return
        
        # 1. 保存用户问题
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=question,
            images=images if images else None,  # 保存图片Base64列表
        )
        db.add(user_msg)
        db.flush()
        yield ("user_msg_created", {"message_id": user_msg.id, "content": user_msg.content})
        
        # 1.5. 意图识别（快速判断用户意图）
        has_files = bool(images)
        logger.debug(f"[Chat Service] [IMAGE] ========== 开始意图识别（已有会话） ==========")
        logger.debug(f"[Chat Service] [IMAGE] 用户消息: {question[:50]}...")
        logger.debug(f"[Chat Service] [IMAGE] 是否有文件: {has_files}")
        
        intent_result = detect_intent(question, has_files=has_files)
        intent = intent_result["intent"]
        logger.info(f"[Chat Service] [IMAGE] 意图识别结果: {intent}, 理由: {intent_result.get('reason', 'N/A')}")
        
        # 2. 根据意图进行路由分发
        if intent == IntentType.IMAGE_GENERATE:
            # 图片生成意图，调用图片生成API
            logger.info(f"[Chat Service] [IMAGE] ========== 检测到图片生成意图，调用图片生成API（已有会话） ==========")
            logger.debug(f"[Chat Service] [IMAGE] 发送image_generating事件")
            yield ("image_generating", {"status": "generating", "message": "正在生成图片，请稍候..."})
            
            # 确定以图生图的源图片
            source_image = None
            if images and len(images) > 0:
                # 用户上传了图片，使用第一张图片作为源图片
                source_image = images[0]
                logger.info(f"[Chat Service] [IMAGE] 使用用户上传的图片作为源图片（以图生图）")
                logger.debug(f"[Chat Service] [IMAGE] 源图片长度: {len(source_image)} 字符")
            else:
                # 用户没有上传图片，尝试查找历史消息中最近生成的图片
                # 优先检查是否明确提到使用上一张图
                should_use_prev = _should_use_previous_image(question)
                logger.debug(f"[Chat Service] [IMAGE] 是否提到使用上一张图: {should_use_prev}")
                
                # 刷新数据库会话，确保能看到最新的数据
                db.flush()
                
                # 查找最近的图片（包括用户上传的和助手生成的）
                source_image = _find_latest_image(db, session.id)
                
                if source_image:
                    if should_use_prev:
                        logger.info(f"[Chat Service] [IMAGE] ✅ 用户提到使用上一张图，找到最近的图片，将用于以图生图")
                    else:
                        # 即使没有明确提到，但如果用户消息包含修改类关键词（如"改"、"改成"等），也使用上一张图
                        modify_keywords = ["改", "改成", "改为", "修改", "改变", "继续"]
                        has_modify_keyword = any(keyword in question.lower() for keyword in modify_keywords)
                        if has_modify_keyword:
                            logger.info(f"[Chat Service] [IMAGE] ✅ 用户消息包含修改关键词，找到最近的图片，将用于以图生图")
                        else:
                            logger.debug(f"[Chat Service] [IMAGE] 找到最近的图片，但用户未明确要求使用，将使用纯文本生成")
                            source_image = None  # 不使用上一张图，使用纯文本生成
                else:
                    if should_use_prev:
                        logger.warning(f"[Chat Service] [IMAGE] ⚠️ 用户提到使用上一张图，但未找到最近的图片（用户上传或助手生成），将使用纯文本生成")
                    else:
                        logger.debug(f"[Chat Service] [IMAGE] 用户未上传图片且未找到历史图片（用户上传或助手生成），使用纯文本生成")
            
            logger.debug(f"[Chat Service] [IMAGE] 调用generate_image_from_user_message")
            image_result = generate_image_from_user_message(
                question,
                image=source_image  # 传入源图片（如果有）
            )
            logger.debug(f"[Chat Service] [IMAGE] 图片生成结果: success={image_result.get('success')}")
            
            if image_result["success"]:
                image_urls = image_result.get("image_urls", [])
                if image_urls:
                    logger.info(f"[Chat Service] [IMAGE] ✅ 图片生成成功，共 {len(image_urls)} 张")
                    for index, url in enumerate(image_urls):
                        logger.debug(f"[Chat Service] [IMAGE] 图片 {index}: {url[:100]}...")
                    
                    # 发送图片生成完成事件
                    logger.debug(f"[Chat Service] [IMAGE] 发送image_generated事件，包含 {len(image_urls)} 张图片")
                    yield ("image_generated", {
                        "image_urls": image_urls,
                        "image_url": image_urls[0] if len(image_urls) == 1 else None
                    })
                    
                    # 使用ChatAPI生成图片描述
                    logger.info(f"[Chat Service] [IMAGE] ========== 开始生成图片描述（已有会话） ==========")
                    logger.debug(f"[Chat Service] [IMAGE] 使用ChatAPI生成图片描述（已有会话）")
                    image_description = f"已为您生成图片：{question}"  # 默认描述
                    
                    try:
                        image_description_prompt = f"请用简洁优美的中文描述这张图片，描述应该生动有趣，不超过50字。图片是根据用户需求'{question}'生成的。"
                        logger.debug(f"[Chat Service] [IMAGE] 图片描述提示词: {image_description_prompt[:100]}...")
                        
                        # 构建多模态消息，包含图片URL
                        from backend.app.ai.service import build_multimodal_content
                        logger.debug(f"[Chat Service] [IMAGE] 构建多模态内容，图片URL数量: {len(image_urls)}")
                        image_description_content = build_multimodal_content(
                            image_description_prompt,
                            image_urls  # 传入图片URL列表
                        )
                        logger.debug(f"[Chat Service] [IMAGE] 多模态内容构建完成")
                        
                        description_messages = [
                            {"role": "system", "content": "你是一个专业的图片描述助手，擅长用简洁优美的语言描述图片内容。"},
                            {"role": "user", "content": image_description_content}
                        ]
                        
                        logger.debug(f"[Chat Service] [IMAGE] 调用ask_with_messages生成图片描述...")
                        image_description = ask_with_messages(description_messages, thinking="disabled")
                        logger.info(f"[Chat Service] [IMAGE] ✅ 图片描述生成成功: {image_description[:50]}...")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 图片描述生成失败: {e}", exc_info=True)
                        logger.warning(f"[Chat Service] [IMAGE] ⚠️ 使用默认描述")
                        image_description = f"已为您生成图片：{question}"
                    
                    # 先发送content_update事件，更新前端显示的描述内容
                    try:
                        logger.info(f"[Chat Service] [IMAGE] ========== 发送content_update事件（已有会话） ==========")
                        logger.debug(f"[Chat Service] [IMAGE] 发送content_update事件，更新图片描述（已有会话）")
                        yield ("content_update", {
                            "content": image_description,
                            "message_id": None  # 此时消息还未保存，使用None
                        })
                        logger.debug(f"[Chat Service] [IMAGE] ✅ content_update事件已发送")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 发送content_update事件失败: {e}", exc_info=True)
                    
                    # 保存 AI 回复（包含生成的图片URL和描述）
                    try:
                        logger.info(f"[Chat Service] [IMAGE] ========== 保存AI回复到数据库（已有会话） ==========")
                        logger.debug(f"[Chat Service] [IMAGE] 保存AI回复到数据库，包含 {len(image_urls)} 张图片URL")
                        logger.debug(f"[Chat Service] [IMAGE] 图片URL列表: {image_urls}")
                        assistant_msg = ChatMessage(
                            session_id=session.id,
                            role="assistant",
                            content=image_description,  # 使用ChatAPI生成的图片描述
                            generated_images=image_urls,  # 保存生成的图片URL列表
                        )
                        db.add(assistant_msg)
                        db.commit()
                        db.refresh(assistant_msg)
                        logger.info(f"[Chat Service] [IMAGE] ✅ AI回复已保存，消息ID: {assistant_msg.id}")
                        # 验证保存的数据
                        logger.debug(f"[Chat Service] [IMAGE] 验证保存的数据 - generated_images类型: {type(assistant_msg.generated_images)}, 值: {assistant_msg.generated_images}")
                        if assistant_msg.generated_images:
                            logger.debug(f"[Chat Service] [IMAGE] 验证保存的数据 - generated_images长度: {len(assistant_msg.generated_images) if isinstance(assistant_msg.generated_images, list) else 'N/A'}")
                        else:
                            logger.error(f"[Chat Service] [IMAGE] ❌ 保存后验证失败：generated_images 为 None 或空！消息ID: {assistant_msg.id}, 原始image_urls: {image_urls}")
                        
                        # 再次从数据库查询验证（确保数据已持久化）
                        try:
                            db.refresh(assistant_msg)
                            verified_msg = db.query(ChatMessage).filter(ChatMessage.id == assistant_msg.id).first()
                            if verified_msg:
                                logger.debug(f"[Chat Service] [IMAGE] 数据库验证 - 消息ID: {verified_msg.id}, generated_images: {verified_msg.generated_images}")
                                if verified_msg.generated_images != image_urls:
                                    logger.error(f"[Chat Service] [IMAGE] ❌ 数据库验证失败：保存的generated_images与原始数据不一致！")
                            else:
                                logger.error(f"[Chat Service] [IMAGE] ❌ 数据库验证失败：无法从数据库查询到消息ID: {assistant_msg.id}")
                        except Exception as e:
                            logger.error(f"[Chat Service] [IMAGE] ❌ 数据库验证时出错: {e}", exc_info=True)
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 保存AI回复到数据库失败: {e}", exc_info=True)
                        db.rollback()
                        # 即使保存失败，也创建一个临时消息对象用于complete事件
                        # 注意：这里不能直接设置id，因为id是数据库自动生成的
                        # 我们使用None来表示未保存的消息
                        assistant_msg = None
                    
                    # 发送complete事件
                    try:
                        logger.info(f"[Chat Service] [IMAGE] ========== 发送complete事件（已有会话） ==========")
                        yield ("complete", {
                            "user_msg_id": user_msg.id,
                            "assistant_msg_id": assistant_msg.id if assistant_msg else None
                        })
                        logger.info(f"[Chat Service] [IMAGE] ✅ 图片生成流程完成（已有会话）")
                    except Exception as e:
                        logger.error(f"[Chat Service] [IMAGE] ❌ 发送complete事件失败: {e}", exc_info=True)
                    
                    return
                else:
                    logger.warning(f"[Chat Service] [IMAGE] ⚠️ 图片生成成功但未获取到URL，降级为普通对话")
                    # 降级为普通对话
            else:
                error_msg = image_result.get("error", "图片生成失败")
                logger.error(f"[Chat Service] [IMAGE] ❌ 图片生成失败: {error_msg}")
                yield ("error", {"error": f"图片生成失败: {error_msg}"})
                return
        
        # 普通对话或文件解析（使用现有逻辑）
        # 2. 获取历史消息
        history = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .all()
        )
        
        # 3. 构造 messages
        from backend.app.ai.service import build_multimodal_content
        
        messages_payload = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
        ]
        for msg in history:
            # 构建消息内容，包含图片（如果有）
            # 根据消息角色决定使用哪种图片
            # user消息：使用images（用户上传的Base64图片）
            # assistant消息：使用generated_images（模型生成的图片URL）
            msg_images = None
            if msg.role == "user" and msg.images:
                msg_images = msg.images
                logger.debug(f"[Chat Service] [IMAGE] 历史消息（用户）包含 {len(msg_images)} 张上传的图片")
            elif msg.role == "assistant" and msg.generated_images:
                msg_images = msg.generated_images
                logger.debug(f"[Chat Service] [IMAGE] 历史消息（助手）包含 {len(msg_images)} 张生成的图片")
            
            # 构建多模态内容（包含图片）
            msg_content = build_multimodal_content(msg.content, msg_images)
            messages_payload.append(
                {"role": msg.role, "content": msg_content}
            )
        # 当前消息支持多模态（图片+文本）
        user_content = build_multimodal_content(question, images)
        messages_payload.append({"role": "user", "content": user_content})
        
        # DEBUG 2: 确认传递给AI service的thinking参数
        logger.debug(f"[Chat Service] ========== 开始调用AI服务（已有会话） ==========")
        logger.debug(f"[Chat Service] 问题: {question[:50]}...")
        logger.debug(f"[Chat Service] thinking参数: {thinking}")
        logger.debug(f"[Chat Service] thinking类型: {type(thinking)}")
        logger.debug(f"[Chat Service] 历史消息数: {len(messages_payload) - 2}")  # 减去system和当前user消息
        logger.debug(f"[Chat Service] 图片数量: {len(images) if images else 0}")
        
        # 4. 流式返回 AI 回答
        chunk_count = 0
        reasoning_content_parts = []  # 用于累积reasoning_content（用于数据库存储）
        
        for chunk_data in ask_with_messages_stream(messages_payload, thinking=thinking):
            chunk_count += 1
            chunk_content = chunk_data.get("content", "")
            chunk_reasoning = chunk_data.get("reasoning_content")
            
            logger.debug(f"[Chat Service] 收到chunk #{chunk_count}: content长度={len(chunk_content)}, reasoning_content={'有' if chunk_reasoning else '无'}")
            
            # 流式发送content片段
            if chunk_content:
                full_answer += chunk_content
                yield ("chunk", {"content": chunk_content})
            
            # 流式发送reasoning_content片段（每个片段都立即发送给客户端，让前端实时显示）
            if chunk_reasoning:
                reasoning_content_parts.append(chunk_reasoning)
                logger.debug(f"[Chat Service] ⭐ 发送reasoning_content片段，长度: {len(chunk_reasoning)}")
                # 立即发送给客户端，让前端实时显示
                yield ("reasoning", {"reasoning_content": chunk_reasoning})
        
        # 合并完整的reasoning_content用于后续数据库存储
        reasoning_content = "".join(reasoning_content_parts) if reasoning_content_parts else None
        logger.debug(f"[Chat Service] 流式调用完成，共处理 {chunk_count} 个chunk，reasoning_content={'有' if reasoning_content else '无'}")
        
        # 5. 保存 AI 回复
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=full_answer,
            reasoning_content=reasoning_content,  # 保存深度思考内容
            generated_images=None,  # 普通对话不生成图片
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        
        yield ("complete", {
            "user_msg_id": user_msg.id,
            "assistant_msg_id": assistant_msg.id
        })
        
    except Exception as e:
        if user_msg:
            db.rollback()
        yield ("error", {"error": str(e)})
