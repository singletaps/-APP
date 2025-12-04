#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Chat API 是否支持 image_file 类型（使用 file_id）
根据搜索结果，可能有 image_file 类型可以使用 file_id
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.ai.client import client

TEST_IMAGE_1 = "test_p1.png"


def test_image_file_type():
    """测试 image_file 类型"""
    print("\n" + "="*60)
    print("测试 Chat API 是否支持 image_file 类型")
    print("="*60)
    
    if not os.path.exists(TEST_IMAGE_1):
        print(f"\n❌ 测试图片不存在: {TEST_IMAGE_1}")
        return
    
    try:
        # 1. 上传图片
        print(f"\n步骤1: 上传图片")
        with open(TEST_IMAGE_1, 'rb') as file_obj:
            uploaded_file = client.files.create(
                file=file_obj,
                purpose="user_data"
            )
        
        file_id = uploaded_file.id
        print(f"✅ 上传成功，File ID: {file_id}")
        
        # 2. 测试方式1: image_file 类型
        print(f"\n步骤2: 测试 image_file 类型")
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_file",
                        "image_file": {
                            "file_id": file_id
                        }
                    },
                    {
                        "type": "text",
                        "text": "请描述这张图片。"
                    }
                ]
            }
        ]
        
        print(f"消息格式: {messages}")
        
        try:
            completion = client.chat.completions.create(
                model="doubao-seed-1-6-251015",
                messages=messages,
                thinking={"type": "disabled"},
                max_tokens=5000,
                temperature=0.3,
            )
            
            if hasattr(completion, 'choices') and len(completion.choices) > 0:
                content = completion.choices[0].message.content
                print(f"\n✅ image_file 类型支持!")
                print(f"响应内容: {content[:300]}...")
                return True
        except Exception as e:
            print(f"❌ image_file 类型不支持: {e}")
        
        # 3. 测试方式2: image_url 使用 base64
        print(f"\n步骤3: 测试 image_url 使用 base64 编码")
        import base64
        
        with open(TEST_IMAGE_1, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # 根据文档，base64格式应该是: data:image/png;base64,{base64_string}
        base64_url = f"data:image/png;base64,{image_base64}"
        
        messages = [
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
                        "text": "请描述这张图片。"
                    }
                ]
            }
        ]
        
        print(f"Base64长度: {len(image_base64)}")
        print(f"发送base64图像理解请求...")
        
        try:
            completion = client.chat.completions.create(
                model="doubao-seed-1-6-251015",
                messages=messages,
                thinking={"type": "disabled"},
                max_tokens=5000,
                temperature=0.3,
            )
            
            if hasattr(completion, 'choices') and len(completion.choices) > 0:
                content = completion.choices[0].message.content
                print(f"\n✅ base64 方式支持!")
                print(f"响应内容: {content[:300]}...")
                return True
        except Exception as e:
            print(f"❌ base64 方式失败: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n结论:")
        print(f"1. image_file 类型: {'支持' if False else '不支持'}")
        print(f"2. base64 方式: {'支持' if False else '需要测试'}")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_image_file_type()




