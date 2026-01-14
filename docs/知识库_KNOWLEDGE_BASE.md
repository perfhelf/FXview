# 鲲侯FXView 开发知识库 (Knowledge Base)

> 创建日期: 2026-01-13
> 记录人: Antigravity Assistant

本文档记录了 FXview 项目的关键开发经验、架构决策及故障排查总结，特别是关于“一浪引擎”实施过程中的宝贵教训。

## 1. 系统架构 (Architecture)

- **Engine (后端)**: Python (`godview.py`)
  - 负责核心指标计算 (RSI, MACD, ADX, SMA Slopes)。
  - 运行环境: GitHub Actions (Ubuntu)。
  - 定时任务: Cron Job (每小时一次)。
- **Database (数据层)**: Supabase (PostgreSQL)
  - 表: `godview_snapshot`
  - 存储格式: JSONB (`data` 列)
- **Frontend (前端)**: Next.js 14+ (App Router)
  - 托管: Vercel
  - 渲染: Client Components (`use client` + `useEffect` fetch)

## 2. 一浪引擎 (Wave 1 Engine) 实施要点

### 2.1 核心逻辑
一浪引擎旨在捕捉趋势反转的早期信号。
- **算法复刻**: 完美复刻了 PineScript 的逻辑，包括六线 RSI 计数、MACD 斜率计数和 ADX 位置/斜率矩阵。
- **聚合逻辑**: 实现 `calc_fw_aggregation` 指挥官逻辑，综合日线和周线信号得出最终状态 (1=多, -1=空, 2=双向, 0=待定)。

### 2.2 数据结构 (Payload)
为了支持前端展示，我们在 JSON Payload 中新增了结构：
```json
{
  "fw_status": 1, // 最终状态
  "fw_signals": {
    "rsi": {"d": true, "w": false}, // 信号灯状态
    "macd": {"d": false, "w": false},
    "adx": {"d": true, "w": true}
  }
}
```

### 2.3 UI 展示策略
- **双行布局**: 表格视图采用 `rowSpan` 设计，每个货币占据两行。
  - Row 1: 趋势跟随 (Trend Following)
  - Row 2: 一浪反转 (Wave 1 Reversal)
- **双信号网格**: 信息卡视图 (Card View) 分区展示两套引擎的详细信号。

## 3. 故障排查与核心教训 (Troubleshooting & Lessons)

### 3.1 时间戳陷阱 (The Timestamp Trap) 🚨 **CRITICAL**
**现象**: GitHub Actions 运行成功，数据已通过 Upsert 写入，但前端显示的 "Last Update" 依然滞后（落后 8 小时或完全未更新）。
**原因**:
1. **Supabase 机制**: `updated_at default now()` 仅在 `INSERT` 时触发。`upsert` 更新现有行时，**不会**自动刷新此字段。
2. **时区解析**: Python `datetime.utcnow().isoformat()` 生成的时间字符串 (e.g., `T15:00:00`) 不带时区后缀。JS `new Date()` 解析时会将其视为**本地时间** (北京时间 15:00)，而非 UTC 15:00，导致显示时间比实际晚 8 小时。

**解决方案**:
1. **显式更新**: 在 SQL `upsert` 中显式传入 `updated_at`。
2. **Payload 优先**: 在 JSON 数据中新增 `last_update` 字段，并强制加上 **"Z"** 后缀 (e.g., `...T15:00:00Z`)，明确告知前端这是 UTC 时间。
3. **前端逻辑**: 优先读取 `row.data.last_update`，确保绝对准确。

### 3.2 Vercel 与 GitHub 的连接
**现象**: GitHub 推送代码后，Vercel 没有触发部署。
**解决**: 检查 Vercel 项目设置 -> Git。有时授权会失效，点击 "Disconnect" 然后重新 "Connect" 即可恢复。

## 4. 运维策略 (CI/CD)

### 4.1 更新频率
- **频率**: 每小时 (1H)。
- **理由**: 外汇市场的 RSI 和斜率变化是分钟/小时级别的。1H 更新是捕捉日内反转 (Wave 1) 和趋势加速 (Trend Slope) 的底线。24H 更新会使工具失去实战价值，退化为历史报告。

### 4.2 GitHub Actions 额度
- 定时任务不会污染代码仓库。
- 运行记录保留 90 天并自动清理。
- 私有仓库每小时运行一次仅消耗约 720 分钟/月，远低于免费额度 (2000 分钟)。

## 5. SEO 配置
- **Title**: `鲲侯FXView · 全球汇率上帝视角`
- **Meta**: 包含核心关键词（趋势跟随、一浪反转、流动性猎杀）。
- **Open Graph**: 优化社交分享展示。
