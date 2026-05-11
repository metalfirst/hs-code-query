import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pybreaker import CircuitBreaker, CircuitBreakerError

# ------------------ 日志配置 ------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hs-api")

# ------------------ 配置 ------------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "hs_data.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY")  # 阿里云百炼 Key
BAILIAN_MODEL = "qwen-vl-plus"                 # 视觉模型
CACHE_TTL = 86400  # 24小时

# ------------------ 熔断器 ------------------
# 用于阿里云百炼 API 调用
circuit_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="bailian"
)

# ------------------ 数据模型 ------------------
class SearchRequest(BaseModel):
    description: str
    material: str

class ImageAnalysisRequest(BaseModel):
    image_base64: str
    mime_type: str

class SearchResultItem(BaseModel):
    hs_code: str
    name: str
    description: Optional[str] = None
    import_tax_rate: Optional[str] = None
    general_import_tax_rate: Optional[str] = None
    vat_rate: Optional[str] = None
    export_rebate_rate: Optional[str] = None
    supervision_conditions: Optional[str] = None
    supervision_description: Optional[str] = None
    match_score: float
    match_reason: str

# ------------------ 生命周期管理 ------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化 Redis 连接
    app.state.redis = await redis.from_url(REDIS_URL, decode_responses=True)
    # 初始化 HTTP 客户端（连接池）
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("✅ Redis & HTTP client 已启动")
    yield
    # 关闭时清理
    await app.state.redis.close()
    await app.state.http_client.aclose()
    logger.info("🛑 资源已关闭")

app = FastAPI(lifespan=lifespan)

# CORS 允许前端任意域名（可改为你的前端地址）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.umtsh.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ 数据库查询（核心：去掉实时爬虫） ------------------
def get_db_connection():
    """返回 SQLite 连接，并启用 row_factory 返回字典"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def search_in_database(description: str, material: str) -> List[Dict[str, Any]]:
    """
    从本地 hs_codes 表中进行关键词匹配检索。
    注意：这里使用了简单的 LIKE 匹配，生产环境建议使用全文搜索或向量检索。
    """
    keywords = set()
    for word in (description + " " + material).split():
        if len(word) >= 2:
            keywords.add(word)
    if not keywords:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # 动态构建 WHERE 子句（避免 SQL 注入：使用参数化查询）
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(name LIKE ? OR description LIKE ? OR keywords LIKE ?)")
        like_kw = f"%{kw}%"
        params.extend([like_kw, like_kw, like_kw])

    sql = f"""
        SELECT hs_code, name, description,
               import_tax_rate, general_import_tax_rate,
               vat_rate, export_rebate_rate,
               supervision_conditions, supervision_description
        FROM hs_codes
        WHERE {' OR '.join(conditions)}
        LIMIT 50
    """
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # 计算简单匹配得分（用于排序）
    results = []
    for row in rows:
        record = dict(row)
        text_for_score = (record.get("name","") + " " + record.get("description","")).lower()
        score = 0
        matched = []
        for kw in keywords:
            if kw.lower() in text_for_score:
                score += 20
                matched.append(kw)
        if score > 0:
            record["match_score"] = min(score, 100)
            record["match_reason"] = f"匹配关键词: {', '.join(matched[:3])}"
            results.append(record)

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:10]

# ------------------ 缓存装饰器 ------------------
async def cached_search(description: str, material: str) -> Optional[List[Dict]]:
    cache_key = f"hs_search:{description}:{material}"
    redis_client = app.state.redis
    cached = await redis_client.get(cache_key)
    if cached:
        logger.info(f"缓存命中: {cache_key}")
        return json.loads(cached)
    # 查数据库（同步方法需在线程池中执行）
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_in_database, description, material)
    if results:
        await redis_client.setex(cache_key, CACHE_TTL, json.dumps(results, ensure_ascii=False))
    return results

# ------------------ API 接口 ------------------
@app.post("/api/search")
async def search(request: SearchRequest):
    """根据描述和材质查询 HS 编码（已去除实时爬虫）"""
    start = time.time()
    results = await cached_search(request.description, request.material)
    elapsed = (time.time() - start) * 1000
    logger.info(f"查询耗时 {elapsed:.2f}ms, 结果数: {len(results) if results else 0}")

    if not results:
        return {"status": "success", "results": []}

    # 转换为 Pydantic 模型格式
    return {
        "status": "success",
        "results": [
            {
                "hs_code": r["hs_code"],
                "name": r["name"],
                "description": r.get("description"),
                "import_tax_rate": r.get("import_tax_rate"),
                "general_import_tax_rate": r.get("general_import_tax_rate"),
                "vat_rate": r.get("vat_rate"),
                "export_rebate_rate": r.get("export_rebate_rate"),
                "supervision_conditions": r.get("supervision_conditions"),
                "supervision_description": r.get("supervision_description"),
                "match_score": r["match_score"],
                "match_reason": r["match_reason"],
            }
            for r in results
        ]
    }

# ------------------ 图片分析（保留原有功能，增加熔断 + 异步） ------------------
@app.post("/api/analyze_image")
async def analyze_image(request: ImageAnalysisRequest):
    """使用阿里云百炼视觉模型识别图片中的物体和材质（带熔断）"""
    if not BAILIAN_API_KEY:
        raise HTTPException(status_code=500, detail="BAILIAN_API_KEY 未配置")

    # 构造阿里云百炼请求
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    headers = {
        "Authorization": f"Bearer {BAILIAN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": BAILIAN_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{request.mime_type};base64,{request.image_base64}"},
                        {"text": "请识别这张图片中的所有物体名称（中文）和可能的材质（如金属、塑料、木材等）。返回 JSON 格式，例如 {\"objects\":[{\"name\":\"椅子\",\"confidence\":0.95}], \"materials\":[{\"name\":\"木材\",\"confidence\":0.9}], \"raw_description\":\"一把木制椅子\"}"}
                    ]
                }
            ]
        },
        "parameters": {"result_format": "message"}
    }

    try:
        # 使用熔断器保护的异步请求
        response = await circuit_breaker.call(
            app.state.http_client.post, url, headers=headers, json=data
        )
        response.raise_for_status()
        result = response.json()
        # 解析百炼返回的文本（假设模型按约定返回 JSON）
        output_text = result["output"]["choices"][0]["message"]["content"][0]["text"]
        # 尝试提取 JSON
        import re
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = {"raw_description": output_text, "objects": [], "materials": []}
        return {"success": True, "analysis": analysis}
    except CircuitBreakerError:
        logger.error("阿里云百炼 API 熔断触发")
        raise HTTPException(status_code=503, detail="AI 服务暂时不可用（熔断）")
    except Exception as e:
        logger.exception("图片分析失败")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------ 健康检查 ------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))