# FXView - 全球汇率上帝视角

Web 版本的 GodView 仪表盘，使用 100% 免费技术栈实现。

## 技术栈

- **前端**: Next.js 15 + Tailwind CSS
- **数据库**: Supabase (PostgreSQL)
- **数据源**: Yahoo Finance (via yfinance)
- **计算引擎**: Python + pandas_ta
- **正式轮询**: cron-job.org / 独立调度器调用 HTTP 或 worker 入口
- **应急补跑**: GitHub Actions 仅保留 `workflow_dispatch`，不能再作为定时写库方案
- **部署**: Vercel

## 项目结构

```
FXview/
├── frontend/           # Next.js 前端应用
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx    # 主页面 (GodView 表格)
│   └── lib/
│       └── supabase.ts # Supabase 客户端
├── engine/             # Python 计算引擎
│   ├── godview.py      # 核心计算逻辑
│   ├── requirements.txt
│   └── godview_schema.sql  # 数据库建表语句
└── .github/
    └── workflows/
        └── update_godview.yml  # 手动应急补跑，不做定时写库
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

正式数据更新由独立 Cron 或 worker 触发，运行环境需要以下变量：

- `SUPABASE_URL`: Supabase Project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase Service Role Key (用于写入数据)

### 4. Vercel 部署

1. 将 `frontend` 目录设置为 Vercel 项目的 Root Directory
2. 在 Vercel 中配置环境变量 (同 .env.local)
3. 绑定自定义域名 `fxview.xuebz.com`

### 5. 手动触发首次数据更新

优先用正式 Cron/worker 入口触发。GitHub Actions 里的 workflow 只用于紧急手动补跑，不能重新加 `schedule`。

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
```
