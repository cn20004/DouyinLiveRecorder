"""Start the bundled local collector; no Git/npm installation on the user's PC."""
import atexit
import os
from pathlib import Path
import subprocess
import threading
import time
import httpx


class CollectorRuntime:
    def __init__(self, root):
        self.root = Path(root)
        self.process = None
        self.log = None
        self.lock = threading.Lock()
        atexit.register(self.close)

    def healthy(self):
        try:
            with httpx.Client(trust_env=False, timeout=2) as client:
                return isinstance(client.get('http://127.0.0.1:8757/api/rooms').raise_for_status().json().get('rooms'), list)
        except Exception:
            return False

    def ensure_started(self):
        with self.lock:
            if self.healthy():
                return
            if self.process is None or self.process.poll() is not None:
                node = self.root / 'runtime/node.exe'
                service = self.root / 'runtime/dyhub/dist/index.js'
                browsers = list((self.root / 'runtime/browsers').glob('chromium-*/chrome-win*/chrome.exe'))
                if not node.is_file() or not service.is_file() or not browsers:
                    raise RuntimeError('采集运行环境不完整，请解压完整 Windows 包后运行')
                env = os.environ.copy()
                env.update(DYHUB_HOST='127.0.0.1', DYHUB_PORT='8757', DYHUB_COLLECTOR='browser',
                           DYHUB_CHROME=str(browsers[0]), DYHUB_HEADED='0')
                (self.root / 'logs').mkdir(exist_ok=True)
                if self.log:
                    self.log.close()
                self.log = open(self.root / 'logs/collector.log', 'ab')
                self.process = subprocess.Popen([str(node), str(service)], cwd=str(service.parent.parent),
                    env=env, stdout=self.log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self.healthy():
                    return
                if self.process.poll() is not None:
                    raise RuntimeError('采集服务退出，请查看 logs/collector.log')
                time.sleep(.5)
            raise RuntimeError('采集服务启动超时，请查看 logs/collector.log')

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.log:
            self.log.close()
            self.log = None
