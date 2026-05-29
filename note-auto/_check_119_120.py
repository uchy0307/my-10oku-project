import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(open('note-auto/queue.json','r',encoding='utf-8'))
items = d.get('items', [])
for tid in ['118','119','120','121']:
    target = [i for i in items if i.get('id') == tid]
    if target:
        t = target[0]
        print(f'\n[id={tid}]')
        print(f'  draftId={t.get("draftId","(empty)")}')
        print(f'  published={t.get("published","(none)")}')
        print(f'  status={t.get("status","(none)")}')
        print(f'  posted_at={t.get("posted_at","(none)")}')
        print(f'  title={t.get("title","")[:50]}')
        print(f'  attached={t.get("attached","(none)")}')
        print(f'  attach_error={t.get("attach_error","(none)")[:100] if t.get("attach_error") else "(none)"}')
        body=t.get("body","")
        print(f'  body_len={len(body)}')
        print(f'  body_first200=' + repr(body[:200]))
