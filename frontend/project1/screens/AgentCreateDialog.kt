// AgentCreateDialog.kt
package com.example.project1.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog

@Composable
fun AgentCreateDialog(
    onDismiss: () -> Unit,
    onConfirm: (String, String) -> Unit  // name, initial_prompt
) {
    var agentName by remember { mutableStateOf("") }
    var initialPrompt by remember { mutableStateOf("") }
    var nameError by remember { mutableStateOf<String?>(null) }
    var promptError by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("创建Agent") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Text("请输入Agent的名称和初始Prompt：")
                
                // Agent名称输入
                TextField(
                    value = agentName,
                    onValueChange = { 
                        agentName = it
                        nameError = null
                    },
                    label = { Text("Agent名称 *") },
                    singleLine = true,
                    isError = nameError != null,
                    supportingText = nameError?.let { { Text(it) } },
                    modifier = Modifier.fillMaxWidth()
                )
                
                // 初始Prompt输入
                TextField(
                    value = initialPrompt,
                    onValueChange = { 
                        initialPrompt = it
                        promptError = null
                    },
                    label = { Text("初始Prompt *") },
                    minLines = 5,
                    maxLines = 10,
                    isError = promptError != null,
                    supportingText = promptError?.let { { Text(it) } },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    // 验证输入
                    var hasError = false
                    
                    if (agentName.isBlank()) {
                        nameError = "Agent名称不能为空"
                        hasError = true
                    }
                    
                    if (initialPrompt.isBlank()) {
                        promptError = "初始Prompt不能为空"
                        hasError = true
                    }
                    
                    if (!hasError) {
                        onConfirm(agentName.trim(), initialPrompt.trim())
                        // 重置状态
                        agentName = ""
                        initialPrompt = ""
                        nameError = null
                        promptError = null
                    }
                },
                enabled = agentName.isNotBlank() && initialPrompt.isNotBlank()
            ) {
                Text("创建")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}

