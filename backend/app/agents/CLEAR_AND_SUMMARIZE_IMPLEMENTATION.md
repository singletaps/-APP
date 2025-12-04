# 清空聊天并总结记忆功能实现说明

## 已完成的工作

### 1. 后端服务函数 (`service.py`)

需要在 `service.py` 文件末尾（第1010行后）添加以下函数：

```python
# ==================== 清空聊天并总结记忆 ====================

def clear_chat_and_summarize(
    db: Session,
    user: User,
    agent_id: int,
) -> Tuple[bool, Optional[str]]:
    """
    清空聊天并总结记忆
    
    流程：
    1. 验证Agent归属
    2. 获取当前会话的所有消息
    3. 如果有消息，使用thinking进行深度思考总结
    4. 创建prompt历史记录
    5. 创建知识库索引（提取topics、key_points、keywords）
    6. 清空会话消息
    7. 更新agent的current_prompt
    
    Args:
        db: 数据库会话
        user: 用户对象
        agent_id: Agent ID
    
    Returns:
        (success, summary_text or error_message)
    """
    logger.info(f"[Agent服务] ========== 开始清空聊天并总结记忆 ==========")
    logger.info(f"[Agent服务] agent_id={agent_id}")
    
    try:
        # 1. 验证Agent归属
        agent = get_agent_for_user(db, user, agent_id)
        if not agent:
            logger.warning(f"[Agent服务] ⚠️ Agent不存在: agent_id={agent_id}")
            return False, "Agent not found"
        
        # 2. 获取或创建会话
        session = get_or_create_agent_session(db, agent_id)
        
        # 3. 获取所有消息
        all_messages = get_agent_session_messages(db, session.id)
        
        if not all_messages:
            logger.info(f"[Agent服务] ✅ 会话中没有消息，无需总结")
            return True, None
        
        # 4. 统计消息信息
        user_messages = [msg for msg in all_messages if msg.role == "user"]
        assistant_messages = [msg for msg in all_messages if msg.role == "assistant"]
        message_count = len(all_messages)
        user_message_count = len(user_messages)
        
        logger.info(f"[Agent服务] 消息统计: 总数={message_count}, 用户={user_message_count}, AI={len(assistant_messages)}")
        
        # 5. 构建总结prompt（以agent为主体，体现成长）
        summary_date = date.today()
        summary_prompt = f"""你是一个观察者和总结者，需要从Agent（{agent.name}）的角度，高度概括今天的对话经历，并将这些经历转化为Agent的成长记忆。

Agent的初始设定：{agent.initial_prompt}

今天（{summary_date}）的对话记录：
"""
        
        # 添加对话记录
        for msg in all_messages:
            role_name = "用户" if msg.role == "user" else "Agent"
            summary_prompt += f"\n{role_name}：{msg.content}\n"
        
        summary_prompt += f"""

请从Agent的角度，进行深度思考并生成总结。要求：

1. **高度概括**：用简洁的语言总结今天的对话核心内容
2. **Agent为主体**：总结要以"我"（Agent）的视角，描述"我"经历了什么
3. **体现成长**：描述这些对话对Agent的影响、改变、感悟或成长
4. **情感化**：让总结更像人的记忆，有情感色彩，而不是冷冰冰的记录

请返回JSON格式：
{{
    "summary": "总结内容（200-500字，高度概括，以Agent为主体）",
    "topics": ["话题1", "话题2", ...],
    "key_points": ["关键点1", "关键点2", ...],
    "keywords": ["关键词1", "关键词2", ...],
    "impact": "这段经历对Agent的影响和改变（100-200字）"
}}

注意：
- summary应该以Agent的第一人称视角，描述"我"今天经历了什么，学到了什么，有什么感悟
- impact应该描述这些经历如何影响了Agent的性格、知识、能力或人设
- topics、key_points、keywords用于后续检索，请提取最重要的内容"""
        
        # 6. 使用thinking进行深度思考总结
        logger.info(f"[Agent服务] 开始使用深度思考总结对话...")
        
        from backend.app.ai.service import ask_with_messages
        
        summary_messages = [
            {"role": "system", "content": "你是一个专业的观察者和总结者，擅长从Agent的角度总结对话经历，并转化为Agent的成长记忆。"},
            {"role": "user", "content": summary_prompt}
        ]
        
        raw_summary = ask_with_messages(
            messages=summary_messages,
            model="doubao-seed-1-6-251015",
            thinking="enabled",  # 使用深度思考
        )
        
        logger.info(f"[Agent服务] ✅ 总结生成完成: 长度={len(raw_summary)} 字符")
        
        # 7. 解析总结JSON
        try:
            # 清理Markdown代码块
            summary_text = clean_markdown_code_block(raw_summary)
            
            # 尝试提取JSON
            json_match = re.search(r'\{.*\}', summary_text, re.DOTALL)
            if json_match:
                summary_data = json.loads(json_match.group())
            else:
                summary_data = json.loads(summary_text)
            
            summary_content = summary_data.get("summary", "")
            topics = summary_data.get("topics", [])
            key_points = summary_data.get("key_points", [])
            keywords = summary_data.get("keywords", [])
            impact = summary_data.get("impact", "")
            
            # 合并summary和impact作为added_prompt
            if impact:
                added_prompt = f"{summary_content}\n\n这段经历对我的影响：{impact}"
            else:
                added_prompt = summary_content
            
            logger.info(f"[Agent服务] ✅ 总结解析成功: topics={len(topics)}, key_points={len(key_points)}, keywords={len(keywords)}")
            
        except Exception as e:
            logger.warning(f"[Agent服务] ⚠️ JSON解析失败，使用原始文本: {e}")
            # 降级：使用原始文本作为总结
            added_prompt = raw_summary
            summary_content = raw_summary
            topics = []
            key_points = []
            keywords = []
        
        # 8. 获取当前prompt（用于记录）
        current_prompt_before = calculate_current_prompt(db, agent)
        
        # 9. 创建prompt历史记录
        prompt_history = AgentPromptHistory(
            agent_id=agent.id,
            added_prompt=added_prompt,
            full_prompt_before=current_prompt_before,
            full_prompt_after=current_prompt_before + "\n\n" + added_prompt,
            summary_date=summary_date,
        )
        db.add(prompt_history)
        db.flush()  # 获取ID
        
        logger.info(f"[Agent服务] ✅ Prompt历史记录已创建: history_id={prompt_history.id}")
        
        # 10. 创建知识库索引
        knowledge_index = AgentKnowledgeIndex(
            agent_id=agent.id,
            prompt_history_id=prompt_history.id,
            summary_date=summary_date,
            summary_summary=summary_content,
            topics=topics if topics else None,
            key_points=key_points if key_points else None,
            keywords=keywords if keywords else None,
            message_count=message_count,
            user_message_count=user_message_count,
        )
        db.add(knowledge_index)
        
        logger.info(f"[Agent服务] ✅ 知识库索引已创建: index_id={knowledge_index.id}")
        
        # 11. 清空会话消息
        for msg in all_messages:
            db.delete(msg)
        
        logger.info(f"[Agent服务] ✅ 已清空 {len(all_messages)} 条消息")
        
        # 12. 更新agent的current_prompt
        agent.current_prompt = calculate_current_prompt(db, agent)
        
        # 13. 更新agent的last_summarized_at
        from sqlalchemy import func
        agent.last_summarized_at = func.now()
        
        db.commit()
        
        logger.info(f"[Agent服务] ✅ 清空聊天并总结记忆完成")
        logger.info(f"[Agent服务] 总结预览: {summary_content[:100]}...")
        
        return True, summary_content
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Agent服务] ❌ 清空聊天并总结记忆失败: {e}", exc_info=True)
        return False, str(e)
```

### 2. API路由 (`routes.py`)

需要在 `routes.py` 文件末尾（第439行后）添加：

```python
# ==================== 清空聊天并总结记忆API ====================

@router.post(
    "/{agent_id}/chat/clear-and-summarize",
    response_model=agent_schemas.ClearAndSummarizeResponse,
)
def clear_and_summarize_chat(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    清空聊天并总结记忆
    """
    logger.info(f"[Agent路由] 清空聊天并总结记忆: agent_id={agent_id}")
    
    success, result = agent_service.clear_chat_and_summarize(
        db=db,
        user=current_user,
        agent_id=agent_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result or "清空聊天并总结记忆失败"
        )
    
    return agent_schemas.ClearAndSummarizeResponse(
        success=True,
        summary=result,
    )
```

### 3. Schema定义 (`schemas.py`)

需要在 `schemas.py` 文件末尾添加：

```python
class ClearAndSummarizeResponse(BaseModel):
    """清空聊天并总结记忆的响应"""
    success: bool
    summary: Optional[str] = None
```

### 4. 前端API接口 (`ApiService.kt`)

需要在 `ApiService.kt` 中的 `ApiService` 接口中添加（约第314行后）：

```kotlin
@POST("/agents/{id}/chat/clear-and-summarize")
suspend fun clearAndSummarizeAgentChat(
    @Header("Authorization") auth: String,
    @Path("id") id: Int
): ClearAndSummarizeResponse
```

并在数据模型部分添加：

```kotlin
data class ClearAndSummarizeResponse(
    val success: Boolean,
    val summary: String?
)
```

### 5. 前端调用 (`AgentChatScreen.kt`)

在 `clearAndSummarize` 函数中（约第67行），取消注释并更新：

```kotlin
fun clearAndSummarize() {
    scope.launch {
        try {
            loading = true
            error = null
            val agentIdInt = agentId.toIntOrNull()
            if (agentIdInt == null) {
                error = "无效的Agent ID"
                loading = false
                return@launch
            }

            val token = SessionManager.authHeader()
            val response = ApiClient.api.clearAndSummarizeAgentChat(token, agentIdInt)
            
            // 清空消息列表
            messages = emptyList()
            
            // 重新加载消息（应该是空的）
            loadAgentChatMessages(agentId)
            
            loading = false
        } catch (e: Exception) {
            loading = false
            error = "清空聊天并总结记忆失败：${e.message}"
            Log.e(TAG, "清空聊天并总结记忆失败", e)
        }
    }
}
```

## 关键特性

1. **使用thinking进行深度思考**：总结时使用 `thinking="enabled"` 让AI进行深度思考
2. **Agent为主体**：总结以Agent的第一人称视角，描述"我"的经历
3. **体现成长**：总结包含impact字段，描述对话对Agent的影响和改变
4. **高度概括**：总结内容200-500字，简洁明了
5. **知识库索引**：自动提取topics、key_points、keywords用于后续检索

## 注意事项

1. 确保 `AgentKnowledgeIndex` 已在 `service.py` 的import中（已确认）
2. 函数中使用了 `clean_markdown_code_block` 函数，该函数已在 `service.py` 中定义
3. 总结prompt需要确保能够生成符合要求的JSON格式

