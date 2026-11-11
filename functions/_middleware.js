
export function onRequest({ request, env, next }) {
    const password = env.SITE_PASSWORD;
  
    // パスワード未設定ならアクセスを拒否
    if (!password) {
      return new Response("Configuration error", { status: 503 });
    }
  
    // ブラウザから送信された認証情報を確認
    const actual = request.headers.get("Authorization");
    const expected = "Basic " + btoa("viewer:" + password);
  
    if (actual !== expected) {
      return new Response("Authentication required", {
        status: 401,
        headers: {
          "WWW-Authenticate": 'Basic realm="GPS Research"',
          "Cache-Control": "no-store"
        }
      });
    }
  
    // 認証成功時だけWebサイトを表示
    return next();
  }
  