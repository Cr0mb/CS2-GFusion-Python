from __future__ import annotations
import os, sys
sys.dont_write_bytecode = True
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')
import json
import urllib.request
from types import SimpleNamespace
from typing import Tuple
OFFSETS_URL = 'https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/offsets.json'
CLIENT_DLL_URL = 'https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/client_dll.json'
HTTP_TIMEOUT_SECONDS = 15
_offsets_cache: SimpleNamespace | None = None
_class_offsets_cache: SimpleNamespace | None = None

def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'GFusion-ESP/offset_manager', 'Accept': 'application/json'}, method='GET')
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
        data = r.read()
    return json.loads(data.decode('utf-8', errors='replace'))

def get_offsets(force_update: bool=False) -> Tuple[SimpleNamespace, SimpleNamespace]:
    global _offsets_cache, _class_offsets_cache
    if _offsets_cache and _class_offsets_cache and (not force_update):
        return (_offsets_cache, _class_offsets_cache)
    offsets_json = _fetch_json(OFFSETS_URL)
    client_json = _fetch_json(CLIENT_DLL_URL)
    flat: dict[str, int] = {}
    classes: dict[str, dict[str, int]] = {}
    for module in offsets_json.values():
        if isinstance(module, dict):
            for k, v in module.items():
                if isinstance(v, int):
                    flat[k] = v
    if 'dwLocalPlayerController' not in flat:
        if 'dwLocalPlayerPawn' in flat:
            flat['dwLocalPlayerController'] = flat['dwLocalPlayerPawn']
        else:
            flat['dwLocalPlayerController'] = 0
    for module in client_json.values():
        for cls_name, cls_data in module.get('classes', {}).items():
            fields = cls_data.get('fields', {})
            if not fields:
                continue
            cls_map = classes.setdefault(cls_name, {})
            for field, value in fields.items():
                if field == 'm_modelState' and cls_name == 'CSkeletonInstance':
                    field = 'm_pBoneArray'
                    value = int(value) + 128
                if isinstance(value, int):
                    cls_map[field] = value
                    flat[field] = value
    _offsets_cache = SimpleNamespace(**flat)
    _class_offsets_cache = SimpleNamespace(**{cls: SimpleNamespace(**fields) for cls, fields in classes.items()})
    return (_offsets_cache, _class_offsets_cache)
