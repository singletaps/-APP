// LoginScreen.kt
package com.example.project1.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.project1.network.ApiClient
import com.example.project1.network.LoginRequest
import com.example.project1.network.SessionManager
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    onNavigateBack: () -> Unit,
    onLoginSuccess: () -> Unit,
    onNavigateToRegister: () -> Unit = {}
) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp)
    ) {
        IconButton(
            onClick = onNavigateBack,
            modifier = Modifier.size(48.dp)
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "返回"
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "登录",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(48.dp))

        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("用户名") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("密码") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            visualTransformation = PasswordVisualTransformation()
        )

        Spacer(modifier = Modifier.height(16.dp))

        if (error != null) {
            Text(
                text = error!!,
                color = MaterialTheme.colorScheme.error
            )
            Spacer(modifier = Modifier.height(8.dp))
        }

        Button(
            onClick = {
                scope.launch {
                    try {
                        loading = true
                        error = null
                        val resp = ApiClient.api.login(
                            LoginRequest(username, password)
                        )
                        SessionManager.accessToken = resp.access_token
                        // 获取用户信息并保存
                        try {
                            val token = SessionManager.authHeader()
                            val user = ApiClient.api.getCurrentUser(token)
                            SessionManager.userId = user.id
                            SessionManager.username = user.username
                        } catch (e: Exception) {
                            // 获取用户信息失败，但继续登录流程
                            SessionManager.username = username // 使用输入的用户名作为备选
                        }
                        loading = false
                        onLoginSuccess()
                    } catch (e: Exception) {
                        loading = false
                        error = "登录失败：${e.message ?: "未知错误"}"
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = username.isNotBlank() && password.isNotBlank() && !loading
        ) {
            Text(if (loading) "登录中..." else "登录", fontSize = 18.sp)
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 注册按钮
        OutlinedButton(
            onClick = onNavigateToRegister,
            modifier = Modifier.fillMaxWidth(),
            enabled = !loading
        ) {
            Text("注册账号", fontSize = 18.sp)
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "请使用你后端注册的账号登录",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.align(Alignment.CenterHorizontally)
        )
    }
}
