import urllib.request
import json

url = "http://192.168.100.30:8788/api/v1/batch/process-runs?asset_id=JF-LB-10"
try:
    req = urllib.request.Request(url, headers={"x-data-mode": "real"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("batch/process-runs response:")
        print(json.dumps(data, indent=2))
except Exception as e:
    print("Error:", e)
