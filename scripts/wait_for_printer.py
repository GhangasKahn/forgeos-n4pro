#!/usr/bin/env python3
"""Wait until printer is REAL — not a cloud RFC1918 SYN-sink.

Success criteria (any):
  - SSH banner starts with SSH-
  - Moonraker returns JSON with result/state
"""
from __future__ import annotations
import argparse, json, socket, time, urllib.request, urllib.error

def ssh_banner(host: str, port: int = 22, timeout: float = 3.0) -> str:
    s = socket.socket(); s.settimeout(timeout)
    try:
        s.connect((host, port))
        data = s.recv(128)
        return data.decode('utf-8', errors='replace')
    except Exception as e:
        return ''
    finally:
        s.close()

def moonraker_ok(url: str, timeout: float = 3.0) -> dict:
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/printer/info', timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='192.168.1.178')
    ap.add_argument('--interval', type=float, default=5.0)
    ap.add_argument('--max-wait', type=float, default=0.0, help='0 = forever')
    args = ap.parse_args()
    t0 = time.time()
    n = 0
    while True:
        n += 1
        banner = ssh_banner(args.host)
        mr = moonraker_ok('http://%s:7125' % args.host)
        real_ssh = banner.startswith('SSH-')
        real_mr = bool(mr.get('result') or mr.get('state') or (isinstance(mr.get('result'), dict)))
        # also accept moonraker error JSON that proves HTTP spoke
        if not real_mr and mr:
            real_mr = 'error' in mr  # still proves HTTP path
        print('[%d] ssh_banner=%r moonraker_keys=%s' % (n, banner[:40], list(mr.keys())[:5]))
        if real_ssh or real_mr:
            print('PRINTER_REAL')
            print(json.dumps({'ssh_banner': banner.strip(), 'moonraker': mr}, indent=2)[:800])
            return 0
        if args.max_wait and (time.time() - t0) > args.max_wait:
            print('TIMEOUT_STILL_SYN_SINK')
            return 2
        time.sleep(args.interval)

if __name__ == '__main__':
    raise SystemExit(main())
