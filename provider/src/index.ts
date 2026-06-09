import { Container, getContainer } from '@cloudflare/containers'

type ProviderTask = 'signal-8h' | 'godview' | 'all'

interface Env {
  FXVIEW_PROVIDER_CONTAINER: DurableObjectNamespace<FxviewProviderContainer>
  PROVIDER_RUN_SECRET?: string
  SUPABASE_URL?: string
  SUPABASE_KEY?: string
  SUPABASE_SERVICE_ROLE_KEY?: string
}

export class FxviewProviderContainer extends Container {
  defaultPort = 8080
  requiredPorts = [8080]
  sleepAfter = '15m'
  enableInternet = true
}

function json(payload: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(payload, null, 2), {
    ...init,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...(init?.headers || {}),
    },
  })
}

function isAuthorized(request: Request, env: Env) {
  if (!env.PROVIDER_RUN_SECRET) {
    return false
  }

  const url = new URL(request.url)
  const secretParam = url.searchParams.get('secret')
  const authHeader = request.headers.get('authorization')

  return secretParam === env.PROVIDER_RUN_SECRET || authHeader === `Bearer ${env.PROVIDER_RUN_SECRET}`
}

function taskFromCron(cron: string): ProviderTask {
  if (cron === '20 */4 * * *') {
    return 'godview'
  }

  return 'signal-8h'
}

function taskFromPath(pathname: string): ProviderTask | null {
  if (pathname === '/run/signal-8h') {
    return 'signal-8h'
  }

  if (pathname === '/run/godview') {
    return 'godview'
  }

  if (pathname === '/run/all') {
    return 'all'
  }

  return null
}

function containerEnv(env: Env, source: string, task: ProviderTask) {
  const supabaseKey = env.SUPABASE_SERVICE_ROLE_KEY || env.SUPABASE_KEY || ''

  return {
    SUPABASE_URL: env.SUPABASE_URL || '',
    SUPABASE_KEY: supabaseKey,
    SUPABASE_SERVICE_ROLE_KEY: supabaseKey,
    PROVIDER_RUN_SOURCE: source,
    PROVIDER_RUN_TASK: task,
  }
}

async function runProvider(env: Env, task: ProviderTask, source: string) {
  const container = getContainer(env.FXVIEW_PROVIDER_CONTAINER, 'fxview-provider-main')

  await container.startAndWaitForPorts({
    startOptions: {
      envVars: containerEnv(env, source, task),
    },
  })

  const response = await container.fetch(`http://localhost/run/${task}`, {
    method: 'POST',
  })
  const body = await response.text()

  return new Response(body, {
    status: response.status,
    headers: {
      'content-type': response.headers.get('content-type') || 'application/json; charset=utf-8',
    },
  })
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url)

    if (url.pathname === '/' || url.pathname === '/health') {
      return json({
        ok: true,
        service: 'fxview-provider',
        manual_endpoints: ['/run/signal-8h', '/run/godview', '/run/all'],
      })
    }

    const task = taskFromPath(url.pathname)
    if (!task) {
      return json({ ok: false, error: 'not_found' }, { status: 404 })
    }

    if (!isAuthorized(request, env)) {
      return json({ ok: false, error: 'unauthorized' }, { status: 401 })
    }

    return runProvider(env, task, 'manual')
  },

  async scheduled(controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    const task = taskFromCron(controller.cron)
    ctx.waitUntil(runProvider(env, task, `cron:${controller.cron}`))
  },
}
