#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Drive 共有フォルダ画像を公開DL (確認トークン対応 + usercontent ホスト)。"""
import re, sys, urllib.request, http.cookiejar
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RAW = Path(r'C:\Users\user\Documents\10oku-project\assets\hp_landing\raw')
RAW.mkdir(parents=True, exist_ok=True)

FILES = [
    ('1-H5bLSoHN1jW1f1ZB_m9Sjsbh_WIjsKl', 'img_2cqy.png'),
    ('1nxp9rVIePDXD_N7FXpNxNLpelyvOlp7p', 'img_o8o3.png'),
    ('1ntMFkDhyioLOhL72y3fY0FnQOjuxepjG', 'img_u890.png'),
    ('1Cx710p19-uQPCV3yG4T9Vn3BQpzVFdNO', 'img_cupru.png'),
    ('19BYPMYguIA6nLbijYoGt8eHZVl4qLeRK', 'img_npycdr.png'),
    ('1LsjOUD22hFo4ADojeK3sNs-OjhZ0oE6N', 'img_azfy95.png'),
]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [('User-Agent', UA)]


def is_png(b):
    return b[:8] == b'\x89PNG\r\n\x1a\n'


def fetch(url):
    with opener.open(url, timeout=90) as r:
        return r.read()


for fid, name in FILES:
    dst = RAW / name
    ok = False
    for url in [
        f'https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t',
        f'https://drive.google.com/uc?export=download&id={fid}&confirm=t',
    ]:
        try:
            data = fetch(url)
        except Exception as e:
            print(f'  [err] {name} {url[:50]}: {e}')
            continue
        if is_png(data):
            dst.write_bytes(data); print(f'[OK] {name}: {len(data)//1024}KB'); ok = True; break
        # HTML なら confirm token を抜いて再取得
        m = re.search(rb'confirm=([0-9A-Za-z_-]+)', data) or re.search(rb'name="confirm"\s+value="([^"]+)"', data)
        uuid = re.search(rb'name="uuid"\s+value="([^"]+)"', data)
        if m:
            tok = m.group(1).decode()
            u2 = f'https://drive.usercontent.google.com/download?id={fid}&export=download&confirm={tok}'
            if uuid:
                u2 += f'&uuid={uuid.group(1).decode()}'
            try:
                data2 = fetch(u2)
                if is_png(data2):
                    dst.write_bytes(data2); print(f'[OK2] {name}: {len(data2)//1024}KB'); ok = True; break
            except Exception as e:
                print(f'  [err2] {name}: {e}')
    if not ok:
        print(f'[FAIL] {name}: 公開DL不可 (フォルダ共有を「リンクを知っている全員」にする必要)')
print('\nDL先:', RAW)
