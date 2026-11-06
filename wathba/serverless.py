"""Vercel entrypoint: browser inference and CPU reports; private demo storage."""
import os
os.environ.setdefault('HF_HOME','/tmp/wathba-hf-cache')
os.environ.setdefault('HF_XET_CACHE','/tmp/wathba-hf-cache/xet')
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
os.environ.setdefault('WATHBA_DATA_DIR','/tmp/wathba-shared/workspace')
os.environ.setdefault('WATHBA_MAX_UPLOAD_MB','4')
os.environ.setdefault('WATHBA_MAX_RECORDING_SECONDS','20')
os.environ.setdefault('WATHBA_CAMERA_BITRATE','800000')
from fastapi.responses import RedirectResponse
from starlette.middleware.gzip import GZipMiddleware
from . import remote
from .access import DemoAccessMiddleware
from .webapp import create_app

app=create_app()
@app.get('/physio')
def clinician():return RedirectResponse('/?screen=portal')
app.add_middleware(GZipMiddleware,minimum_size=1000)
app.add_middleware(DemoAccessMiddleware)
