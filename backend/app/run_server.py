#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI后端服务器启动脚本
支持局域网访问配置

使用方法:
    python run_server.py                    # 使用默认配置（localhost:8000）
    python run_server.py --host 0.0.0.0     # 允许局域网访问
    python run_server.py --host 0.0.0.0 --port 8000
"""

import argparse
import uvicorn
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='启动FastAPI后端服务器')
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='服务器绑定的主机地址 (默认: 127.0.0.1，使用 0.0.0.0 允许局域网访问)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='服务器端口 (默认: 8000)'
    )
    parser.add_argument(
        '--reload',
        action='store_true',
        help='启用自动重载（开发模式）'
    )
    
    args = parser.parse_args()
    
    # 获取项目根目录
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent
    
    print("=" * 60)
    print("FastAPI 后端服务器启动配置")
    print("=" * 60)
    print(f"主机地址: {args.host}")
    print(f"端口: {args.port}")
    print(f"自动重载: {'启用' if args.reload else '禁用'}")
    print("=" * 60)
    
    if args.host == '0.0.0.0':
        print("\n⚠️  注意：服务器已配置为允许局域网访问")
        print("   请确保防火墙允许端口", args.port, "的入站连接")
        print("\n   局域网访问地址示例：")
        print("   - http://<你的IP地址>:" + str(args.port))
        print("   - 在Android应用中配置此地址作为API服务器URL")
        print()
    
    # 启动服务器
    uvicorn.run(
        "backend.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(current_dir)] if args.reload else None,
    )

if __name__ == "__main__":
    main()


