# 鲲侯FXView 项目知识库 (Knowledge Base)

> **创建日期**: 2026-01-14
> **记录人**: Antigravity Assistant
> **项目地址**: https://fxview.xuebz.com

本文档记录了 FXview 项目的完整开发经验、架构决策、故障排查及所有踩过的坑。

---

## 目录
1. [系统架构](#1-系统架构)
2. [一浪引擎实施](#2-一浪引擎-wave-1-engine)
3. [添加新货币踩坑实录](#3-添加新货币踩坑实录-cnhmyr)
4. [时间戳陷阱](#4-时间戳陷阱-critical)
5. [Vercel 部署问题](#5-vercel-部署问题)
6. [运维策略](#6-运维策略)
7. [SEO 配置](#7-seo-配置)

---

## 1. 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Yahoo Finance  │───>│   godview.py    │───>│    Supabase     │
│   (数据源)      │    │ (GitHub Actions)│    │   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                       ┌─────────────────┐             │
                       │    Vercel       │<────────────┘
                       │   (Next.js)     │───> 用户浏览器
                       └─────────────────┘
```

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| **后端引擎** | Python + Pandas | 指标计算 (RSI, MACD, ADX, EMA) |
| **定时任务** | GitHub Actions | 每小时运行一次 Cron Job |
| **数据库** | Supabase (PostgreSQL) | JSONB 存储快照数据 |
| **前端** | Next.js 14+ (App Router) | Client Components 渲染 |
| **部署** | Vercel | 自动部署（需要正确配置 Root Directory） |

---

## 2. 一浪引擎 (Wave 1 Engine)

### 2.1 核心功能
捕捉趋势反转的早期信号，复刻 PineScript 原始逻辑。

### 2.2 新增函数
| 函数名 | 用途 |
|--------|------|
| `calc_rsi_fw_day` | 日线 RSI 一浪 (6 SMA, 阈值 ≥2) |
| `calc_rsi_fw_week` | 周线 RSI 一浪 (3 SMA, 阈值 ≥1) |
| `calc_macd_fw` | MACD 一浪 (DIF/DEA 斜率计数) |
| `calc_adx_fw` | ADX 一浪 (位置/斜率矩阵) |
| `calc_fw_aggregation` | 指挥官逻辑，聚合最终状态 |

### 2.3 UI 展示
- **表格视图**: 双行布局 (Row 1: 趋势跟随, Row 2: 一浪反转)
- **卡片视图**: 双信号网格 + 双状态徽章

---

## 3. 添加新货币踩坑实录 (CNH/MYR)

### 3.1 🚨 坑1: Vercel 自动部署失败
**现象**:
```
Error: Couldn't find any `pages` or `app` directory.
Please create one under the project root
```

**原因**:
- 代码通过 `git push` 触发了 GitHub Webhook 自动部署
- Vercel 从**仓库根目录**开始构建，而 Next.js 项目在 `frontend/` 子目录
- 之前手动用 `vercel --prod` 部署是在 `frontend/` 目录内，所以没问题

**解决方案**:
```bash
# 永远在 frontend 目录内执行
cd /path/to/FXview/frontend
vercel --prod --yes
```

**教训**:
- Vercel Dashboard 的 **Root Directory** 设置不一定存在（取决于项目配置方式）
- 如果项目是通过 `vercel link` 在子目录内绑定的，就只能通过 CLI 手动部署
- 或者重新在 Vercel 控制台创建项目，导入时明确指定 Root Directory

---

### 3.2 🚨 坑2: Yahoo Finance 数据不足
**现象**:
```
Processing CNH...
Not enough data for CNH
```
CNH 卡片在前端不显示，但 MYR 正常。

**原因**:
- `godview.py` 要求至少 **200 天历史数据** (用于 EMA200 计算)
- Yahoo Finance 的 `USDCNH=X` (离岸人民币) 返回的数据**少于 200 天**
- MYR 的 `USDMYR=X` 数据充足，所以正常

**解决方案**:
使用 `CNY=X` (在岸人民币) 替代 `USDCNH=X` (离岸人民币)：
```python
# engine/godview.py
SYMBOLS_MAP = {
    ...
    'CNH': 'CNY=X',  # 改用在岸人民币，数据更长
    ...
}
```

**注意**: TradingView 公式仍然使用 `OANDA:USDCNH`，因为 TV 上只需要实时数据，离岸数据可用。

---

### 3.3 🚨 坑3: 前端显示但数据为空
**现象**: 卡片显示货币名称，但没有信号数据。

**原因**:
- 前端代码 (`page.tsx`) 已更新，但后端 (`godview.py`) 没有
- 或者后端代码推送了，但 **GitHub Actions 还没运行**

**解决方案**:
```bash
# 手动触发 GitHub Actions
gh workflow run update_godview.yml

# 等待 1-2 分钟后刷新网站
```

---

## 4. 时间戳陷阱 🚨 CRITICAL

### 4.1 问题描述
`Last Update` 时间戳不更新，始终显示旧时间，尽管数据已刷新。

### 4.2 根本原因

**原因 1: Supabase `default now()` 机制**
```sql
updated_at timestamptz default now()
```
- `default now()` 只在 **INSERT** 时触发
- `upsert` 更新现有行时，**不会自动刷新** 此字段

**原因 2: ISO 时间字符串时区问题**
```python
datetime.utcnow().isoformat()  # 生成: "2026-01-14T15:00:00"
```
- 没有 `Z` 后缀，JavaScript `new Date()` 会将其当作**本地时间**
- 导致显示时间比实际晚 8 小时（北京时区）

### 4.3 解决方案

**后端修复** (`godview.py`):
```python
# 1. 在 payload 中添加显式时间戳（带 Z 后缀）
payload = {
    "last_update": datetime.utcnow().isoformat() + "Z",
    ...
}

# 2. upsert 时也显式更新 SQL 列
sb.table('godview_snapshot').upsert({
    'symbol': sym,
    'data': clean_data,
    'updated_at': datetime.utcnow().isoformat() + "Z"
}).execute()
```

**前端修复** (`page.tsx`):
```typescript
// 优先读取 payload 中的时间
const payloadTime = rows[0]?.data?.last_update
setLastUpdate(payloadTime || rows[0]?.updated_at)
```

---

## 5. Vercel 部署问题

### 5.1 GitHub Webhook 断连
**现象**: `git push` 后 Vercel 不自动部署。

**解决**:
1. 登录 Vercel Dashboard → Settings → Git
2. 点击 **Disconnect**
3. 重新 **Connect** GitHub 仓库

### 5.2 Root Directory 问题
见 [坑1: Vercel 自动部署失败](#31--坑1-vercel-自动部署失败)

---

## 6. 运维策略

### 6.1 更新频率
| 频率 | 推荐度 | 说明 |
|------|--------|------|
| **1 小时** | ⭐⭐⭐⭐⭐ | 当前配置，平衡成本与实时性 |
| 4 小时 | ⭐⭐⭐ | 可接受，但会错过日内反转 |
| 24 小时 | ⭐ | 不推荐，系统失去实战价值 |

**理由**: 一浪引擎 (Wave 1) 用于捕捉反转，反转信号往往在日内产生。24 小时更新会导致错过最佳入场点。

### 6.2 GitHub Actions 额度
- 运行记录保留 **90 天**，自动清理
- 私有仓库每月 **2000 分钟**，每小时运行仅消耗约 720 分钟/月
- **不会污染代码仓库**，日志独立存储

---

## 7. SEO 配置

**文件**: `frontend/app/layout.tsx`

```typescript
export const metadata: Metadata = {
  title: '鲲侯FXView · 全球汇率上帝视角',
  description: '提供全球汇率实时分析，集成趋势跟随、一浪反转、流动性猎杀三大引擎...',
  keywords: 'FXView, 鲲侯, 汇率分析, 外汇交易, 趋势跟随, 一浪反转...',
  openGraph: { ... }
}
```

---

## 8. 新增货币指数标准流程

### 8.1 三步完成（5分钟搞定）

**Step 1: 后端 `engine/godview.py`**
```python
SYMBOLS_MAP = {
    ...
    'XXX': 'USDXXX=X',  # Yahoo Finance 代码
}
```

**Step 2: 前端 `frontend/app/page.tsx`**
```typescript
// 1. 显示名称
const SYMBOL_NAMES = {
    ...
    XXX: '货币中文名',
}

// 2. TradingView 公式 (可选，用于图表跳转)
const TV_FORMULAS = {
    ...
    XXX: '1/USDXXX/基准值+...',
}
```

**Step 3: 部署**
```bash
git add . && git commit -m "feat: add XXX" && git push
gh workflow run update_godview.yml  # 触发后端数据更新
cd frontend && vercel --prod --yes  # 部署前端
```

### 8.2 检查清单

| 检查项 | 说明 |
|--------|------|
| **Yahoo 数据充足?** | 至少 200 天历史，否则改用其他代码 |
| **TradingView 代码可用?** | 在 TV 搜索框先测试公式是否能显示 |
| **等待 Actions 运行** | 前端部署后，必须等 GitHub Actions 跑完才有数据 |

---

## 9. 货币指数公式推导指南

### 9.1 TAIXI 公式原理

每个货币的**综合强弱指数** = 该货币相对于多个主要货币的汇率之和（标准化后）

```
该货币/货币A ÷ 基准值A + 该货币/货币B ÷ 基准值B + ...
```

**意义**: 消除单一货币波动的干扰，得出"该货币本身的真实强度"。

### 9.2 推导新货币公式（模板）

假设要添加 **XXX 货币**：

```
1/USDXXX/基准1 + EURUSD/USDXXX/基准2 + GBPUSD/USDXXX/基准3 + USDJPY/USDXXX/基准4 + AUDUSD/USDXXX/基准5
```

### 9.3 基准值计算方法

1. 选择一个**锚点时刻**（如今天的汇率）
2. 计算各项的当前值，这些就是基准值

**示例**: 如果 USDXXX = 5.0
- `1/USDXXX = 0.2` → 基准1 = `0.2`
- `EURUSD/USDXXX` = 1.07/5.0 = 0.214 → 基准2 = `0.214`
- 以此类推...

### 9.4 现有公式参考

公式文件: `TAIXI 指数.txt`

| 行号 | 货币 | 说明 |
|------|------|------|
| 1 | AUD | 澳元指数 |
| 2 | CAD | 加元指数 |
| 3 | CHF | 瑞郎指数 |
| 4 | JPY | 日元指数 |
| 5 | EUR | 欧元指数 |
| 6 | GBP | 英镑指数 |
| 7 | USD | 美元指数 |
| 8 | NZD | 纽元指数 |
| 9 | SGD | 新加坡元指数 |
| 10 | MXN | 墨西哥比索指数 |
| 11 | SEK | 瑞典克朗指数 |
| 12 | NOK | 挪威克朗指数 |
| 13 | CNH | 人民币指数 |
| 14 | MYR | 林吉特指数 |

---

## 10. 踩坑记录与教训

### 10.1 黄金/白银数据缺失问题 (2026-01-14)

**问题**：XAU（黄金）和 XAG（白银）在 Yahoo Finance 上的 Ticker `XAUUSD=X` 和 `XAGUSD=X` 返回空数据，导致后端崩溃。

**原因**：Yahoo Finance 这两个现货 Ticker 数据不稳定/已下架。

**解决方案**：切换到期货合约 Ticker：
```python
SYMBOLS_MAP = {
    'XAU': 'GC=F',  # 黄金期货 (原: XAUUSD=X)
    'XAG': 'SI=F',  # 白银期货 (原: XAGUSD=X)
    'XCU': 'HG=F',  # 铜期货 (本就正确)
}
```

**教训**：
- 添加新货币前，先在 Yahoo Finance 网页验证 Ticker 是否有效
- 期货合约（`=F`）通常比现货（`=X`）更稳定

---

### 10.2 后端 `apply_formula` 逻辑重复问题 (2026-01-14)

**问题**：新增货币后后端报 `KeyError`，但 `calc_synthetic_indices` 函数明明已更新。

**原因**：`godview.py` 中存在**两处**几乎相同的公式计算逻辑：
1. 全局函数 `calc_synthetic_indices()` — 用于计算 Close 价格指数
2. `main()` 内部的嵌套函数 `apply_formula()` — 用于计算 High/Low 价格指数

**只更新了前者，忘了后者！**

**解决方案**：确保两处逻辑同步更新，包括：
- 新增变量获取 (`xau = series_getter(SYMBOLS_MAP['XAU'])`)
- 新增公式计算 (`res['XAU'] = xau/基准值 + ...`)

**教训**：
- 搜索 `def ` 和函数名，确认没有重复定义
- 添加新货币时的完整检查清单应包含"检查 `apply_formula` 嵌套函数"

---

### 10.3 前端 Vercel 部署问题 (2026-01-14)

**问题**：本地 `npm run build` 成功，但 Vercel 部署失败。

**可能原因**：
1. `package-lock.json` 与 `package.json` 版本不一致
2. 依赖未正确安装（如 `@dnd-kit/modifiers` 被引用但未安装）
3. Monorepo 结构下 Vercel 的 Root Directory 配置错误

**解决方案**：
```bash
# 删除锁文件，重新生成
rm frontend/package-lock.json
cd frontend && npm install
vercel --prod --yes
```

**教训**：
- 添加新依赖后立即本地 `npm run build` 验证
- 如果 Vercel 失败，先检查是否漏装依赖

---

### 10.4 拖拽功能改崩事故 (2026-01-15)

**问题**：尝试为卡片/表格添加拖拽排序功能，结果导致多个核心功能丢失：
- ❌ 每张卡片上的周期切换按钮消失（变成全局选择器）
- ❌ 黑暗模式切换按钮消失
- ❌ 整体 UI 结构被破坏

**原因**：对 `page.tsx` 进行了**破坏性重写**，而非增量修改。

**正确做法**：
1. **备份**：`cp page.tsx page.tsx.backup`
2. **增量添加**：仅在现有组件外层包裹 `DndContext` 和 `useSortable`
3. **不动内部逻辑**：保留所有原有的子组件、状态、交互
4. **逐步验证**：
   - [ ] 卡片周期切换存在
   - [ ] 黑暗模式按钮存在
   - [ ] TradingView 链接正常
   - [ ] 趋势颜色正确
   - [ ] 拖拽功能正常

**教训**：
- 大型组件改造必须采用**最小改动原则**
- 每改一小步就本地测试，确保原有功能不受影响
- 功能改造前务必 git commit 当前稳定版本

**稳定版本回滚点**：`76dba4a` (fix: switch XAU/XAG to futures)

---

## 11. 股指综合指数添加指南

### 11.1 TAIXI 方法应用于股指

股指与货币指数不同，股指有**本币计价**的问题。TAIXI 方法将股指转换为**多货币标准化视角**，消除本币汇率波动干扰。

**通用公式结构**：
```
指数综合 = 指数/USD基准 + 指数/EUR基准 + 指数/GBP基准 + 指数/JPY基准 + 指数/AUD基准
```

### 11.2 不同计价币种的换算公式

| 计价币种 | 第1项(USD) | 第2项(EUR) | 第3项(GBP) | 第4项(JPY) | 第5项(AUD) |
|---------|-----------|-----------|-----------|-----------|-----------|
| **USD** | Index | Index/EURUSD | Index/GBPUSD | Index×USDJPY | Index/AUDUSD |
| **EUR** | Index×EURUSD | Index | Index×EURUSD/GBPUSD | Index×EURUSD×USDJPY | Index×EURUSD/AUDUSD |
| **GBP** | Index×GBPUSD | Index×GBPUSD/EURUSD | Index | Index×GBPUSD×USDJPY | Index×GBPUSD/AUDUSD |
| **JPY** | Index/USDJPY | Index/USDJPY/EURUSD | Index/USDJPY/GBPUSD | Index | Index/USDJPY/AUDUSD |
| **其他(XXX)** | Index/USDXXX | Index/USDXXX/EURUSD | Index/USDXXX/GBPUSD | Index/USDXXX×USDJPY | Index/USDXXX/AUDUSD |

### 11.3 基准值计算方法

1. 获取当前市场价格（指数价格 + 相关汇率）
2. 代入公式各项，计算当前值
3. 这些值即为基准值（使指数归一化到约 5 左右）

**示例**：SPX500 (USD 计价)，当前价格 5950
- 第1项基准：5950
- 第2项基准：5950/1.07 ≈ 6367
- 第3项基准：5950/1.27 ≈ 7557
- 第4项基准：5950×143 ≈ 850850
- 第5项基准：5950/0.66 ≈ 9015

### 11.4 添加新股指的步骤

1. **确定计价币种**：在 TradingView 上查看指数的实际报价单位
2. **创建公式文档**：先写出 TV 公式供用户测试
3. **用户验证公式**：在 TV 搜索框粘贴公式，确认能正常显示
4. **后端添加**：
   - `SYMBOLS_MAP` 添加 Yahoo Ticker
   - `calc_synthetic_indices` 添加公式
   - `apply_formula` **必须同步添加**（教训！）
5. **前端添加**：
   - `SYMBOL_NAMES` 添加中文名
   - `TV_FORMULAS` 添加 TV 公式

---

## 12. 高效开发流程总结

### 12.1 为什么 17 个股指能快速添加？

| 因素 | 说明 |
|------|------|
| **踩坑经验文档化** | 之前的失败记录在知识库，避免重复犯错 |
| **先创建公式文档** | 让用户先测试 TV 公式，避免返工 |
| **本地构建验证** | 每次改动后立即 `npm run build` |
| **同步两处公式逻辑** | 记住 `calc_synthetic_indices` 和 `apply_formula` 必须同步 |
| **增量而非重写** | 只添加新代码，不改动原有逻辑 |

### 12.2 添加新品种的标准流程

```
1. 讨论需求 → 确定品种列表和计价币种
2. 创建公式文档 → 用户在 TV 测试
3. 用户确认通过 → 开始写代码
4. 后端 godview.py:
   - SYMBOLS_MAP (Yahoo Ticker)
   - calc_synthetic_indices (公式)
   - apply_formula (公式，同步！)
5. 前端 page.tsx:
   - SYMBOL_NAMES (中文名)
   - TV_FORMULAS (TV 公式)
6. 本地构建 → git push → 触发 Actions → Vercel 部署
```

### 12.3 核心检查清单

- [ ] 计价币种确认正确（USD/EUR/GBP/JPY/其他）
- [ ] TV 公式用户测试通过
- [ ] `calc_synthetic_indices` 已添加公式
- [ ] `apply_formula` **已同步添加公式**
- [ ] `SYMBOL_NAMES` 已添加中文名
- [ ] `TV_FORMULAS` 已添加 TV 公式
- [ ] 本地 `npm run build` 成功
- [ ] `git push` 后等待 GitHub Actions 完成

---

## 附录: 关键文件清单

| 文件 | 用途 |
|------|------|
| `engine/godview.py` | 后端指标计算，数据推送 |
| `frontend/app/page.tsx` | 前端主页，UI 渲染 |
| `frontend/app/layout.tsx` | 布局，SEO 元数据 |
| `.github/workflows/update_godview.yml` | 定时任务配置 |
| `engine/requirements.txt` | Python 依赖 |
| `TAIXI 指数.txt` | 货币指数公式参考 |
| `股指综合指数公式.md` | 股指公式参考 |

---

**最后更新**: 2026-01-15

