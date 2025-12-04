# 数据库迁移说明 - 添加images字段

## 变更内容

在 `ChatMessage` 表中添加了 `images` 字段，用于存储图片的Base64编码列表。

## 数据库变更

```sql
ALTER TABLE chat_messages ADD COLUMN images JSON;
```

## 迁移方法

### 方法1：自动迁移（开发环境推荐）

如果使用SQLAlchemy的自动创建表功能，可以：

1. **删除旧表（注意：会丢失数据）**
   ```sql
   DROP TABLE IF EXISTS chat_messages;
   DROP TABLE IF EXISTS chat_sessions;
   ```

2. **重启应用**，SQLAlchemy会自动创建新表结构

### 方法2：手动迁移（生产环境推荐）

使用数据库迁移工具（如Alembic）或手动执行SQL：

```sql
-- 添加images字段
ALTER TABLE chat_messages ADD COLUMN images JSON;
```

### 方法3：使用Alembic（推荐用于生产环境）

如果项目使用Alembic进行数据库迁移：

```bash
# 生成迁移文件
alembic revision --autogenerate -m "add_images_field_to_chat_messages"

# 执行迁移
alembic upgrade head
```

## 字段说明

- **字段名**: `images`
- **类型**: `JSON` (PostgreSQL) 或 `TEXT` (SQLite)
- **可空**: `True`
- **用途**: 存储图片的Base64编码字符串列表（仅用户消息）
- **格式**: `["data:image/jpeg;base64,xxx", "data:image/jpeg;base64,yyy"]`

## 注意事项

1. 该字段仅用于用户消息，AI回复消息不需要存储图片
2. Base64编码会增加约33%的数据大小
3. 建议限制单条消息的图片数量和大小




