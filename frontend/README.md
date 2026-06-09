# FXview Frontend

Next.js frontend for FXview, deployed to Cloudflare through OpenNext.

## Local Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Cloudflare Build

```bash
npm run lint
npm run build
npm run cf:build
npm run cf:deploy
```

## Runtime

- Public domain: `fxview.xuebz.com`
- Worker: `fxview-xuebz`
- Data source: Supabase tables populated by the Cloudflare Provider

## Relevant API Routes

- `GET /api/signal-8h`
- `GET /api/cron/signal-8h-supervisor`
