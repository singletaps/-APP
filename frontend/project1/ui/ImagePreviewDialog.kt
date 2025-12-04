package com.example.project1.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.zIndex
import kotlin.math.max
import kotlin.math.min

/**
 * 图片预览对话框
 * 支持缩放、滑动查看多张图片
 */
@Composable
fun ImagePreviewDialog(
    images: List<ImageBitmap>,
    initialIndex: Int = 0,
    onDismiss: () -> Unit
) {
    if (images.isEmpty()) return

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.95f))
        ) {
            // 图片查看器（支持多张图片滑动）
            var currentIndex by remember { mutableStateOf(initialIndex.coerceIn(0, images.size - 1)) }
            var dragOffsetX by remember { mutableStateOf(0f) }
            
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .pointerInput(Unit) {
                        if (images.size > 1) {
                            // 检测水平滑动切换图片
                            detectDragGestures(
                                onDragEnd = {
                                    val threshold = size.width * 0.3f
                                    if (dragOffsetX > threshold && currentIndex > 0) {
                                        // 向右滑动，显示上一张
                                        currentIndex--
                                    } else if (dragOffsetX < -threshold && currentIndex < images.size - 1) {
                                        // 向左滑动，显示下一张
                                        currentIndex++
                                    }
                                    // 重置拖拽偏移
                                    dragOffsetX = 0f
                                }
                            ) { change, dragAmount ->
                                dragOffsetX += dragAmount.x
                            }
                        }
                    }
            ) {
                // 显示当前图片和相邻图片（用于滑动效果）
                if (images.size > 1) {
                    // 显示上一张（如果存在）
                    if (currentIndex > 0) {
                        ZoomableImage(
                            image = images[currentIndex - 1],
                            modifier = Modifier
                                .fillMaxSize()
                                .graphicsLayer {
                                    translationX = dragOffsetX - size.width
                                    alpha = 0.5f
                                }
                        )
                    }

                    // 显示当前图片
                    ZoomableImage(
                        image = images[currentIndex],
                        modifier = Modifier
                            .fillMaxSize()
                            .graphicsLayer {
                                translationX = dragOffsetX
                            }
                    )

                    // 显示下一张（如果存在）
                    if (currentIndex < images.size - 1) {
                        ZoomableImage(
                            image = images[currentIndex + 1],
                            modifier = Modifier
                                .fillMaxSize()
                                .graphicsLayer {
                                    translationX = dragOffsetX + size.width
                                    alpha = 0.5f
                                }
                        )
                    }

                    // 页码指示器
                    Surface(
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .padding(bottom = 32.dp),
                        color = Color.Black.copy(alpha = 0.6f),
                        shape = MaterialTheme.shapes.small
                    ) {
                        Text(
                            text = "${currentIndex + 1} / ${images.size}",
                            color = Color.White,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                        )
                    }
                } else {
                    // 单张图片
                    ZoomableImage(
                        image = images[0],
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }
            
            // 关闭按钮（放在最上层，确保可以点击）
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(16.dp)
                    .zIndex(10f)  // 确保在最上层
            ) {
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.size(48.dp)  // 增大点击区域
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "关闭",
                        tint = Color.White,
                        modifier = Modifier.size(32.dp)
                    )
                }
            }
        }
    }
}

/**
 * 可缩放的图片组件
 * 支持：
 * - 双指缩放（pinch to zoom）
 * - 双击放大/缩小
 * - 拖拽移动
 */
@Composable
fun ZoomableImage(
    image: ImageBitmap,
    modifier: Modifier = Modifier
) {
    var scale by remember { mutableStateOf(1f) }
    var offsetX by remember { mutableStateOf(0f) }
    var offsetY by remember { mutableStateOf(0f) }

    // 计算缩放和偏移的约束
    val minScale = 1f
    val maxScale = 5f

    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center
    ) {
        androidx.compose.foundation.Image(
            bitmap = image,
            contentDescription = null,
            modifier = Modifier
                .fillMaxSize()
                .pointerInput(Unit) {
                    // 双指缩放和拖拽
                    detectTransformGestures { _, pan, zoom, _ ->
                        val newScale = (scale * zoom).coerceIn(minScale, maxScale)
                        scale = newScale

                        // 如果已缩放，允许拖拽
                        if (scale > minScale) {
                            offsetX = (offsetX + pan.x).coerceIn(
                                -size.width * (scale - 1) / 2,
                                size.width * (scale - 1) / 2
                            )
                            offsetY = (offsetY + pan.y).coerceIn(
                                -size.height * (scale - 1) / 2,
                                size.height * (scale - 1) / 2
                            )
                        } else {
                            // 如果缩放回到1，重置偏移
                            offsetX = 0f
                            offsetY = 0f
                        }
                    }
                }
                .pointerInput(Unit) {
                    // 双击放大/缩小
                    detectTapGestures(
                        onDoubleTap = { tapOffset ->
                            // 双击切换缩放状态
                            if (scale > minScale) {
                                // 缩小
                                scale = minScale
                                offsetX = 0f
                                offsetY = 0f
                            } else {
                                // 放大到2倍
                                scale = 2f
                            }
                        }
                    )
                }
                .graphicsLayer(
                    scaleX = scale,
                    scaleY = scale,
                    translationX = offsetX,
                    translationY = offsetY
                ),
            contentScale = ContentScale.Fit
        )
    }
}

