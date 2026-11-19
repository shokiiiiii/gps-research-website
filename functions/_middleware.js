// サイト全体のパスワード保護（Cloudflare Pages Functions）
// - 環境変数 SITE_PASSWORD にパスワードを設定する
// - ログインすると署名付きCookieを発行し、COOKIE_DAYS 日間はログイン不要
// - パスワードを変更すると、発行済みのCookieはすべて無効になる

const COOKIE_NAME = "gps_auth";
const COOKIE_DAYS = 30;
const LOGIN_PATH = "/__login";
const LOGOUT_PATH = "/__logout";

export async function onRequest({ request, env, next }) {
  const password = env.SITE_PASSWORD;
  if (!password) {
    return new Response("SITE_PASSWORD が設定されていません", { status: 503 });
  }

  const url = new URL(request.url);

  if (url.pathname === LOGOUT_PATH) {
    return redirect("/", clearCookie());
  }

  if (url.pathname === LOGIN_PATH && request.method === "POST") {
    const form = await request.formData();
    const input = String(form.get("password") || "");
    const back = safePath(String(form.get("next") || "/"));

    if (await safeEqual(input, password)) {
      const expires = Date.now() + COOKIE_DAYS * 86400 * 1000;
      const token = `${expires}.${await sign(String(expires), password)}`;
      return redirect(back, setCookie(token));
    }
    return loginPage(back, true);
  }

  if (await isLoggedIn(request, password)) {
    const res = await next();
    const out = new Response(res.body, res);
    out.headers.set("Cache-Control", "private, no-store");
    return out;
  }

  return loginPage(safePath(url.pathname + url.search), false);
}

async function isLoggedIn(request, password) {
  const cookie = request.headers.get("Cookie") || "";
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${COOKIE_NAME}=([^;]+)`));
  if (!match) return false;

  const [expires, sig] = match[1].split(".");
  if (!expires || !sig || Number(expires) < Date.now()) return false;
  return safeEqual(sig, await sign(expires, password));
}

async function sign(value, secret) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(value));
  return btoa(String.fromCharCode(...new Uint8Array(mac)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// 文字列比較にかかる時間から内容を推測されないよう、ハッシュ同士を比較する
async function safeEqual(a, b) {
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(a)),
    crypto.subtle.digest("SHA-256", enc.encode(b)),
  ]);
  const x = new Uint8Array(ha), y = new Uint8Array(hb);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

// ログイン後の戻り先は同じサイト内のパスだけに限定する
function safePath(p) {
  if (!p.startsWith("/") || p.startsWith("//") || p.startsWith(LOGIN_PATH)) return "/";
  return p;
}

function setCookie(token) {
  return `${COOKIE_NAME}=${token}; Path=/; Max-Age=${COOKIE_DAYS * 86400}; HttpOnly; Secure; SameSite=Lax`;
}

function clearCookie() {
  return `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
}

function redirect(location, cookie) {
  return new Response(null, {
    status: 303,
    headers: { Location: location, "Set-Cookie": cookie, "Cache-Control": "no-store" },
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function loginPage(next, failed) {
  const html = `<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>ログイン | GPS Co-location Research</title>
<style>
  :root { --bg:#f5f7fa; --card:#fff; --text:#1f2933; --muted:#6b7785; --line:#d9dee5; --accent:#2780e3; --err:#c0392b; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#16181d; --card:#22252b; --text:#e6e8eb; --muted:#9aa3ad; --line:#3a3f47; --accent:#5aa9ff; --err:#ff7b6b; }
  }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; padding:16px;
         background:var(--bg); color:var(--text);
         font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; }
  .card { width:100%; max-width:360px; background:var(--card); border:1px solid var(--line);
          border-radius:12px; padding:32px 28px; box-shadow:0 8px 30px rgba(0,0,0,.06); }
  h1 { font-size:1.15rem; margin:0 0 4px; }
  p { margin:0 0 24px; color:var(--muted); font-size:.9rem; }
  label { display:block; font-size:.85rem; margin-bottom:6px; }
  input { width:100%; padding:10px 12px; font-size:1rem; border:1px solid var(--line); border-radius:8px;
          background:transparent; color:var(--text); }
  input:focus { outline:2px solid var(--accent); outline-offset:1px; border-color:transparent; }
  button { width:100%; margin-top:16px; padding:10px; font-size:1rem; border:0; border-radius:8px;
           background:var(--accent); color:#fff; cursor:pointer; }
  button:hover { filter:brightness(1.08); }
  .err { color:var(--err); font-size:.85rem; margin-top:10px; }
</style>
</head>
<body>
  <form class="card" method="post" action="${LOGIN_PATH}">
    <h1>GPS Co-location Research</h1>
    <p>このサイトは関係者限定です。パスワードを入力してください。</p>
    <label for="pw">パスワード</label>
    <input id="pw" name="password" type="password" autocomplete="current-password" required autofocus>
    <input type="hidden" name="next" value="${escapeHtml(next)}">
    <button type="submit">ログイン</button>
    ${failed ? '<div class="err" role="alert">パスワードが違います。</div>' : ""}
  </form>
</body>
</html>`;
  return new Response(html, {
    status: 401,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}
