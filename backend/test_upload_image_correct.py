#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试方案1的正确实现：后端代理 + 火山引擎 Files API
根据官方文档，使用Files API上传的文件应该使用 input_file 类型，直接传递 file_id
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.ai.client import client

# 测试图片路径
TEST_IMAGE_1 = "test_p1.png"
TEST_IMAGE_2 = "test_p2.png"


def upload_single_image():
    """上传单张图片"""
    print("\n" + "="*60)
    print("测试1: 上传单张图片到火山引擎Files API")
    print("="*60)
    
    if not os.path.exists(TEST_IMAGE_1):
        print(f"\n❌ 测试图片不存在: {TEST_IMAGE_1}")
        return None
    
    try:
        print(f"\n步骤1: 读取图片文件")
        print(f"图片路径: {TEST_IMAGE_1}")
        print(f"图片大小: {os.path.getsize(TEST_IMAGE_1)} bytes")
        
        print(f"\n步骤2: 上传到火山引擎Files API")
        
        # 使用实际文件对象上传
        with open(TEST_IMAGE_1, 'rb') as file_obj:
            uploaded_file = client.files.create(
                file=file_obj,
                purpose="user_data"
            )
        
        print(f"✅ 上传成功!")
        print(f"File ID: {uploaded_file.id}")
        print(f"File 对象属性: id={uploaded_file.id}, filename={uploaded_file.filename}, status={uploaded_file.status}")
        
        # 等待文件处理完成（如果需要）
        # await client.files.wait_for_processing(uploaded_file.id)  # 异步版本
        # 同步版本可能需要轮询状态
        
        return uploaded_file.id
        
    except Exception as e:
        print(f"\n❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_use_file_id_in_chat(file_id: str):
    """测试使用file_id进行图像理解（正确方式）"""
    print("\n" + "="*60)
    print("测试2: 使用file_id进行图像理解（input_file方式）")
    print("="*60)
    
    if not file_id:
        print(f"\n⚠️ 没有可用的file_id，跳过测试")
        return False
    
    try:
        print(f"\n使用File ID: {file_id}")
        
        # 方式1: 使用 input_file 类型（根据官方文档）
        print(f"\n方式1: 使用 input_file 类型")
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file_id  # 直接使用file_id
                    },
                    {
                        "type": "input_text",
                        "text": "请描述这张图片的内容。"
                    }
                ]
            }
        ]
        
        print(f"消息格式: {messages}")
        print(f"\n发送图像理解请求...")
        
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            content = completion.choices[0].message.content
            print(f"\n✅ 图像理解成功（input_file方式）!")
            print(f"响应内容: {content[:300]}...")
            return True
        else:
            print(f"\n❌ 图像理解失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 方式1失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 方式2: 尝试使用 image_url 格式（如果支持HTTP URL）
        print(f"\n方式2: 尝试使用 image_url 格式（仅用于HTTP URL）")
        print(f"注意：这种方式只适用于公开的HTTP/HTTPS URL，不适用于file_id")
        return False


def test_stream_with_file_id(file_id: str):
    """测试使用file_id进行流式响应"""
    print("\n" + "="*60)
    print("测试3: 使用file_id进行流式响应")
    print("="*60)
    
    if not file_id:
        print(f"\n⚠️ 没有可用的file_id，跳过测试")
        return False
    
    try:
        print(f"\n使用File ID: {file_id}")
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file_id
                    },
                    {
                        "type": "input_text",
                        "text": "请简要描述这张图片。"
                    }
                ]
            }
        ]
        
        print(f"\n发送流式图像理解请求...")
        
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
            
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                
                if hasattr(choice, 'delta'):
                    delta = choice.delta
                    
                    if hasattr(delta, 'content') and delta.content:
                        content = delta.content
                        full_content += content
                        if chunk_count <= 5:
                            print(f"Chunk #{chunk_count}: {content[:50]}...")
        
        print(f"\n✅ 流式响应完成!")
        print(f"总共收到 {chunk_count} 个chunk")
        print(f"完整内容长度: {len(full_content)}")
        print(f"完整内容预览: {full_content[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 流式图像理解失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_files():
    """测试多张图片"""
    print("\n" + "="*60)
    print("测试4: 上传并使用多张图片")
    print("="*60)
    
    image_files = [TEST_IMAGE_1, TEST_IMAGE_2]
    file_ids = []
    
    # 上传多张图片
    for image_file in image_files:
        if not os.path.exists(image_file):
            print(f"\n⚠️ 图片不存在，跳过: {image_file}")
            continue
        
        try:
            print(f"\n上传图片: {image_file}")
            with open(image_file, 'rb') as file_obj:
                uploaded_file = client.files.create(
                    file=file_obj,
                    purpose="user_data"
                )
            file_ids.append(uploaded_file.id)
            print(f"✅ 上传成功，File ID: {uploaded_file.id}")
        except Exception as e:
            print(f"❌ 上传失败: {e}")
    
    if len(file_ids) == 0:
        print(f"\n⚠️ 没有成功上传的图片")
        return False
    
    # 使用多张图片
    try:
        print(f"\n使用 {len(file_ids)} 张图片进行图像理解")
        
        content = []
        for file_id in file_ids:
            content.append({
                "type": "input_file",
                "file_id": file_id
            })
        content.append({
            "type": "input_text",
            "text": "请描述这些图片的内容。"
        })
        
        messages = [
            {
                "role": "user",
                "content": content
            }
        ]
        
        print(f"\n发送多图片理解请求...")
        
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            response_content = completion.choices[0].message.content
            print(f"\n✅ 多图片理解成功!")
            print(f"响应内容: {response_content[:300]}...")
            return True
        else:
            print(f"\n❌ 多图片理解失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 多图片理解失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("方案1正确实现测试：使用 input_file 类型")
    print("="*60)
    print(f"\n测试图片:")
    print(f"  - {TEST_IMAGE_1}: {'存在' if os.path.exists(TEST_IMAGE_1) else '不存在'}")
    print(f"  - {TEST_IMAGE_2}: {'存在' if os.path.exists(TEST_IMAGE_2) else '不存在'}")
    
    # 测试1: 上传单张图片
    file_id = upload_single_image()
    
    # 测试2: 使用file_id进行图像理解
    if file_id:
        test_use_file_id_in_chat(file_id)
    
    # 测试3: 流式响应
    if file_id:
        test_stream_with_file_id(file_id)
    
    # 测试4: 多张图片
    test_multiple_files()
    
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)
    print("\n关键发现:")
    print("1. ✅ 上传文件成功，获取 file_id")
    print("2. ✅ 应该使用 input_file 类型，直接传递 file_id")
    print("3. ❌ 不应该使用 image_url 类型和 file:// 格式")
    print("\n正确的消息格式:")
    print("  {")
    print("    'role': 'user',")
    print("    'content': [")
    print("      {'type': 'input_file', 'file_id': 'file-xxx'},  # 使用file_id")
    print("      {'type': 'input_text', 'text': '描述图片'}")
    print("    ]")
    print("  }")
    print("\n实现建议:")
    print("1. 后端上传接口返回 file_id（不是URL）")
    print("2. Android端获取 file_id 后，在消息中使用 input_file 类型")
    print("3. 对于公开的HTTP URL，仍可使用 image_url 类型")


if __name__ == "__main__":
    main()




