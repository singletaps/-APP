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
