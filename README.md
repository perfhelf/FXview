# FXView - 全球汇率上帝视角

Web 版本的 GodView 仪表盘。前端运行在 Cloudflare OpenNext，数据计算由 Cloudflare Worker + Container 调度现有 Python 引擎写入 Supabase。

## 技术栈

- **前端**: Next.js 15 + Tailwind CSS
- **数据库**: Supabase (PostgreSQL)
- **数据源**: Yahoo Finance (via yfinance)
- **计算引擎**: Python + pandas_ta
- **正式轮询**: Cloudflare Worker Cron
- **计算容器**: Cloudflare Containers
- **部署**: Cloudflare Workers / OpenNext

## 项目结构

```
FXview/
├── frontend/           # Next.js 前端应用
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   └── godview/
│   └── lib/
│       └── supabase.ts # Supabase 客户端
├── engine/             # Python 计算引擎
│   ├── godview.py      # 核心计算逻辑
│   ├── requirements.txt
│   └── godview_schema.sql  # 数据库建表语句
└── provider/           # Cloudflare Worker + Container 调度层
    ├── src/index.ts
    ├── container/runner.py
    ├── Dockerfile
    └── wrangler.jsonc
```

## 部署步骤

### 1. Supabase 设置

1. 登录 Supabase Dashboard
2. 执行 `engine/godview_schema.sql` 中的 SQL 语句创建表
3. 记录你的 Project URL 和 API Keys

### 2. 前端环境变量

在 `frontend/` 目录下创建 `.env.local` 文件：

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### 3. Cron / Service Secrets

正式数据更新由 Cloudflare Worker Cron 触发，Provider 运行环境需要以下变量：

- `SUPABASE_URL`: Supabase Project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase Service Role Key (用于写入数据)
- `PROVIDER_RUN_SECRET`: 手动触发 Provider 时使用的鉴权密钥

### 4. Cloudflare 部署

```bash
cd frontend
npm run cf:build
npm run cf:deploy

cd ../provider
npm run deploy
```

### 5. 手动触发数据更新

Provider 支持以下手动入口，需携带 `Authorization: Bearer <PROVIDER_RUN_SECRET>`：

- `POST /run/godview`
- `POST /run/signal-8h`
- `POST /run/all`

## 本地开发

```bash
# 前端
cd frontend
npm install
npm run dev

# 引擎测试 (需要设置环境变量)
cd engine
pip install -r requirements.txt
python godview.py

# Provider
cd ../provider
npm install
npm run typecheck
npm run dry-run
```
