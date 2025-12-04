# 数据库迁移说明：添加 generated_images 字段

## 变更说明

为 `chat_messages` 表添加 `generated_images` 字段，用于存储模型生成的图片URL列表。

### 字段信息
- **字段名**: `generated_images`
- **类型**: JSON (或 TEXT，取决于数据库)
- **可空**: 是 (nullable=True)
- **用途**: 存储模型生成的图片URL列表（图片生成、图生图等功能）

### 字段设计
- `images`: 存储用户上传的图片（Base64编码，仅用户消息）
- `generated_images`: 存储模型生成的图片（URL列表，仅assistant消息）

## 迁移SQL脚本

### SQLite
```sql
ALTER TABLE chat_messages ADD COLUMN generated_images TEXT;
```

### PostgreSQL
```sql
ALTER TABLE chat_messages ADD COLUMN generated_images JSONB;
```

### MySQL
```sql
ALTER TABLE chat_messages ADD COLUMN generated_images JSON;
```

## 迁移步骤

### 方法1: 手动执行SQL（推荐用于生产环境）

1. 备份数据库
2. 连接到数据库
3. 执行上述对应的SQL语句
4. 验证字段已添加

### 方法2: 使用Python脚本（开发环境）

如果使用SQLite且数据不重要，可以删除数据库文件重新创建，或者执行：

```python
from backend.app.database.session import engine
from sqlalchemy import text

# 执行迁移
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE chat_messages ADD COLUMN generated_images TEXT"))
    conn.commit()
```

### 方法3: 删除重建（仅开发环境，会丢失数据）

如果当前是开发环境且可以接受数据丢失：

1. 删除数据库文件（SQLite）或删除表
2. 重新运行应用，`Base.metadata.create_all()` 会自动创建新表结构

## 验证

迁移完成后，可以通过以下方式验证：

```python
from backend.app.database.session import SessionLocal
from backend.app.models.chat import ChatMessage

db = SessionLocal()
# 检查字段是否存在
columns = [column.name for column in ChatMessage.__table__.columns]
assert 'generated_images' in columns
print("✅ generated_images 字段已添加")
```

## 注意事项

1. **数据兼容性**: 现有数据中 `generated_images` 字段将为 NULL，这是正常的
2. **向后兼容**: 新字段是可选的，不会影响现有功能
3. **数据格式**: `generated_images` 存储JSON格式的字符串列表，例如：`["url1", "url2"]`


