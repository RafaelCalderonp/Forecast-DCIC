const BACKEND = "https://forecast-dcic-backend.onrender.com"

export async function onRequest(context) {
  const url = new URL(context.request.url)
  const target = BACKEND + url.pathname + url.search

  const headers = new Headers(context.request.headers)
  headers.delete("host")

  const init = {
    method: context.request.method,
    headers,
    body: ["GET", "HEAD"].includes(context.request.method) ? undefined : context.request.body,
  }

  const resp = await fetch(target, init)
  return new Response(resp.body, {
    status: resp.status,
    headers: resp.headers,
  })
}
