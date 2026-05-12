# Keepa Scout

## 启动

```bash
cp env.example .env  # 填入 API key
docker compose up --build
```

容器启动时自动运行 ETL（拉取 Keepa 数据 → 写入 SQLite），然后启动服务，地址 `http://localhost:8000`。

## 端点 curl 示例

```bash
# 健康检查
curl http://localhost:8000/health

# UPC 查询
curl "http://localhost:8000/upc?upc=070537500052"

# 单个 ASIN 合格性
curl http://localhost:8000/eligibility/B00HEON30Y

# 批量合格性
curl -X POST http://localhost:8000/eligibility/batch \
  -H "Content-Type: application/json" \
  -d '{"asins": ["B00HEON30Y", "B010MU00UM"]}'

# 自然语言查询
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many ASINs are eligible?"}'

# 多轮对话
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "Show me eligible ASINs"}'
```

## /ask 示例问题

```
"How many ASINs are eligible?"
"Show me ASINs with ROI over 25%"
"Top 5 ROI ASINs that Amazon doesn't dominate"
"Why is B006JVZXJM not eligible?"
"Which eligible ASIN is the best opportunity?"
"What is ROI?"
```

## /chat 多轮对话示例

```bash
# 第 1 轮：列出合格 ASIN
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "Show me eligible ASINs"}'

# 第 2 轮：缩小到 ROI > 25%（保留 eligible 筛选）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "Now only those with ROI over 25%"}'

# 第 3 轮：用序数引用
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "Tell me about the second one"}'
```

## 演示脚本

启动服务后，运行 demo 脚本一键演示所有端点：

```bash
bash scripts/demo.sh
```

## Postman 测试集

导入 `keepa-scout.postman_collection.json` 到 Postman，包含 33 个请求覆盖所有端点和 4 个 /chat 场景。

