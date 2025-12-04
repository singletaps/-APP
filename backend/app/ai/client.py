# backend/app/ai/client.py
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key="d9916506-93c8-4815-bc41-fc1e6ec96204",
)

