import urllib.request
import json

try:
    req = urllib.request.Request(
        "http://192.168.100.30:8788/api/v1/assets?process=jetflow",
        headers={"x-data-mode": "real"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assets = data.get('assets', [])
        jf10 = [a for a in assets if a.get('id') == 'JF-LB-10']
        print("Response for JF-LB-10:")
        if jf10:
            print(json.dumps(jf10[0], indent=2))
        else:
            print("JF-LB-10 not found in assets list!")
except Exception as e:
    print("API Error:", e)
