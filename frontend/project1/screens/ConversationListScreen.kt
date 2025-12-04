// ConversationListScreen.kt
package com.example.project1.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.project1.network.ApiClient
import com.example.project1.network.SessionManager
import kotlinx.coroutines.launch

data class Conversation(
    val id: String,
    val title: String,
    val lastMessage: String,
    val timestamp: String,
    val messageCount: Int
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationListScreen(
    onNavigateBack: () -> Unit,
    onConversationClick: (String) -> Unit,
    onNewConversation: () -> Unit,
    onNavigateToSearch: () -> Unit = {},
    onLogout: () -> Unit = {}
) {
    var conversations by remember { mutableStateOf<List<Conversation>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    val scope = rememberCoroutineScope()
    var showDeleteDialog by remember { mutableStateOf<Conversation?>(null) }
    var showRenameDialog by remember { mutableStateOf<Conversation?>(null) }
    var showTopMenu by remember { mutableStateOf(false) }
    
    // Drawer状态
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)

    // 加载会话列表的函数
    fun loadConversations() {
        scope.launch {
            try {
                loading = true
                error = null
                val token = SessionManager.authHeader()
                val resp = ApiClient.api.getSessions(token)
                conversations = resp.map {
                    Conversation(
                        id = it.id.toString(),
                        title = it.title ?: "未命名会话",
                        lastMessage = "", // 可以再请求最后一条消息，这里先空着
                        timestamp = it.updated_at,
                        messageCount = 0 // 同上
                    )
                }
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "加载会话失败：${e.message}"
            }
        }
    }

    // 删除对话的函数
    fun deleteConversation(conversation: Conversation) {
        scope.launch {
            try {
                val token = SessionManager.authHeader()
                val sessionId = conversation.id.toIntOrNull()
                if (sessionId != null) {
                    val response = ApiClient.api.deleteSession(token, sessionId)
                    if (response.isSuccessful) {
                        // 删除成功，刷新列表
                        loadConversations()
                    } else {
                        error = "删除失败：${response.code()}"
                    }
                } else {
                    error = "无效的会话ID"
                }
            } catch (e: Exception) {
                error = "删除失败：${e.message}"
            }
        }
    }

    // 重命名对话的函数
    fun renameConversation(conversation: Conversation, newTitle: String) {
        scope.launch {
            try {
                val token = SessionManager.authHeader()
                val sessionId = conversation.id.toIntOrNull()
                if (sessionId != null) {
                    val updatedSession = ApiClient.api.updateSession(
                        token,
                        sessionId,
                        com.example.project1.network.ChatSessionUpdateRequest(newTitle)
                    )
                    // 重命名成功，刷新列表
                    loadConversations()
                } else {
                    error = "无效的会话ID"
                }
            } catch (e: Exception) {
                error = "重命名失败：${e.message}"
            }
        }
    }

    // 页面首次进入时加载会话列表
    LaunchedEffect(Unit) {
        loadConversations()
    }

    UserInfoDrawer(
        drawerState = drawerState,
        conversationCount = conversations.size,
        onLogout = {
            SessionManager.logout()
            onLogout()
        }
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
        // 顶部栏
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(
                onClick = {
                    scope.launch {
                        drawerState.open()
                    }
                }
            ) {
                Icon(
                    Icons.Filled.Settings,
                    contentDescription = "设置"
                )
            }

            Text(
                text = "对话列表",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold
            )

            Box {
                IconButton(onClick = { showTopMenu = true }) {
                    Icon(Icons.Filled.MoreVert, contentDescription = "更多")
                }
                DropdownMenu(
                    expanded = showTopMenu,
                    onDismissRequest = { showTopMenu = false }
                ) {
                    DropdownMenuItem(
                        text = { 
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Filled.Search,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("查找对话")
                            }
                        },
                        onClick = {
                            showTopMenu = false
                            onNavigateToSearch()
                        }
                    )
                    DropdownMenuItem(
                        text = { Text("刷新列表") },
                        onClick = {
                            showTopMenu = false
                            loadConversations()
                        }
                    )
                }
            }
        }

        if (loading) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        }

        if (error != null) {
            Text(
                text = error!!,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(16.dp)
            )
        }

        LazyColumn(
            modifier = Modifier.weight(1f)
        ) {
            items(conversations) { conversation ->
                ConversationItem(
                    conversation = conversation,
                    onClick = { onConversationClick(conversation.id) },
                    onDelete = { showDeleteDialog = conversation },
                    onRename = { showRenameDialog = conversation }
                )
            }
        }

        // 删除确认对话框
        showDeleteDialog?.let { conversationToDelete ->
            AlertDialog(
                onDismissRequest = { showDeleteDialog = null },
                title = { Text("删除对话") },
                text = { Text("确定要删除对话\"${conversationToDelete.title}\"吗？此操作不可撤销。") },
                confirmButton = {
                    TextButton(
                        onClick = {
                            deleteConversation(conversationToDelete)
                            showDeleteDialog = null
                        }
                    ) {
                        Text("删除", color = MaterialTheme.colorScheme.error)
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showDeleteDialog = null }) {
                        Text("取消")
                    }
                }
            )
        }

        // 重命名对话框
        showRenameDialog?.let { conversationToRename ->
            var newTitle by remember { mutableStateOf(conversationToRename.title) }
            
            AlertDialog(
                onDismissRequest = { showRenameDialog = null },
                title = { Text("重命名对话") },
                text = {
                    Column {
                        Text("请输入新的对话标题：")
                        Spacer(modifier = Modifier.height(8.dp))
                        TextField(
                            value = newTitle,
                            onValueChange = { newTitle = it },
                            label = { Text("标题") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            if (newTitle.isNotBlank()) {
                                renameConversation(conversationToRename, newTitle.trim())
                                showRenameDialog = null
                            }
                        },
                        enabled = newTitle.isNotBlank() && newTitle.trim() != conversationToRename.title
                    ) {
                        Text("确定")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showRenameDialog = null }) {
                        Text("取消")
                    }
                }
            )
        }

        Button(
            onClick = onNewConversation,
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Icon(Icons.Filled.Add, contentDescription = "新建对话")
            Spacer(modifier = Modifier.width(8.dp))
            Text("新建对话")
        }
        }
    }
}
