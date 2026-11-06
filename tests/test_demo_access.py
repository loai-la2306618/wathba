from fastapi import FastAPI
from fastapi.testclient import TestClient
from wathba.access import DemoAccessMiddleware, session_value, valid_session


def app_client(monkeypatch):
    monkeypatch.setenv('WATHBA_DEMO_PASSWORD','demo-test-code')
    monkeypatch.setenv('WATHBA_COOKIE_SECRET','test-signing-key')
    app=FastAPI()
    @app.get('/')
    def home():return {'private':'app'}
    @app.get('/api/config')
    def config():return {'private':'config'}
    @app.get('/media/private.mp4')
    def video():return {'private':'video'}
    app.add_middleware(DemoAccessMiddleware)
    return TestClient(app,base_url='https://testserver')


def test_data_is_blocked_until_demo_login(monkeypatch):
    client=app_client(monkeypatch)
    assert 'Demo access code' in client.get('/').text
    assert client.get('/api/config').status_code==401
    assert client.get('/media/private.mp4').status_code==401
    client.post('/login',data={'password':'incorrect'})
    assert client.get('/api/config').status_code==401
    response=client.post('/login',data={'password':'demo-test-code'},follow_redirects=False)
    assert response.status_code==303
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    assert client.get('/api/config').json()=={'private':'config'}
    assert client.get('/media/private.mp4').json()=={'private':'video'}


def test_share_link_cleans_access_code_and_signed_cookie_cannot_be_forged(monkeypatch):
    client=app_client(monkeypatch)
    response=client.get('/?screen=welcome&access=demo-test-code',follow_redirects=False)
    assert response.status_code==303
    assert 'access=' not in response.headers['location']
    assert 'screen=welcome' in response.headers['location']
    assert client.get('/api/config').status_code==200
    assert not valid_session('0.invalid','test-signing-key')
    assert not valid_session(session_value('different-key'),'test-signing-key')
    assert not valid_session(session_value('test-signing-key',1),'test-signing-key')
