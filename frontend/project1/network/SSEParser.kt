package com.example.project1.network

import android.util.Log
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import okhttp3.ResponseBody
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * SSE (Server-Sent Events) 事件数据类
 */
data class SSEEvent(
    val eventType: String,
    val data: String
)

/**
 * SSE 解析器，将 ResponseBody 转换为 Flow<SSEEvent>
 */
object SSEParser {
    private const val TAG = "SSEParser"
    
    fun parse(responseBody: ResponseBody): Flow<SSEEvent> = flow {
        Log.d(TAG, "[SSE] 开始解析流式响应")
        val reader = BufferedReader(InputStreamReader(responseBody.byteStream(), "UTF-8"))
        var currentEvent: String? = null
        var currentData = StringBuilder()
        var isFirstDataLine = true
        var lineCount = 0
        var eventCount = 0
        
        try {
            // 使用 readLine() 逐行读取，实现真正的流式处理
            var line: String?
            Log.d(TAG, "[SSE] 开始逐行读取...")
            while (reader.readLine().also { line = it } != null) {
                lineCount++
                val currentLine = line!!
                Log.d(TAG, "[SSE] 读取第 $lineCount 行: ${currentLine.take(100)}")
                
                when {
                    currentLine.isEmpty() -> {
                        // 空行表示一个完整的事件
                        if (currentData.isNotEmpty()) {
                            eventCount++
                            val eventType = currentEvent ?: "message"
                            // 移除最后一个多余的换行符
                            val data = currentData.toString().trimEnd()
                            Log.d(TAG, "[SSE] 发出事件 #$eventCount: type=$eventType, data长度=${data.length}, 预览=${data.take(50)}")
                            emit(SSEEvent(eventType, data))
                            currentEvent = null
                            currentData.clear()
                            isFirstDataLine = true
                        }
                    }
                    currentLine.startsWith("event: ") -> {
                        currentEvent = currentLine.substring(7).trim()
                        Log.d(TAG, "[SSE] 设置事件类型: $currentEvent")
                    }
                    currentLine.startsWith("data: ") -> {
                        // SSE规范：如果有多行data，每行都以"data: "开头
                        // 第一行data后添加换行，后续行也添加换行（除了最后一行）
                        if (!isFirstDataLine) {
                            currentData.append("\n")
                        }
                        val dataContent = currentLine.substring(6)
                        currentData.append(dataContent)
                        Log.d(TAG, "[SSE] 添加data内容，当前data长度: ${currentData.length}, 新增: ${dataContent.take(50)}")
                        isFirstDataLine = false
                    }
                    else -> {
                        Log.d(TAG, "[SSE] 未识别的行: ${currentLine.take(50)}")
                    }
                }
            }
            
            Log.d(TAG, "[SSE] 读取完成，共读取 $lineCount 行，发出 $eventCount 个事件")
            
            // 处理最后一个事件（如果没有空行结尾）
            if (currentData.isNotEmpty()) {
                eventCount++
                val eventType = currentEvent ?: "message"
                val data = currentData.toString().trimEnd()
                Log.d(TAG, "[SSE] 发出最后一个事件 #$eventCount: type=$eventType, data长度=${data.length}")
                emit(SSEEvent(eventType, data))
            }
        } catch (e: Exception) {
            Log.e(TAG, "[SSE] 解析错误: ${e.message}", e)
            throw e
        } finally {
            reader.close()
            Log.d(TAG, "[SSE] 解析器关闭")
        }
    }
    
    /**
     * 解析 JSON 格式的 data 字段
     */
    fun parseJsonData(data: String): JSONObject? {
        return try {
            JSONObject(data)
        } catch (e: Exception) {
            null
        }
    }
}

