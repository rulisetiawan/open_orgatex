import psycopg2
import json
import time
import requests
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

print("=" * 60)
print("1. MEMERIKSA ALIRAN PESAN EMQX BROKER (tcp://192.168.100.30:1883)")
print("=" * 60)

mqtt_messages = {}

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode('utf-8'))
        mqtt_messages[topic] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "payload_preview": payload if not isinstance(payload, dict) or 'points' not in payload else {
                "asset_id": payload.get("asset_id"),
                "machine_no": payload.get("machine_no"),
                "batch_no": payload.get("batch_no"),
                "points_count": len(payload.get("points", []))
            }
        }
    except Exception as e:
        mqtt_messages[msg.topic] = {"error": str(e)}

try:
    c = mqtt.Client(client_id="verify_agent_inspector")
    c.username_pw_set("admin", "sensorSMM!")
    c.on_message = on_message
    c.connect("192.168.100.30", 1883, keepalive=10)
    c.subscribe("smm/jetflow/+/telemetry")
    c.subscribe("smm/jetflow/+/status")
    c.subscribe("smm/jetflow/+/batch_curve")
    c.subscribe("smm/jetflow/+/alarms")
    c.loop_start()

    print("Mendengarkan topik MQTT selama 4 detik...")
    time.sleep(4)
    c.loop_stop()
    c.disconnect()

    if mqtt_messages:
        print(f"-> Berhasil menerima {len(mqtt_messages)} topik MQTT dari broker:")
        for top, data in mqtt_messages.items():
            print(f"   * Topik: {top}")
            if "payload_preview" in data and isinstance(data["payload_preview"], dict):
                p = data["payload_preview"]
                if "tags" in p:
                    print(f"     Batch={p.get('batch_no')}, Step={p.get('step_no')}, Total Tags={len(p.get('tags', {}))}")
                    sample_tags = {k: v for k, v in list(p['tags'].items())[:3]}
                    print(f"     Sample Tags: {sample_tags}")
                else:
                    print(f"     Payload: {p}")
    else:
        print("-> [WARNING] Belum ada pesan MQTT yang tertangkap dalam 4 detik.")
except Exception as e:
    print(f"-> Error menghubungkan ke EMQX: {e}")

print("\n" + "=" * 60)
print("2. MEMERIKSA DATABASE pt_smm_scada (PostgreSQL Port 5433)")
print("=" * 60)

try:
    conn_scada = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
    cur = conn_scada.cursor()

    # Cek tag_latest
    cur.execute("""
        SELECT tag_code, value_number, quality, source_ts, updated_at 
        FROM tag_latest 
        WHERE asset_id = 'JF-LB-10' AND (tag_code LIKE '%TEMPERATURE%' OR tag_code LIKE '%SPEED%' OR tag_code LIKE '%LEVEL%')
        ORDER BY updated_at DESC LIMIT 6;
    """)
    rows = cur.fetchall()
    print("-> tag_latest terbaru (JF-LB-10):")
    for r in rows:
        print(f"   * {r[0]}: {r[1]} | Updated={r[4]} | Quality={r[2]}")

    # Cek asset_snapshot
    cur.execute("""
        SELECT asset_id, machine_state, batch_no, connected, updated_at, values_json 
        FROM asset_snapshot WHERE asset_id = 'JF-LB-10';
    """)
    snap = cur.fetchone()
    if snap:
        v = snap[5] or {}
        print(f"-> asset_snapshot: State={snap[1]}, Batch={snap[2]}, Connected={snap[3]}, LastUpdated={snap[4]}")
        print(f"   * Metrics di Snapshot: Temp PV={v.get('main_temp')}°C, Temp SP={v.get('main_temp_sp')}°C, Step={v.get('step_no')}")
        if 'program' in v:
            print(f"   * Resep Aktif: {len(v['program'])} steps terpasang!")

    conn_scada.close()
except Exception as e:
    print(f"-> Error pt_smm_scada: {e}")

print("\n" + "=" * 60)
print("3. MEMERIKSA DATABASE pt_smm_jetflow (PostgreSQL Port 5433)")
print("=" * 60)

try:
    conn_jf = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn_jf.cursor()

    # Cek live_iw_telemetry
    cur.execute("SELECT machine_id, last_updated, connection_status, batch_no, step_no FROM live_iw_telemetry WHERE machine_id = '10B';")
    live_iw = cur.fetchone()
    if live_iw:
        print(f"-> live_iw_telemetry: Machine={live_iw[0]}, Updated={live_iw[1]}, Status={live_iw[2]}, Batch={live_iw[3]}, Step={live_iw[4]}")

    # Cek datalog_iw_records terbaru
    cur.execute("SELECT time, tag_name, value, quality FROM datalog_iw_records WHERE machine_id = '10B' ORDER BY time DESC LIMIT 3;")
    iw_recs = cur.fetchall()
    print("-> datalog_iw_records terbaru:")
    for r in iw_recs:
        print(f"   * Time={r[0]} | Tag={r[1]} | Val={r[2]}")

    # Cek datalog_cyclic_records terbaru (dari PR<batch>.LOG)
    cur.execute("SELECT log_timestamp, machine_no, batch_ref_no, temp_pv, temp_sp, step_no FROM datalog_cyclic_records WHERE machine_no = '10B' ORDER BY log_timestamp DESC LIMIT 3;")
    cyc = cur.fetchall()
    print("-> datalog_cyclic_records terbaru (PR.LOG):")
    for r in cyc:
        print(f"   * Time={r[0]} | Batch={r[2]} | TempPV={r[3]} | TempSP={r[4]} | Step={r[5]}")

    conn_jf.close()
except Exception as e:
    print(f"-> Error pt_smm_jetflow: {e}")

print("\n" + "=" * 60)
print("4. MEMERIKSA API SCADA DASHBOARD (http://192.168.100.30:8788)")
print("=" * 60)

try:
    resp = requests.get("http://192.168.100.30:8788/api/v1/assets?process=jetflow", timeout=4)
    if resp.status_code == 200:
        assets = resp.json().get("data", resp.json()) if isinstance(resp.json(), dict) else resp.json()
        target = next((a for a in assets if a.get("asset_id") == "JF-LB-10"), None)
        if target:
            print(f"-> API SCADA Response JF-LB-10 (HTTP 200 OK):")
            print(f"   * Display Name : {target.get('display_name')}")
            print(f"   * State        : {target.get('machine_state')}")
            print(f"   * Connected    : {target.get('connected')}")
            print(f"   * Batch No     : {target.get('batch_no')}")
            v = target.get("values_json") or {}
            print(f"   * Temp PV / SV : {v.get('main_temp')} °C / {v.get('main_temp_sp')} °C")
            print(f"   * Step Aktif   : {v.get('step_no')}")
            if "program" in v:
                print(f"   * Program Resep: {len(v['program'])} steps siap dirender di tabel proses!")
        else:
            print("-> JF-LB-10 tidak ditemukan dalam response API jetflow")
    else:
        print(f"-> HTTP Error {resp.status_code}")
except Exception as e:
    print(f"-> Gagal menghubungi API SCADA port 8788: {e}")

print("=" * 60)
