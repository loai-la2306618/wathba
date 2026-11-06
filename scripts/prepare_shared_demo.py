"""Prepare the lightweight deployment without credentials or private recordings."""
from pathlib import Path
import json
import shutil

BASE=Path(__file__).resolve().parents[1]
STAGE=BASE/'.wathba/deploy/wathba-demo'
STAGE.mkdir(parents=True,exist_ok=True)
for name in ('web','wathba','assets'):
    shutil.copytree(BASE/name,STAGE/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(BASE/'assets/vendor',STAGE/'public/vendor',dirs_exist_ok=True)
shutil.rmtree(STAGE/'assets/vendor')
(STAGE/'assets/vendor').mkdir()
(STAGE/'assets/vendor/NOTICE.md').write_text('Open model/runtime assets are served from public/vendor by the deployment CDN.\n')
shutil.copy2(BASE/'requirements-shared.txt',STAGE/'requirements.txt')
(STAGE/'app.py').write_text('from wathba.serverless import app\n')
(STAGE/'.python-version').write_text('3.12\n')
(STAGE/'.vercelignore').write_text('.env*\n__pycache__\n*.pyc\n')
(STAGE/'vercel.json').write_text(json.dumps({'framework':'fastapi','functions':{'app.py':{'maxDuration':300,'excludeFiles':'{public/**,**/__pycache__/**}'}},'regions':['fra1']},indent=2))
print(STAGE)
