#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开发环境数据库迁移脚本（简化版）
删除旧数据库，让 SQLAlchemy 自动创建新表结构
注意：此操作会删除所有数据，仅用于开发环境！
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from backend.app.config.settings import settings

def migrate_database():
    """执行数据库迁移（开发环境简化版）"""
    print("\n" + "="*60)
    print("开发环境数据库迁移")
    print("="*60)
    
    # 从数据库URL中提取文件路径
    db_url = settings.SQLALCHEMY_DATABASE_URL
    print(f"\n数据库URL: {db_url}")
    
    if db_url.startswith("sqlite:///"):
        # SQLite数据库
        if db_url.startswith("sqlite:////"):
            # 绝对路径：sqlite:////path/to/db
            db_path = db_url[11:]  # 去掉 "sqlite:////"
        else:
            # 相对路径：sqlite:///path/to/db
            db_path = db_url[10:]  # 去掉 "sqlite:///"
        
        print(f"数据库文件路径: {db_path}")
        
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path)
            print(f"数据库文件大小: {file_size} bytes ({file_size / 1024:.2f} KB)")
            
            # 确认删除
            print(f"\n⚠️  警告：此操作将删除数据库文件，所有数据将丢失！")
            print(f"文件路径: {db_path}")
            
            try:
                os.remove(db_path)
                print(f"\n✅ 数据库文件已删除: {db_path}")
                print(f"\n下一步：")
                print(f"1. 重启后端应用")
                print(f"2. SQLAlchemy 会自动创建新表结构（包含 images 字段）")
                return True
            except Exception as e:
                print(f"\n❌ 删除数据库文件失败: {e}")
                return False
        else:
            print(f"\n✅ 数据库文件不存在，无需删除")
            print(f"\n下一步：")
            print(f"1. 启动后端应用")
            print(f"2. SQLAlchemy 会自动创建新表结构（包含 images 字段）")
            return True
    else:
        print(f"\n⚠️  非 SQLite 数据库，请手动执行迁移")
        print(f"请参考 DATABASE_MIGRATION.md 文件")
        return False


if __name__ == "__main__":
    print("\n此脚本将删除旧数据库文件，让 SQLAlchemy 自动创建新表结构")
    print("注意：此操作会删除所有数据，仅用于开发环境！\n")
    
    response = input("确认继续？(yes/no): ")
    if response.lower() in ['yes', 'y']:
        migrate_database()
    else:
        print("\n操作已取消")



