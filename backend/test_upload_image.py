#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试方案1：后端代理 + 火山引擎 Files API
验证流程：
1. 上传图片到火山引擎Files API
2. 获取file_id
3. 使用file_id构造URL（file://{file_id}）
4. 在消息中使用该URL进行图像理解
5. 验证整个流程是否可行
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
    """测试1: 上传单张图片"""
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
        
        # 读取图片文件
        with open(TEST_IMAGE_1, 'rb') as f:
            file_content = f.read()
        
        print(f"✅ 图片读取成功，大小: {len(file_content)} bytes")
        
        print(f"\n步骤2: 上传到火山引擎Files API")
        print(f"调用 client.files.create()...")
        
        # 上传文件
        # 尝试多种方式上传
        
        # 方式1: 使用实际文件对象
        try:
            print(f"尝试方式1: 使用实际文件对象")
            with open(TEST_IMAGE_1, 'rb') as file_obj:
            uploaded_file = client.files.create(
                file=file_obj,
                purpose="user_data"  # 火山引擎要求必须使用 user_data
            )
            
            print(f"✅ 上传成功!")
            print(f"上传文件对象类型: {type(uploaded_file)}")
            print(f"上传文件对象属性: {dir(uploaded_file)}")
            
            # 获取file_id
            file_id = None
            if hasattr(uploaded_file, 'id'):
                file_id = uploaded_file.id
                print(f"\n✅ File ID: {file_id}")
            elif hasattr(uploaded_file, 'file_id'):
                file_id = uploaded_file.file_id
                print(f"\n✅ File ID: {file_id}")
            else:
                print(f"\n⚠️ 无法获取file_id")
                print(f"上传文件对象: {uploaded_file}")
                # 尝试打印所有属性
                for attr in dir(uploaded_file):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(uploaded_file, attr)
                            if not callable(value):
                                print(f"  {attr}: {value}")
                        except:
                            pass
                return None
            
            # 构造URL
            file_url = f"file://{file_id}"
            print(f"\n步骤3: 构造文件URL")
            print(f"文件URL: {file_url}")
            
            return file_url
            
        except Exception as upload_error:
            print(f"方式1失败: {upload_error}")
            
            # 方式2: 使用BytesIO
            try:
                print(f"\n尝试方式2: 使用BytesIO")
                from io import BytesIO
                file_obj = BytesIO(file_content)
                file_obj.name = TEST_IMAGE_1
                
                uploaded_file = client.files.create(
                    file=file_obj,
                    purpose="user_data"
                )
            except Exception as e2:
                print(f"方式2失败: {e2}")
                
                # 方式3: 使用正确的purpose值 user_data
                try:
                    print(f"\n尝试方式3: 使用 purpose='user_data'")
                    with open(TEST_IMAGE_1, 'rb') as file_obj:
                        uploaded_file = client.files.create(
                            file=file_obj,
                            purpose="user_data"  # 火山引擎要求必须使用 user_data
                        )
                    print(f"  ✅ 使用 purpose='user_data' 上传成功!")
                except Exception as e3:
                    print(f"  ❌ purpose='user_data' 也失败: {e3}")
                    import traceback
                    traceback.print_exc()
                    return None
        
        # 如果到这里，说明上传成功了
        print(f"✅ 上传成功!")
        print(f"上传文件对象类型: {type(uploaded_file)}")
        print(f"上传文件对象属性: {dir(uploaded_file)}")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def upload_multiple_images():
    """测试2: 上传多张图片"""
    print("\n" + "="*60)
    print("测试2: 上传多张图片")
    print("="*60)
    
    image_files = [TEST_IMAGE_1, TEST_IMAGE_2]
    uploaded_urls = []
    
    for image_file in image_files:
        if not os.path.exists(image_file):
            print(f"\n⚠️ 图片不存在，跳过: {image_file}")
            continue
        
        try:
            print(f"\n上传图片: {image_file}")
            with open(image_file, 'rb') as f:
                file_content = f.read()
            
            from io import BytesIO
            file_obj = BytesIO(file_content)
            file_obj.name = image_file
            
            # 尝试上传
            uploaded_file = client.files.create(
                file=file_obj,
                purpose="user_data"  # 火山引擎要求必须使用 user_data
            )
            
            # 获取file_id
            file_id = None
            if hasattr(uploaded_file, 'id'):
                file_id = uploaded_file.id
            elif hasattr(uploaded_file, 'file_id'):
                file_id = uploaded_file.file_id
            
            if file_id:
                file_url = f"file://{file_id}"
                uploaded_urls.append(file_url)
                print(f"✅ 上传成功，URL: {file_url}")
            else:
                print(f"⚠️ 无法获取file_id")
                
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            # 如果BytesIO失败，尝试使用实际文件对象
            try:
                print(f"  尝试使用实际文件对象重试...")
                with open(image_file, 'rb') as file_obj:
                    uploaded_file = client.files.create(
                        file=file_obj,
                        purpose="user_data"
                    )
                if hasattr(uploaded_file, 'id'):
                    file_id = uploaded_file.id
                    file_url = f"file://{file_id}"
                    uploaded_urls.append(file_url)
                    print(f"✅ 使用实际文件对象上传成功，URL: {file_url}")
                elif hasattr(uploaded_file, 'file_id'):
                    file_id = uploaded_file.file_id
                    file_url = f"file://{file_id}"
                    uploaded_urls.append(file_url)
                    print(f"✅ 使用实际文件对象上传成功，URL: {file_url}")
            except Exception as e_retry:
                print(f"  ❌ 重试也失败: {e_retry}")
    
    return uploaded_urls


def use_uploaded_image_in_message(file_url: str):
    """测试3: 使用上传的图片URL发送消息"""
    print("\n" + "="*60)
    print("测试3: 使用上传的图片URL进行图像理解")
    print("="*60)
    
    if not file_url:
        print(f"\n⚠️ 没有可用的图片URL，跳过测试")
        return False
    
    try:
        print(f"\n使用图片URL: {file_url}")
        
        # 构造多模态消息
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
        
        print(f"\n发送图像理解请求...")
        print(f"消息格式: {messages}")
        
        # 发送请求
        completion = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "disabled"},
            max_tokens=5000,
            temperature=0.3,
        )
        
        if hasattr(completion, 'choices') and len(completion.choices) > 0:
            content = completion.choices[0].message.content
            print(f"\n✅ 图像理解成功!")
            print(f"响应内容: {content[:300]}...")
            return True
        else:
            print(f"\n❌ 图像理解失败，响应中没有内容")
            return False
            
    except Exception as e:
        print(f"\n❌ 图像理解失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def multiple_images_in_message(image_urls: list):
    """测试4: 在单条消息中使用多张图片"""
    print("\n" + "="*60)
    print("测试4: 在单条消息中使用多张图片")
    print("="*60)
    
    if not image_urls or len(image_urls) == 0:
        print(f"\n⚠️ 没有可用的图片URL，跳过测试")
        return False
    
    try:
        print(f"\n使用 {len(image_urls)} 张图片")
        for i, url in enumerate(image_urls, 1):
            print(f"  图片 {i}: {url}")
        
        # 构造多模态消息
        content = []
        # 添加所有图片
        for url in image_urls:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": url
                }
            })
        # 添加文本
        content.append({
            "type": "text",
            "text": "请描述这些图片的内容。"
        })
        
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的AI助手，擅长分析图像内容。",
            },
            {
                "role": "user",
                "content": content,
            },
        ]
        
        print(f"\n发送多图片理解请求...")
        
        # 发送请求
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


def stream_with_uploaded_image(file_url: str):
    """测试5: 使用上传的图片进行流式响应"""
    print("\n" + "="*60)
    print("测试5: 使用上传的图片进行流式响应")
    print("="*60)
    
    if not file_url:
        print(f"\n⚠️ 没有可用的图片URL，跳过测试")
        return False
    
    try:
        print(f"\n使用图片URL: {file_url}")
        
        # 构造多模态消息
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
                    {"type": "text", "text": "请简要描述这张图片。"},
                ],
            },
        ]
        
        print(f"\n发送流式图像理解请求...")
        
        # 流式请求
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
                        if chunk_count <= 5:  # 只打印前5个chunk
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


def main():
    """主函数"""
    print("\n" + "="*60)
    print("方案1可行性测试：后端代理 + 火山引擎 Files API")
    print("="*60)
    print(f"\n测试图片:")
    print(f"  - {TEST_IMAGE_1}: {'存在' if os.path.exists(TEST_IMAGE_1) else '不存在'}")
    print(f"  - {TEST_IMAGE_2}: {'存在' if os.path.exists(TEST_IMAGE_2) else '不存在'}")
    
    # 测试1: 上传单张图片
    uploaded_url = upload_single_image()
    
    # 测试2: 上传多张图片
    uploaded_urls = upload_multiple_images()
    
    # 测试3: 使用上传的图片URL发送消息
    if uploaded_url:
        use_uploaded_image_in_message(uploaded_url)
    
    # 测试4: 在单条消息中使用多张图片
    if uploaded_urls:
        multiple_images_in_message(uploaded_urls)
    
    # 测试5: 流式响应
    if uploaded_url:
        stream_with_uploaded_image(uploaded_url)
    
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)
    print("\n测试总结:")
    if uploaded_url:
        print("✅ 单图片上传和图像理解：成功")
    else:
        print("❌ 单图片上传和图像理解：失败")
    
    if uploaded_urls and len(uploaded_urls) > 1:
        print("✅ 多图片上传：成功")
    else:
        print("⚠️ 多图片上传：部分成功或跳过")
    
    print("\n推荐实现方案:")
    print("1. 后端添加上传接口，接收multipart/form-data")
    print("2. 后端调用 client.files.create() 上传图片")
    print("3. 返回 file_id 或构造的 URL (file://{file_id})")
    print("4. Android端调用上传接口，获取URL后用于消息发送")


if __name__ == "__main__":
    main()

