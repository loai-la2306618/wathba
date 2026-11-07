"""Optional private Hugging Face dataset persistence for the shareable deployment."""
import json
import os
import re
import shutil
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlparse


def enabled():return bool(os.getenv('WATHBA_REMOTE_REPO'))

def root():
    from . import storage
    return storage.root()

def relative_path(value):
    p=Path(value)
    if p.is_absolute():p=p.resolve().relative_to(root().resolve())
    if '..' in p.parts or not p.parts:raise ValueError('Invalid demo media path.')
    return p.as_posix()

def token():return os.environ['WATHBA_STORAGE_TOKEN']

@lru_cache(maxsize=1)
def manifest():
    from huggingface_hub import hf_hub_download
    p=hf_hub_download(os.environ['WATHBA_REMOTE_REPO'],'workspace/manifest.json',repo_type='dataset',token=token(),cache_dir='/tmp/wathba-hf-cache')
    return json.loads(Path(p).read_text(encoding='utf-8'))

def canonical(path):return manifest().get('aliases',{}).get(relative_path(path),relative_path(path))

def exists(path):
    if not enabled():return (root()/relative_path(path)).exists()
    name=canonical(path)
    if name in manifest()['files']:return True
    from huggingface_hub import HfApi
    return HfApi(token=token()).file_exists(os.environ['WATHBA_REMOTE_REPO'],'workspace/'+name,repo_type='dataset')

def ensure(path,refresh=False,check=False):
    target=root()/relative_path(path)
    if not enabled() or (target.exists() and not (refresh or check)):return target
    from huggingface_hub import hf_hub_download
    p=hf_hub_download(os.environ['WATHBA_REMOTE_REPO'],'workspace/'+canonical(path),repo_type='dataset',token=token(),force_download=refresh,cache_dir='/tmp/wathba-hf-cache')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,target)
    return target

def rebase(s):
    folder=root()/s['id']
    for key in ('source_video','annotated_video','guide_video'):
        if s.get(key):s[key]=str(folder/Path(s[key]).name)
    for f in s.get('flags',[]):
        for key in ('clip','picture','reference_picture'):
            if f.get(key):f[key]=str(folder/Path(f[key]).name)
    return s

def portable(s):
    s=json.loads(json.dumps(s))
    for key in ('source_video','annotated_video','guide_video'):
        if s.get(key):s[key]=Path(s[key]).name
    for f in s.get('flags',[]):
        for key in ('clip','picture','reference_picture'):
            if f.get(key):f[key]=Path(f[key]).name
    return s

def bootstrap():
    if not enabled():return
    m=manifest()
    for name in m['metadata']:
        ensure(name)
    (root()/'library').mkdir(exist_ok=True)

def refresh_reports():
    if not enabled():return
    from huggingface_hub import HfApi
    paths=HfApi(token=token()).list_repo_files(os.environ['WATHBA_REMOTE_REPO'],repo_type='dataset')
    for path in paths:
        if re.fullmatch(r'workspace/[a-f0-9]{32}/report.json',path):ensure(path[len('workspace/'):],check=True)

def persist_file(path):
    if not enabled():return
    from huggingface_hub import HfApi
    name=relative_path(path)
    HfApi(token=token()).upload_file(path_or_fileobj=root()/name,path_in_repo='workspace/'+name,repo_id=os.environ['WATHBA_REMOTE_REPO'],repo_type='dataset',commit_message='Save shared demo state')

def persist_session(session_id):
    if not enabled():return
    from huggingface_hub import HfApi,CommitOperationAdd
    folder=root()/session_id
    operations=[]
    for p in folder.iterdir():
        if not p.is_file() or p.name.endswith('-raw.mp4') or p.suffix=='.tmp':continue
        content=p
        if p.name=='report.json':content=json.dumps(portable(json.loads(p.read_text(encoding='utf-8'))),ensure_ascii=False,allow_nan=False).encode()
        operations.append(CommitOperationAdd(path_in_repo=f'workspace/{session_id}/{p.name}',path_or_fileobj=content))
    HfApi(token=token()).create_commit(os.environ['WATHBA_REMOTE_REPO'],repo_type='dataset',operations=operations,commit_message='Save consented shared demo session')

def signed_url(path):
    """Return a temporary object-storage URL, never a Hugging Face access token."""
    from huggingface_hub import hf_hub_url,get_hf_file_metadata
    url=hf_hub_url(os.environ['WATHBA_REMOTE_REPO'],'workspace/'+canonical(path),repo_type='dataset')
    metadata=get_hf_file_metadata(url,token=token())
    location=metadata.location
    if urlparse(location).hostname not in ('huggingface.co','www.huggingface.co') and location.startswith('https://'):
        return location
    return None
