package com.example.project1.network

import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.http.*
import retrofit2.Retrofit
import retrofit2.Response
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.Call
import java.util.concurrent.TimeUnit

// ====== 数据模型，对应后端 Pydantic 模型 ======


data class LoginRequest(
    val username: String,
    val password: String
)

data class LoginResponse(
    val access_token: String,
    val token_type: String
)

data class RegisterRequest(
    val username: String,
    val password: String
)

data class UserOut(
    val id: Int,
    val username: String
)

data class ChatSessionSummaryDto(
    val id: Int,
    val title: String?,
    val created_at: String,
    val updated_at: String
)

data class ChatMessageOutDto(
    val id: Int,
    val role: String,
    val content: String,
    val reasoning_content: String? = null,  // 深度思考内容（可选）
    val created_at: String,
    val images: List<String>? = null,  // 用户上传的图片Base64列表（可选，仅用户消息）
    val generated_images: List<String>? = null  // 模型生成的图片URL列表（可选，仅assistant消息）
)

data class ChatSessionCreateRequest(
    val question: String,
    val title: String?,
    val images: List<String>? = null  // 图片Base64编码字符串列表（可选）
)

data class ChatMessageCreateRequest(
    val question: String,
    val images: List<String>? = null  // 图片Base64编码字符串列表（可选）
)

data class ChatSessionUpdateRequest(
    val title: String
)

data class ChatSessionCreatedResponse(
    val session: ChatSessionSummaryDto,
    val messages: List<ChatMessageOutDto>
)

data class ChatTurnResponse(
    val messages: List<ChatMessageOutDto>
)

data class ChatSessionWithMessagesResponse(
    val session: ChatSessionSummaryDto,
    val messages: List<ChatMessageOutDto>
)

// ====== Agent数据模型 ======

data class AgentSummaryDto(
    val id: Int,
    val name: String,
    val created_at: String,
    val updated_at: String,
    val last_summarized_at: String? = null
)

data class AgentDetailDto(
    val id: Int,
    val name: String,
    val initial_prompt: String,
    val current_prompt: String,
    val created_at: String,
    val updated_at: String,
    val last_summarized_at: String? = null
)

data class AgentChatMessageOutDto(
    val id: Int,
    val role: String,
    val content: String,
    val reasoning_content: String? = null,
    val batch_id: String? = null,
    val batch_index: Int? = null,
    val send_delay_seconds: Int? = null,
    val created_at: String
)

data class AgentChatSessionOutDto(
    val id: Int,
    val agent_id: Int,
    val title: String? = null,
    val created_at: String,
    val updated_at: String
)

data class AgentChatSessionWithMessagesDto(
    val session: AgentChatSessionOutDto,
    val messages: List<AgentChatMessageOutDto>
)

data class AgentCreateRequest(
    val name: String,
    val initial_prompt: String
)

data class AgentUpdateRequest(
    val name: String
)

data class AgentBatchMessageCreateRequest(
    val messages: List<String>
)

data class AgentReplyDto(
    val id: Int? = null,
    val content: String,
    val send_delay_seconds: Int = 0,
    val order: Int = 0
)

data class AgentBatchMessageResponse(
    val batch_id: String,
    val replies: List<AgentReplyDto>
)

data class AgentCreatedResponse(
    val agent: AgentDetailDto,
    val session: AgentChatSessionOutDto
)

data class AgentPromptHistoryOutDto(
    val id: Int,
    val agent_id: Int,
    val added_prompt: String,
    val summary_date: String,  // YYYY-MM-DD格式
    val created_at: String
)

data class AgentPromptHistoryResponse(
    val histories: List<AgentPromptHistoryOutDto>,
    val total: Int
)

data class DeletePromptSummaryResponse(
    val success: Boolean,
    val deleted_summary_date: String? = null,  // YYYY-MM-DD格式
    val remaining_count: Int,
    val current_prompt_preview: String? = null
)

data class ClearAndSummarizeResponse(
    val success: Boolean,
    val summary: String? = null
)

// ====== Retrofit 接口 ======

interface ApiService {

    @POST("/auth/register")
    suspend fun register(
        @Body body: RegisterRequest
    ): UserOut

    @POST("/auth/login")
    suspend fun login(
        @Body body: LoginRequest
    ): LoginResponse

    @GET("/auth/me")
    suspend fun getCurrentUser(
        @Header("Authorization") auth: String
    ): UserOut

    @GET("/chat/sessions")
    suspend fun getSessions(
        @Header("Authorization") auth: String
    ): List<ChatSessionSummaryDto>

    @DELETE("/chat/sessions/{id}")
    suspend fun deleteSession(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): Response<Unit>

    @PUT("/chat/sessions/{id}")
    suspend fun updateSession(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: ChatSessionUpdateRequest
    ): ChatSessionSummaryDto

    @POST("/chat/sessions")
    suspend fun createSession(
        @Header("Authorization") auth: String,
        @Body body: ChatSessionCreateRequest
    ): ChatSessionCreatedResponse

    @GET("/chat/sessions/{id}/messages")
    suspend fun getSessionMessages(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): ChatSessionWithMessagesResponse

    @POST("/chat/sessions/{id}/messages")
    suspend fun sendMessage(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: ChatMessageCreateRequest
    ): ChatTurnResponse

    // ====== 流式接口 ======

    @POST("/ai/ask/stream")
    fun askStream(
        @Header("Authorization") auth: String,
        @Body body: AIQuestionRequest
    ): Call<ResponseBody>

    @POST("/chat/sessions/stream")
    fun createSessionStream(
        @Header("Authorization") auth: String,
        @Body body: ChatSessionCreateRequest
    ): Call<ResponseBody>

    @POST("/chat/sessions/{id}/messages/stream")
    fun sendMessageStream(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: ChatMessageCreateRequest
    ): Call<ResponseBody>

    // ====== Agent API ======

    @GET("/agents")
    suspend fun getAgents(
        @Header("Authorization") auth: String,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 20
    ): List<AgentSummaryDto>

    @POST("/agents")
    suspend fun createAgent(
        @Header("Authorization") auth: String,
        @Body body: AgentCreateRequest
    ): AgentCreatedResponse

    @GET("/agents/{id}")
    suspend fun getAgentDetail(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): AgentDetailDto

    @PUT("/agents/{id}")
    suspend fun updateAgent(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: AgentUpdateRequest
    ): AgentDetailDto

    @DELETE("/agents/{id}")
    suspend fun deleteAgent(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): Response<Unit>

    @GET("/agents/{id}/chat")
    suspend fun getAgentChatSession(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): AgentChatSessionWithMessagesDto

    @POST("/agents/{id}/chat/messages/batch")
    suspend fun sendAgentBatchMessages(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: AgentBatchMessageCreateRequest
    ): AgentBatchMessageResponse

    // Prompt管理
    @GET("/agents/{id}/prompt-history")
    suspend fun getAgentPromptHistory(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): AgentPromptHistoryResponse

    @DELETE("/agents/{id}/prompt-history/latest")
    suspend fun deleteLatestAgentPromptSummary(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): DeletePromptSummaryResponse

    // 清空聊天并总结记忆
    @POST("/agents/{id}/chat/clear-and-summarize")
    suspend fun clearAndSummarizeAgentChat(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): ClearAndSummarizeResponse
}

data class AIQuestionRequest(
    val question: String
)

// ====== Retrofit 单例 ======

object ApiClient {
    // 注意把 baseUrl 换成你后端实际地址
    // 如果是 Android 模拟器连本机： http://10.0.2.2:8000/
    const val BASE_URL = "http://10.0.2.2:8000/"

    // 配置 OkHttpClient 以支持流式响应
    val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS) // 流式响应需要无限读取超时
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    val api: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient) // 使用配置好的 OkHttpClient
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
