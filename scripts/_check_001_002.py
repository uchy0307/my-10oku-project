import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
for label, vid in [('001 just-up', 'njRyXb1ohtQ'), ('002 just-up', 'nyJtZDUqjRI')]:
    try:
        with urllib.request.urlopen(f'https://www.youtube.com/oembed?url=https%3A//youtu.be/{vid}&format=json', timeout=10) as r:
            d = json.loads(r.read())
            print(f'{label} {vid} PUBLIC title="{d.get("title")}" author="{d.get("author_name")}"')
    except urllib.error.HTTPError as e:
        print(f'{label} {vid} FAIL HTTP {e.code}')
