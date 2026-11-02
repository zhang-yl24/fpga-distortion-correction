"""Bound reset pipeline with deterministic content-addressed CPU proof reuse.
Every cache hit rehashes the full original watched file closure. Native stages
remain the existing frozen executors, and native source instructions unchanged.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import camera720_view_toggle_build as build
import camera720_view_toggle_route as routing
import camera720_view_toggle_reset_apply as application
import camera720_view_toggle_final_inspect as final
import camera720_view_toggle_reset_effect as effect

HERE = Path(__file__).resolve().parent
SELF = Path(__file__).resolve()
LOG = HERE/'reset-effect-driver-b.json'
LOCK = threading.RLock()
ENTRIES=[]

def save():
    payload={'Schema':'camera720-view-toggle-reset-pipeline-cpu-cache-v1',
      'Driver':{'Path':str(SELF),'SHA256':build.sha(SELF)},
      'CachePolicy':'Reuse deterministic CPU parse only after full canonical watched-closure SHA256 revalidation; no new parse claimed.',
      'HardwareAccessed':False,'BitstreamRequested':False,'Records':ENTRIES}
    LOG.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')

def memo(module,name):
    original=getattr(module,name);cache={}
    def call(path):
        key=str(Path(path).resolve())
        with LOCK:
            if key in cache:
                result=cache[key]; watched=result[-1]
                for p,h in watched.items():
                    p=Path(p)
                    build.require(p==p.resolve() and p.is_file() and build.sha(p)==h,'cache input drift '+str(p))
                ENTRIES.append({'Function':module.__name__+'.'+name,'Path':key,
                  'Validation':'Full watched closure SHA256 recheck; deterministic parse reused',
                  'RehashedFiles':len(watched),'UTC':datetime.now(timezone.utc).isoformat()});save()
                return result
            result=original(path);cache[key]=result
            ENTRIES.append({'Function':module.__name__+'.'+name,'Path':key,
              'Validation':'Original full CPU validation performed','WatchedFiles':len(result[-1]),
              'UTC':datetime.now(timezone.utc).isoformat()});save()
            return result
    setattr(module,name,call)

for module,name in [(routing,'bind_completed'),(application,'bind_completed'),
                    (final,'bind_receipt'),(effect,'verify')]:memo(module,name)

try:
    receipt=HERE/'reset-save-a/result.json'
    value,_=effect.audit_value(receipt,HERE/'final-export-a/result.json')
    build.write(HERE/'effect-a.json',value)
    verified,_=effect.verify(HERE/'effect-a.json')
    ENTRIES.append({'PipelinePassed':True,'Effect':final.ref(HERE/'effect-a.json'),
                    'CornerSummaries':verified['CornerSummaries']});save()
    print(json.dumps({'PipelinePassed':True,'Effect':str(HERE/'effect-a.json'),
                      'CornerSummaries':verified['CornerSummaries']}),flush=True)
except BaseException as error:
    ENTRIES.append({'PipelinePassed':False,'Error':type(error).__name__+': '+str(error)});save()
    raise
