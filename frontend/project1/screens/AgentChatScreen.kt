// AgentChatScreen.kt
package com.example.project1.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.util.Log
import com.example.project1.network.*
import com.example.project1.ui.DisplayMessageContentOptimized
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.Job
import java.util.UUID
import kotlin.random.Random

data class AgentChatMessageUi(
    val id: String,
    val content: String,
    val isUser: Boolean,
    val timestamp: String,
    val batchId: String? = null,
    val batchIndex: Int? = null,
    val sendDelaySeconds: Int? = null
)

private const val TAG = "AgentChatScreen"
private const val MIN_WAIT_SECONDS = 5
private const val MAX_WAIT_SECONDS = 15

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentChatScreen(
    onNavigateBack: () -> Unit,
    agentId: String
) {
    val scope = rememberCoroutineScope()
    val lazyListState = rememberLazyListState()

    var messages by remember { mutableStateOf<List<AgentChatMessageUi>>(emptyList()) }
    var inputText by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    
    // 批量消息相关状态
    var pendingMessages by remember { mutableStateOf<List<String>>(emptyList()) }
    var isWaiting by remember { mutableStateOf(false) }
    var waitJob: Job? by remember { mutableStateOf(null) }
    var waitingIndicator by remember { mutableStateOf("") }
    
    // Agent信息对话框状态
    var showAgentInfoDialog by remember { mutableStateOf(false) }
    var agentName by remember { mutableStateOf("Agent") }
    
    // 加载Agent名称
    fun loadAgentName() {
        scope.launch {
            try {
                val agentIdInt = agentId.toIntOrNull()
                if (agentIdInt == null) return@launch
                
                val token = SessionManager.authHeader()
                val detail = ApiClient.api.getAgentDetail(token, agentIdInt)
                agentName = detail.name
            } catch (e: Exception) {
                Log.e(TAG, "加载Agent名称失败", e)
            }
        }
    }


    // 加载Agent聊天会话和消息的函数
    fun loadAgentChatMessages(agentIdStr: String) {
        scope.launch {
            try {
                loading = true
                error = null
                val agentIdInt = agentIdStr.toIntOrNull()
                if (agentIdInt == null) {
                    error = "无效的Agent ID"
                    loading = false
                    return@launch
                }

                val token = SessionManager.authHeader()
                val response = ApiClient.api.getAgentChatSession(token, agentIdInt)
                
                messages = response.messages.map {
                    AgentChatMessageUi(
                        id = it.id.toString(),
                        content = it.content,
                        isUser = it.role == "user",
                        timestamp = it.created_at,
                        batchId = it.batch_id,
                        batchIndex = it.batch_index,
                        sendDelaySeconds = it.send_delay_seconds
                    )
                }
                
                loading = false
                // 滚动到底部
                scope.launch {
                    delay(100)
                    if (messages.isNotEmpty()) {
                        lazyListState.animateScrollToItem(messages.size - 1)
                    }
                }
            } catch (e: Exception) {
                loading = false
                error = "加载消息失败：${e.message}"
                Log.e(TAG, "加载Agent聊天消息失败", e)
            }
        }
    }

    // 清空聊天并总结记忆
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


    // 显示回复（带延迟）
    fun displayRepliesWithDelay(replies: List<AgentReplyDto>, batchId: String) {
        replies.forEachIndexed { index, reply ->
            scope.launch {
                // 第一条回复延迟0秒，后续回复按指定延迟
                if (index > 0) {
                    val delayMs = (reply.send_delay_seconds * 1000).toLong()
                    delay(delayMs)
                }
                
                // 添加到消息列表
                val newMessage = AgentChatMessageUi(
                    id = reply.id?.toString() ?: UUID.randomUUID().toString(),
                    content = reply.content,
                    isUser = false,
                    timestamp = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date()),
                    batchId = batchId,
                    batchIndex = index,
                    sendDelaySeconds = reply.send_delay_seconds
                )
                
                messages = messages + newMessage
                
                // 滚动到底部
                scope.launch {
                    delay(100)
                    lazyListState.animateScrollToItem(messages.size - 1)
                }
            }
        }
    }

    // 发送批量消息
    fun sendBatchMessages(userMessages: List<String>) {
        if (userMessages.isEmpty()) return
        
        scope.launch {
            try {
                loading = true
                error = null
                isWaiting = false
                waitingIndicator = ""
                
                // 用户消息已经在addMessageToPending中立即显示了，这里不需要再次添加
                // 只需要发送到后端并接收AI回复
                
                val agentIdInt = agentId.toIntOrNull()
                if (agentIdInt == null) {
                    error = "无效的Agent ID"
                    loading = false
                    return@launch
                }
                
                val token = SessionManager.authHeader()
                val response = ApiClient.api.sendAgentBatchMessages(
                    token,
                    agentIdInt,
                    AgentBatchMessageCreateRequest(userMessages)
                )
                
                loading = false
                
                // 显示AI回复（带延迟）
                displayRepliesWithDelay(response.replies, response.batch_id)
                
            } catch (e: Exception) {
                loading = false
                error = "发送消息失败：${e.message}"
                Log.e(TAG, "发送批量消息失败", e)
            }
        }
    }

    // 添加消息到待发送列表（需要调用sendBatchMessages，所以放在后面）
    fun addMessageToPending(message: String) {
        if (message.isBlank()) return
        
        val trimmedMessage = message.trim()
        if (trimmedMessage.isEmpty()) return
        
        // 取消之前的等待
        waitJob?.cancel()
        
        // 添加到待发送列表
        pendingMessages = pendingMessages + trimmedMessage
        
        // 立即显示用户消息到界面
        val newUserMessage = AgentChatMessageUi(
            id = UUID.randomUUID().toString(),
            content = trimmedMessage,
            isUser = true,
            timestamp = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date()),
            batchId = null,
            batchIndex = null
        )
        messages = messages + newUserMessage
        
        // 滚动到底部
        scope.launch {
            delay(100)
            lazyListState.animateScrollToItem(messages.size - 1)
        }
        
        inputText = ""
        isWaiting = true
        waitingIndicator = ""
        
        // 开始新的等待（5-15秒随机）
        waitJob = scope.launch {
            val waitSeconds = Random.nextInt(MIN_WAIT_SECONDS, MAX_WAIT_SECONDS + 1)
            
            // 显示等待倒计时
            for (i in waitSeconds downTo 1) {
                if (!isWaiting) return@launch // 如果等待被取消，退出
                waitingIndicator = "等待更多消息... (${i}秒)"
                delay(1000)
            }
            
            waitingIndicator = ""
            
            // 等待结束，发送所有累积的消息
            if (pendingMessages.isNotEmpty() && isWaiting) {
                val messagesToSend = pendingMessages.toList()
                pendingMessages = emptyList()
                isWaiting = false
                sendBatchMessages(messagesToSend)
            }
        }
    }

    // 加载Agent聊天会话和消息
    LaunchedEffect(agentId) {
        if (agentId.isNotEmpty() && agentId != "new") {
            loadAgentName()
            loadAgentChatMessages(agentId)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // 顶部栏
        TopAppBar(
            title = { Text("Agent聊天") },
            navigationIcon = {
                IconButton(onClick = onNavigateBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                }
            },
            actions = {
                // Agent信息按钮（人物图标）
                IconButton(onClick = { showAgentInfoDialog = true }) {
                    Icon(Icons.Filled.Person, contentDescription = "Agent信息")
                }
            }
        )

        // 错误提示
        error?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            )
        }

        // 等待提示
        if (isWaiting && waitingIndicator.isNotEmpty()) {
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Text(
                    text = waitingIndicator,
                    modifier = Modifier.padding(8.dp),
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        // 消息列表
        LazyColumn(
            state = lazyListState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(messages) { message ->
                AgentChatMessageItem(message = message)
            }
        }

        // 输入框和发送按钮
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.Bottom
        ) {
            TextField(
                value = inputText,
                onValueChange = { inputText = it },
                modifier = Modifier
                    .weight(1f)
                    .padding(end = 8.dp),
                placeholder = { 
                    Text(
                        if (isWaiting) "等待中...输入新消息重置等待时间" 
                        else "输入消息（输入后等待5-15秒，可继续输入多条）"
                    ) 
                },
                maxLines = 5,
                enabled = true  // 始终允许输入，即使在AI响应时也可以继续输入
            )
            
            IconButton(
                onClick = {
                    if (inputText.isNotBlank()) {
                        addMessageToPending(inputText)
                    }
                },
                enabled = inputText.isNotBlank()  // 只要有文本就可以发送，不限制loading状态
            ) {
                Icon(Icons.Filled.Send, contentDescription = "发送")
            }
        }
        
        // Agent信息对话框
        if (showAgentInfoDialog) {
            AgentInfoDialog(
                agentId = agentId,
                agentName = agentName,
                onDismiss = { showAgentInfoDialog = false },
                onClearAndSummarize = {
                    clearAndSummarize()
                    showAgentInfoDialog = false
                },
                onPromptHistoryDeleted = {
                    // Prompt历史删除后，可以刷新数据
                }
            )
        }
    }
}

@Composable
fun AgentChatMessageItem(message: AgentChatMessageUi) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = if (message.isUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .padding(horizontal = 8.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (message.isUser) {
                    MaterialTheme.colorScheme.primaryContainer
                } else {
                    MaterialTheme.colorScheme.surfaceVariant
                }
            )
        ) {
            Column(
                modifier = Modifier.padding(12.dp)
            ) {
                DisplayMessageContentOptimized(
                    content = message.content
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = message.timestamp,
                    style = MaterialTheme.typography.bodySmall,
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
                )
            }
        }
    }
}
