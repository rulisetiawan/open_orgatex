import requests
import json

URL = "http://192.168.100.30:4141/api/iw-telemetry/mapping/10B"

try:
    r = requests.get(URL, timeout=5)
    data = r.json()
    items = data.get("data", [])
    print(f"Total mappings returned by API: {len(items)}")
    
    streamed = 0
    no_stream = 0
    for it in items:
        val = it.get("live_value")
        status = it.get("status")
        reg = it.get("register_index")
        tag = it.get("tag_name")
        if val is not None and val != "--":
            streamed += 1
        else:
            no_stream += 1
            if no_stream <= 10:
                print(f"  No stream: IW {reg} ({tag})")

    print(f"Streamed with live values: {streamed}")
    print(f"No stream (pending new collector restart on server): {no_stream}")
except Exception as e:
    print("API Error:", e)
