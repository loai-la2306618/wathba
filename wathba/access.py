"""Optional password gate for the shared demo; disabled for local development."""
import hashlib
import hmac
import html
import os
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE='wathba_demo_access'

def session_value(secret, expires=None):
    expires=int(time.time()+7*86400) if expires is None else expires
    payload=str(expires)
    return payload+'.'+hmac.new(secret.encode(),payload.encode(),hashlib.sha256).hexdigest()

def valid_session(value, secret):
    try:
        expires,signature=value.split('.',1)
        return int(expires)>time.time() and hmac.compare_digest(value,session_value(secret,int(expires)))
    except (ValueError,TypeError,AttributeError):return False

def login_page(error=''):
    return HTMLResponse('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Wathba · Private Demo</title><style>*{box-sizing:border-box}body{margin:0;min-height:100svh;display:grid;place-items:center;padding:25px;background:radial-gradient(ellipse at 80% 15%,#76717d,#353d43 70%);font:15px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;color:#f8f9fa}.card{width:100%;max-width:380px;border-radius:28px;padding:32px 27px;background:#ffffff16;border:1px solid #ffffff50;box-shadow:0 15px 70px #1218203b;backdrop-filter:blur(24px)}h1{font-size:35px;margin:0 0 5px;letter-spacing:-1px}h1 span{font-size:26px;margin-left:10px}p{color:#e0e3e7;font-size:13px;margin:0 0 22px}label{font-size:12px}input,button{width:100%;font:inherit;border-radius:15px;min-height:49px;margin-top:9px}input{padding:12px;background:#ffffff14;border:1px solid #ffffff60;color:white}button{border:1px solid #d1ffdf;background:linear-gradient(120deg,#bcffda,#81ebaa);color:#163c2b;font-weight:700;cursor:pointer;margin-top:17px}.note{font-size:11px;line-height:1.7;margin:19px 0 0;color:#d4d9dd}.error{color:#ffe2bc;margin-top:10px}</style></head><body><main class="card"><h1>Wathba <span lang="ar">وثبة</span></h1><p>Your recovery, connected.<br>A private preview for the team.</p><form action="/login" method="post"><label for="password">Demo access code</label><input id="password" name="password" type="password" autocomplete="current-password" required autofocus><button type="submit">Open Wathba</button></form>'''+('<p class="error">'+html.escape(error)+'</p>' if error else '')+'''<p class="note">Includes staged exercise recordings shared with participant permission. Use demonstration footage when trying the camera.</p></main></body></html>''',headers={'Cache-Control':'private, no-store','X-Robots-Tag':'noindex, nofollow'})

class DemoAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        password=os.getenv('WATHBA_DEMO_PASSWORD')
        if not password:return await call_next(request)
        secret=os.environ.get('WATHBA_COOKIE_SECRET',password)
        if request.url.path=='/_health':return JSONResponse({'status':'ok'})
        supplied=request.query_params.get('access')
        if supplied and hmac.compare_digest(supplied.encode(),password.encode()):
            response=RedirectResponse(str(request.url.remove_query_params('access')),status_code=303)
            response.set_cookie(COOKIE,session_value(secret),max_age=7*86400,httponly=True,secure=request.url.scheme=='https',samesite='lax')
            response.headers['Cache-Control']='private, no-store'
            response.headers['Referrer-Policy']='no-referrer'
            return response
        if request.url.path=='/login' and request.method=='POST':
            form=await request.form()
            if hmac.compare_digest(str(form.get('password','')).encode(),password.encode()):
                response=RedirectResponse('/',status_code=303)
                response.set_cookie(COOKIE,session_value(secret),max_age=7*86400,httponly=True,secure=request.url.scheme=='https',samesite='lax')
                response.headers['Cache-Control']='private, no-store'
                return response
            return login_page('That code did not match. Try again.')
        if not valid_session(request.cookies.get(COOKIE),secret):
            if request.url.path in ('/','/login'):return login_page()
            return JSONResponse({'detail':'Enter the demo access code first.'},status_code=401,headers={'Cache-Control':'no-store'})
        response=await call_next(request)
        response.headers['Cache-Control']='private, no-store'
        response.headers['X-Robots-Tag']='noindex, nofollow'
        response.headers['Referrer-Policy']='no-referrer'
        return response
