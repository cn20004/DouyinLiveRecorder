"""Execute bundled runtime and EXEs on Windows, without requesting a live room."""
import os
from pathlib import Path
import subprocess
import sys
import time
from src.collector_runtime import CollectorRuntime
root = Path(sys.argv[1]).resolve()
subprocess.run([str(root/'DouyinLiveRecorder-Core.exe'),'--self-test'],check=True,timeout=45)
runtime=CollectorRuntime(root)
try:
    runtime.ensure_started()
    assert runtime.healthy(), 'Packaged collector health check failed'
finally:
    runtime.close()
p=subprocess.Popen([str(root/'Zhenglaoshi-DouyinLive-v1.1.1.exe')],cwd=root)
try:
    time.sleep(4)
    assert p.poll() is None, 'Desktop launcher exited unexpectedly'
finally:
    if p.poll() is None: p.terminate();p.wait(timeout=10)
print('Windows EXEs, FFmpeg, JavaScript runtime, Chromium and collector startup OK')
