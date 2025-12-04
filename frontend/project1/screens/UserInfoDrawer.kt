// UserInfoDrawer.kt
package com.example.project1.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.project1.network.SessionManager
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UserInfoDrawer(
    drawerState: DrawerState,
    conversationCount: Int,
    onLogout: () -> Unit,
    content: @Composable () -> Unit
) {
    val scope = rememberCoroutineScope()
    
    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            Box(
                modifier = Modifier
                    .fillMaxHeight()
                    .width(280.dp)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
            ) {
                UserInfoDrawerContent(
                    conversationCount = conversationCount,
                    onLogout = {
                        onLogout()
                        scope.launch {
                            drawerState.close()
                        }
                    },
                    onDismiss = {
                        scope.launch {
                            drawerState.close()
                        }
                    }
                )
            }
        },
        content = content
    )
}

@Composable
fun UserInfoDrawerContent(
    conversationCount: Int,
    onLogout: () -> Unit,
    onDismiss: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxHeight()
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        // 标题
        Text(
            text = "用户信息",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 32.dp)
        )

        Spacer(modifier = Modifier.height(16.dp))

        // 用户ID
        Column(modifier = Modifier.padding(bottom = 24.dp)) {
            Text(
                text = "用户ID",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            Text(
                text = SessionManager.username ?: "未知",
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium
            )
        }

        Divider(modifier = Modifier.padding(vertical = 8.dp))

        // 当前聊天总数
        Column(modifier = Modifier.padding(bottom = 24.dp)) {
            Text(
                text = "当前聊天总数",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            Text(
                text = "$conversationCount",
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        Divider(modifier = Modifier.padding(vertical = 8.dp))

        // 退出登录按钮
        Button(
            onClick = onLogout,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 16.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.error
            )
        ) {
            Icon(
                imageVector = Icons.Filled.ExitToApp,
                contentDescription = null,
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text("退出登录", fontSize = 16.sp)
        }
    }
}

