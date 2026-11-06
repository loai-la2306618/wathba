"""Download pinned, locally served MediaPipe runtime and pretrained pose model."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

VERSION='0.10.32'
ROOT=Path(__file__).resolve().parents[1]/'assets/vendor'
MODEL_URL='https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task'
MODEL_SHA='5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1'


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    info=json.load(urllib.request.urlopen('https://registry.npmjs.org/@mediapipe/tasks-vision/'+VERSION))
    raw=urllib.request.urlopen(info['dist']['tarball']).read()
    integrity=info['dist']['integrity']
    algorithm,encoded=integrity.split('-',1)
    assert base64.b64encode(hashlib.new(algorithm,raw).digest()).decode()==encoded,'npm integrity mismatch'
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
        for m in tar.getmembers():
            name=m.name.removeprefix('package/')
            if m.isfile() and (name=='vision_bundle.mjs' or name.startswith('wasm/')):
                target=ROOT/name
                assert target.resolve().is_relative_to(ROOT.resolve())
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(tar.extractfile(m).read())
    target=ROOT/'pose_landmarker_full.task'
    if not target.exists():urllib.request.urlretrieve(MODEL_URL,target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if digest!=MODEL_SHA:raise ValueError(f'Unexpected model SHA256: {digest}')
    license_url='https://raw.githubusercontent.com/google-ai-edge/mediapipe/master/LICENSE'
    (ROOT/'LICENSE').write_bytes(urllib.request.urlopen(license_url).read())
    files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (ROOT/'manifest.json').write_text(json.dumps({'package':'@mediapipe/tasks-vision','version':VERSION,'npm_integrity':integrity,'model_url':MODEL_URL,'files':files},indent=2))
    print(f'MediaPipe {VERSION} and Full pose model ready under {ROOT}')

if __name__=='__main__':main()
