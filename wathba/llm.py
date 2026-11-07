"""Local Qwen3 (text) and Qwen3-VL (vision) inference with transformers.

* Models load lazily from Hugging Face at pinned revisions and run on this
  machine; patient data is not sent anywhere.
* At most one model is resident at a time (an 8 GB laptop GPU cannot hold a
  text and a vision model together); switching unloads the previous one.
* 4B models load in 4-bit NF4 when the GPU has less than 12 GB.
* A hosted provider (Hugging Face Inference API) can be added behind the same
  `generate_text` / `generate_vision` functions later; it is not enabled here.
"""

import importlib.util
import os
import threading
import time

MODELS = {
    'qwen3-0.6b': {'repo': 'Qwen/Qwen3-0.6B', 'revision': 'c1899de289a04d12100db370d81485cdf75e47ca', 'kind': 'text', 'params_b': 0.75, 'hybrid_thinking': True},
    'qwen3-1.7b': {'repo': 'Qwen/Qwen3-1.7B', 'revision': '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e', 'kind': 'text', 'params_b': 2.03, 'hybrid_thinking': True},
    'qwen3-4b': {'repo': 'Qwen/Qwen3-4B-Instruct-2507', 'revision': 'cdbee75f17c01a7cc42f958dc650907174af0554', 'kind': 'text', 'params_b': 4.02, 'hybrid_thinking': False},
    'qwen3-vl-2b': {'repo': 'Qwen/Qwen3-VL-2B-Instruct', 'revision': '89644892e4d85e24eaac8bacfd4f463576704203', 'kind': 'vision', 'params_b': 2.13},
    'qwen3-vl-4b': {'repo': 'Qwen/Qwen3-VL-4B-Instruct', 'revision': 'ebb281ec70b05090aa6165b016eac8ec08e71b17', 'kind': 'vision', 'params_b': 4.44},
}
DEFAULT_TEXT = os.getenv('WATHBA_QWEN_TEXT_MODEL', 'qwen3-4b')
# Defaults chosen from benchmarks/qwen3/RESULTS.md (best checked quality on an 8 GB GPU).
DEFAULT_VISION = os.getenv('WATHBA_QWEN_VISION_MODEL', 'qwen3-vl-4b')
# Qwen3 recommended sampling for non-thinking use; a fixed seed makes runs repeatable.
SAMPLING = {'do_sample': True, 'temperature': .7, 'top_p': .8, 'top_k': 20}
LOCK = threading.RLock()
_state = {'key': None, 'bundle': None, 'errors': {}, 'load_seconds': {}}


class Unavailable(RuntimeError):
    """The model cannot run here (packages missing, disabled, or failed to load)."""


def available(kind='text'):
    if os.getenv('WATHBA_QWEN', '1') == '0':
        return False, 'Qwen3 features are disabled on this server (WATHBA_QWEN=0).'
    missing = [m for m in ('torch', 'transformers', 'accelerate') if importlib.util.find_spec(m) is None]
    if missing:
        return False, f"Qwen3 needs optional packages ({', '.join(missing)}). Install requirements-qwen.txt."
    key = DEFAULT_TEXT if kind == 'text' else DEFAULT_VISION
    if _state['errors'].get(key):
        return False, _state['errors'][key]
    return True, ''


def quantize(key):
    """NF4 for 4B models on GPUs with < 12 GB; None (bf16) otherwise."""
    import torch
    if MODELS[key]['params_b'] < 3 or not torch.cuda.is_available():
        return None
    total = torch.cuda.get_device_properties(0).total_memory / 2**30
    if total >= 12 or importlib.util.find_spec('bitsandbytes') is None:
        return None
    return 'nf4'


def unload():
    with LOCK:
        if _state['bundle'] is not None:
            import gc
            import torch
            _state['bundle'] = None
            _state['key'] = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


def preload():
    """Load the coach in the background on a GPU, so the first summary does not wait for it."""
    def run():
        try:
            import torch
            if available('text')[0] and torch.cuda.is_available():
                load(DEFAULT_TEXT)
        except Exception as exc:  # A later request retries and shows the reason.
            print(f'Could not preload Qwen: {exc}', flush=True)
    threading.Thread(target=run, daemon=True, name='qwen-preload').start()


def load(key):
    """Load (or reuse) one model. Returns a bundle dict."""
    if key not in MODELS:
        raise ValueError(f'Unknown model: {key}')
    with LOCK:
        if _state['key'] == key:
            return _state['bundle']
        unload()
        spec = MODELS[key]
        started = time.perf_counter()
        try:
            import torch
            import transformers
            offline = os.getenv('WATHBA_OFFLINE', '0') == '1'
            cuda = torch.cuda.is_available()
            # Older GPUs such as the T4 only emulate bf16, which is very slow.
            native_bf16 = cuda and torch.cuda.is_bf16_supported(including_emulation=False)
            half = torch.bfloat16 if native_bf16 else torch.float16
            kwargs = {'revision': spec['revision'], 'local_files_only': offline,
                      'dtype': half if cuda else torch.float32, 'device_map': 'cuda:0' if cuda else 'cpu'}
            mode = quantize(key)
            if mode == 'nf4':
                kwargs['quantization_config'] = transformers.BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=half, bnb_4bit_use_double_quant=True)
            if spec['kind'] == 'text':
                tokenizer = transformers.AutoTokenizer.from_pretrained(spec['repo'], revision=spec['revision'], local_files_only=offline)
                model = transformers.AutoModelForCausalLM.from_pretrained(spec['repo'], **kwargs).eval()
                bundle = {'tokenizer': tokenizer, 'model': model}
            else:
                processor = transformers.AutoProcessor.from_pretrained(spec['repo'], revision=spec['revision'], local_files_only=offline)
                model = transformers.AutoModelForImageTextToText.from_pretrained(spec['repo'], **kwargs).eval()
                bundle = {'processor': processor, 'model': model}
            bundle.update(key=key, device='cuda' if cuda else 'cpu', precision=mode or (('bf16' if native_bf16 else 'fp16') if cuda else 'fp32'))
        except Exception as exc:  # download, memory or version problems are reported, never simulated
            cause = f' ({exc.__cause__!r})' if exc.__cause__ else ''
            _state['errors'][key] = f"{spec['repo']} could not be loaded: {exc}{cause}"[:400]
            raise Unavailable(_state['errors'][key]) from exc
        _state['load_seconds'][key] = round(time.perf_counter() - started, 2)
        _state.update(key=key, bundle=bundle)
        return bundle


def _run(bundle, inputs, max_new_tokens, seed):
    import torch
    model = bundle['model']
    if torch.cuda.is_available():
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
    torch.manual_seed(seed)
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=max_new_tokens, **SAMPLING)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    seconds = time.perf_counter() - started
    new = output[0, inputs['input_ids'].shape[1]:]
    stats = {'model': bundle['key'], 'repo': MODELS[bundle['key']]['repo'], 'device': bundle['device'], 'precision': bundle['precision'],
             'prompt_tokens': int(inputs['input_ids'].shape[1]), 'new_tokens': int(new.shape[0]), 'seconds': round(seconds, 3),
             'tokens_per_second': round(new.shape[0] / seconds, 1) if seconds else None,
             'peak_gpu_mb': round(torch.cuda.max_memory_allocated() / 2**20) if torch.cuda.is_available() else None,
             'load_seconds': _state['load_seconds'].get(bundle['key'])}
    return new, stats


def generate_text(messages, key=None, max_new_tokens=320, seed=0):
    key = key or DEFAULT_TEXT
    with LOCK:
        bundle = load(key)
        tok = bundle['tokenizer']
        template = {'enable_thinking': False} if MODELS[key].get('hybrid_thinking') else {}
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **template)
        inputs = tok(prompt, return_tensors='pt').to(bundle['model'].device)
        new, stats = _run(bundle, inputs, max_new_tokens, seed)
        return tok.decode(new, skip_special_tokens=True), stats


def generate_vision(images, prompt, key=None, max_new_tokens=320, seed=0, max_side=640):
    """images: list of RGB numpy arrays or PIL images (resized so the longest side <= max_side)."""
    from PIL import Image
    key = key or DEFAULT_VISION
    pictures = []
    for im in images:
        im = Image.fromarray(im) if not isinstance(im, Image.Image) else im
        scale = min(1, max_side / max(im.size))
        pictures.append(im.resize((round(im.width * scale), round(im.height * scale))) if scale < 1 else im)
    with LOCK:
        bundle = load(key)
        processor = bundle['processor']
        messages = [{'role': 'user', 'content': [*({'type': 'image', 'image': p} for p in pictures), {'type': 'text', 'text': prompt}]}]
        inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_dict=True,
                                               return_tensors='pt').to(bundle['model'].device)
        new, stats = _run(bundle, inputs, max_new_tokens, seed)
        stats['images'] = len(pictures)
        return processor.decode(new, skip_special_tokens=True), stats
