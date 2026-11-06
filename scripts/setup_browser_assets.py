"""Download the pinned, locally served browser pose runtime and models.

* ONNX Runtime Web (WebAssembly build) from npm, verified against the registry
  integrity hash.
* Xenova/yolov8n-pose and Xenova/movenet-singlepose-lightning ONNX weights from
  Hugging Face at fixed revisions, verified by SHA256.

ViTPose is not downloaded here: it runs on the backend (requirements-vitpose.txt)
and is fetched by transformers at its pinned revision on first use.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]/'assets/vendor'
MODELS_JSON = Path(__file__).resolve().parents[1]/'web/pose/models.json'
ORT_VERSION = '1.30.0'
ORT_FILES = {
    'ort.wasm.min.mjs': '219e6a1fc8a9938268d18efca3c91d310bd2f4a59bbd13744df5b2b7fc6cee3b',
    'ort-wasm-simd-threaded.mjs': 'e13f7f94fc51b4ca72b12faeb1ee95f4ace6dfbc8939bc718aabdc0a27c4299b',
    'ort-wasm-simd-threaded.wasm': '3398c10d07d229bd91b364548e130e0e51a8e5704b88c7c083ebbeb78842dee2',
}
ORT_LICENSE = f'https://raw.githubusercontent.com/microsoft/onnxruntime/v{ORT_VERSION}/LICENSE'
# SHA256 of the exact files served to browsers. A mismatch stops setup.
MODEL_FILES = {
    'yolov8n-pose': {
        'onnx/model.onnx': '04f6d2416266f2aba6c5ba8b26de33ed9eba3279f972ac02e33f9f1366547586',
        'onnx/model_quantized.onnx': '8fc1edb4977c37bf8b8a6c4cfd1dca7a0b46a67d6ef33088ac69e76e0ea84270',
        'config.json': '005945fdfc71f2716e24c1db8ea67994e95fb58206c2750ed6ea4011d7a23925',
        'preprocessor_config.json': 'ab3bdd56daa5f2d59ec8f8723ae8bdf4ef28cb067d3688e99932c21bcb1fe151',
    },
    'movenet-singlepose-lightning': {
        'onnx/model.onnx': '1ad4f8d6c2f776a9967db3993c9ca740bc350104f9d37c151dc183fc29a464ad',
        'config.json': 'dddf6d4409af28ffd04284d00f4f06b2dc3f0615ab2657fd70e5cb1a6e70137d',
    },
}
# MediaPipe artefacts from the previous engine; removed if still present.
OBSOLETE = ('vision_bundle.mjs', 'pose_landmarker_full.task', 'wasm')


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'wathba-setup'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name in OBSOLETE:
        target = ROOT/name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    info = json.loads(fetch(f'https://registry.npmjs.org/onnxruntime-web/{ORT_VERSION}'))
    raw = fetch(info['dist']['tarball'])
    algorithm, encoded = info['dist']['integrity'].split('-', 1)
    if base64.b64encode(hashlib.new(algorithm, raw).digest()).decode() != encoded:
        raise ValueError('onnxruntime-web npm integrity mismatch')
    ort = ROOT/'ort'
    ort.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        for member in tar.getmembers():
            name = member.name.removeprefix('package/dist/')
            if member.isfile() and name in ORT_FILES:
                (ort/name).write_bytes(tar.extractfile(member).read())
    for name, expected in ORT_FILES.items():
        if not (ort/name).is_file() or sha256((ort/name).read_bytes()) != expected:
            raise ValueError(f'onnxruntime-web file missing or modified: {name}')
    (ort/'LICENSE').write_bytes(fetch(ORT_LICENSE))

    registry = json.loads(MODELS_JSON.read_text())['models']
    for model, files in MODEL_FILES.items():
        spec = registry[model]
        folder = ROOT/'models'/model
        folder.mkdir(parents=True, exist_ok=True)
        for rel, expected in files.items():
            target = folder/Path(rel).name
            data = target.read_bytes() if target.exists() else fetch(
                f"https://huggingface.co/{spec['repository']}/resolve/{spec['revision']}/{rel}")
            if sha256(data) != expected:
                raise ValueError(f'Unexpected SHA256 for {model}/{rel}: {sha256(data)}')
            target.write_bytes(data)

    files = {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes())
             for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name not in ('manifest.json', 'NOTICE.md')}
    manifest = {'onnxruntime-web': {'version': ORT_VERSION, 'npm_integrity': info['dist']['integrity'], 'license': 'MIT'},
                'models': {m: {k: registry[m][k] for k in ('repository', 'revision', 'license')} for m in MODEL_FILES},
                'files': files}
    (ROOT/'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'ONNX Runtime Web {ORT_VERSION}, YOLOv8n-pose and MoveNet Lightning ready under {ROOT}')


if __name__ == '__main__':
    main()
