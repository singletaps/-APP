# 快速数据库迁移指南（开发环境）

## 方法1：使用迁移脚本（推荐）

运行迁移脚本：

```bash
cd E:\PythonProject2\backend
python migrate_database.py
```

脚本会自动：
1. 检测数据库文件位置
2. 删除旧数据库文件
3. 提示重启应用

## 方法2：手动删除数据库文件

1. 找到数据库文件：`E:/PythonProject2/chatbot.db`
2. 删除该文件
3. 重启后端应用

## 重启应用后

SQLAlchemy 会自动检测到数据库不存在，并创建新表结构（包含 `images` 字段）。

## 验证迁移

启动应用后，检查数据库文件是否重新创建，并确认 `chat_messages` 表包含 `images` 字段。



