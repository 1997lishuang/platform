# 外部模型/网络询价数据源

## 是否可以用豆包 API 或 CloseAI

可以。豆包/火山方舟、CloseAI、本地部署大模型以及其他 OpenAI-compatible API 都可以作为“市场参考价数据源”，用于补充企业价格库不足的场景。

但建议遵守这条边界：

```text
模型输出 = 待复核参考价
正式综合单价 = 规则审批通过后的价格
```

也就是说，模型查询结果不直接参与自动取价，必须先进入 `market_price_quote`，再由造价员/审核员确认后，转成价格规则或组成价。

## 当前实现

新增：

- `market_price_quote`：市场参考价表
- `DoubaoMarketQuoteProvider`：豆包/火山方舟 Chat Completions 调用器
- `CloseAIMarketQuoteProvider`：CloseAI OpenAI-compatible 调用器
- `LocalMarketQuoteProvider`：本地 OpenAI-compatible 大模型调用器
- `OpenAICompatibleMarketQuoteProvider`：通用 OpenAI-compatible 适配基类
- `MarketQuoteRepository`：市场价结果入库
- `POST /api/market-quotes/estimate`：发起模型询价
- `GET /api/market-quotes`：查看最近参考价
- 前端 `市场询价` 页面

## 环境变量

```powershell
$env:ARK_API_KEY="your-api-key"
$env:ARK_MODEL="your-doubao-model-id"
```

也支持：

```powershell
$env:DOUBAO_API_KEY="your-api-key"
$env:DOUBAO_MODEL="your-model-id"
$env:DOUBAO_CHAT_ENDPOINT="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
```

CloseAI：

```powershell
$env:MARKET_QUOTE_PROVIDER="closeai"
$env:CLOSEAI_API_KEY="your-api-key"
$env:CLOSEAI_MODEL="gpt-4o-mini"
$env:CLOSEAI_BASE_URL="https://api.openai-proxy.org/v1"
```

API 也可以通过查询参数临时选择：

```http
POST /api/market-quotes/estimate?provider=closeai
```

CloseAI 是 OpenAI-compatible 形态，`CLOSEAI_BASE_URL` 应包含 `/v1`，系统会自动拼接 `/chat/completions`。

本地大模型：

```powershell
$env:MARKET_QUOTE_PROVIDER="local"
$env:LOCAL_LLM_BASE_URL="http://127.0.0.1:8001/v1"
$env:LOCAL_LLM_MODEL="qwen2.5"
$env:LOCAL_LLM_API_KEY="local"
```

如果你用 Ollama 的 OpenAI-compatible 接口，通常可以配置为：

```powershell
$env:LOCAL_LLM_BASE_URL="http://127.0.0.1:11434/v1"
$env:LOCAL_LLM_MODEL="qwen2.5"
```

API 临时选择：

```http
POST /api/market-quotes/estimate?provider=local
```

## 输出要求

模型必须返回结构化 JSON：

```json
{
  "price_min": 82,
  "price_max": 88,
  "recommended_price": 85,
  "tax_included": true,
  "confidence": 0.62,
  "source_urls": ["https://example.com"],
  "assumptions": {
    "region": "华南",
    "unit": "元/m"
  }
}
```

## 风险控制

- 必须保存原始响应 `raw_response`。
- 必须保存来源 URL 和关键假设。
- 低置信度结果只能作为线索，不能自动发布。
- 进入正式价格库前必须走规则审批流。
- 如果用于投标或结算，应优先使用企业历史价、地区信息价、供应商报价和合同价。

## 后续增强

1. 增加“从市场参考价一键生成规则草稿”。
2. 增加来源 URL 可访问性校验和截图留存。
3. 增加多模型交叉询价，取中位数或置信加权价。
4. 增加地区信息价/供应商报价 API 作为更权威来源。
5. 增加模型输出反作弊：价格异常、无来源、区间过宽自动拦截。
