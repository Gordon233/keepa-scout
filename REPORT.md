# 设计报告

## DB / LLM 选型

**SQLite** — 30 行数据，单用户，ETL 写一次后只读，零配置。

**GPT-5.5 via OpenRouter** — 指令跟随好，支持 structured outputs，自己工作项目有使用。

## Prompt 迭代

### v1 prompt

```
system: "You are a SQL assistant. Answer user questions with SQL."
```

**失败 case 1：** 问 "Show me ASINs with ROI over 25%"，LLM 回答 "There are some results with high ROI" — 不引用具体 ASIN 和数字。

**失败 case 2：** 问 "add a product to the database"，LLM 生成 `INSERT INTO asins VALUES (...)` — 非 SELECT 语句。

### v2 prompt（当前版本）

```
system: "You are a SQL assistant. Given the following table schema,
generate a single SQLite SELECT query that answers the user's question.

Table: asins
Columns:
  asin TEXT PRIMARY KEY
  buybox_price REAL              -- BuyBox price in USD
  computed_roi_pct REAL          -- ROI percentage
  eligible BOOLEAN
  filter_failed TEXT             -- first failed rule, NULL if eligible
  ...
Notes:
  - eligible = 1 for eligible
  - ORDER BY computed_roi_pct DESC NULLS LAST for ROI ranking

Return ONLY the raw SQL. No markdown, no explanation, no code fences."
```

三个改动：
1. 注入完整 TABLE_SCHEMA — 模型首次就能生成有效 SQL
2. 明确 "Return ONLY the raw SQL" — 消除 markdown 包裹
3. 拆成两次 LLM 调用：第一次生成 SQL，第二次传入结果让 LLM 总结并"引用具体 ASIN 和数字" — 回答从笼统变为有数据支撑

## AI 工具披露

使用 Claude Code（Opus 4.6）进行架构设计、规划和代码生成。无手动写,修改过任何代码。

## 如果有更多时间

- 覆盖所有基本使用情况的自动化测试：mock LLM 端到端测试 /ask 的 6 种问题类型 + /chat 的 4 个场景（筛选累积、代词解析、主题切换、偏好持久化），确保 prompt 改动不会引入回归
- Prompt 缓存降低 LLM 成本
- Keepa 响应缓存加速容器重启
- GitHub Actions CI 管道
- /ask 也改用 structured outputs
