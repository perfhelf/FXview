export function isAuthorizedCronRequest(request: Request): boolean {
  const cronSecret = process.env.CRON_SECRET

  if (!cronSecret) {
    return true
  }

  const url = new URL(request.url)
  const authHeader = request.headers.get('authorization')
  const secretParam = url.searchParams.get('secret')

  return authHeader === `Bearer ${cronSecret}` || secretParam === cronSecret
}
