// ChatScreen.kt
package com.example.project1.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Image
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import android.util.Log
import android.net.Uri
import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import com.example.project1.network.*
import com.example.project1.ui.DisplayMessageContentOptimized
import com.example.project1.ui.ImagePreviewDialog
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.delay
import org.json.JSONObject
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.io.IOException
import java.io.InputStream
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.ByteArrayOutputStream
import android.util.Base64
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import coil.compose.AsyncImagePainter
import coil.compose.SubcomposeAsyncImage
import coil.compose.SubcomposeAsyncImageContent
import coil.request.ImageRequest

data class ChatMessageUi(
    val id: String,
    val content: String,
    val isUser: Boolean,
    val timestamp: String,
    val reasoningContent: String? = null,  // 深度思考内容
    val thinkingTimeMs: Long? = null,  // 深度思考时间（毫秒）
    val images: List<String>? = null,  // 用户上传的图片Base64列表（仅用户消息）
    val generatedImages: List<String>? = null  // 模型生成的图片URL列表（仅assistant消息）
)

// 注意：parseMessageContent 和 RenderMathContent 已移至 MarkdownRenderer.kt
// 这里保留 DisplayMessageContent 作为向后兼容，但实际使用 DisplayMessageContentWithMarkwon

private const val TAG = "ChatScreen"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onNavigateBack: () -> Unit,
    conversationId: String,
    onSessionCreated: ((Int) -> Unit)? = null  // 新会话创建时的回调
) {
    var showMenu by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val lazyListState = rememberLazyListState()

    var messages by remember { mutableStateOf<List<ChatMessageUi>>(emptyList()) }
    var inputText by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var streamingMessageId by remember { mutableStateOf<String?>(null) }
    var streamingContent by remember { mutableStateOf("") }
    var streamingReasoningContent by remember { mutableStateOf("") }  // 流式累积的深度思考内容
    var streamingGeneratedImages by remember { mutableStateOf<List<String>>(emptyList()) }  // 流式累积的生成图片URL列表
    var enableThinking by remember { mutableStateOf(false) }  // 深度思考开关
    var thinkingStartTime by remember { mutableStateOf<Long?>(null) }  // 深度思考开始时间
    var selectedImages by remember { mutableStateOf<List<Uri>>(emptyList()) }  // 选中的图片URI列表
    var previewImages by remember { mutableStateOf<List<androidx.compose.ui.graphics.ImageBitmap>?>(null) }  // 预览图片列表
    var previewInitialIndex by remember { mutableStateOf(0) }  // 预览初始索引
    val context = LocalContext.current
    
    // 图片选择器
    val imagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris: List<Uri> ->
        selectedImages = selectedImages + uris
    }

    LaunchedEffect(conversationId) {
        val existingId = conversationId.toIntOrNull()
        if (existingId != null) {
            scope.launch {
                try {
                    Log.d(TAG, "[ChatScreen] ========== 开始加载历史消息 ==========")
                    Log.d(TAG, "[ChatScreen] 会话ID: $existingId")
                    
                    loading = true
                    val token = SessionManager.authHeader()
                    Log.d(TAG, "[ChatScreen] 获取会话消息...")
                    
                    val resp = ApiClient.api.getSessionMessages(token, existingId)
                    Log.d(TAG, "[ChatScreen] 收到响应，消息数量: ${resp.messages.size}")
                    
                    messages = resp.messages.mapIndexed { index, msg ->
                        Log.d(TAG, "[ChatScreen] [IMAGE] 处理消息 $index:")
                        Log.d(TAG, "[ChatScreen] [IMAGE]   - ID: ${msg.id}, Role: ${msg.role}")
                        Log.d(TAG, "[ChatScreen] [IMAGE]   - Content长度: ${msg.content.length}")
                        Log.d(TAG, "[ChatScreen] [IMAGE]   - 用户上传图片数量: ${msg.images?.size ?: 0}")
                        Log.d(TAG, "[ChatScreen] [IMAGE]   - 生成图片数量: ${msg.generated_images?.size ?: 0}")
                        msg.images?.forEachIndexed { imgIndex, imgUrl ->
                            Log.d(TAG, "[ChatScreen] [IMAGE]   - 用户图片 $imgIndex 长度: ${imgUrl.length}, 前缀: ${imgUrl.take(50)}...")
                        }
                        msg.generated_images?.forEachIndexed { imgIndex, imgUrl ->
                            Log.d(TAG, "[ChatScreen] [IMAGE]   - 生成图片 $imgIndex URL: ${imgUrl.take(100)}...")
                        }
                        
                        ChatMessageUi(
                            id = msg.id.toString(),
                            content = msg.content,
                            isUser = msg.role == "user",
                            timestamp = msg.created_at,
                            reasoningContent = msg.reasoning_content,  // 加载深度思考内容
                            thinkingTimeMs = null,  // 历史消息不显示思考时间
                            images = msg.images,  // 加载用户上传的图片Base64列表
                            generatedImages = msg.generated_images  // 加载模型生成的图片URL列表
                        )
                    }
                    
                    Log.d(TAG, "[ChatScreen] ✅ 消息加载完成，共 ${messages.size} 条")
                    loading = false
                } catch (e: retrofit2.HttpException) {
                    // 处理HTTP错误（如404）
                    if (e.code() == 404) {
                        Log.w(TAG, "[ChatScreen] ⚠️ 会话不存在或尚未完全创建（404），这是正常情况，忽略错误")
                        Log.w(TAG, "[ChatScreen] 会话ID: $existingId，可能正在创建中")
                        // 404错误是正常的（新会话刚创建时可能还没有完全保存），不显示错误
                        messages = emptyList()
                    } else {
                        Log.e(TAG, "[ChatScreen] ❌ 加载消息失败，HTTP错误: ${e.code()}", e)
                        error = "加载消息失败：HTTP ${e.code()}"
                    }
                    loading = false
                } catch (e: Exception) {
                    Log.e(TAG, "[ChatScreen] ❌ 加载消息失败", e)
                    Log.e(TAG, "[ChatScreen] 错误类型: ${e.javaClass.simpleName}")
                    Log.e(TAG, "[ChatScreen] 错误消息: ${e.message}")
                    e.printStackTrace()
                    loading = false
                    error = "加载消息失败：${e.message}"
                }
            }
        }
    }

    // 自动滚动到底部 - 监听消息列表变化和流式内容变化
    LaunchedEffect(messages.size, streamingContent) {
        if (messages.isNotEmpty()) {
            // 使用 animateScrollToItem 平滑滚动
            try {
                lazyListState.animateScrollToItem(messages.size - 1)
            } catch (e: Exception) {
                // 如果动画失败，使用直接滚动
                try {
                    lazyListState.scrollToItem(messages.size - 1)
                } catch (e2: Exception) {
                    // 忽略滚动错误
                }
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = {
                Text(
                    text = if (conversationId == "new") "新对话" else "会话 $conversationId",
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            },
            navigationIcon = {
                IconButton(onClick = onNavigateBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "返回"
                    )
                }
            },
            actions = {
                Box {
                    IconButton(onClick = { showMenu = true }) {
                        Icon(
                            Icons.Filled.MoreVert,
                            contentDescription = "更多选项"
                        )
                    }
                    DropdownMenu(
                        expanded = showMenu,
                        onDismissRequest = { showMenu = false }
                    ) {
                        // 菜单项预留位置，供后续功能使用
                        // 例如：导出对话、分享对话等
                    }
                }
            }
        )

        if (loading) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }

        if (error != null) {
            Text(
                text = error!!,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(8.dp)
            )
        }

        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 8.dp),
            state = lazyListState,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(messages) { message ->
                MessageBubble(
                    message = message,
                    onImageClick = { images, index ->
                        previewImages = images
                        previewInitialIndex = index
                    }
                )
            }
        }

        // 深度思考开关
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "深度思考",
                modifier = Modifier.padding(end = 8.dp),
                fontSize = 14.sp
            )
            Switch(
                checked = enableThinking,
                onCheckedChange = { enableThinking = it }
            )
        }

        // 选中的图片预览
        if (selectedImages.isNotEmpty()) {
            Log.d(TAG, "[ChatScreen] 显示图片预览，数量: ${selectedImages.size}")
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(selectedImages.size) { index ->
                    val imageUri = selectedImages[index]
                    val colorScheme = MaterialTheme.colorScheme
                    
                    // DEBUG: 记录URI信息
                    LaunchedEffect(imageUri) {
                        Log.d(TAG, "[ChatScreen] 预览图片 $index: $imageUri")
                    }
                    
                    Box(
                        modifier = Modifier.size(80.dp)
                    ) {
                        // 使用Coil加载图片预览
                        SubcomposeAsyncImage(
                            model = ImageRequest.Builder(LocalContext.current)
                                .data(imageUri)
                                .crossfade(true)
                                .build(),
                            contentDescription = "图片预览 ${index + 1}",
                            modifier = Modifier
                                .fillMaxSize()
                                .clip(RoundedCornerShape(8.dp)),
                            contentScale = androidx.compose.ui.layout.ContentScale.Crop
                        ) {
                            val state = painter.state
                            when {
                                state is AsyncImagePainter.State.Loading -> {
                                    // 加载中显示占位符
                                    Log.d(TAG, "[ChatScreen] 预览图片 $index 加载中...")
                                    Box(
                                        modifier = Modifier
                                            .fillMaxSize()
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(colorScheme.surfaceVariant),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(20.dp),
                                            strokeWidth = 2.dp
                                        )
                                    }
                                }
                                state is AsyncImagePainter.State.Error -> {
                                    // 加载失败时显示占位符
                                    val error = state.result.throwable
                                    Log.e(TAG, "[ChatScreen] 预览图片 $index 加载失败", error)
                                    Log.e(TAG, "[ChatScreen] 错误类型: ${error?.javaClass?.simpleName}")
                                    Log.e(TAG, "[ChatScreen] 错误消息: ${error?.message}")
                                    Log.e(TAG, "[ChatScreen] URI: $imageUri")
                                    
                                    Box(
                                        modifier = Modifier
                                            .fillMaxSize()
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(colorScheme.surfaceVariant),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("图片 ${index + 1}", fontSize = 12.sp)
                                    }
                                }
                                state is AsyncImagePainter.State.Success -> {
                                    Log.d(TAG, "[ChatScreen] 预览图片 $index 加载成功")
                                    SubcomposeAsyncImageContent()
                                }
                                else -> {
                                    Log.d(TAG, "[ChatScreen] 预览图片 $index 状态: ${state.javaClass.simpleName}")
                                    SubcomposeAsyncImageContent()
                                }
                            }
                        }
                        // 删除按钮
                        IconButton(
                            onClick = { 
                                Log.d(TAG, "[ChatScreen] 删除预览图片 $index")
                                selectedImages = selectedImages.filterIndexed { i, _ -> i != index } 
                            },
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .size(24.dp)
                        ) {
                            Text("×", fontSize = 16.sp, color = colorScheme.error)
                        }
                    }
                }
            }
        }
        
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 图片选择按钮
            IconButton(
                onClick = { imagePickerLauncher.launch("image/*") }
            ) {
                Icon(
                    Icons.Filled.Image,
                    contentDescription = "选择图片",
                    tint = MaterialTheme.colorScheme.primary
                )
            }
            TextField(
                value = inputText,
                onValueChange = { inputText = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("输入消息...") }
            )
            Spacer(modifier = Modifier.width(8.dp))
            Button(
                onClick = {
                    if (inputText.isBlank() && selectedImages.isEmpty()) return@Button
                    scope.launch {
                        try {
                            loading = true
                            error = null
                            val token = SessionManager.authHeader()
                            val question = inputText
                            val images = selectedImages.toList()  // 保存当前选中的图片
                            inputText = ""
                            selectedImages = emptyList()  // 清空选中的图片

                            val currentConvId = conversationId.toIntOrNull()
                            val timestamp = System.currentTimeMillis()
                            
                            // 将图片URI转换为Base64编码
                            val imageBase64List = withContext(Dispatchers.IO) {
                                images.mapNotNull { uri ->
                                    try {
                                        val inputStream: InputStream? = context.contentResolver.openInputStream(uri)
                                        inputStream?.use { stream ->
                                            val bitmap = BitmapFactory.decodeStream(stream)
                                            val outputStream = ByteArrayOutputStream()
                                            
                                            // 使用JPEG格式压缩以减少大小（质量85%）
                                            // JPEG比PNG更适合照片，文件更小
                                            bitmap.compress(Bitmap.CompressFormat.JPEG, 85, outputStream)
                                            val imageBytes = outputStream.toByteArray()
                                            
                                            // 检查大小，如果超过5MB则进一步压缩
                                            val maxSize = 5 * 1024 * 1024  // 5MB
                                            val finalBytes = if (imageBytes.size > maxSize) {
                                                // 进一步压缩
                                                val compressedStream = ByteArrayOutputStream()
                                                var quality = 70
                                                bitmap.compress(Bitmap.CompressFormat.JPEG, quality, compressedStream)
                                                compressedStream.toByteArray()
                                            } else {
                                                imageBytes
                                            }
                                            
                                            // 转换为Base64字符串，并添加data URL前缀
                                            val base64 = Base64.encodeToString(finalBytes, Base64.NO_WRAP)
                                            // 构造完整的data URL格式：data:image/jpeg;base64,{base64}
                                            val dataUrl = "data:image/jpeg;base64,$base64"
                                            Log.d(TAG, "图片转Base64成功，原始大小: ${imageBytes.size} bytes, 最终大小: ${finalBytes.size} bytes, Base64长度: ${base64.length}, DataURL长度: ${dataUrl.length}")
                                            dataUrl
                                        }
                                    } catch (e: Exception) {
                                        Log.e(TAG, "图片转Base64失败: ${e.message}", e)
                                        null
                                    }
                                }
                            }
                            
                            // 先添加用户消息到 UI
                            val tempUserId = "temp_user_$timestamp"
                            val userMessage = ChatMessageUi(
                                id = tempUserId,
                                content = question,
                                isUser = true,
                                timestamp = "",
                                reasoningContent = null,
                                thinkingTimeMs = null,
                                images = if (imageBase64List.isNotEmpty()) imageBase64List else null
                            )
                            messages = messages + userMessage
                            
                            // 添加一个空的 AI 消息占位符，显示加载状态
                            val tempAiId = "temp_ai_$timestamp"
                            streamingMessageId = tempAiId
                            streamingContent = ""
                            streamingReasoningContent = ""  // 重置深度思考内容
                            messages = messages + ChatMessageUi(
                                id = tempAiId,
                                content = "正在思考...", // 初始占位文本
                                isUser = false,
                                timestamp = "",
                                reasoningContent = null,
                                thinkingTimeMs = null
                            )

                            // 使用 OkHttp 直接处理流式响应，避免 Retrofit 缓冲
                            // Log.d(TAG, "[Chat] 准备发送流式请求，问题: $question")
                            
                            scope.launch {
                                try {
                                    // 构建请求 URL 和 body
                                    val url = if (currentConvId == null) {
                                        "${ApiClient.BASE_URL}chat/sessions/stream"
                                    } else {
                                        "${ApiClient.BASE_URL}chat/sessions/$currentConvId/messages/stream"
                                    }
                                    
                                    val thinkingValue = if (enableThinking) "enabled" else "disabled"
                                    
                                    // DEBUG: 打印前端发送的请求
                                    Log.d(TAG, "[Frontend] ========== 发送流式请求 ==========")
                                    Log.d(TAG, "[Frontend] enableThinking开关状态: $enableThinking")
                                    Log.d(TAG, "[Frontend] thinking参数值: $thinkingValue")
                                    Log.d(TAG, "[Frontend] 问题: $question")
                                    Log.d(TAG, "[Frontend] 图片数量: ${imageBase64List.size}")
                                    
                                    val requestBody = if (currentConvId == null) {
                                        val json = org.json.JSONObject().apply {
                                            put("question", question)
                                            put("title", JSONObject.NULL)
                                            put("thinking", thinkingValue)
                                            // 添加图片Base64列表（如果有）
                                            if (imageBase64List.isNotEmpty()) {
                                                val imagesArray = org.json.JSONArray()
                                                imageBase64List.forEach { base64 ->
                                                    imagesArray.put(base64)
                                                }
                                                put("images", imagesArray)
                                                Log.d(TAG, "[Frontend] 添加了 ${imageBase64List.size} 张图片的Base64编码")
                                            }
                                        }
                                        val jsonString = json.toString()
                                        Log.d(TAG, "[Frontend] 请求JSON (新会话): $jsonString")
                                        jsonString.toRequestBody("application/json".toMediaType())
                                    } else {
                                        val json = org.json.JSONObject().apply {
                                            put("question", question)
                                            put("thinking", thinkingValue)
                                            // 添加图片Base64列表（如果有）
                                            if (imageBase64List.isNotEmpty()) {
                                                val imagesArray = org.json.JSONArray()
                                                imageBase64List.forEach { base64 ->
                                                    imagesArray.put(base64)
                                                }
                                                put("images", imagesArray)
                                                Log.d(TAG, "[Frontend] 添加了 ${imageBase64List.size} 张图片的Base64编码")
                                            }
                                        }
                                        val jsonString = json.toString()
                                        Log.d(TAG, "[Frontend] 请求JSON (已有会话): $jsonString")
                                        jsonString.toRequestBody("application/json".toMediaType())
                                    }
                                    
                                    // 如果启用深度思考，记录开始时间
                                    if (enableThinking) {
                                        thinkingStartTime = System.currentTimeMillis()
                                        Log.d(TAG, "[Frontend] 深度思考已启用，开始计时")
                                    }
                                    
                                    val request = okhttp3.Request.Builder()
                                        .url(url)
                                        .post(requestBody)
                                        .addHeader("Authorization", token)
                                        .addHeader("Content-Type", "application/json")
                                        .addHeader("Accept", "text/event-stream")
                                        .build()
                                    
                                    // Log.d(TAG, "[Chat] 发送 OkHttp 请求: $url")
                                    
                                    // 使用 OkHttp 直接处理，确保流式响应
                                    val call = ApiClient.okHttpClient.newCall(request)
                                    
                                    call.enqueue(object : okhttp3.Callback {
                                        override fun onResponse(
                                            call: okhttp3.Call,
                                            response: okhttp3.Response
                                        ) {
                                            // Log.d(TAG, "[Chat] 收到响应，成功: ${response.isSuccessful}, code: ${response.code}")
                                            if (response.isSuccessful && response.body != null) {
                                                // Log.d(TAG, "[Chat] 响应体不为空，开始解析流式数据")
                                                // 关键：立即获取 ResponseBody，在 IO 线程处理
                                                scope.launch(Dispatchers.IO) {
                                                    var sessionId: Int? = null
                                                    var userMsgId: Int? = null
                                                    var assistantMsgId: Int? = null
                                                    var eventCount = 0
                                                    
                                                    // 立即获取 ResponseBody，开始流式读取
                                                    val responseBody = response.body!!
                                                    // Log.d(TAG, "[Chat] ResponseBody 已获取，开始收集SSE事件")
                                                    
                                                    // 处理流式响应 - 使用 collect 确保实时处理
                                                    try {
                                                        // Log.d(TAG, "[Chat] 开始收集SSE事件")
                                                        SSEParser.parse(responseBody).collect { event ->
                                                            eventCount++
                                                            Log.d(TAG, "[Frontend] [IMAGE] ========== 收到事件 #$eventCount ==========")
                                                            Log.d(TAG, "[Frontend] [IMAGE] 事件类型: ${event.eventType}")
                                                            Log.d(TAG, "[Frontend] [IMAGE] 数据长度: ${event.data.length}, 预览: ${event.data.take(100)}")
                                                            // 切换到主线程更新UI
                                                            withContext(Dispatchers.Main) {
                                                                when (event.eventType) {
                                                                    "start" -> {
                                                                        Log.d(TAG, "[Frontend] [IMAGE] 处理start事件")
                                                                        // 流式输出开始，清除占位文本
                                                                        streamingContent = ""
                                                                        streamingReasoningContent = ""  // 重置深度思考内容
                                                                        streamingGeneratedImages = emptyList()  // 重置生成的图片列表
                                                                        val currentMessages = messages.toMutableList()
                                                                        val aiMessageIndex = currentMessages.indexOfFirst { it.id == tempAiId }
                                                                        if (aiMessageIndex >= 0) {
                                                                            currentMessages[aiMessageIndex] = currentMessages[aiMessageIndex].copy(
                                                                                content = ""
                                                                            )
                                                                            messages = currentMessages
                                                                        }
                                                                    }
                                                                    "reasoning" -> {
                                                                        // 收到深度思考内容片段（流式）
                                                                        Log.d(TAG, "[Frontend] ========== 收到reasoning事件 ==========")
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        Log.d(TAG, "[Frontend] reasoning事件JSON: $json")
                                                                        val reasoningChunk = json?.optString("reasoning_content")
                                                                        Log.d(TAG, "[Frontend] reasoning_content片段: ${reasoningChunk?.take(50)}...")
                                                                        
                                                                        reasoningChunk?.let { chunk ->
                                                                            // 累积流式的reasoning_content片段
                                                                            streamingReasoningContent += chunk
                                                                            Log.d(TAG, "[Frontend] 累积reasoning片段，片段长度: ${chunk.length}, 累积总长度: ${streamingReasoningContent.length}")
                                                                            
                                                                            // 计算深度思考时间（从开始到当前）
                                                                            val thinkingTime = thinkingStartTime?.let { start ->
                                                                                System.currentTimeMillis() - start
                                                                            }
                                                                            Log.d(TAG, "[Frontend] 深度思考时间: ${thinkingTime}ms")
                                                                            
                                                                            // 实时更新消息的reasoning_content
                                                                            val currentMessages = messages.toMutableList()
                                                                            val aiMessageIndex = currentMessages.indexOfFirst { it.id == tempAiId }
                                                                            Log.d(TAG, "[Frontend] AI消息索引: $aiMessageIndex, tempAiId: $tempAiId")
                                                                            
                                                                            if (aiMessageIndex >= 0) {
                                                                                val currentMessage = currentMessages[aiMessageIndex]
                                                                                Log.d(TAG, "[Frontend] 当前消息content: '${currentMessage.content}', reasoningContent: ${currentMessage.reasoningContent?.take(20)}...")
                                                                                
                                                                                // 如果content还是"正在思考..."，清除它，让深度思考内容可以显示
                                                                                val updatedContent = if (currentMessage.content == "正在思考...") {
                                                                                    Log.d(TAG, "[Frontend] 清除'正在思考...'占位文本")
                                                                                    ""  // 清除占位文本
                                                                                } else {
                                                                                    currentMessage.content
                                                                                }
                                                                                
                                                                                currentMessages[aiMessageIndex] = currentMessage.copy(
                                                                                    content = updatedContent,  // 清除"正在思考..."占位文本
                                                                                    reasoningContent = streamingReasoningContent,  // 使用累积的完整内容
                                                                                    thinkingTimeMs = thinkingTime
                                                                                )
                                                                                messages = currentMessages
                                                                                Log.d(TAG, "[Frontend] ✅ 已更新消息，reasoningContent长度: ${streamingReasoningContent.length}, content: '${updatedContent}'")
                                                                            } else {
                                                                                Log.w(TAG, "[Frontend] ⚠️ 找不到AI消息，ID: $tempAiId, 当前消息数: ${messages.size}")
                                                                                Log.w(TAG, "[Frontend] 当前消息ID列表: ${messages.map { it.id }}")
                                                                            }
                                                                        } ?: run {
                                                                            Log.w(TAG, "[Frontend] ⚠️ reasoning_content片段为空")
                                                                        }
                                                                    }
                                                                    "session_created" -> {
                                                                        Log.d(TAG, "[Frontend] [IMAGE] ========== 收到session_created事件 ==========")
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        json?.let {
                                                                            val newSessionId = it.optInt("session_id")
                                                                            sessionId = newSessionId
                                                                            Log.d(TAG, "[Frontend] [IMAGE] 新会话ID: $newSessionId")
                                                                            
                                                                            // 注意：不在收到session_created时立即更新导航
                                                                            // 因为这会触发导航更新，导致当前的ChatScreen被替换，协程作用域被取消
                                                                            // 我们将在收到complete事件时再更新导航
                                                                            Log.d(TAG, "[Frontend] [IMAGE] 会话ID已保存，等待complete事件后再更新导航")
                                                                        }
                                                                    }
                                                                    "user_msg_created" -> {
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        json?.let {
                                                                            userMsgId = it.optInt("message_id")
                                                                            // 更新用户消息 ID
                                                                            val currentMessages = messages.toMutableList()
                                                                            val userMessageIndex = currentMessages.indexOfFirst { it.id == tempUserId }
                                                                            if (userMessageIndex >= 0) {
                                                                                currentMessages[userMessageIndex] = currentMessages[userMessageIndex].copy(
                                                                                    id = userMsgId.toString()
                                                                                )
                                                                                messages = currentMessages
                                                                            }
                                                                        }
                                                                    }
                                                                    "chunk" -> {
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        val chunk = json?.optString("content") ?: event.data
                                                                        // DEBUG: 检查chunk事件中是否有reasoning_content
                                                                        if (json != null && json.has("reasoning_content")) {
                                                                            Log.d(TAG, "[Frontend] ⚠️ chunk事件中包含reasoning_content字段！")
                                                                            Log.d(TAG, "[Frontend] chunk事件JSON: ${json.toString()}")
                                                                        }
                                                                        // Log.d(TAG, "[Chat] 处理chunk事件，chunk长度: ${chunk.length}, 内容预览: ${chunk.take(30)}")
                                                                        streamingContent += chunk
                                                                        // Log.d(TAG, "[Chat] 更新流式内容，总长度: ${streamingContent.length}")
                                                                        // 优化：只更新流式消息，避免重建整个列表
                                                                        val currentMessages = messages.toMutableList()
                                                                        val aiMessageIndex = currentMessages.indexOfFirst { it.id == tempAiId }
                                                                        if (aiMessageIndex >= 0) {
                                                                            currentMessages[aiMessageIndex] = currentMessages[aiMessageIndex].copy(
                                                                                content = streamingContent
                                                                            )
                                                                            messages = currentMessages
                                                                            // Log.d(TAG, "[Chat] 已更新消息列表，消息内容长度: ${messages[aiMessageIndex].content.length}")
                                                                        } else {
                                                                            // Log.w(TAG, "[Chat] 警告：找不到AI消息，ID: $tempAiId")
                                                                            // 如果找不到，回退到原来的方式
                                                                            messages = messages.map { msg ->
                                                                                if (msg.id == tempAiId) {
                                                                                    msg.copy(content = streamingContent)
                                                                                } else {
                                                                                    msg
                                                                                }
                                                                            }
                                                                        }
                                                                    }
                                                                    "image_generating" -> {
                                                                        Log.d(TAG, "[Frontend] [IMAGE] ========== 收到image_generating事件 ==========")
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        val message = json?.optString("message") ?: "正在生成图片，请稍候..."
                                                                        Log.d(TAG, "[Frontend] [IMAGE] 图片生成中: $message")
                                                                        
                                                                        // 更新消息内容，显示图片生成状态
                                                                        val currentMessages = messages.toMutableList()
                                                                        val aiMessageIndex = currentMessages.indexOfFirst { it.id == tempAiId }
                                                                        if (aiMessageIndex >= 0) {
                                                                            currentMessages[aiMessageIndex] = currentMessages[aiMessageIndex].copy(
                                                                                content = message
                                                                            )
                                                                            messages = currentMessages
                                                                            Log.d(TAG, "[Frontend] [IMAGE] ✅ 已更新消息，显示图片生成状态")
                                                                        }
                                                                    }
                                                                    "image_generated" -> {
                                                                        Log.d(TAG, "[Frontend] [IMAGE] ========== 收到image_generated事件 ==========")
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        Log.d(TAG, "[Frontend] [IMAGE] image_generated事件JSON: $json")
                                                                        
                                                                        // 提取图片URL列表
                                                                        val imageUrls = mutableListOf<String>()
                                                                        if (json != null) {
                                                                            // 尝试获取image_urls数组
                                                                            val imageUrlsArray = json.optJSONArray("image_urls")
                                                                            if (imageUrlsArray != null) {
                                                                                for (i in 0 until imageUrlsArray.length()) {
                                                                                    val url = imageUrlsArray.optString(i)
                                                                                    if (url.isNotEmpty()) {
                                                                                        imageUrls.add(url)
                                                                                    }
                                                                                }
                                                                            } else {
                                                                                // 如果没有数组，尝试获取单个image_url
                                                                                val singleUrl = json.optString("image_url")
                                                                                if (singleUrl.isNotEmpty()) {
                                                                                    imageUrls.add(singleUrl)
                                                                                }
                                                                            }
                                                                        }
                                                                        
                                                                        Log.d(TAG, "[Frontend] [IMAGE] 提取到 ${imageUrls.size} 张图片URL")
                                                                        imageUrls.forEachIndexed { index, url ->
                                                                            Log.d(TAG, "[Frontend] [IMAGE] 图片 $index: ${url.take(100)}...")
                                                                        }
                                                                        
                                                                        // 更新消息，添加生成的图片
                                                                        streamingGeneratedImages = imageUrls
                                                                        val currentMessages = messages.toMutableList()
                                                                        val aiMessageIndex = currentMessages.indexOfFirst { it.id == tempAiId }
                                                                        if (aiMessageIndex >= 0) {
                                                                            val currentMessage = currentMessages[aiMessageIndex]
                                                                            currentMessages[aiMessageIndex] = currentMessage.copy(
                                                                                content = currentMessage.content.ifEmpty { "图片已生成" },
                                                                                generatedImages = imageUrls
                                                                            )
                                                                            messages = currentMessages
                                                                            Log.d(TAG, "[Frontend] [IMAGE] ✅ 已更新消息，添加 ${imageUrls.size} 张生成的图片")
                                                                        } else {
                                                                            Log.w(TAG, "[Frontend] [IMAGE] ⚠️ 找不到AI消息，ID: $tempAiId")
                                                                        }
                                                                    }
                                                                    "content_update" -> {
                                                                        Log.d(TAG, "[Frontend] [IMAGE] ========== 收到content_update事件 ==========")
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        val updatedContent = json?.optString("content")
                                                                        Log.d(TAG, "[Frontend] [IMAGE] 更新的内容: ${updatedContent?.take(50)}...")
                                                                        
                                                                        // 更新消息内容（图片描述）
                                                                        updatedContent?.let { content ->
                                                                            val currentMessages = messages.toMutableList()
                                                                            val aiMessageIndex = currentMessages.indexOfFirst { it.id == tempAiId }
                                                                            if (aiMessageIndex >= 0) {
                                                                                val currentMessage = currentMessages[aiMessageIndex]
                                                                                currentMessages[aiMessageIndex] = currentMessage.copy(
                                                                                    content = content
                                                                                )
                                                                                messages = currentMessages
                                                                                Log.d(TAG, "[Frontend] [IMAGE] ✅ 已更新消息内容（图片描述）")
                                                                            } else {
                                                                                Log.w(TAG, "[Frontend] [IMAGE] ⚠️ 找不到AI消息，无法更新内容")
                                                                            }
                                                                        }
                                                                    }
                                                                    "complete", "end" -> {
                                                                        Log.d(TAG, "[Frontend] [IMAGE] ========== 收到complete/end事件 ==========")
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        json?.let {
                                                                            assistantMsgId = it.optInt("assistant_msg_id", -1)
                                                                            if (assistantMsgId == -1) {
                                                                                assistantMsgId = null
                                                                            }
                                                                            if (userMsgId == null) {
                                                                                val uid = it.optInt("user_msg_id", -1)
                                                                                userMsgId = if (uid != -1) uid else null
                                                                            }
                                                                            if (sessionId == null) {
                                                                                val sid = it.optInt("session_id", -1)
                                                                                sessionId = if (sid != -1) sid else null
                                                                            }
                                                                            
                                                                            // 在流式响应完成后，如果当前conversationId是"new"，更新导航
                                                                            val currentSessionId = sessionId
                                                                            if (conversationId == "new" && currentSessionId != null && currentSessionId > 0) {
                                                                                Log.d(TAG, "[Frontend] [IMAGE] 流式响应完成，检测到新会话创建，更新导航: $currentSessionId")
                                                                                // 使用协程延迟一小段时间，确保所有UI更新完成
                                                                                scope.launch {
                                                                                    kotlinx.coroutines.delay(100) // 延迟100ms，确保UI更新完成
                                                                                    onSessionCreated?.invoke(currentSessionId)
                                                                                }
                                                                            }
                                                                        }
                                                                        // 更新消息 ID 为真实的数据库 ID，并确保生成的图片被保存
                                                                        val currentMessages = messages.toMutableList()
                                                                        currentMessages.forEachIndexed { index, msg ->
                                                                            when {
                                                                                msg.id == tempUserId && userMsgId != null -> {
                                                                                    currentMessages[index] = msg.copy(id = userMsgId.toString())
                                                                                }
                                                                                msg.id == tempAiId && assistantMsgId != null -> {
                                                                                    // 确保生成的图片被保存到最终消息中
                                                                                    currentMessages[index] = msg.copy(
                                                                                        id = assistantMsgId.toString(),
                                                                                        generatedImages = streamingGeneratedImages.ifEmpty { msg.generatedImages }
                                                                                    )
                                                                                }
                                                                            }
                                                                        }
                                                                        messages = currentMessages
                                                                        streamingMessageId = null
                                                                        streamingContent = ""
                                                                        streamingReasoningContent = ""  // 重置深度思考内容
                                                                        streamingGeneratedImages = emptyList()  // 重置生成的图片列表
                                                                        thinkingStartTime = null  // 重置深度思考开始时间
                                                                        loading = false
                                                                        Log.d(TAG, "[Frontend] [IMAGE] ✅ 流式响应完成")
                                                                    }
                                                                    "error" -> {
                                                                        val json = SSEParser.parseJsonData(event.data)
                                                                        val errorMsg = json?.optString("error") ?: event.data
                                                                        error = "错误：$errorMsg"
                                                                        // 移除流式消息
                                                                        messages = messages.filter { it.id != tempAiId && it.id != tempUserId }
                                                                        streamingMessageId = null
                                                                        streamingContent = ""
                                                                        streamingReasoningContent = ""  // 重置深度思考内容
                                                                        thinkingStartTime = null
                                                                        loading = false
                                                                    }
                                                                    else -> {
                                                                        // 处理其他事件类型（如 "chunk" 等）
                                                                        // 如果事件类型是 "chunk"，已经在上面处理了
                                                                    }
                                                                }
                                                            }
                                                        }
                                                        // Log.d(TAG, "[Chat] SSE事件收集完成，共处理 $eventCount 个事件")
                                                        withContext(Dispatchers.Main) {
                                                            loading = false
                                                        }
                                                    } catch (e: Exception) {
                                                        // Log.e(TAG, "[Chat] 流式处理错误: ${e.message}", e)
                                                        withContext(Dispatchers.Main) {
                                                            error = "流式处理错误：${e.message}"
                                                            loading = false
                                                        }
                                                    } finally {
                                                        response.close()
                                                    }
                                                }
                                            } else {
                                                // Log.e(TAG, "[Chat] 响应失败或响应体为空，code: ${response.code}")
                                                scope.launch {
                                                    error = "请求失败：${response.code}"
                                                    messages = messages.filter { it.id != tempAiId && it.id != tempUserId }
                                                    streamingMessageId = null
                                                    streamingContent = ""
                                                    streamingReasoningContent = ""
                                                    thinkingStartTime = null
                                                    loading = false
                                                }
                                                response.close()
                                            }
                                        }

                                        override fun onFailure(call: okhttp3.Call, e: IOException) {
                                            // Log.e(TAG, "[Chat] 网络请求失败: ${e.message}", e)
                                            scope.launch {
                                                error = "网络错误：${e.message}"
                                                messages = messages.filter { it.id != tempAiId && it.id != tempUserId }
                                                streamingMessageId = null
                                                streamingContent = ""
                                                streamingReasoningContent = ""
                                                thinkingStartTime = null
                                                loading = false
                                            }
                                        }
                                    })
                                } catch (e: Exception) {
                                    // Log.e(TAG, "[Chat] 请求构建错误: ${e.message}", e)
                                    error = "请求错误：${e.message}"
                                    loading = false
                                }
                            }
                        } catch (e: Exception) {
                            loading = false
                            error = "发送失败：${e.message}"
                        }
                    }
                },
                enabled = (inputText.isNotBlank() || selectedImages.isNotEmpty()) && !loading
            ) {
                Text("发送")
            }
        }
        
        // 图片预览对话框
        previewImages?.let { images ->
            ImagePreviewDialog(
                images = images,
                initialIndex = previewInitialIndex,
                onDismiss = { previewImages = null }
            )
        }
    }
}

@Composable
fun MessageBubble(
    message: ChatMessageUi,
    onImageClick: (List<androidx.compose.ui.graphics.ImageBitmap>, Int) -> Unit = { _, _ -> }
) {
    val isUser = message.isUser
    val bubbleColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.surfaceVariant
    }
    val textColor = if (isUser) {
        MaterialTheme.colorScheme.onPrimary
    } else {
        MaterialTheme.colorScheme.onSurfaceVariant
    }
    
    // 深度思考内容折叠状态
    // 默认展开，让用户可以看到思考过程
    var isReasoningExpanded by remember { mutableStateOf(true) }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Column(
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start,
            // 修复：使用更合适的宽度限制，避免截断
            modifier = Modifier.fillMaxWidth(if (isUser) 0.85f else 0.9f)
        ) {
            // 深度思考内容（仅在非用户消息且有深度思考内容时显示）
            // 注意：即使content为空，只要有reasoningContent就应该显示深度思考卡片
            if (!isUser && message.reasoningContent != null && message.reasoningContent.isNotEmpty()) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 4.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                    )
                ) {
                    Column {
                        // 折叠/展开按钮和标题
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                Text(
                                    text = "深度思考",
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                                    modifier = Modifier.padding(end = 8.dp)
                                )
                                message.thinkingTimeMs?.let { timeMs ->
                                    val seconds = timeMs / 1000.0
                                    Text(
                                        text = "已深度思考 ${String.format("%.1f", seconds)}秒",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
                                    )
                                }
                            }
                            IconButton(
                                onClick = { isReasoningExpanded = !isReasoningExpanded },
                                modifier = Modifier.size(24.dp)
                            ) {
                                Icon(
                                    imageVector = if (isReasoningExpanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                                    contentDescription = if (isReasoningExpanded) "折叠" else "展开",
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        }
                        
                        // 深度思考内容（可折叠）
                        if (isReasoningExpanded) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 12.dp, vertical = 8.dp)
                                    .padding(bottom = 8.dp)
                            ) {
                                Text(
                                    text = message.reasoningContent,
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }
                }
            }
            
            // 显示生成的图片（如果有，仅assistant消息）
            message.generatedImages?.let { imageUrls ->
                if (imageUrls.isNotEmpty()) {
                    Log.d(TAG, "[MessageBubble] [IMAGE] 显示生成的图片，数量: ${imageUrls.size}")
                    imageUrls.forEachIndexed { index, url ->
                        Log.d(TAG, "[MessageBubble] [IMAGE] 生成图片 $index: ${url.take(100)}...")
                    }
                    
                    LazyRow(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(imageUrls.size) { index ->
                            val imageUrl = imageUrls[index]
                            val colorScheme = MaterialTheme.colorScheme
                            
                            Box(
                                modifier = Modifier
                                    .size(200.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(colorScheme.surfaceVariant)
                                    .clickable {
                                        // 点击图片，打开预览（需要将URL转换为Bitmap）
                                        // 这里可以后续优化为直接使用URL预览
                                        Log.d(TAG, "[MessageBubble] [IMAGE] 点击生成的图片 $index")
                                    }
                            ) {
                                // 使用Coil加载网络图片
                                SubcomposeAsyncImage(
                                    model = ImageRequest.Builder(LocalContext.current)
                                        .data(imageUrl)
                                        .crossfade(true)
                                        .build(),
                                    contentDescription = "生成的图片 ${index + 1}",
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .clip(RoundedCornerShape(8.dp)),
                                    contentScale = androidx.compose.ui.layout.ContentScale.Crop
                                ) {
                                    val state = painter.state
                                    when {
                                        state is AsyncImagePainter.State.Loading -> {
                                            Box(
                                                modifier = Modifier
                                                    .fillMaxSize()
                                                    .clip(RoundedCornerShape(8.dp))
                                                    .background(colorScheme.surfaceVariant),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                CircularProgressIndicator(
                                                    modifier = Modifier.size(20.dp),
                                                    strokeWidth = 2.dp
                                                )
                                            }
                                        }
                                        state is AsyncImagePainter.State.Error -> {
                                            val error = state.result.throwable
                                            Log.e(TAG, "[MessageBubble] [IMAGE] 加载生成的图片失败", error)
                                            Box(
                                                modifier = Modifier.fillMaxSize(),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                Column(
                                                    horizontalAlignment = Alignment.CenterHorizontally,
                                                    modifier = Modifier.padding(8.dp)
                                                ) {
                                                    Text(
                                                        "加载失败",
                                                        fontSize = 12.sp,
                                                        color = colorScheme.error
                                                    )
                                                }
                                            }
                                        }
                                        state is AsyncImagePainter.State.Success -> {
                                            SubcomposeAsyncImageContent()
                                        }
                                        else -> {
                                            SubcomposeAsyncImageContent()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            // 显示用户上传的图片（如果有，仅用户消息）
            message.images?.let { imageDataUrls ->
                if (imageDataUrls.isNotEmpty()) {
                    Log.d(TAG, "[MessageBubble] 显示图片，数量: ${imageDataUrls.size}")
                    
                    // 解码所有图片为Bitmap列表
                    val imageBitmaps = remember(imageDataUrls) {
                        imageDataUrls.mapNotNull { imageDataUrl ->
                            try {
                                // 提取Base64部分（去掉 data:image/jpeg;base64, 前缀）
                                val base64String = if (imageDataUrl.startsWith("data:")) {
                                    val commaIndex = imageDataUrl.indexOf(',')
                                    if (commaIndex >= 0) {
                                        imageDataUrl.substring(commaIndex + 1)
                                    } else {
                                        imageDataUrl
                                    }
                                } else {
                                    imageDataUrl
                                }
                                
                                // 解码Base64
                                val imageBytes = Base64.decode(base64String, Base64.DEFAULT)
                                
                                // 转换为Bitmap
                                val bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
                                bitmap?.asImageBitmap()
                            } catch (e: Exception) {
                                Log.e(TAG, "[MessageBubble] 图片解码失败", e)
                                null
                            }
                        }
                    }
                    
                    LazyRow(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(imageBitmaps.size) { index ->
                            val imageBitmap = imageBitmaps[index]
                            val colorScheme = MaterialTheme.colorScheme
                            
                            Box(
                                modifier = Modifier
                                    .size(200.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(colorScheme.surfaceVariant)
                                    .clickable {
                                        // 点击图片，打开预览
                                        onImageClick(imageBitmaps, index)
                                    }
                            ) {
                                when {
                                    imageBitmap != null -> {
                                        // 成功解码，显示图片
                                        Image(
                                            bitmap = imageBitmap,
                                            contentDescription = "图片 ${index + 1}",
                                            modifier = Modifier.fillMaxSize(),
                                            contentScale = androidx.compose.ui.layout.ContentScale.Crop
                                        )
                                    }
                                    else -> {
                                        // 解码失败，显示错误信息
                                        Box(
                                            modifier = Modifier.fillMaxSize(),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Column(
                                                horizontalAlignment = Alignment.CenterHorizontally,
                                                modifier = Modifier.padding(8.dp)
                                            ) {
                                                Text(
                                                    "加载失败",
                                                    fontSize = 12.sp,
                                                    color = colorScheme.error
                                                )
                                                Text(
                                                    "无法解码图片",
                                                    fontSize = 10.sp,
                                                    color = colorScheme.error.copy(alpha = 0.7f),
                                                    modifier = Modifier.padding(top = 4.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            // 正常消息内容（只有当content不为空时才显示消息气泡）
            // 如果content为空但有reasoningContent，不显示空的消息气泡
            if (message.content.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .clip(
                            RoundedCornerShape(
                                topStart = 16.dp,
                                topEnd = 16.dp,
                                bottomStart = if (isUser) 16.dp else 4.dp,
                                bottomEnd = if (isUser) 4.dp else 16.dp
                            )
                        )
                        .background(bubbleColor)
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                ) {
                    // 使用高性能的 Markwon 渲染（替代 WebView）
                    DisplayMessageContentOptimized(message.content)
                }
            } else if (!isUser && (message.reasoningContent.isNullOrEmpty()) && message.images.isNullOrEmpty() && message.generatedImages.isNullOrEmpty()) {
                // 如果既没有content也没有reasoningContent，显示"正在思考..."
                Box(
                    modifier = Modifier
                        .clip(
                            RoundedCornerShape(
                                topStart = 16.dp,
                                topEnd = 16.dp,
                                bottomStart = 4.dp,
                                bottomEnd = 16.dp
                            )
                        )
                        .background(bubbleColor)
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                ) {
                    Text(
                        text = "正在思考...",
                        fontSize = 14.sp,
                        color = textColor.copy(alpha = 0.7f)
                    )
                }
            }

            Text(
                text = message.timestamp,
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
            )
        }
    }
}