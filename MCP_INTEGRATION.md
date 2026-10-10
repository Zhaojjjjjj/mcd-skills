# MCP 接入说明 · MCP Integration

本仓库四个 Skill 全部基于 **麦当劳中国 MCP 服务**（`M-China/mcd-mcp-server`），
遵循 Model Context Protocol 标准，面向中国大陆地区使用。

- 开放平台官网：<https://open.mcd.cn/mcp>
- 服务地址：`https://mcp.mcd.cn`（Streamable HTTP）
- 鉴权：请求头 `Authorization: Bearer <YOUR_MCP_TOKEN>`

## 申请 MCP Token

1. 打开 <https://open.mcd.cn/mcp>，点击右上角，手机号验证登录；
2. 点击右上角→申请 MCP Token，同意服务协议后一键复制；
3. 妥善保管 Token，不要提交到公开仓库（本仓库 `.gitignore` 已覆盖 `.env`）。

## MCP Client 配置示例

```json
{
"mcpServers": {
"mcd-mcp": {
"type": "streamablehttp",
"url": "https://mcp.mcd.cn",
"headers": {
"Authorization": "Bearer <YOUR_MCP_TOKEN>"
}
}
}
}
```

## 注意事项

- 每个 Token 每分钟最多 600 次请求，超限返回 429；
- Token 无效或过期返回 401，请检查请求头配置；
- 客户端需支持 Streamable HTTP（WorkBuddy / Cherry Studio / Cursor / VS Code / Trae 均支持）。

## 四个 Skill 用到的工具一览

| Skill | 使用的 MCP 工具 |
|---|---|
| mcd-points-guardian | `query-my-account`、`mall-points-products`、`mall-product-detail`、`mall-create-order`、`available-coupons`、`auto-bind-coupons`、`query-my-coupons`、`now-time-info` |
| mcd-fitmeal | `list-nutrition-foods`、`query-meals`、`query-meal-detail`、`calculate-price`、`create-order`、`now-time-info` |
| mcd-party-buddy | `query-party-city`、`query-party-store`、`query-partystore-date`、`query-partystore-session`、`party-order-create`、`query-meal-assistance`、`query-meals`、`calculate-price`、`create-order`、`now-time-info` |
| mcd-lottery-ev | `query-lottery-info`、`draw-lottery`、`query-my-prizes`、`query-my-account`、`now-time-info` |

以上均为麦当劳官方文档中的真实工具，未虚构任何接口。
使用麦当劳 MCP 服务须遵守麦当劳中国《使用条款》及相关服务规则。
