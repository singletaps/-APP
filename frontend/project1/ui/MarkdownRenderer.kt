package com.example.project1.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import io.noties.markwon.Markwon
import io.noties.markwon.ext.strikethrough.StrikethroughPlugin
import io.noties.markwon.ext.tables.TablePlugin
import io.noties.markwon.linkify.LinkifyPlugin
import io.noties.markwon.image.ImagesPlugin
// import io.noties.markwon.ext.math.MathPlugin  // 暂时注释，等 ext-math 依赖解决后再启用
import android.content.Context
import android.widget.TextView
import android.util.TypedValue
import android.view.Gravity
import androidx.compose.ui.graphics.toArgb
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * Markwon 实例单例
 */
object MarkwonProvider {
    private var markwonInstance: Markwon? = null
    
    fun getMarkwon(context: Context): Markwon {
        if (markwonInstance == null) {
            markwonInstance = Markwon.builder(context)
                .usePlugin(StrikethroughPlugin.create())
                .usePlugin(TablePlugin.create(context))
                .usePlugin(LinkifyPlugin.create())
                .usePlugin(ImagesPlugin.create())
                // .usePlugin(MathPlugin.create(context))  // 暂时注释，等 ext-math 依赖解决后再启用
                .build()
        }
        return markwonInstance!!
    }
}

/**
 * 检测内容中是否包含 LaTeX 数学公式
 */
private fun containsLatex(content: String): Boolean {
    // 检测行内公式 $...$ 或块级公式 $$...$$
    val inlineLatex = Regex("""\$[^$]+\$""").containsMatchIn(content)
    val blockLatex = Regex("""\$\$[^$]+\$\$""").containsMatchIn(content)
    // 检测 \(...\) 或 \[...\]
    val parenLatex = Regex("""\\\([^)]+\\\)""").containsMatchIn(content) ||
                     Regex("""\\\[[^\]]+\\\]""").containsMatchIn(content)
    return inlineLatex || blockLatex || parenLatex
}

/**
 * 将 Markdown 转换为 HTML，并处理 LaTeX 公式
 */
private fun markdownToHtml(content: String, textColor: Color): String {
    // 先保护 LaTeX 公式，使用占位符
    val latexPlaceholders = mutableMapOf<String, String>()
    var placeholderIndex = 0
    
    // 处理块级公式 $$...$$
    var processed = content.replace(Regex("""\$\$([^$]+)\$\$""")) {
        val placeholder = "___LATEX_BLOCK_${placeholderIndex}___"
        placeholderIndex++
        latexPlaceholders[placeholder] = "<div class=\"math-display\">${it.groupValues[1]}</div>"
        placeholder
    }
    
    // 处理行内公式 $...$（但排除 $$...$$）
    processed = processed.replace(Regex("""(?<!\$)\$([^$\n]+?)\$(?!\$)""")) {
        val placeholder = "___LATEX_INLINE_${placeholderIndex}___"
        placeholderIndex++
        latexPlaceholders[placeholder] = "<span class=\"math-inline\">${it.groupValues[1]}</span>"
        placeholder
    }
    
    // 处理 \(...\) 和 \[...\]
    processed = processed.replace(Regex("""\\\[([^\]]+)\\]""")) {
        val placeholder = "___LATEX_BLOCK_${placeholderIndex}___"
        placeholderIndex++
        latexPlaceholders[placeholder] = "<div class=\"math-display\">${it.groupValues[1]}</div>"
        placeholder
    }
    processed = processed.replace(Regex("""\\\(([^)]+)\\\)""")) {
        val placeholder = "___LATEX_INLINE_${placeholderIndex}___"
        placeholderIndex++
        latexPlaceholders[placeholder] = "<span class=\"math-inline\">${it.groupValues[1]}</span>"
        placeholder
    }
    
    // 转义 HTML 特殊字符
    var html = processed
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#39;")
    
    // 恢复 LaTeX 占位符
    latexPlaceholders.forEach { (placeholder, latexHtml) ->
        html = html.replace(placeholder, latexHtml)
    }
    
    // 简单的 Markdown 转 HTML（基础功能）
    html = html
        // 标题
        .replace(Regex("""^###\s+(.+)$""", RegexOption.MULTILINE), "<h3>$1</h3>")
        .replace(Regex("""^##\s+(.+)$""", RegexOption.MULTILINE), "<h2>$1</h2>")
        .replace(Regex("""^#\s+(.+)$""", RegexOption.MULTILINE), "<h1>$1</h1>")
        // 粗体
        .replace(Regex("""\*\*(.+?)\*\*"""), "<strong>$1</strong>")
        // 斜体（排除粗体）
        .replace(Regex("""(?<!\*)\*([^*\n]+?)\*(?!\*)"""), "<em>$1</em>")
        // 代码块
        .replace(Regex("""```([^`]+)```""", RegexOption.DOT_MATCHES_ALL), "<pre><code>$1</code></pre>")
        // 行内代码
        .replace(Regex("""`([^`]+)`"""), "<code>$1</code>")
        // 换行
        .replace("\n", "<br>")
    
    return html
}

/**
 * 使用 WebView + KaTeX 渲染包含 LaTeX 的内容
 */
@Composable
fun LatexWebViewContent(
    content: String,
    modifier: Modifier = Modifier,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    val htmlContent = remember(content, textColor) {
        val html = markdownToHtml(content, textColor)
        val colorHex = String.format("#%06X", 0xFFFFFF and textColor.toArgb())
        
        """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
            <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
            <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    color: $colorHex;
                    margin: 0;
                    padding: 8px;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                }
                h1, h2, h3 {
                    margin: 12px 0 8px 0;
                    font-weight: 600;
                }
                h1 { font-size: 1.3em; }
                h2 { font-size: 1.2em; }
                h3 { font-size: 1.1em; }
                code {
                    background-color: rgba(0,0,0,0.05);
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: monospace;
                }
                pre {
                    background-color: rgba(0,0,0,0.05);
                    padding: 8px;
                    border-radius: 4px;
                    overflow-x: auto;
                }
                .math-display {
                    margin: 12px 0;
                    text-align: center;
                }
                .math-inline {
                    display: inline;
                }
            </style>
        </head>
        <body>
            $html
            <script>
                document.addEventListener("DOMContentLoaded", function() {
                    renderMathInElement(document.body, {
                        delimiters: [
                            {left: "$$", right: "$$", display: true},
                            {left: "$", right: "$", display: false},
                            {left: "\\[", right: "\\]", display: true},
                            {left: "\\(", right: "\\)", display: false}
                        ],
                        throwOnError: false
                    });
                });
            </script>
        </body>
        </html>
        """.trimIndent()
    }
    
    AndroidView(
        factory = { ctx ->
            WebView(ctx).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.loadWithOverviewMode = true
                settings.useWideViewPort = true
                settings.builtInZoomControls = false
                settings.displayZoomControls = false
                webViewClient = WebViewClient()
            }
        },
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 40.dp, max = 2000.dp),
        update = { webView ->
            webView.loadDataWithBaseURL(
                "https://cdn.jsdelivr.net/npm/katex@0.16.9/",
                htmlContent,
                "text/html",
                "UTF-8",
                null
            )
        }
    )
}

/**
 * 使用 Markwon 渲染 Markdown 内容（高性能，原生 Android View）
 * 如果包含 LaTeX，使用 WebView + KaTeX 渲染
 */
@Composable
fun MarkdownContent(
    content: String,
    modifier: Modifier = Modifier,
    textStyle: TextStyle = MaterialTheme.typography.bodyMedium,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    val hasLatex = remember(content) { containsLatex(content) }
    
    if (hasLatex) {
        // 如果包含 LaTeX，使用 WebView + KaTeX
        LatexWebViewContent(content, modifier, textColor)
    } else {
        // 如果不包含 LaTeX，使用 Markwon（性能更好）
        val context = androidx.compose.ui.platform.LocalContext.current
        val markwon = remember { MarkwonProvider.getMarkwon(context) }
        
        AndroidView(
            factory = { ctx ->
                TextView(ctx).apply {
                    // 设置字体大小（sp 单位，会根据系统字体大小设置自动缩放）
                    // Compose 的 fontSize.value 已经是 sp 单位，直接使用
                    val textSizeSp = textStyle.fontSize.value
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, textSizeSp)
                    
                    // 设置文本颜色
                    setTextColor(textColor.toArgb())
                    
                    // 设置行间距（增加可读性）
                    val lineSpacingExtraPx = TypedValue.applyDimension(
                        TypedValue.COMPLEX_UNIT_DIP, 4f, ctx.resources.displayMetrics
                    )
                    setLineSpacing(lineSpacingExtraPx, 1.2f)
                    
                    // 设置内边距
                    val paddingDp = 8f
                    val paddingPx = TypedValue.applyDimension(
                        TypedValue.COMPLEX_UNIT_DIP, paddingDp, ctx.resources.displayMetrics
                    ).toInt()
                    setPadding(paddingPx, paddingPx, paddingPx, paddingPx)
                    
                    // 启用自动换行
                    setHorizontallyScrolling(false)
                    isHorizontalScrollBarEnabled = false
                    
                    // 设置文本对齐方式
                    gravity = Gravity.START or Gravity.TOP
                    
                    // 启用文本选择（使用 setter 方法）
                    setTextIsSelectable(true)
                    
                    // 设置链接颜色（如果 Markwon 渲染链接）
                    setLinkTextColor(textColor.toArgb())
                }
            },
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            update = { textView ->
                // 使用 Markwon 渲染 Markdown（Markwon 会自动处理颜色和样式）
                markwon.setMarkdown(textView, content)
            }
        )
    }
}

/**
 * 渲染思考过程和答案的完整组件
 */
@Composable
fun DisplayMessageContentWithMarkwon(
    content: String,
    modifier: Modifier = Modifier
) {
    val (thinking, answer) = remember(content) {
        parseMessageContent(content)
    }
    
    Column(
        modifier = modifier.fillMaxWidth()
    ) {
        if (thinking.isNotEmpty()) {
            Text(
                text = "思考过程:",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            MarkdownContent(
                content = thinking,
                textColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(12.dp))
        }
        
        if (answer.isNotEmpty()) {
            Text(
                text = "回答:",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            MarkdownContent(
                content = answer,
                textColor = MaterialTheme.colorScheme.onSurface
            )
        }
        
        if (thinking.isEmpty() && answer.isEmpty()) {
            MarkdownContent(
                content = content,
                textColor = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

/**
 * 解析消息内容，提取 thinking 和 answer
 */
private fun parseMessageContent(content: String): Pair<String, String> {
    return try {
        // 先尝试解析标准的JSON格式
        if (content.contains("\"thinking\"") && content.contains("\"answer\"")) {
            val jsonString = content.replace("'", "\"")
            val thinkingStart = jsonString.indexOf("\"thinking\":\"") + 11
            val thinkingEnd = jsonString.indexOf("\",\"answer\"", thinkingStart)
            val answerStart = jsonString.indexOf("\"answer\":\"") + 9
            val answerEnd = jsonString.lastIndexOf("\"}")
            
            val thinking = if (thinkingStart > 10 && thinkingEnd > thinkingStart) {
                jsonString.substring(thinkingStart, thinkingEnd)
                    .replace("\\n", "\n")
                    .replace("\\\"", "\"")
            } else ""
            
            val answer = if (answerStart > 8 && answerEnd > answerStart) {
                jsonString.substring(answerStart, answerEnd)
                    .replace("\\n", "\n")
                    .replace("\\\"", "\"")
            } else ""
            
            thinking to answer
        } else {
            // 如果不是标准JSON，尝试简单解析
            if (content.contains("thinking") && content.contains("answer")) {
                val thinkingMatch = Regex("'thinking':\\s*'([^']*)'").find(content)
                val answerMatch = Regex("'answer':\\s*'([^']*)'").find(content)
                
                val thinking = thinkingMatch?.groupValues?.get(1)?.replace("\\n", "\n") ?: ""
                val answer = answerMatch?.groupValues?.get(1)?.replace("\\n", "\n") ?: ""
                
                thinking to answer
            } else {
                "" to content
            }
        }
    } catch (e: Exception) {
        "" to content
    }
}

