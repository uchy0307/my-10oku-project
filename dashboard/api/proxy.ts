// Vercel Edge Function: CORS proxy fallback.
// 使い方: config.ts の CORS_PROXY を "/api/proxy?url=" にする。
// 許可ドメインを絞っているので任意 URL の踏み台にはなりません。
export const config = { runtime: "edge" };

const ALLOWED = [
  /^https:\/\/note\.com\/api\//,
  /^https:\/\/www\.youtube\.com\/feeds\/videos\.xml/
];

export default async function handler(req: Request): Promise<Response> {
  const u = new URL(req.url);
  const target = u.searchParams.get("url");
  if (!target) {
    return new Response("missing url", { status: 400 });
  }
  if (!ALLOWED.some((re) => re.test(target))) {
    return new Response("forbidden host", { status: 403 });
  }
  const upstream = await fetch(target, {
    headers: { "User-Agent": "uchy-dashboard-proxy/0.1" }
  });
  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") ?? "application/octet-stream",
      "Cache-Control": "public, max-age=60",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
