import urllib.request
import json

for port in [8787, 8788]:
    try:
        url = f"http://192.168.100.30:{port}/api/v1/assets?process=jetflow"
        req = urllib.request.Request(url, headers={"x-data-mode": "real"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assets = data.get('assets', [])
            jf10 = [a for a in assets if a.get('id') == 'JF-LB-10']
            print(f"Port {port}: found {len(assets)} assets, JF-LB-10: {jf10[0] if jf10 else 'None'}")
    except Exception as e:
        print(f"Port {port} error: {e}")
