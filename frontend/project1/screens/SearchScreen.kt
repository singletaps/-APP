// SearchScreen.kt
package com.example.project1.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.project1.network.ApiClient
import com.example.project1.network.SessionManager
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

// 扩展的对话数据类，包含消息内容用于搜索
data class ConversationWithMessages(
    val id: String,
    val title: String,
    val lastMessage: String,
    val timestamp: String,
    val messageCount: Int,
    val messages: List<String> // 所有消息内容（用户提问和回答，不包括深度思考）
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    onNavigateBack: () -> Unit,
    onConversationClick: (String) -> Unit
) {
    var searchKeyword by remember { mutableStateOf("") }
    var allConversationsWithMessages by remember { mutableStateOf<List<ConversationWithMessages>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    val scope = rememberCoroutineScope()

    // 加载所有对话及其消息内容
    fun loadAllConversations() {
        scope.launch {
            try {
                loading = true
                error = null
                val token = SessionManager.authHeader()
                val sessionsResp = ApiClient.api.getSessions(token)
                
                // 为每个对话加载消息
                val conversationsWithMessages = mutableListOf<ConversationWithMessages>()
                for (session in sessionsResp) {
                    try {
                        val messagesResp = ApiClient.api.getSessionMessages(token, session.id)
                        // 收集所有消息内容（只包括用户提问和回答，不包括深度思考内容）
                        val messageContents = messagesResp.messages.mapNotNull { msg ->
                            // 只包含用户和助手的消息内容，排除深度思考内容
                            if (msg.role == "user" || msg.role == "assistant") {
                                msg.content
                            } else {
                                null
                            }
                        }
                        
                        conversationsWithMessages.add(
                            ConversationWithMessages(
                                id = session.id.toString(),
                                title = session.title ?: "未命名会话",
                                lastMessage = messageContents.lastOrNull() ?: "",
                                timestamp = session.updated_at,
                                messageCount = messageContents.size,
                                messages = messageContents
                            )
                        )
                    } catch (e: Exception) {
                        // 如果某个对话加载失败，仍然添加基本信息
                        conversationsWithMessages.add(
                            ConversationWithMessages(
                                id = session.id.toString(),
                                title = session.title ?: "未命名会话",
                                lastMessage = "",
                                timestamp = session.updated_at,
                                messageCount = 0,
                                messages = emptyList()
                            )
                        )
                    }
                }
                
                allConversationsWithMessages = conversationsWithMessages
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "加载对话失败：${e.message}"
            }
        }
    }

    // 页面首次进入时加载所有对话
    LaunchedEffect(Unit) {
        loadAllConversations()
    }

    // 根据关键词过滤对话（在标题和消息内容中搜索）
    val filteredConversations = remember(allConversationsWithMessages, searchKeyword) {
        if (searchKeyword.isBlank()) {
            emptyList()
        } else {
            val keyword = searchKeyword.lowercase().trim()
            allConversationsWithMessages.filter { conversation ->
                // 在标题中搜索
                val titleMatch = conversation.title.lowercase().contains(keyword)
                // 在消息内容中搜索（只搜索用户提问和回答，不包括深度思考内容）
                val contentMatch = conversation.messages.any { message ->
                    message.lowercase().contains(keyword)
                }
                titleMatch || contentMatch
            }.sortedByDescending { conversation ->
                // 按时间倒序排列（最新的在前）
                try {
                    // 尝试解析时间戳，支持多种格式
                    val timestamp = conversation.timestamp
                    val formats = listOf(
                        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
                        "yyyy-MM-dd'T'HH:mm:ss",
                        "yyyy-MM-dd HH:mm:ss"
                    )
                    var parsedTime: Long? = null
                    for (format in formats) {
                        try {
                            val dateFormat = SimpleDateFormat(format, Locale.getDefault())
                            parsedTime = dateFormat.parse(timestamp)?.time
                            if (parsedTime != null) break
                        } catch (e: Exception) {
                            // 继续尝试下一个格式
                        }
                    }
                    parsedTime ?: 0L
                } catch (e: Exception) {
                    0L
                }
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // 顶部栏
        TopAppBar(
            title = {
                Text(
                    text = "查找对话",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
            },
            navigationIcon = {
                IconButton(onClick = onNavigateBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "返回"
                    )
                }
            }
        )

        // 搜索输入框
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = searchKeyword,
                onValueChange = { searchKeyword = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("输入关键词搜索对话...") },
                leadingIcon = {
                    Icon(
                        Icons.Filled.Search,
                        contentDescription = "搜索"
                    )
                },
                singleLine = true
            )
        }

        if (loading) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else if (error != null) {
            Text(
                text = error!!,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(16.dp)
            )
        } else if (searchKeyword.isBlank()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "请输入关键词搜索对话",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 16.sp
                )
            }
        } else if (filteredConversations.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "未找到包含\"$searchKeyword\"的对话",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 16.sp
                )
            }
        } else {
            // 显示搜索结果
            LazyColumn(
                modifier = Modifier.weight(1f)
            ) {
                item {
                    Text(
                        text = "找到 ${filteredConversations.size} 个对话",
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                items(filteredConversations) { conversationWithMessages ->
                    // 转换为Conversation类型用于显示
                    val conversation = Conversation(
                        id = conversationWithMessages.id,
                        title = conversationWithMessages.title,
                        lastMessage = conversationWithMessages.lastMessage,
                        timestamp = conversationWithMessages.timestamp,
                        messageCount = conversationWithMessages.messageCount
                    )
                    ConversationItem(
                        conversation = conversation,
                        onClick = { onConversationClick(conversation.id) },
                        onDelete = { },
                        onRename = { }
                    )
                }
            }
        }
    }
}

