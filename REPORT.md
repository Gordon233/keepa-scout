# 设计报告

## DB / LLM 选型

**SQLite** — 30 行数据，单用户，ETL 写一次后只读，零配置。

**GPT-5.5 via OpenRouter** — 指令跟随好，支持 structured outputs，自己工作项目有使用。

## Prompt 迭代（v2 → v3）

### v2 的域外检测：关键词匹配

```python
_DOMAIN_TERMS = {"roi", "asin", "buybox", "eligib", "amazon", "cost", ...}

def is_out_of_scope(question):
    return not any(term in question.lower() for term in _DOMAIN_TERMS)
```

**失败 case：** `/chat` 场景 C 第 2 轮 — 先问"Top 3 by ROI"，再问"What's the weather in NYC?"。因为会话已有上下文（last_result_asins 非空），关键词检查被跳过（否则"the second one"等代词消息会被误拦）。天气问题漏到 LLM，生成了伪造 SQL `SELECT 'Weather data is not available...' AS message`，而非客户要求的固定拒答。

### v3 修复：让 LLM 判断域外

**`/ask`** — 关键词匹配换成轻量 LLM 分类调用：

```
system: "You are a scope classifier for an Amazon ASIN arbitrage analysis tool.
Answer ONLY 'yes' or 'no'.
- 'yes' = question is about Amazon arbitrage, ASINs, products, pricing, ROI...
- 'no' = weather, cooking, sports, general knowledge...
Domain concepts like 'What is ROI?' are IN scope (yes)."
```

**`/chat`** — 在 structured output JSON schema 中加 `is_out_of_scope` 布尔字段，LLM 在同一次调用中同时判断域外 + 生成 SQL（零额外延迟）：

```json
{
  "sql": "SELECT ...",
  "active_filters_json": "{\"eligible_only\": true}",
  "is_out_of_scope": false
}
```

当 `is_out_of_scope: true` 时，返回固定拒答 `"I can only help with Amazon ASIN arbitrage analysis."`，保留全部会话状态。修复后该 case 正确拒答。

## AI 工具披露

使用 Claude Code（Opus 4.6）进行架构设计、规划和代码生成。无手动写,修改过任何代码。

## 如果有更多时间

- 覆盖所有基本使用情况的自动化测试：mock LLM 端到端测试 /ask 的 6 种问题类型 + /chat 的 4 个场景（筛选累积、代词解析、主题切换、偏好持久化），确保 prompt 改动不会引入回归
- Prompt 缓存降低 LLM 成本
- Keepa 响应缓存加速容器重启
- GitHub Actions CI 管道
- /ask 也改用 structured outputs
