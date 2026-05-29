import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(open('note-auto/queue.json','r',encoding='utf-8'))
items = d.get('items', [])
for tid in ['112','150','180']:
    target = [i for i in items if i.get('id') == tid]
    if target:
        t = target[0]
        print(f'\n[id={tid}] draftId={t.get("draftId","")} published={t.get("published","")} title={t.get("title","")[:40]}')
