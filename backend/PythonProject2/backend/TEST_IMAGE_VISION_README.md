# 图像理解功能测试说明

## 测试脚本

运行测试脚本：
```bash
cd E:\PythonProject2\backend
python test_image_vision.py
```

## 测试内容

1. **URL方式 - 非流式响应**：测试使用公开URL发送图像+文本
2. **URL方式 - 流式响应**：测试流式响应格式是否与文本响应一致
3. **Files API上传方式**：测试本地文件上传后使用（推荐方法）
4. **多张图片支持**：测试单条消息包含多张图片
5. **响应结构对比**：验证图像响应与文本响应结构是否一致

## 推荐的文件上传方法

根据火山引擎文档，推荐以下两种方式：

### 方法1：URL方式（推荐用于公开图片）

**适用场景**：
- 图片已经上传到可公开访问的服务器
- 使用火山引擎对象存储服务
- 图片URL可以直接访问

**实现方式**：
```python
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://example.com/image.jpg"
                },
            },
            {"type": "text", "text": "请描述这张图片。"},
        ],
    },
]
```

**优点**：
- 实现简单，直接使用URL
- 不需要额外的上传步骤
- 适合已有图片存储服务的场景

**缺点**：
- 需要图片可公开访问
- 需要额外的图片存储服务

### 方法2：Files API上传（推荐用于本地文件）

**适用场景**：
- 用户从本地选择图片
- 需要临时存储图片
- 图片不需要长期保存

**实现方式**：
```python
# 步骤1: 上传文件
with open("local_image.jpg", 'rb') as f:
    file_obj = client.files.create(
        file=f,
        purpose="vision"  # 根据文档确定purpose值
    )

# 步骤2: 获取file_id
file_id = file_obj.id  # 或 file_obj.file_id

# 步骤3: 使用file_id构造URL
file_url = f"file://{file_id}"

# 步骤4: 在消息中使用
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": file_url
                },
            },
            {"type": "text", "text": "请描述这张图片。"},
        ],
    },
]
```

**优点**：
- 支持本地文件
- 由火山引擎管理文件存储
- 不需要自己的图片存储服务

**缺点**：
- 需要额外的上传步骤
- 可能有文件大小和数量限制

## 图片大小限制建议

根据最佳实践，建议：
- **单张图片大小**：不超过 10MB
- **单条消息图片数量**：不超过 5-10 张（根据实际测试确定）
- **图片格式**：支持常见格式（JPEG, PNG, WebP等）

## 响应结构

根据测试结果，图像理解的响应结构与文本响应**完全一致**：

```python
# 非流式响应
completion.choices[0].message.content  # 文本内容

# 流式响应
chunk.choices[0].delta.content  # 文本片段
chunk.choices[0].delta.reasoning_content  # 深度思考内容（如果启用）
```

这意味着：
- ✅ 可以复用现有的响应处理代码
- ✅ 流式响应格式与文本响应相同
- ✅ 深度思考功能同样支持图像理解

## 多模态消息格式

支持在单条消息中混合文本和图片：

```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": "请分析这些图片："},
        {
            "type": "image_url",
            "image_url": {
                "url": "https://example.com/image1.jpg"
            },
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "https://example.com/image2.jpg"
            },
        },
        {"type": "text", "text": "它们有什么共同点？"},
    ],
}
```

## 实现建议

### 后端实现

1. **修改 schemas**：在 `ChatSessionCreate` 和 `ChatMessageCreate` 中添加 `images` 字段
   ```python
   images: Optional[List[str]] = None  # 图片URL列表
   ```

2. **修改 AI service**：支持多模态消息格式
   ```python
   def build_multimodal_content(text: str, image_urls: List[str]) -> List[Dict]:
       content = []
       for url in image_urls:
           content.append({
               "type": "image_url",
               "image_url": {"url": url}
           })
       content.append({"type": "text", "text": text})
       return content
   ```

3. **图片上传接口**（可选）：如果需要支持本地文件上传
   ```python
   @router.post("/upload-image")
   async def upload_image(file: UploadFile):
       # 使用Files API上传
       file_obj = client.files.create(file=file, purpose="vision")
       return {"file_id": file_obj.id, "url": f"file://{file_obj.id}"}
   ```

### Android实现

1. **图片选择**：使用 Android 图片选择器
2. **图片上传**：上传到后端获取URL，或直接使用Files API
3. **消息发送**：在请求体中包含图片URL列表
4. **UI显示**：在消息气泡中显示图片预览

## 测试结果检查

运行测试后，检查以下内容：

1. ✅ URL方式是否成功
2. ✅ 流式响应格式是否与文本响应一致
3. ✅ Files API上传是否可用
4. ✅ 多图片是否支持
5. ✅ 响应结构是否一致

如果所有测试通过，可以开始修改实际代码。



