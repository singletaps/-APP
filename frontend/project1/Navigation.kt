//Navigation,kt
package com.example.project1
import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.project1.screens.ChatScreen
import com.example.project1.screens.HomeScreen
import com.example.project1.screens.LoginScreen
import com.example.project1.screens.RegisterScreen
import com.example.project1.screens.SearchScreen
import com.example.project1.screens.AgentListScreen
import com.example.project1.screens.AgentChatScreen
import androidx.compose.ui.platform.LocalContext
import com.example.project1.network.SessionManager
import androidx.compose.runtime.LaunchedEffect

// 定义应用中的屏幕路由
sealed class Screen(val route: String) {
    object Home : Screen("home")
    object Login : Screen("login")
    object Register : Screen("register")
    object Conversations : Screen("conversations")
    object Chat : Screen("chat/{conversationId}") {
        fun createRoute(conversationId: String) = "chat/$conversationId"
    }
    object Search : Screen("search")
    object AgentList : Screen("agents")
    object AgentChat : Screen("agents/{agentId}") {
        fun createRoute(agentId: String) = "agents/$agentId"
    }
}

@Composable
fun ChatBotApp() {
    // 创建导航控制器
    val navController = rememberNavController()
    val context = LocalContext.current
    
    // 初始化 SessionManager
    SessionManager.init(context)
    
    // 检查登录状态，自动跳转
    LaunchedEffect(Unit) {
        if (SessionManager.isLoggedIn()) {
            // 如果已登录，直接跳转到对话列表
            navController.navigate(Screen.Conversations.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    // 设置导航图
    NavHost(
        navController = navController,
        startDestination = Screen.Home.route // 应用启动时显示首页
    ) {
        // 首页
        composable(Screen.Home.route) {
            HomeScreen(
                onNavigateToLogin = {
                    // 跳转到登录界面
                    navController.navigate(Screen.Login.route)
                },
                onNavigateToConversations = {
                    // 跳转到对话列表界面
                    navController.navigate(Screen.Conversations.route)
                }
            )
        }

        // 登录界面
        composable(Screen.Login.route) {
            LoginScreen(
                onNavigateBack = {
                    // 返回上一个界面（首页）
                    navController.popBackStack()
                },
                onLoginSuccess = {
                    // 登录成功后跳转到对话列表（用户信息已在LoginScreen中保存）
                    navController.navigate(Screen.Conversations.route) {
                        popUpTo(Screen.Home.route) {
                            inclusive = false
                        }
                    }
                },
                onNavigateToRegister = {
                    navController.navigate(Screen.Register.route)
                }
            )
        }

        // 注册界面
        composable(Screen.Register.route) {
            RegisterScreen(
                onNavigateBack = {
                    navController.popBackStack()
                },
                onRegisterSuccess = {
                    // 注册成功后跳转到登录界面
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Register.route) {
                            inclusive = true
                        }
                    }
                }
            )
        }

        // 对话列表界面
        composable(Screen.Conversations.route) {
            _root_ide_package_.com.example.project1.screens.ConversationListScreen(
                onNavigateBack = {
                    // 返回首页
                    navController.popBackStack(Screen.Home.route, inclusive = false)
                },
                onConversationClick = { conversationId ->
                    // 跳转到具体的聊天界面，并传递对话ID
                    navController.navigate(Screen.Chat.createRoute(conversationId))
                },
                onNewConversation = {
                    // 创建新对话，跳转到聊天界面
                    navController.navigate(Screen.Chat.createRoute("new"))
                },
                onNavigateToSearch = {
                    // 跳转到查找对话界面
                    navController.navigate(Screen.Search.route)
                },
                onNavigateToAgent = {
                    // 跳转到Agent列表界面
                    navController.navigate(Screen.AgentList.route)
                },
                onLogout = {
                    // 退出登录后跳转到登录界面
                    navController.navigate(Screen.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }

        // 聊天界面（需要先定义这个界面）
        composable(Screen.Chat.route) { backStackEntry ->
            val conversationId = backStackEntry.arguments?.getString("conversationId") ?: "new"

            // 调用正确的 ChatScreen 并传递参数
            ChatScreen(
                onNavigateBack = { navController.popBackStack() },
                conversationId = conversationId,
                onSessionCreated = { newSessionId ->
                    // 当新会话创建时，更新导航路由，使用新的会话ID
                    // 这样后续的提问就会使用同一个会话
                    android.util.Log.d("Navigation", "[IMAGE] 新会话创建，更新导航: $newSessionId")
                    navController.navigate(Screen.Chat.createRoute(newSessionId.toString())) {
                        // 替换当前路由，避免返回栈中有多个"new"会话
                        popUpTo(Screen.Chat.createRoute("new")) { inclusive = true }
                    }
                }
            )

        }

        // 查找对话界面
        composable(Screen.Search.route) {
            SearchScreen(
                onNavigateBack = { navController.popBackStack() },
                onConversationClick = { conversationId ->
                    // 跳转到具体的聊天界面，并传递对话ID
                    navController.navigate(Screen.Chat.createRoute(conversationId)) {
                        // 清除查找页面的返回栈，这样从聊天界面返回时会直接回到之前的页面
                        popUpTo(Screen.Search.route) { inclusive = true }
                    }
                }
            )
        }

        // Agent列表界面
        composable(Screen.AgentList.route) {
            AgentListScreen(
                onNavigateBack = {
                    // 返回到对话列表
                    navController.navigate(Screen.Conversations.route) {
                        popUpTo(Screen.AgentList.route) { inclusive = true }
                    }
                },
                onAgentClick = { agentId ->
                    // 跳转到Agent聊天界面
                    navController.navigate(Screen.AgentChat.createRoute(agentId))
                },
                onCreateAgent = {
                    // AgentListScreen内部处理创建对话框
                },
                onLogout = {
                    // 退出登录后跳转到登录界面
                    navController.navigate(Screen.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }

        // Agent聊天界面
        composable(Screen.AgentChat.route) { backStackEntry ->
            val agentId = backStackEntry.arguments?.getString("agentId") ?: ""
            AgentChatScreen(
                onNavigateBack = { navController.popBackStack() },
                agentId = agentId
            )
        }
    }
}