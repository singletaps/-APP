// AgentInfoDialog.kt
package com.example.project1.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.project1.network.*
import kotlinx.coroutines.launch

data class AgentPromptHistoryItem(
    val id: Int,
    val addedPrompt: String,
    val summaryDate: String,
    val createdAt: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentInfoDialog(
    agentId: String,
    agentName: String,
    onDismiss: () -> Unit,
    onClearAndSummarize: () -> Unit,
    onPromptHistoryDeleted: () -> Unit
) {
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    
    var agentDetail by remember { mutableStateOf<AgentDetailDto?>(null) }
    var promptHistories by remember { mutableStateOf<List<AgentPromptHistoryItem>>(emptyList()) }
    var showDeleteConfirm by remember { mutableStateOf<AgentPromptHistoryItem?>(null) }
    
    // 加载Agent详情
    fun loadAgentDetail() {
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
                agentDetail = ApiClient.api.getAgentDetail(token, agentIdInt)
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "加载Agent详情失败：${e.message}"
            }
        }
    }
    
    // 加载Prompt历史
    fun loadPromptHistory() {
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
                val response = ApiClient.api.getAgentPromptHistory(token, agentIdInt)
                
                promptHistories = response.histories.map {
                    AgentPromptHistoryItem(
                        id = it.id,
                        addedPrompt = it.added_prompt,
                        summaryDate = it.summary_date,
                        createdAt = it.created_at
                    )
                }
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "加载Prompt历史失败：${e.message}"
            }
        }
    }
    
    // 删除最新的Prompt总结
    fun deleteLatestPromptSummary() {
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
                ApiClient.api.deleteLatestAgentPromptSummary(token, agentIdInt)
                
                // 重新加载数据
                loadPromptHistory()
                onPromptHistoryDeleted()
                
                loading = false
            } catch (e: Exception) {
                loading = false
                error = "删除Prompt总结失败：${e.message}"
            }
        }
    }
    
    // 首次加载
    LaunchedEffect(agentId) {
        loadAgentDetail()
        loadPromptHistory()
    }
    
    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.9f),
            shape = RoundedCornerShape(16.dp)
        ) {
            Column(modifier = Modifier.fillMaxSize()) {
                // 顶部标题栏
                TopAppBar(
                    title = { 
                        Text(
                            text = agentName,
                            fontWeight = FontWeight.Bold
                        ) 
                    },
                    navigationIcon = {
                        IconButton(onClick = onDismiss) {
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = "关闭"
                            )
                        }
                    }
                )
                
                Divider()
                
                if (loading && agentDetail == null) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator()
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        // 错误提示
                        error?.let {
                            item {
                                Text(
                                    text = it,
                                    color = MaterialTheme.colorScheme.error,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }
                        
                        // Agent基本信息
                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp)
                                ) {
                                    Text(
                                        text = "基本信息",
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(bottom = 8.dp)
                                    )
                                    
                                    agentDetail?.let { detail ->
                                        Text(
                                            text = "创建时间：${detail.created_at}",
                                            fontSize = 14.sp,
                                            modifier = Modifier.padding(bottom = 4.dp)
                                        )
                                        Text(
                                            text = "更新时间：${detail.updated_at}",
                                            fontSize = 14.sp
                                        )
                                    }
                                }
                            }
                        }
                        
                        // 初始Prompt
                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp)
                                ) {
                                    Text(
                                        text = "初始Prompt",
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(bottom = 8.dp)
                                    )
                                    
                                    agentDetail?.let { detail ->
                                        Text(
                                            text = detail.initial_prompt,
                                            fontSize = 14.sp,
                                            modifier = Modifier.fillMaxWidth()
                                        )
                                    }
                                }
                            }
                        }
                        
                        // Prompt历史
                        item {
                            Text(
                                text = "Prompt历史（${promptHistories.size}条）",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        
                        items(promptHistories) { history ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = "日期：${history.summaryDate}",
                                                fontSize = 14.sp,
                                                fontWeight = FontWeight.Medium,
                                                modifier = Modifier.padding(bottom = 4.dp)
                                            )
                                            Text(
                                                text = "创建时间：${history.createdAt}",
                                                fontSize = 12.sp,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                                            )
                                        }
                                        
                                        IconButton(
                                            onClick = { showDeleteConfirm = history },
                                            enabled = promptHistories.indexOf(history) == 0 // 只能删除最新的
                                        ) {
                                            Icon(
                                                Icons.Default.Delete,
                                                contentDescription = "删除",
                                                tint = if (promptHistories.indexOf(history) == 0) {
                                                    MaterialTheme.colorScheme.error
                                                } else {
                                                    MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f)
                                                }
                                            )
                                        }
                                    }
                                    
                                    Spacer(modifier = Modifier.height(8.dp))
                                    
                                    Text(
                                        text = history.addedPrompt,
                                        fontSize = 14.sp,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            }
                        }
                        
                        // 清空聊天并总结记忆按钮
                        item {
                            Button(
                                onClick = onClearAndSummarize,
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = MaterialTheme.colorScheme.primary
                                )
                            ) {
                                Text(
                                    text = "立即清空当前聊天界面并总结记忆",
                                    modifier = Modifier.padding(8.dp)
                                )
                            }
                        }
                        
                        // 底部留白
                        item {
                            Spacer(modifier = Modifier.height(16.dp))
                        }
                    }
                }
            }
        }
    }
    
    // 删除确认对话框
    showDeleteConfirm?.let { historyToDelete ->
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = null },
            title = { Text("删除Prompt总结") },
            text = { Text("确定要删除日期为\"${historyToDelete.summaryDate}\"的Prompt总结吗？此操作不可撤销。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        deleteLatestPromptSummary()
                        showDeleteConfirm = null
                    }
                ) {
                    Text("删除", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = null }) {
                    Text("取消")
                }
            }
        )
    }
}

