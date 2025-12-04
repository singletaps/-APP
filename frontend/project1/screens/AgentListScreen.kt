// AgentListScreen.kt
package com.example.project1.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Person
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentListScreen(
    onNavigateBack: () -> Unit,
    onAgentClick: (String) -> Unit,
    onCreateAgent: () -> Unit,
    onLogout: () -> Unit = {}
) {
    var agents by remember { mutableStateOf<List<Agent>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    val scope = rememberCoroutineScope()
    var showDeleteDialog by remember { mutableStateOf<Agent?>(null) }
    var showRenameDialog by remember { mutableStateOf<Agent?>(null) }
    var showTopMenu by remember { mutableStateOf(false) }
    var showCreateDialog by remember { mutableStateOf(false) }
    
    // Drawer状态
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)

    // 加载Agent列表的函数
    fun loadAgents() {
        scope.launch {
            try {
                loading = true
                error = null
                val token = SessionManager.authHeader()
                val resp = ApiClient.api.getAgents(token)
                agents = resp.map {
                    Agent(
                        id = it.id.toString(),
                        name = it.name,
                        createdAt = it.created_at,
                        updatedAt = it.updated_at
                    )
                }
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "加载Agent列表失败：${e.message}"
            }
        }
    }

    // 创建Agent的函数
    fun createAgent(name: String, initialPrompt: String) {
        scope.launch {
            try {
                loading = true
                error = null
                val token = SessionManager.authHeader()
                val response = ApiClient.api.createAgent(
                    token,
                    com.example.project1.network.AgentCreateRequest(name, initialPrompt)
                )
                // 创建成功，刷新列表
                loadAgents()
                showCreateDialog = false
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "创建Agent失败：${e.message}"
            }
        }
    }

    // 删除Agent的函数
    fun deleteAgent(agent: Agent) {
        scope.launch {
            try {
                val token = SessionManager.authHeader()
                val agentId = agent.id.toIntOrNull()
                if (agentId != null) {
                    val response = ApiClient.api.deleteAgent(token, agentId)
                    if (response.isSuccessful) {
                        // 删除成功，刷新列表
                        loadAgents()
                    } else {
                        error = "删除失败：${response.code()}"
                    }
                } else {
                    error = "无效的Agent ID"
                }
            } catch (e: Exception) {
                error = "删除失败：${e.message}"
            }
        }
    }

    // 重命名Agent的函数
    fun renameAgent(agent: Agent, newName: String) {
        scope.launch {
            try {
                val token = SessionManager.authHeader()
                val agentId = agent.id.toIntOrNull()
                if (agentId != null) {
                    val updatedAgent = ApiClient.api.updateAgent(
                        token,
                        agentId,
                        com.example.project1.network.AgentUpdateRequest(newName)
                    )
                    // 重命名成功，刷新列表
                    loadAgents()
                } else {
                    error = "无效的Agent ID"
                }
            } catch (e: Exception) {
                error = "重命名失败：${e.message}"
            }
        }
    }

    // 页面首次进入时加载Agent列表
    LaunchedEffect(Unit) {
        loadAgents()
    }

    UserInfoDrawer(
        drawerState = drawerState,
        conversationCount = agents.size, // 暂时用agent数量代替
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
                    text = "Agent列表",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )

                // 右侧按钮组："+"图标和三点菜单
                Row(
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 新建Agent按钮（"+"图标）
                    IconButton(onClick = { showCreateDialog = true }) {
                        Icon(
                            Icons.Filled.Add,
                            contentDescription = "新建Agent"
                        )
                    }
                    
                    // 三点菜单
                    Box {
                        IconButton(onClick = { showTopMenu = true }) {
                            Icon(Icons.Filled.MoreVert, contentDescription = "更多")
                        }
                        DropdownMenu(
                            expanded = showTopMenu,
                            onDismissRequest = { showTopMenu = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("刷新列表") },
                                onClick = {
                                    showTopMenu = false
                                    loadAgents()
                                }
                            )
                        }
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
                items(agents) { agent ->
                    AgentItem(
                        agent = agent,
                        onClick = { onAgentClick(agent.id) },
                        onDelete = { showDeleteDialog = agent },
                        onRename = { showRenameDialog = agent }
                    )
                }
            }

            // 删除确认对话框
            showDeleteDialog?.let { agentToDelete ->
                AlertDialog(
                    onDismissRequest = { showDeleteDialog = null },
                    title = { Text("删除Agent") },
                    text = { Text("确定要删除Agent\"${agentToDelete.name}\"吗？此操作不可撤销。") },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                deleteAgent(agentToDelete)
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
            showRenameDialog?.let { agentToRename ->
                var newName by remember { mutableStateOf(agentToRename.name) }
                
                AlertDialog(
                    onDismissRequest = { showRenameDialog = null },
                    title = { Text("重命名Agent") },
                    text = {
                        Column {
                            Text("请输入新的Agent名称：")
                            Spacer(modifier = Modifier.height(8.dp))
                            TextField(
                                value = newName,
                                onValueChange = { newName = it },
                                label = { Text("名称") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                if (newName.isNotBlank()) {
                                    renameAgent(agentToRename, newName.trim())
                                    showRenameDialog = null
                                }
                            },
                            enabled = newName.isNotBlank() && newName.trim() != agentToRename.name
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

            // Agent创建对话框
            if (showCreateDialog) {
                AgentCreateDialog(
                    onDismiss = { showCreateDialog = false },
                    onConfirm = { name, initialPrompt ->
                        createAgent(name, initialPrompt)
                    }
                )
            }

            // 底部页面切换导航栏（与ConversationListScreen保持一致）
            NavigationBar {
                NavigationBarItem(
                    selected = false,
                    onClick = onNavigateBack,
                    icon = {
                        Icon(
                            Icons.Filled.Chat,
                            contentDescription = "聊天"
                        )
                    },
                    label = { Text("聊天") }
                )
                NavigationBarItem(
                    selected = true,
                    onClick = {},
                    icon = {
                        Icon(
                            Icons.Filled.Person,
                            contentDescription = "Agent"
                        )
                    },
                    label = { Text("Agent") }
                )
            }
        }
    }
}

