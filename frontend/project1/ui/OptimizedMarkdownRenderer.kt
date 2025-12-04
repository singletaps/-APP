package com.example.project1.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import io.noties.markwon.Markwon
import io.noties.markwon.ext.strikethrough.StrikethroughPlugin
import io.noties.markwon.ext.tables.TablePlugin
import io.noties.markwon.linkify.LinkifyPlugin
import io.noties.markwon.image.ImagesPlugin
import android.content.Context
import android.widget.TextView
import android.util.TypedValue
import android.view.Gravity
import androidx.compose.ui.graphics.toArgb
import android.webkit.WebView
import android.webkit.WebViewClient
import android.util.Log
import org.json.JSONObject
import org.json.JSONException
import kotlinx.coroutines.Dispatchers
import android.graphics.Color as AndroidColor

/**
 * 高性能流式渲染方案
 * 
 * 策略：
 * 1. 普通文本使用 Markwon（原生 TextView，性能最佳）
 * 2. LaTeX 公式使用优化的 WebView（仅在需要时创建）
 * 3. 流式更新时，只更新新增内容，不重新渲染整个内容
 */

/**
 * 检测内容中是否包含 LaTeX 数学公式
 * 支持多种格式：
 * - $...$ 或 $$...$$ (标准格式)
 * - \(...\) 或 \[...\] (LaTeX 标准格式)
 * - (包含 LaTeX 命令的括号内容，如 \frac, \sqrt 等)
 */
private fun containsLatex(content: String): Boolean {
    // 检测标准格式
    val standardPattern = Regex("""\$[^$]+\$|\$\$[^$]+\$\$|\\\([^)]+\\\)|\\\[[^\]]+\\\]""")
    val hasStandard = standardPattern.containsMatchIn(content)
    
    // 检测包含 LaTeX 命令的内容（即使没有 $ 或 \( 包裹）
    // 常见的 LaTeX 命令：\frac, \sqrt, \sum, \int, \alpha, \beta, \Delta, \neq, \pm, \leq, \geq 等
    val latexCommandPattern = Regex("""\\[a-zA-Z]+\{?[^}]*\}?|\\[^a-zA-Z\s]""")
    val hasLatexCommands = latexCommandPattern.containsMatchIn(content)
    
    val hasLatex = hasStandard || hasLatexCommands
    Log.d("LaTeX_DEBUG", "containsLatex: $hasLatex (standard: $hasStandard, commands: $hasLatexCommands)")
    if (hasLatex) {
        if (hasStandard) {
            val matches = standardPattern.findAll(content)
            Log.d("LaTeX_DEBUG", "Found standard LaTeX matches: ${matches.map { it.value.take(50) }.joinToString(", ")}")
        }
        if (hasLatexCommands) {
            val commandMatches = latexCommandPattern.findAll(content).take(5)
            Log.d("LaTeX_DEBUG", "Found LaTeX commands: ${commandMatches.map { it.value }.joinToString(", ")}")
        }
    }
    return hasLatex
}

/**
 * 将内容分割为文本块和 LaTeX 块
 */
data class ContentBlock(
    val type: BlockType,
    val content: String
)

enum class BlockType {
    TEXT,      // 普通文本（使用 Markwon）
    LATEX      // LaTeX 公式（使用 WebView）
}

/**
 * 查找所有 \(...\) 格式的 LaTeX 匹配（支持嵌套）
 */
private fun findEscapedBracketLatexMatches(content: String): List<MatchResult> {
    val matches = mutableListOf<MatchResult>()
    var i = 0
    
    while (i < content.length - 1) {
        // 查找 \(
        if (content[i] == '\\' && i + 1 < content.length && content[i + 1] == '(') {
            val startIndex = i
            // 查找匹配的 \)
            var depth = 1
            var j = i + 2
            
            while (j < content.length && depth > 0) {
                // 检查是否是转义字符
                if (content[j] == '\\' && j + 1 < content.length) {
                    // 检查转义后的字符
                    when (content[j + 1]) {
                        '(' -> {
                            depth++
                            j += 2
                        }
                        ')' -> {
                            depth--
                            if (depth == 0) {
                                // 找到匹配的 \)
                                val match = SimpleMatchResult(
                                    range = startIndex..(j + 1),
                                    value = content.substring(startIndex, j + 2)
                                )
                                matches.add(match)
                                i = j + 2
                                break
                            } else {
                                j += 2
                            }
                        }
                        else -> {
                            // 其他转义字符，跳过
                            j += 2
                        }
                    }
                } else if (content[j] == '(') {
                    // 普通左括号，增加深度
                    depth++
                    j++
                } else if (content[j] == ')') {
                    // 普通右括号，减少深度（但这不是我们要找的 \)，所以继续）
                    depth--
                    if (depth == 0) {
                        // 深度为0但没有反斜杠，说明不是 \(...\) 格式，跳过
                        i++
                        break
                    } else {
                        j++
                    }
                } else {
                    j++
                }
            }
            if (depth > 0) {
                // 没有找到匹配的 \)，跳过这个 \(
                i++
            }
        } else {
            i++
        }
    }
    
    return matches
}

/**
 * 查找匹配的括号位置（支持嵌套）
 */
private fun findMatchingBracket(content: String, startIndex: Int, openChar: Char, closeChar: Char): Int? {
    if (startIndex >= content.length || content[startIndex] != openChar) return null
    
    var depth = 1
    var i = startIndex + 1
    var inEscape = false
    
    while (i < content.length && depth > 0) {
        when {
            inEscape -> {
                inEscape = false
                i++
            }
            content[i] == '\\' -> {
                inEscape = true
                i++
            }
            content[i] == openChar -> {
                depth++
                i++
            }
            content[i] == closeChar -> {
                depth--
                if (depth == 0) {
                    return i
                }
                i++
            }
            else -> i++
        }
    }
    return null
}

/**
 * 简单的匹配结果数据类
 */
private data class SimpleMatchResult(
    override val range: IntRange,
    override val value: String
) : MatchResult {
    override val groups: MatchGroupCollection = object : MatchGroupCollection {
        override val size: Int = 1
        override fun contains(element: MatchGroup?): Boolean {
            return element?.value == value && element.range == range
        }

        override fun containsAll(elements: Collection<MatchGroup?>): Boolean {
            return elements.all { it?.value == value && it.range == range }
        }


        override operator fun get(index: Int): MatchGroup? = if (index == 0) {
            MatchGroup(value, range)
        } else null
        
        override fun iterator(): Iterator<MatchGroup> = listOf(MatchGroup(value, range)).iterator()

        
        override fun isEmpty(): Boolean = false
    }
    
    override val groupValues: List<String> = listOf(value)
    
    override fun next(): MatchResult? = null
}

/**
 * 查找包含 LaTeX 命令的括号对（正确处理嵌套）
 */
private fun findBracketLatexMatches(content: String): List<MatchResult> {
    val matches = mutableListOf<MatchResult>()
    var i = 0
    
    while (i < content.length) {
        // 查找左括号
        val openIndex = content.indexOf('(', i)
        if (openIndex == -1) break
        
        // 检查这个括号内是否包含 LaTeX 命令或数学符号
        val closeIndex = findMatchingBracket(content, openIndex, '(', ')')
        if (closeIndex != null) {
            val bracketContent = content.substring(openIndex + 1, closeIndex)
            // 检查是否包含 LaTeX 特征
            val hasLatex = bracketContent.contains(Regex("""\\[a-zA-Z]+|\^|_|\{|\}"""))
            
            if (hasLatex) {
                // 创建匹配结果
                val match = SimpleMatchResult(
                    range = openIndex..closeIndex,
                    value = content.substring(openIndex, closeIndex + 1)
                )
                matches.add(match)
                i = closeIndex + 1
            } else {
                i = openIndex + 1
            }
        } else {
            i = openIndex + 1
        }
    }
    
    return matches
}

/**
 * 解析内容，分割为文本块和 LaTeX 块
 */
private fun parseContent(content: String): List<ContentBlock> {
    Log.d("LaTeX_DEBUG", "parseContent called, content length: ${content.length}")
    Log.d("LaTeX_DEBUG", "Content preview (first 200 chars): ${content.take(200)}")
    
    val blocks = mutableListOf<ContentBlock>()
    var currentIndex = 0
    
    // 匹配所有 LaTeX 公式（包括 $...$ 和 $$...$$ 和 \(...\) 和 \[...\]）
    val dollarDoublePattern = Regex("""\$\$[^$]+\$\$""")
    val dollarSinglePattern = Regex("""(?<!\$)\$(?!\$)[^$]+\$""")
    
    val dollarDoubleMatches = dollarDoublePattern.findAll(content).toList()
    val dollarSingleMatches = dollarSinglePattern.findAll(content).toList()
    
    // 使用专门的函数匹配 \(...\) 格式（支持嵌套）
    val bracketInlineMatches = findEscapedBracketLatexMatches(content)
    
    // 匹配 \[...\] 格式（显示公式）
    val bracketDisplayPattern = Regex("""\\\[[^\]]+\\\]""")
    val bracketDisplayMatches = bracketDisplayPattern.findAll(content).toList()
    
    val standardMatches = dollarDoubleMatches + dollarSingleMatches + bracketInlineMatches + bracketDisplayMatches
    
    Log.d("LaTeX_DEBUG", "LaTeX pattern matches: $$=${dollarDoubleMatches.size}, $=${dollarSingleMatches.size}, \\(...\\)=${bracketInlineMatches.size}, \\[...\\]=${bracketDisplayMatches.size}")
    
    // 调试：检查内容中是否包含 \( 或 \)
    if (content.contains("\\(") || content.contains("\\)")) {
        Log.d("LaTeX_DEBUG", "Content contains \\( or \\): ${content.contains("\\(")} / ${content.contains("\\)")}")
        bracketInlineMatches.forEachIndexed { index, match ->
            Log.d("LaTeX_DEBUG", "Bracket inline match $index: '${match.value.take(80)}'")
        }
    }
    
    // 使用改进的括号匹配（支持嵌套）
    val bracketMatches = findBracketLatexMatches(content)
    
    Log.d("LaTeX_DEBUG", "Standard matches: ${standardMatches.size}, Bracket matches: ${bracketMatches.size}")
    bracketMatches.forEachIndexed { index, match ->
        Log.d("LaTeX_DEBUG", "Bracket match $index: '${match.value.take(80)}'")
    }
    
    // 合并所有匹配，去除重叠
    val allMatches = mutableListOf<MatchResult>()
    val processedRanges = mutableSetOf<IntRange>()
    
    (standardMatches + bracketMatches).sortedBy { it.range.first }.forEach { match ->
        // 检查是否与已处理的匹配重叠
        val overlaps = processedRanges.any { range ->
            !(match.range.last < range.first || match.range.first > range.last)
        }
        if (!overlaps) {
            allMatches.add(match)
            processedRanges.add(match.range)
        } else {
            Log.d("LaTeX_DEBUG", "Skipping overlapping match: ${match.value.take(50)}")
        }
    }
    
    Log.d("LaTeX_DEBUG", "Found ${standardMatches.size} standard LaTeX matches, ${bracketMatches.size} bracket LaTeX matches")
    allMatches.forEachIndexed { index, match ->
        Log.d("LaTeX_DEBUG", "Match $index: '${match.value.take(50)}...' at position ${match.range}")
    }
    
    for (match in allMatches) {
        // 添加 LaTeX 之前的文本
        if (match.range.first > currentIndex) {
            val textBlock = content.substring(currentIndex, match.range.first)
            if (textBlock.isNotBlank()) {
                Log.d("LaTeX_DEBUG", "Adding TEXT block: '${textBlock.take(50)}...'")
                blocks.add(ContentBlock(BlockType.TEXT, textBlock))
            }
        }
        
        // 添加 LaTeX 块
        var latexContent = match.value
        // 如果是括号格式但没有 $ 或 \(，需要转换为 KaTeX 可识别的格式
        if (!latexContent.startsWith("$") && !latexContent.startsWith("\\(") && !latexContent.startsWith("\\[")) {
            // 移除外层括号，内容本身就是 LaTeX
            if (latexContent.startsWith("(") && latexContent.endsWith(")")) {
                latexContent = latexContent.removePrefix("(").removeSuffix(")")
            }
            // 不需要添加 $，直接使用内容，KaTeX 的 auto-render 会处理
        }
        Log.d("LaTeX_DEBUG", "Adding LATEX block: '${latexContent.take(50)}...'")
        blocks.add(ContentBlock(BlockType.LATEX, latexContent))
        
        currentIndex = match.range.last + 1
    }
    
    // 添加剩余的文本
    if (currentIndex < content.length) {
        val textBlock = content.substring(currentIndex)
        if (textBlock.isNotBlank()) {
            Log.d("LaTeX_DEBUG", "Adding final TEXT block: '${textBlock.take(50)}...'")
            blocks.add(ContentBlock(BlockType.TEXT, textBlock))
        }
    }
    
    // 如果没有找到 LaTeX，整个内容作为文本块
    if (blocks.isEmpty()) {
        Log.d("LaTeX_DEBUG", "No LaTeX found, adding entire content as TEXT block")
        blocks.add(ContentBlock(BlockType.TEXT, content))
    }
    
    Log.d("LaTeX_DEBUG", "Total blocks: ${blocks.size} (${blocks.count { it.type == BlockType.TEXT }} TEXT, ${blocks.count { it.type == BlockType.LATEX }} LATEX)")
    return blocks
}

/**
 * 使用 Markwon 渲染文本块（高性能）
 */
@Composable
private fun TextBlock(
    content: String,
    modifier: Modifier = Modifier,
    textStyle: TextStyle = MaterialTheme.typography.bodyMedium,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val markwon = remember { MarkwonProvider.getMarkwon(context) }
    
    AndroidView(
        factory = { ctx ->
            TextView(ctx).apply {
                val textSizeSp = textStyle.fontSize.value
                setTextSize(TypedValue.COMPLEX_UNIT_SP, textSizeSp)
                setTextColor(textColor.toArgb())
                
                val lineSpacingExtraPx = TypedValue.applyDimension(
                    TypedValue.COMPLEX_UNIT_DIP, 4f, ctx.resources.displayMetrics
                )
                setLineSpacing(lineSpacingExtraPx, 1.2f)
                
                val paddingPx = TypedValue.applyDimension(
                    TypedValue.COMPLEX_UNIT_DIP, 8f, ctx.resources.displayMetrics
                ).toInt()
                setPadding(paddingPx, paddingPx, paddingPx, paddingPx)
                
                setHorizontallyScrolling(false)
                gravity = Gravity.START or Gravity.TOP
                setTextIsSelectable(true)
                setLinkTextColor(textColor.toArgb())
            }
        },
        modifier = modifier.fillMaxWidth(),
        update = { textView ->
            markwon.setMarkdown(textView, content)
        }
    )
}

/**
 * 使用 Markwon + MathJax 渲染 LaTeX（WebView 方案，使用 MathJax 替代 KaTeX）
 */
@Composable
private fun LatexBlock(
    latex: String,
    modifier: Modifier = Modifier,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    val htmlContent = remember(latex, textColor) {
        Log.d("LaTeX_DEBUG", "LatexBlock: Processing LaTeX: '$latex'")
        
        // 清理 LaTeX 内容，移除各种标记
        var cleanLatex = latex.trim()
        
        // 移除标准格式标记
        if (cleanLatex.startsWith("$$") && cleanLatex.endsWith("$$")) {
            cleanLatex = cleanLatex.removePrefix("$$").removeSuffix("$$")
        } else if (cleanLatex.startsWith("$") && cleanLatex.endsWith("$") && !cleanLatex.startsWith("$$")) {
            cleanLatex = cleanLatex.removePrefix("$").removeSuffix("$")
        } else if (cleanLatex.startsWith("\\(") && cleanLatex.endsWith("\\)")) {
            cleanLatex = cleanLatex.removePrefix("\\(").removeSuffix("\\)")
        } else if (cleanLatex.startsWith("\\[") && cleanLatex.endsWith("\\]")) {
            cleanLatex = cleanLatex.removePrefix("\\[").removeSuffix("\\]")
        }
        // 注意：括号格式的内容已经在 parseContent 中移除了括号，这里不需要再处理
        
        cleanLatex = cleanLatex.trim()
        Log.d("LaTeX_DEBUG", "LatexBlock: Cleaned LaTeX: '$cleanLatex'")
        
        val isDisplay = latex.startsWith("$$") || latex.startsWith("\\[")
        val colorHex = String.format("#%06X", 0xFFFFFF and textColor.toArgb())
        
        val mathClass = if (isDisplay) "math-display" else "math-inline"
        
        // 如果清理后的 LaTeX 不包含 $ 标记，说明是括号格式，需要用 $ 包裹
        val latexForRender = if (!cleanLatex.startsWith("$") && !cleanLatex.startsWith("\\(") && !cleanLatex.startsWith("\\[")) {
            if (isDisplay) "$$${cleanLatex}$$" else "$${cleanLatex}$"  // 行内公式用单个 $，显示公式用 $$
        } else {
            cleanLatex
        }
        
        Log.d("LaTeX_DEBUG", "LatexBlock: isDisplay=$isDisplay, mathClass=$mathClass")
        Log.d("LaTeX_DEBUG", "LatexBlock: latexForRender='$latexForRender'")
        
        val html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    margin: 0;
                    padding: 4px;
                    background: transparent;
                    color: $colorHex;
                }
                .math-display {
                    margin: 8px 0;
                    text-align: center;
                }
                .math-inline {
                    display: inline-block;
                }
                .katex {
                    color: $colorHex !important;
                }
            </style>
        </head>
        <body>
            <div class="$mathClass">$latexForRender</div>
            <script>
                var katexLoaded = false;
                var autoRenderLoaded = false;
                
                function loadKaTeX() {
                    if (window.AndroidLog) {
                        AndroidLog.log('Starting KaTeX loading...');
                    }
                    
                    // 加载 CSS
                    var link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css';
                    link.onerror = function() {
                        if (window.AndroidLog) {
                            AndroidLog.log('KaTeX CSS failed to load');
                        }
                    };
                    document.head.appendChild(link);
                    
                    // 加载 KaTeX 核心库
                    var script1 = document.createElement('script');
                    script1.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js';
                    script1.onload = function() {
                        katexLoaded = true;
                        if (window.AndroidLog) {
                            AndroidLog.log('KaTeX core loaded');
                        }
                        checkAndRender();
                    };
                    script1.onerror = function() {
                        if (window.AndroidLog) {
                            AndroidLog.log('KaTeX core failed to load, trying alternative CDN...');
                        }
                        // 尝试备用 CDN
                        var script1Alt = document.createElement('script');
                        script1Alt.src = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js';
                        script1Alt.onload = function() {
                            katexLoaded = true;
                            if (window.AndroidLog) {
                                AndroidLog.log('KaTeX core loaded from alternative CDN');
                            }
                            checkAndRender();
                        };
                        script1Alt.onerror = function() {
                            if (window.AndroidLog) {
                                AndroidLog.log('KaTeX core failed from all CDNs');
                            }
                        };
                        document.head.appendChild(script1Alt);
                    };
                    document.head.appendChild(script1);
                    
                    // 加载 auto-render
                    var script2 = document.createElement('script');
                    script2.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js';
                    script2.onload = function() {
                        autoRenderLoaded = true;
                        if (window.AndroidLog) {
                            AndroidLog.log('KaTeX auto-render loaded');
                        }
                        checkAndRender();
                    };
                    script2.onerror = function() {
                        if (window.AndroidLog) {
                            AndroidLog.log('KaTeX auto-render failed to load, trying alternative CDN...');
                        }
                        // 尝试备用 CDN
                        var script2Alt = document.createElement('script');
                        script2Alt.src = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js';
                        script2Alt.onload = function() {
                            autoRenderLoaded = true;
                            if (window.AndroidLog) {
                                AndroidLog.log('KaTeX auto-render loaded from alternative CDN');
                            }
                            checkAndRender();
                        };
                        script2Alt.onerror = function() {
                            if (window.AndroidLog) {
                                AndroidLog.log('KaTeX auto-render failed from all CDNs');
                            }
                        };
                        document.head.appendChild(script2Alt);
                    };
                    document.head.appendChild(script2);
                }
                
                function checkAndRender() {
                    if (katexLoaded && autoRenderLoaded && typeof renderMathInElement !== 'undefined' && typeof katex !== 'undefined') {
                        if (window.AndroidLog) {
                            AndroidLog.log('All KaTeX components loaded, starting render...');
                        }
                        try {
                            renderMathInElement(document.body, {
                                delimiters: [
                                    {left: "$$", right: "$$", display: true},
                                    {left: "$", right: "$", display: false},
                                    {left: "\\\\(", right: "\\\\)", display: false},
                                    {left: "\\\\[", right: "\\\\]", display: true}
                                ],
                                throwOnError: false,
                                strict: false
                            });
                            if (window.AndroidLog) {
                                AndroidLog.log('KaTeX rendering completed successfully');
                            }
                        } catch (e) {
                            if (window.AndroidLog) {
                                AndroidLog.log('KaTeX render error: ' + (e.message || String(e)));
                            }
                        }
                    } else {
                        if (window.AndroidLog) {
                            AndroidLog.log('Waiting for KaTeX: katexLoaded=' + katexLoaded + 
                                ', autoRenderLoaded=' + autoRenderLoaded + 
                                ', renderMathInElement=' + (typeof renderMathInElement !== 'undefined' ? 'exists' : 'missing') +
                                ', katex=' + (typeof katex !== 'undefined' ? 'exists' : 'missing'));
                        }
                    }
                }
                
                // 开始加载
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', loadKaTeX);
                } else {
                    loadKaTeX();
                }
            </script>
        </body>
        </html>
        """.trimIndent()
        
        Log.d("LaTeX_DEBUG", "LatexBlock: Generated HTML length: ${html.length}")
        Log.d("LaTeX_DEBUG", "LatexBlock: HTML preview: ${html.take(300)}...")
        
        html
    }
    
    AndroidView(
        factory = { ctx ->
            Log.d("LaTeX_DEBUG", "LatexBlock: Creating WebView")
            WebView(ctx).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.loadWithOverviewMode = true
                settings.useWideViewPort = true
                settings.builtInZoomControls = false
                settings.displayZoomControls = false
                settings.setSupportZoom(false)
                // 优化性能
                settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
                settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                settings.allowFileAccess = true
                settings.allowContentAccess = true
                setBackgroundColor(0x00000000) // 透明背景
                
                // 添加 JavaScript 接口用于调试
                addJavascriptInterface(object {
                    @android.webkit.JavascriptInterface
                    fun log(message: String) {
                        Log.d("LaTeX_DEBUG", "WebView JS: $message")
                    }
                }, "AndroidLog")
                
                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        super.onPageFinished(view, url)
                        Log.d("LaTeX_DEBUG", "LatexBlock: WebView page finished loading, URL: $url")
                        // 页面加载完成后，触发渲染检查
                        view?.evaluateJavascript("""
                            if (typeof checkAndRender === 'function') {
                                checkAndRender();
                            } else {
                                AndroidLog.log('checkAndRender function not found');
                            }
                        """.trimIndent(), null)
                    }
                    
                    override fun onReceivedError(
                        view: WebView?,
                        request: android.webkit.WebResourceRequest?,
                        error: android.webkit.WebResourceError?
                    ) {
                        super.onReceivedError(view, request, error)
                        val url = request?.url?.toString() ?: "unknown"
                        Log.e("LaTeX_DEBUG", "LatexBlock: WebView error loading $url: ${error?.description}, code: ${error?.errorCode}")
                        // 如果是 KaTeX 脚本加载失败，尝试备用 CDN
                        if (url.contains("katex") && error?.errorCode == android.webkit.WebViewClient.ERROR_HOST_LOOKUP) {
                            view?.evaluateJavascript("""
                                if (window.AndroidLog) {
                                    AndroidLog.log('KaTeX CDN failed, trying alternative...');
                                }
                                var link = document.createElement('link');
                                link.rel = 'stylesheet';
                                link.href = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css';
                                document.head.appendChild(link);
                                
                                var script1 = document.createElement('script');
                                script1.src = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js';
                                script1.onload = function() {
                                    var script2 = document.createElement('script');
                                    script2.src = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js';
                                    script2.onload = function() {
                                        if (window.AndroidLog) AndroidLog.log('Alternative KaTeX CDN loaded');
                                        setTimeout(function() {
                                            if (typeof renderMathInElement !== 'undefined') {
                                                renderMathInElement(document.body, {
                                                    delimiters: [
                                                        {left: "$$", right: "$$", display: true},
                                                        {left: "$", right: "$", display: false},
                                                        {left: "\\\\(", right: "\\\\)", display: false},
                                                        {left: "\\\\[", right: "\\\\]", display: true}
                                                    ],
                                                    throwOnError: false,
                                                    strict: false
                                                });
                                                if (window.AndroidLog) AndroidLog.log('KaTeX rendering completed');
                                            }
                                        }, 500);
                                    };
                                    document.head.appendChild(script2);
                                };
                                document.head.appendChild(script1);
                            """.trimIndent(), null)
                        }
                    }
                    
                    override fun onReceivedHttpError(
                        view: WebView?,
                        request: android.webkit.WebResourceRequest?,
                        errorResponse: android.webkit.WebResourceResponse?
                    ) {
                        super.onReceivedHttpError(view, request, errorResponse)
                        val url = request?.url?.toString() ?: "unknown"
                        Log.e("LaTeX_DEBUG", "LatexBlock: WebView HTTP error loading $url: ${errorResponse?.statusCode}")
                    }
                }
                
                // 在 factory 中也加载内容（确保首次加载）
                Log.d("LaTeX_DEBUG", "LatexBlock: Loading HTML in factory, content length: ${htmlContent.length}")
                loadDataWithBaseURL(
                    "https://cdn.jsdelivr.net/npm/katex@0.16.9/",
                    htmlContent,
                    "text/html",
                    "UTF-8",
                    null
                )
            }
        },
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 24.dp, max = 500.dp),
        update = { webView ->
            Log.d("LaTeX_DEBUG", "LatexBlock: Update called, loading HTML into WebView")
            Log.d("LaTeX_DEBUG", "LatexBlock: HTML content length: ${htmlContent.length}")
            webView.loadDataWithBaseURL(
                "https://cdn.jsdelivr.net/npm/katex@0.16.9/",
                htmlContent,
                "text/html",
                "UTF-8",
                null
            )
            Log.d("LaTeX_DEBUG", "LatexBlock: loadDataWithBaseURL called")
        }
    )
}

/**
 * 高性能混合渲染组件（支持流式更新）
 * 
 * 优势：
 * 1. 普通文本使用原生 TextView（性能最佳）
 * 2. LaTeX 公式使用优化的 WebView（仅在需要时创建）
 * 3. 流式更新时，Compose 会自动优化，只更新变化的部分
 */
@Composable
fun OptimizedMarkdownContent(
    content: String,
    modifier: Modifier = Modifier,
    textStyle: TextStyle = MaterialTheme.typography.bodyMedium,
    textColor: Color = MaterialTheme.colorScheme.onSurface
) {
    Log.d("LaTeX_DEBUG", "OptimizedMarkdownContent: Called with content length: ${content.length}")
    val blocks = remember(content) { 
        Log.d("LaTeX_DEBUG", "OptimizedMarkdownContent: Parsing content")
        parseContent(content) 
    }
    Log.d("LaTeX_DEBUG", "OptimizedMarkdownContent: Rendering ${blocks.size} blocks")
    
    Column(
        modifier = modifier.fillMaxWidth()
    ) {
        blocks.forEach { block ->
            when (block.type) {
                BlockType.TEXT -> {
                    TextBlock(
                        content = block.content,
                        textStyle = textStyle,
                        textColor = textColor
                    )
                }
                BlockType.LATEX -> {
                    LatexBlock(
                        latex = block.content,
                        textColor = textColor
                    )
                }
            }
        }
    }
}

/**
 * 解析消息内容，提取 thinking 和 answer
 * 支持两种格式：
 * 1. 分隔符格式：---思考过程--- 和 ---回答---
 * 2. JSON 格式：{"thinking": "...", "answer": "..."}（向后兼容）
 */
private fun parseMessageContent(content: String): Pair<String, String> {
    return try {
        Log.d("LaTeX_DEBUG", "parseMessageContent: Starting parse")
        Log.d("LaTeX_DEBUG", "parseMessageContent: Content starts with: ${content.take(100)}")
        
        // 优先检查新的分隔符格式
        val thinkingMarker = "---思考过程---"
        val answerMarker = "---回答---"
        
        if (content.contains(thinkingMarker) && content.contains(answerMarker)) {
            Log.d("LaTeX_DEBUG", "parseMessageContent: Detected separator format")
            Log.d("LaTeX_DEBUG", "parseMessageContent: Content length: ${content.length}")
            Log.d("LaTeX_DEBUG", "parseMessageContent: Thinking marker position: ${content.indexOf(thinkingMarker)}")
            Log.d("LaTeX_DEBUG", "parseMessageContent: Answer marker position: ${content.indexOf(answerMarker)}")
            
            val thinkingStart = content.indexOf(thinkingMarker) + thinkingMarker.length
            val answerStart = content.indexOf(answerMarker)
            
            if (thinkingStart >= thinkingMarker.length && answerStart > thinkingStart) {
                val thinking = content.substring(thinkingStart, answerStart)
                    .trim()
                    .removePrefix("\n")
                    .removeSuffix("\n")
                
                val answer = content.substring(answerStart + answerMarker.length)
                    .trim()
                    .removePrefix("\n")
                    .removeSuffix("\n")
                
                Log.d("LaTeX_DEBUG", "parseMessageContent: Separator format parsed successfully")
                Log.d("LaTeX_DEBUG", "parseMessageContent: Thinking length: ${thinking.length}, Answer length: ${answer.length}")
                Log.d("LaTeX_DEBUG", "parseMessageContent: Thinking preview: ${thinking.take(100)}")
                Log.d("LaTeX_DEBUG", "parseMessageContent: Answer preview: ${answer.take(100)}")
                
                return thinking to answer
            } else {
                Log.w("LaTeX_DEBUG", "parseMessageContent: Separator format detected but parsing failed")
                Log.w("LaTeX_DEBUG", "parseMessageContent: thinkingStart=$thinkingStart, answerStart=$answerStart")
            }
        } else {
            Log.d("LaTeX_DEBUG", "parseMessageContent: Separator format not found")
            Log.d("LaTeX_DEBUG", "parseMessageContent: Contains thinking marker: ${content.contains(thinkingMarker)}")
            Log.d("LaTeX_DEBUG", "parseMessageContent: Contains answer marker: ${content.contains(answerMarker)}")
        }
        
        // 回退到 JSON 格式（向后兼容）
        if (content.contains("\"thinking\"") && content.contains("\"answer\"")) {
            Log.d("LaTeX_DEBUG", "parseMessageContent: Detected JSON format with quotes")
            
            // 尝试使用 JSONObject 解析
            try {
                val json = JSONObject(content)
                var thinking = json.optString("thinking", "")
                var answer = json.optString("answer", "")
                
                Log.d("LaTeX_DEBUG", "parseMessageContent: JSON parsed successfully")
                Log.d("LaTeX_DEBUG", "parseMessageContent: Thinking length: ${thinking.length}, Answer length: ${answer.length}")
                
                // 检查并修复丢失的反斜杠
                // 如果发现 LaTeX 命令没有反斜杠，尝试修复
                if (answer.contains("frac") && !answer.contains("\\frac")) {
                    Log.w("LaTeX_DEBUG", "parseMessageContent: Fixing missing backslashes in LaTeX commands")
                    // 修复常见的 LaTeX 命令
                    answer = answer
                        .replace("frac", "\\frac")
                        .replace("left", "\\left")
                        .replace("right", "\\right")
                        .replace("sqrt", "\\sqrt")
                        .replace("pm", "\\pm")
                        .replace("neq", "\\neq")
                        .replace("boxed", "\\boxed")
                    Log.d("LaTeX_DEBUG", "parseMessageContent: Fixed answer preview (first 300 chars): ${answer.take(300)}")
                }
                
                return thinking to answer
            } catch (e: JSONException) {
                Log.d("LaTeX_DEBUG", "parseMessageContent: JSON parsing failed, trying manual parse: ${e.message}")
                
                // 手动解析（处理转义字符）
                val jsonString = content
                val thinkingStart = jsonString.indexOf("\"thinking\":\"") + 11
                Log.d("LaTeX_DEBUG", "parseMessageContent: thinkingStart = $thinkingStart")
                
                if (thinkingStart <= 11) {
                    Log.d("LaTeX_DEBUG", "parseMessageContent: thinkingStart invalid")
                    return "" to content
                }
                
                // 查找 thinking 的结束位置（需要考虑转义的引号）
                var thinkingEnd = thinkingStart
                var inEscape = false
                for (i in thinkingStart until jsonString.length) {
                    when {
                        inEscape -> inEscape = false
                        jsonString[i] == '\\' -> inEscape = true
                        jsonString[i] == '"' && jsonString.substring(i).startsWith("\",\"answer\"") -> {
                            thinkingEnd = i
                            break
                        }
                    }
                }
                
                Log.d("LaTeX_DEBUG", "parseMessageContent: thinkingEnd = $thinkingEnd")
                
                val answerStart = jsonString.indexOf("\"answer\":\"", thinkingEnd) + 9
                Log.d("LaTeX_DEBUG", "parseMessageContent: answerStart = $answerStart")
                
                if (answerStart <= 9) {
                    Log.d("LaTeX_DEBUG", "parseMessageContent: answerStart invalid")
                    return "" to content
                }
                
                // 查找 answer 的结束位置
                var answerEnd = answerStart
                inEscape = false
                for (i in answerStart until jsonString.length) {
                    when {
                        inEscape -> inEscape = false
                        jsonString[i] == '\\' -> inEscape = true
                        jsonString[i] == '"' && (i == jsonString.length - 1 || jsonString[i + 1] == '}') -> {
                            answerEnd = i
                            break
                        }
                    }
                }
                
                Log.d("LaTeX_DEBUG", "parseMessageContent: answerEnd = $answerEnd")
                
                val thinking = if (thinkingEnd > thinkingStart) {
                    jsonString.substring(thinkingStart, thinkingEnd)
                        .replace("\\n", "\n")
                        .replace("\\\"", "\"")
                        .replace("\\\\", "\\")
                } else ""
                
                val answer = if (answerEnd > answerStart) {
                    jsonString.substring(answerStart, answerEnd)
                        .replace("\\n", "\n")
                        .replace("\\\"", "\"")
                        .replace("\\\\", "\\")
                } else ""
                
                Log.d("LaTeX_DEBUG", "parseMessageContent: Manual parse result - Thinking: ${thinking.length}, Answer: ${answer.length}")
                return thinking to answer
            }
        } else {
            Log.d("LaTeX_DEBUG", "parseMessageContent: Not JSON format, checking for simple format")
            if (content.contains("thinking") && content.contains("answer")) {
                val thinkingMatch = Regex("'thinking':\\s*'([^']*)'").find(content)
                val answerMatch = Regex("'answer':\\s*'([^']*)'").find(content)
                
                val thinking = thinkingMatch?.groupValues?.get(1)?.replace("\\n", "\n") ?: ""
                val answer = answerMatch?.groupValues?.get(1)?.replace("\\n", "\n") ?: ""
                
                Log.d("LaTeX_DEBUG", "parseMessageContent: Simple format - Thinking: ${thinking.length}, Answer: ${answer.length}")
                return thinking to answer
            } else {
                Log.d("LaTeX_DEBUG", "parseMessageContent: No thinking/answer found, returning full content")
                return "" to content
            }
        }
    } catch (e: Exception) {
        Log.e("LaTeX_DEBUG", "parseMessageContent: Exception: ${e.message}", e)
        return "" to content
    }
}

/**
 * 渲染思考过程和答案的完整组件（优化版）
 */
@Composable
fun DisplayMessageContentOptimized(
    content: String,
    modifier: Modifier = Modifier
) {
    Log.d("LaTeX_DEBUG", "DisplayMessageContentOptimized: Called")
    Log.d("LaTeX_DEBUG", "DisplayMessageContentOptimized: Content length: ${content.length}")
    Log.d("LaTeX_DEBUG", "DisplayMessageContentOptimized: Content preview: ${content.take(200)}")
    
    val (thinking, answer) = remember(content) {
        Log.d("LaTeX_DEBUG", "DisplayMessageContentOptimized: Parsing message content")
        val result = parseMessageContent(content)
        Log.d("LaTeX_DEBUG", "DisplayMessageContentOptimized: Thinking length: ${result.first.length}, Answer length: ${result.second.length}")
        result
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
            OptimizedMarkdownContent(
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
            OptimizedMarkdownContent(
                content = answer,
                textColor = MaterialTheme.colorScheme.onSurface
            )
        }
        
        if (thinking.isEmpty() && answer.isEmpty()) {
            OptimizedMarkdownContent(
                content = content,
                textColor = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

