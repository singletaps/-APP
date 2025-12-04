#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Base64编码图片的图像理解功能
验证流程：
1. 读取图片文件
2. 转换为Base64编码
3. 构造多模态消息（使用data:image/png;base64,{base64}格式）
4. 调用Chat API进行图像理解
5. 测试流式响应
"""

import sys
import os
import base64
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.ai.client import client

# 测试图片路径
TEST_IMAGE_1 = "test_p1.png"
TEST_IMAGE_2 = "test_p2.png"


def image_to_base64(image_path: str) -> str:
    """
    将图片文件转换为Base64编码字符串
    
    Args:
        image_path: 图片文件路径
    
    Returns:
        Base64编码字符串（不包含data:image前缀）
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    
    with open(image_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    return image_base64


def get_image_mime_type(image_path: str) -> str:
    """
    根据文件扩展名获取MIME类型
    
    Args:
        image_path: 图片文件路径
    
    Returns:
        MIME类型字符串
    """
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    return mime_types.get(ext, 'image/png')


def build_base64_url(image_path: str) -> str:
    """
    构建Base64格式的图片URL
    
    Args:
        image_path: 图片文件路径
    
    Returns:
        data:image/png;base64,{base64_string} 格式的URL
    """
    base64_str = image_to_base64(image_path)
    mime_type = get_image_mime_type(image_path)
    return f"data:{mime_type};base64,{base64_str}"


def test_single_image_base64():
    """测试1: 单张图片Base64编码"""
    print("\n" + "="*60)
    print("测试1: 单张图片Base64编码 - 非流式响应")
    print("="*60)
    
    if not os.path.exists(TEST_IMAGE_1):
        print(f"\n❌ 测试图片不存在: {TEST_IMAGE_1}")
        return False
    
    try:
        print(f"\n步骤1: 读取并转换图片为Base64")
        print(f"图片路径: {TEST_IMAGE_1}")
        print(f"图片大小: {os.path.getsize(TEST_IMAGE_1)} bytes")
        
        # 转换为Base64
        base64_url = build_base64_url(TEST_IMAGE_1)
        base64_str = image_to_base64(TEST_IMAGE_1)
        
        print(f"✅ Base64编码成功")
        print(f"Base64字符串长度: {len(base64_str)}")
        print(f"Base64 URL长度: {len(base64_url)}")
        print(f"Base64 URL预览: {base64_url[:100]}...")
        
        print(f"\n步骤2: 构造多模态消息")
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
                            "url": base64_url
                        }
                    },
                    {
                        "type": "text",
                        "text": "请描述这张图片的内容。"
                    }
                ]
            }
        ]
        
        print(f"消息格式: {messages}")
        
        print(f"\n步骤3: 发送图像理解请求...")
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
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_single_image_base64_stream():
    """测试2: 单张图片Base64编码 - 流式响应"""
    print("\n" + "="*60)
    print("测试2: 单张图片Base64编码 - 流式响应")
    print("="*60)
    
    if not os.path.exists(TEST_IMAGE_1):
        print(f"\n❌ 测试图片不存在: {TEST_IMAGE_1}")
        return False
    
    try:
        print(f"\n步骤1: 转换为Base64")
        base64_url = build_base64_url(TEST_IMAGE_1)
        print(f"✅ Base64编码成功，URL长度: {len(base64_url)}")
        
        print(f"\n步骤2: 构造多模态消息")
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
                            "url": base64_url
                        }
                    },
                    {
                        "type": "text",
                        "text": "请简要描述这张图片。"
                    }
                ]
            }
        ]
        
        print(f"\n步骤3: 发送流式图像理解请求...")
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
        print(f"\n❌ 流式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_images_base64():
    """测试3: 多张图片Base64编码"""
    print("\n" + "="*60)
    print("测试3: 多张图片Base64编码")
    print("="*60)
    
    image_files = [TEST_IMAGE_1, TEST_IMAGE_2]
    base64_urls = []
    
    # 转换所有图片为Base64
    for image_file in image_files:
        if not os.path.exists(image_file):
            print(f"\n⚠️ 图片不存在，跳过: {image_file}")
            continue
        
        try:
            print(f"\n转换图片: {image_file}")
            base64_url = build_base64_url(image_file)
            base64_urls.append(base64_url)
            print(f"✅ 转换成功，URL长度: {len(base64_url)}")
        except Exception as e:
            print(f"❌ 转换失败: {e}")
    
    if len(base64_urls) == 0:
        print(f"\n⚠️ 没有成功转换的图片")
        return False
    
    try:
        print(f"\n使用 {len(base64_urls)} 张图片进行图像理解")
        
        # 构造多模态消息
        content = []
        for base64_url in base64_urls:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": base64_url
                }
            })
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


def test_base64_with_thinking():
    """测试4: Base64图片 + 深度思考"""
    print("\n" + "="*60)
    print("测试4: Base64图片 + 深度思考")
    print("="*60)
    
    if not os.path.exists(TEST_IMAGE_1):
        print(f"\n❌ 测试图片不存在: {TEST_IMAGE_1}")
        return False
    
    try:
        print(f"\n步骤1: 转换为Base64")
        base64_url = build_base64_url(TEST_IMAGE_1)
        print(f"✅ Base64编码成功")
        
        print(f"\n步骤2: 构造多模态消息（启用深度思考）")
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
                            "url": base64_url
                        }
                    },
                    {
                        "type": "text",
                        "text": "请详细分析这张图片的内容。"
                    }
                ]
            }
        ]
        
        print(f"\n步骤3: 发送流式请求（启用深度思考）...")
        stream = client.chat.completions.create(
            model="doubao-seed-1-6-251015",
            messages=messages,
            thinking={"type": "enabled"},  # 启用深度思考
            max_tokens=5000,
            temperature=0.3,
            stream=True,
        )
        
        print(f"\n✅ 流式请求成功!")
        print(f"开始接收流式响应（包含深度思考）...\n")
        
        chunk_count = 0
        full_content = ""
        reasoning_content = ""
        
        for chunk in stream:
            chunk_count += 1
            
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                
                if hasattr(choice, 'delta'):
                    delta = choice.delta
                    
                    # 检查深度思考内容
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reasoning = str(delta.reasoning_content)
                        reasoning_content += reasoning
                        if chunk_count <= 3:
                            print(f"Chunk #{chunk_count} [思考]: {reasoning[:50]}...")
                    
                    # 检查正常内容
                    if hasattr(delta, 'content') and delta.content:
                        content = delta.content
                        full_content += content
                        if chunk_count <= 5:
                            print(f"Chunk #{chunk_count} [内容]: {content[:50]}...")
        
        print(f"\n✅ 流式响应完成!")
        print(f"总共收到 {chunk_count} 个chunk")
        print(f"深度思考内容长度: {len(reasoning_content)}")
        print(f"正常内容长度: {len(full_content)}")
        if reasoning_content:
            print(f"深度思考预览: {reasoning_content[:200]}...")
        if full_content:
            print(f"正常内容预览: {full_content[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_base64_size_limit():
    """测试5: Base64大小限制测试"""
    print("\n" + "="*60)
    print("测试5: Base64大小限制测试")
    print("="*60)
    
    if not os.path.exists(TEST_IMAGE_1):
        print(f"\n❌ 测试图片不存在: {TEST_IMAGE_1}")
        return False
    
    try:
        # 获取图片大小
        image_size = os.path.getsize(TEST_IMAGE_1)
        base64_str = image_to_base64(TEST_IMAGE_1)
        base64_size = len(base64_str)
        base64_url = build_base64_url(TEST_IMAGE_1)
        url_size = len(base64_url)
        
        print(f"\n图片文件大小: {image_size} bytes ({image_size / 1024:.2f} KB)")
        print(f"Base64字符串大小: {base64_size} bytes ({base64_size / 1024:.2f} KB)")
        print(f"Base64 URL大小: {url_size} bytes ({url_size / 1024:.2f} KB)")
        print(f"大小增加比例: {(base64_size / image_size - 1) * 100:.1f}%")
        
        # 估算消息总大小
        estimated_message_size = url_size + 500  # 加上其他字段
        print(f"\n估算消息总大小: {estimated_message_size / 1024:.2f} KB")
        
        if estimated_message_size > 10 * 1024 * 1024:  # 10MB
            print(f"⚠️ 警告: 消息大小超过10MB，可能影响性能")
        elif estimated_message_size > 5 * 1024 * 1024:  # 5MB
            print(f"⚠️ 注意: 消息大小超过5MB，建议压缩图片")
        else:
            print(f"✅ 消息大小在合理范围内")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("Base64图片编码测试")
    print("="*60)
    print(f"\n测试图片:")
    print(f"  - {TEST_IMAGE_1}: {'存在' if os.path.exists(TEST_IMAGE_1) else '不存在'}")
    print(f"  - {TEST_IMAGE_2}: {'存在' if os.path.exists(TEST_IMAGE_2) else '不存在'}")
    
    results = {}
    
    # 运行所有测试
    results['单图片非流式'] = test_single_image_base64()
    results['单图片流式'] = test_single_image_base64_stream()
    results['多图片'] = test_multiple_images_base64()
    results['深度思考'] = test_base64_with_thinking()
    results['大小限制'] = test_base64_size_limit()
    
    # 总结
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)
    print("\n测试结果总结:")
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    print(f"\n总计: {success_count}/{total_count} 测试通过")
    
    if success_count == total_count:
        print("\n✅ 所有测试通过！Base64方案可行")
        print("\n实现建议:")
        print("1. Android端: 将图片转换为Base64字符串")
        print("2. 后端: 接收Base64字符串，构造 data:image/png;base64,{base64} 格式")
        print("3. 消息格式: 使用 image_url 类型，url字段为Base64 URL")
        print("4. 大小限制: 建议单张图片不超过5MB（Base64后约6.7MB）")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")


if __name__ == "__main__":
    main()



