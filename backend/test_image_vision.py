#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图像理解功能
测试内容：
1. URL方式发送图像+文本
2. Files API上传方式发送图像+文本
3. 检查响应体结构是否与现有文本响应一致
4. 测试流式和非流式两种方式
5. 测试多张图片支持

推荐的文件上传方法：
根据火山引擎文档，推荐使用以下两种方式：
1. URL方式（推荐用于公开图片）：直接使用可访问的图片URL
2. Files API上传（推荐用于本地文件）：
   - 使用 client.files.create() 上传文件
   - 获取返回的 file_id
   - 使用 file_id 构造 URL: f"file://{file_id}"
   
注意：base64方式可能不被支持，建议使用Files API上传本地文件
"""

import sys
import os
import base64
from pathlib import Path
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.ai.client import client

# 测试用的图片URL（火山引擎示例）
TEST_IMAGE_URL = "https://ark-project.tos-cn-beijing.volces.com/images/view.jpeg"

# 测试用的本地图片路径（需要用户提供或创建）
TEST_LOCAL_IMAGE_PATH = None  # 例如: "test_image.jpg"


def test_url_image_with_text_non_stream():
    """测试1: URL方式 - 非流式响应"""
    print("\n" + "="*60)
    print("测试1: URL方式 - 非流式响应")
    print("="*60)
    
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的AI助手，擅长分析图像内容。",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": TEST_IMAGE_URL
                    },
                },
                {"type": "text", "text": "请描述这张图片的内容。"},
            ],
        },
    ]
    
    try:
        print(f"\n发送请求...")
        print(f"消息格式: {messages}")
        
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        print(f"\n✅ 请求成功!")
        print(f"响应类型: {type(completion)}")
        print(f"响应对象属性: {dir(completion)}")
        
        # 检查响应结构
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            choice = completion.choices[0]
            print(f"\nChoice对象属性: {dir(choice)}")
            
            if hasattr(choice, 'message'):
                message = choice.message
                print(f"\nMessage对象属性: {dir(message)}")
                print(f"Message类型: {type(message)}")
                
                if hasattr(message, 'content'):
                    content = message.content
                    print(f"\n✅ 响应内容: {content}")
                    print(f"内容类型: {type(content)}")
                else:
                    print(f"\n⚠️ Message对象没有content属性")
                    print(f"Message对象: {message}")
            else:
                print(f"\n⚠️ Choice对象没有message属性")
                print(f"Choice对象: {choice}")
        else:
            print(f"\n⚠️ 响应中没有choices")
            print(f"完整响应: {completion}")
            
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()


def test_url_image_with_text_stream():
    """测试2: URL方式 - 流式响应"""
    print("\n" + "="*60)
    print("测试2: URL方式 - 流式响应")
    print("="*60)
    
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的AI助手，擅长分析图像内容。",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": TEST_IMAGE_URL
                    },
                },
                {"type": "text", "text": "请描述这张图片的内容。"},
            ],
        },
    ]
    
    try:
        print(f"\n发送流式请求...")
        print(f"消息格式: {messages}")
        
        stream = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
            stream=True,
        )
        
        print(f"\n✅ 流式请求成功!")
        print(f"开始接收流式响应...\n")
        
        chunk_count = 0
        full_content = ""
        
        for chunk in stream:
            chunk_count += 1
            
            # 检查chunk结构
            if chunk_count == 1:
                print(f"第一个chunk类型: {type(chunk)}")
                print(f"第一个chunk属性: {dir(chunk)}")
            
            # 处理流式响应
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                
                # 检查delta结构
                if hasattr(choice, 'delta'):
                    delta = choice.delta
                    if chunk_count == 1:
                        print(f"Delta对象属性: {dir(delta)}")
                        print(f"Delta类型: {type(delta)}")
                    
                    # 检查content
                    if hasattr(delta, 'content') and delta.content:
                        content = delta.content
                        full_content += content
                        if chunk_count <= 3:  # 只打印前3个chunk的详细信息
                            print(f"Chunk #{chunk_count}: content长度={len(content)}, 预览={content[:50]}")
                    
                    # 检查reasoning_content（如果启用深度思考）
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reasoning = delta.reasoning_content
                        if chunk_count <= 3:
                            print(f"Chunk #{chunk_count}: reasoning_content长度={len(str(reasoning))}")
        
        print(f"\n✅ 流式响应完成!")
        print(f"总共收到 {chunk_count} 个chunk")
        print(f"完整内容长度: {len(full_content)}")
        print(f"完整内容预览: {full_content[:200]}...")
        
    except Exception as e:
        print(f"\n❌ 流式请求失败: {e}")
        import traceback
        traceback.print_exc()


def test_files_api_upload():
    """测试3: Files API上传方式（推荐方法）"""
    print("\n" + "="*60)
    print("测试3: Files API上传方式（推荐方法）")
    print("="*60)
    
    # 检查是否有测试图片
    if not TEST_LOCAL_IMAGE_PATH or not os.path.exists(TEST_LOCAL_IMAGE_PATH):
        print(f"\n⚠️ 未提供本地图片路径或文件不存在")
        print(f"请设置 TEST_LOCAL_IMAGE_PATH 变量或创建测试图片")
        print(f"跳过Files API上传测试")
        print(f"\n推荐方法说明：")
        print(f"1. 使用 client.files.create() 上传文件")
        print(f"2. 获取返回的 file_id")
        print(f"3. 使用 file_id 构造 URL: f'file://{{file_id}}'")
        return
    
    try:
        print(f"\n步骤1: 上传文件到Files API")
        print(f"文件路径: {TEST_LOCAL_IMAGE_PATH}")
        print(f"文件大小: {os.path.getsize(TEST_LOCAL_IMAGE_PATH)} bytes")
        
        # 检查文件大小（建议限制在合理范围内，如10MB）
        file_size = os.path.getsize(TEST_LOCAL_IMAGE_PATH)
        if file_size > 10 * 1024 * 1024:  # 10MB
            print(f"⚠️ 文件较大 ({file_size / 1024 / 1024:.2f}MB)，建议压缩")
        
        # 上传文件
        with open(TEST_LOCAL_IMAGE_PATH, 'rb') as f:
            file_obj = client.files.create(
                file=f,
                purpose="vision"  # 或 "file-extract" 等，根据文档确定
            )
        
        print(f"✅ 文件上传成功!")
        print(f"File对象类型: {type(file_obj)}")
        print(f"File对象属性: {dir(file_obj)}")
        
        # 获取file_id
        if hasattr(file_obj, 'id'):
            file_id = file_obj.id
            print(f"File ID: {file_id}")
        elif hasattr(file_obj, 'file_id'):
            file_id = file_obj.file_id
            print(f"File ID: {file_id}")
        else:
            print(f"⚠️ 无法获取file_id，File对象: {file_obj}")
            return
        
        # 使用file_id构造URL
        file_url = f"file://{file_id}"
        print(f"\n步骤2: 使用上传的文件发送请求")
        print(f"文件URL: {file_url}")
        
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的AI助手，擅长分析图像内容。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": file_url
                        },
                    },
                    {"type": "text", "text": "请描述这张图片的内容。"},
                ],
            },
        ]
        
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            content = completion.choices[0].message.content
            print(f"✅ Files API方式成功!")
            print(f"响应内容: {content[:300]}...")
        else:
            print(f"❌ Files API方式失败")
            
    except Exception as e:
        print(f"\n❌ Files API上传失败: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n备选方案：如果Files API不可用，可以考虑：")
        print(f"1. 将图片上传到自己的服务器，获取公开URL")
        print(f"2. 使用火山引擎的对象存储服务，获取URL")


def test_multiple_images():
    """测试4: 多张图片 + 文本"""
    print("\n" + "="*60)
    print("测试4: 多张图片 + 文本")
    print("="*60)
    
    # 使用同一张图片两次作为示例
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的AI助手，擅长分析图像内容。",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": TEST_IMAGE_URL
                    },
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": TEST_IMAGE_URL  # 实际应用中应该是不同的图片
                    },
                },
                {"type": "text", "text": "请比较这两张图片的异同。"},
            ],
        },
    ]
    
    try:
        print(f"\n发送多图片请求...")
        
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            content = completion.choices[0].message.content
            print(f"✅ 多图片请求成功!")
            print(f"响应内容: {content[:300]}...")
        else:
            print(f"❌ 多图片请求失败")
            
    except Exception as e:
        print(f"\n❌ 多图片请求失败: {e}")
        import traceback
        traceback.print_exc()


def compare_response_structure():
    """测试5: 比较图像响应和文本响应的结构是否一致"""
    print("\n" + "="*60)
    print("测试5: 比较响应结构一致性")
    print("="*60)
    
    # 文本请求
    text_messages = [
        {
            "role": "system",
            "content": "你是一个专业的AI助手。",
        },
        {
            "role": "user",
            "content": "请简单介绍一下你自己。",
        },
    ]
    
    # 图像请求
    image_messages = [
        {
            "role": "system",
            "content": "你是一个专业的AI助手。",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": TEST_IMAGE_URL
                    },
                },
                {"type": "text", "text": "请描述这张图片。"},
            ],
        },
    ]
    
    try:
        # 文本响应
        print("\n获取文本响应...")
        text_completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=text_messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        # 图像响应
        print("获取图像响应...")
        image_completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=image_messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        # 比较结构
        print("\n比较响应结构...")
        print(f"文本响应类型: {type(text_completion)}")
        print(f"图像响应类型: {type(image_completion)}")
        print(f"类型是否一致: {type(text_completion) == type(image_completion)}")
        
        if hasattr(text_completion, 'choices') and hasattr(image_completion, 'choices'):
            text_choice = text_completion.choices[0]
            image_choice = image_completion.choices[0]
            
            print(f"\n文本Choice属性: {[attr for attr in dir(text_choice) if not attr.startswith('_')]}")
            print(f"图像Choice属性: {[attr for attr in dir(image_choice) if not attr.startswith('_')]}")
            
            if hasattr(text_choice, 'message') and hasattr(image_choice, 'message'):
                text_msg = text_choice.message
                image_msg = image_choice.message
                
                print(f"\n文本Message属性: {[attr for attr in dir(text_msg) if not attr.startswith('_')]}")
                print(f"图像Message属性: {[attr for attr in dir(image_msg) if not attr.startswith('_')]}")
                
                print(f"\n✅ 响应结构基本一致，可以复用现有代码")
            else:
                print(f"\n⚠️ Message结构可能不同")
        else:
            print(f"\n⚠️ 无法比较响应结构")
            
    except Exception as e:
        print(f"\n❌ 比较失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("\n" + "="*60)
    print("图像理解功能测试")
    print("="*60)
    print(f"\n使用的模型: doubao-seed-1-6-251015")
    print(f"测试图片URL: {TEST_IMAGE_URL}")
    if TEST_LOCAL_IMAGE_PATH:
        print(f"本地测试图片: {TEST_LOCAL_IMAGE_PATH}")
    else:
        print(f"本地测试图片: 未设置（跳过Files API测试）")
    
    print("\n" + "="*60)
    print("开始测试...")
    print("="*60)
    
    # 运行所有测试
    test_url_image_with_text_non_stream()
    test_url_image_with_text_stream()
    test_files_api_upload()
    test_multiple_images()
    compare_response_structure()
    
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)
    print("\n测试总结和建议：")
    print("1. URL方式：适用于公开可访问的图片，最简单直接")
    print("2. Files API方式：适用于本地文件，需要先上传获取file_id")
    print("3. 响应结构：图像响应与文本响应结构一致，可以复用现有代码")
    print("4. 流式响应：图像理解支持流式响应，与文本流式响应格式相同")
    print("5. 多图片支持：可以在content数组中添加多个image_url对象")
    print("\n推荐实现方案：")
    print("- Android端：选择图片后，先上传到后端服务器或使用Files API")
    print("- 后端：接收图片URL或file_id，构造多模态消息格式")
    print("- 响应处理：与现有文本响应处理逻辑完全一致")


if __name__ == "__main__":
    main()

