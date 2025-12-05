# backend/app/agents/test_agent.py
"""
Agent模块测试文件

用于快速测试Agent功能，方便开发调试

使用方法：
1. 直接运行（推荐）：python agents/test_agent.py
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
from backend.app.models.agent import Agent, AgentChatSession, AgentChatMessage
from backend.app.models.user import User

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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

        # 3. 列出现有Agent
        _test_list_agents(db, user)

        # 4. 创建测试Agent
        agent = _test_create_agent(db, user)

        if agent:
            # 5. 测试会话
            _test_agent_session(db, agent)

            # 6. 测试计算current_prompt
            from backend.app.agents.service import calculate_current_prompt
            current_prompt = calculate_current_prompt(db, agent)
            logger.info(f"当前Prompt长度: {len(current_prompt)} 字符")

            # 7. 测试更新Agent名称
            from backend.app.agents.service import update_agent_name
            updated_agent = update_agent_name(db, user, agent.id, "更新后的测试Agent")
            if updated_agent:
                logger.info(f"✅ Agent名称更新成功: {updated_agent.name}")

        logger.info("=" * 50)
        logger.info("✅ 测试完成！")

    except Exception as e:
        logger.error(f"❌ 测试过程出错: {e}", exc_info=True)

    finally:
        db.close()


if __name__ == "__main__":
    main()
