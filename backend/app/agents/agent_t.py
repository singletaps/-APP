# backend/app/agents/agent_t.py
"""
Agent模块测试文件

用于快速测试Agent功能，方便开发调试

使用方法：
1. 直接运行（推荐）：python agents/agent_t.py
2. 或在IDE中直接运行此文件（右键 -> Run）

⚠️ 注意：这不是pytest测试文件，是独立的测试脚本
   如果被pytest识别，请在PyCharm中：
   - 右键文件 -> Run 'test_agent'
   - 或者配置PyCharm不将此文件识别为pytest测试
"""

import logging
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent  # backend目录
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session

from backend.app.database.session import SessionLocal
# 导入所有相关模型，确保SQLAlchemy可以解析所有relationship
from backend.app.models.agent import Agent, AgentChatSession, AgentChatMessage
from backend.app.models.chat import ChatSession, ChatMessage  # 确保ChatSession被导入
from backend.app.models.user import User

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 使用INFO级别
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    force=True  # 如果已经配置过，强制重新配置
)
logger = logging.getLogger(__name__)
# 设置Agent服务的日志级别为INFO，以便看到处理过程
logging.getLogger("backend.app.agents.service").setLevel(logging.INFO)
logging.getLogger("backend.app.agents.intent_detector").setLevel(logging.INFO)


def _test_create_agent(db: Session, user: User):
    """测试创建Agent（内部函数，不以test_开头，避免pytest识别）"""
    logger.info("=" * 50)
    logger.info("测试：创建Agent")
    logger.info("=" * 50)

    try:
        from backend.app.agents.service import create_agent

        # 创建Agent
        agent = create_agent(
            db=db,
            user=user,
            name="测试Agent",
            initial_prompt="你是一个友好的助手，擅长回答问题。请使用简洁明了的语言。"
        )

        logger.info(f"✅ Agent创建成功！")
        logger.info(f"   Agent ID: {agent.id}")
        logger.info(f"   Agent名称: {agent.name}")
        logger.info(f"   初始Prompt: {agent.initial_prompt[:50]}...")
        logger.info(f"   当前Prompt: {agent.current_prompt[:50]}...")
        logger.info(f"   会话ID: {agent.chat_session.id if agent.chat_session else None}")

        return agent

    except Exception as e:
        logger.error(f"❌ 创建Agent失败: {e}", exc_info=True)
        return None


def _test_list_agents(db: Session, user: User):
    """测试列出Agent列表（内部函数）"""
    logger.info("=" * 50)
    logger.info("测试：列出Agent列表")
    logger.info("=" * 50)

    try:
        agents = db.query(Agent).filter(Agent.user_id == user.id).all()

        logger.info(f"✅ 找到 {len(agents)} 个Agent")
        for agent in agents:
            logger.info(f"   - Agent ID: {agent.id}, 名称: {agent.name}")

        return agents

    except Exception as e:
        logger.error(f"❌ 列出Agent失败: {e}", exc_info=True)
        return []


def _test_agent_session(db: Session, agent: Agent):
    """测试Agent会话（内部函数）"""
    logger.info("=" * 50)
    logger.info("测试：Agent会话")
    logger.info("=" * 50)

    try:
        from backend.app.agents.service import get_or_create_agent_session, get_agent_session_messages

        # 获取或创建会话
        session = get_or_create_agent_session(db, agent.id)

        logger.info(f"✅ 会话获取成功！")
        logger.info(f"   会话ID: {session.id}")
        logger.info(f"   Agent ID: {session.agent_id}")

        # 获取消息
        messages = get_agent_session_messages(db, session.id)
        logger.info(f"   消息数量: {len(messages)}")

        return session

    except Exception as e:
        logger.error(f"❌ 获取会话失败: {e}", exc_info=True)
        return None


def _test_database_tables(db: Session):
    """测试数据库表是否存在（内部函数）"""
    logger.info("=" * 50)
    logger.info("测试：检查数据库表")
    logger.info("=" * 50)

    try:
        from backend.app.database.session import Base, engine
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        required_tables = [
            "agents",
            "agent_chat_sessions",
            "agent_chat_messages",
            "agent_prompt_history",
            "agent_knowledge_indexes"
        ]

        logger.info("检查必需的表：")
        all_exist = True
        for table in required_tables:
            if table in tables:
                logger.info(f"   ✅ {table} 存在")
            else:
                logger.error(f"   ❌ {table} 不存在")
                all_exist = False

        if all_exist:
            logger.info("✅ 所有表都存在！")
        else:
            logger.warning("⚠️  部分表不存在，可能需要运行数据库迁移")

        return all_exist

    except Exception as e:
        logger.error(f"❌ 检查数据库表失败: {e}", exc_info=True)
        return False


def _test_batch_messages(db: Session, user: User, agent_id: int):
    """测试批量消息处理完整流程"""
    logger.info("=" * 50)
    logger.info("测试：批量消息处理完整流程")
    logger.info("=" * 50)
    
    try:
        from backend.app.agents.service import send_batch_messages_to_agent
        
        # 用户批量消息
        user_messages = ["你好啊", "你是谁", "我得了感冒"]
        
        logger.info(f"准备发送批量消息：")
        for idx, msg in enumerate(user_messages, 1):
            logger.info(f"   {idx}. {msg}")
        
        logger.info("")
        logger.info("开始处理批量消息...")
        
        # 调用批量消息处理服务
        batch_id, ai_replies = send_batch_messages_to_agent(
            db=db,
            user=user,
            agent_id=agent_id,
            user_messages=user_messages,
        )
        
        logger.info("")
        logger.info(f"✅ 批量消息处理成功！")
        logger.info(f"   批次ID: {batch_id}")
        logger.info(f"   收到 {len(ai_replies)} 条AI回复：")
        logger.info("")
        
        for idx, reply in enumerate(ai_replies, 1):
            delay = reply.get("send_delay_seconds", 0)
            content = reply.get("content", "")
            logger.info(f"   回复 {idx} (延迟 {delay}秒):")
            logger.info(f"   {content}")
            logger.info("")
        
        # 验证消息已保存到数据库
        from backend.app.agents.service import get_agent_session_messages, get_or_create_agent_session
        from backend.app.models.agent import Agent
        
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            session = get_or_create_agent_session(db, agent_id)
            messages = get_agent_session_messages(db, session.id)
            
            user_msg_count = len([m for m in messages if m.role == "user"])
            assistant_msg_count = len([m for m in messages if m.role == "assistant"])
            
            logger.info(f"   数据库验证：")
            logger.info(f"   - 用户消息数量: {user_msg_count}")
            logger.info(f"   - AI回复数量: {assistant_msg_count}")
        
        return batch_id, ai_replies
        
    except Exception as e:
        logger.error(f"❌ 批量消息处理失败: {e}", exc_info=True)
        return None, []


def main():
    """主测试函数"""
    logger.info("🚀 开始Agent模块测试")
    logger.info("=" * 50)

    db = SessionLocal()

    try:
        # 1. 检查数据库表
        tables_ok = _test_database_tables(db)
        if not tables_ok:
            logger.error("数据库表检查失败，请先确保表已创建")
            return

        # 2. 获取测试用户（使用第一个用户，或者创建一个）
        user = db.query(User).first()
        if not user:
            logger.error("❌ 没有找到用户，请先创建用户")
            return

        logger.info(f"使用用户: {user.username} (ID: {user.id})")
        logger.info("")

        # ========== 测试批量消息处理 ==========
        logger.info("=" * 50)
        logger.info("=" * 50)
        logger.info("测试场景：医学教授Agent + 批量消息")
        logger.info("=" * 50)
        logger.info("=" * 50)
        logger.info("")
        
        # 3. 创建医学教授Agent
        from backend.app.agents.service import create_agent
        
        logger.info("创建医学教授Agent...")
        medical_agent = create_agent(
            db=db,
            user=user,
            name="医学教授Agent",
            initial_prompt="你是一个医学教授，负责解答医学相关的问题"
        )
        
        logger.info(f"✅ 医学教授Agent创建成功！")
        logger.info(f"   Agent ID: {medical_agent.id}")
        logger.info(f"   Agent名称: {medical_agent.name}")
        logger.info(f"   初始Prompt: {medical_agent.initial_prompt}")
        logger.info("")
        
        # 4. 测试批量消息处理
        batch_id, ai_replies = _test_batch_messages(
            db=db,
            user=user,
            agent_id=medical_agent.id,
        )
        
        if batch_id:
            logger.info("=" * 50)
            logger.info("=" * 50)
            logger.info("✅ 批量消息处理测试完成！")
            logger.info("=" * 50)
            logger.info("=" * 50)
        
        logger.info("")
        logger.info("=" * 50)
        logger.info("✅ 所有测试完成！")

    except Exception as e:
        logger.error(f"❌ 测试过程出错: {e}", exc_info=True)

    finally:
        db.close()


if __name__ == "__main__":
    main()
