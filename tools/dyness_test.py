"""
Dyness API Tester v4.0
Testet v1 (bestehende API) UND v2 (neue API) für alle Dyness Geräteserien.

Geräteserien mit v2-Dokumentation:
  - Low-voltage battery (DL5, PowerDepot G2, PowerBox G2, Junior Box)
  - High-voltage battery (Tower, Stack100, PowerBox Pro)
  - Cygni HA/HS (Hybrid-Wechselrichter)
  - HT-A / LS Series (All-in-One Systeme)
  - AquaVolt / AquaVolt_LV / SolarCube

Verwendung:
    pip install requests
    python3 dyness_test.py

Bitte Output als Issue auf GitHub teilen!
https://github.com/shopf/dyness_battery
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import hashlib, hmac, base64, json, re, requests
from email.utils import formatdate

# ===== HIER DEINE ZUGANGSDATEN EINTRAGEN =====
API_ID     = "DEINE_API_ID"
API_SECRET = "DEIN_API_SECRET"

# Wähle deine Region für v1 (nur eine Zeile einkommentieren):
API_BASE_V1 = "https://open-api.dyness.com/openapi/ems-device"         # Europa v1 (Standard)
# API_BASE_V1 = "https://apacopen-api.dyness.com/openapi/ems-device"   # Asia-Pacific v1

# Wähle deine Region für v2 (nur eine Zeile einkommentieren):
API_BASE_V2 = "https://eu-openapi.dyness.com/openapi/emsdevice"        # Europa v2
# API_BASE_V2 = "https://apacopen-api.dyness.com/openapi/emsdevice"    # Asia-Pacific v2
# API_BASE_V2 = "https://na-openapi.dyness.com/openapi/emsdevice"      # North America v2
# API_BASE_V2 = "https://latam-openapi.dyness.com/openapi/emsdevice"   # Latin America v2
# API_BASE_V2 = "https://me-openapi.dyness.com/openapi/emsdevice"      # Middle East v2
# API_BASE_V2 = "https://af-openapi.dyness.com/openapi/emsdevice"      # Africa v2
# API_BASE_V2 = "https://sa-openapi.dyness.com/openapi/emsdevice"      # South America v2
# API_BASE_V2 = "https://global-openapi.dyness.com/openapi/emsdevice"  # Global v2
# API_BASE_V2 = "https://openapi.dyness.com.cn/openapi/emsdevice"      # China v2

# Optional: Wenn Auto-Discovery fehlschlägt
DEVICE_SN = ""
DONGLE_SN = ""
# =============================================

SEP  = "=" * 60
SEP2 = "-" * 60


# ── Auth Helpers ──────────────────────────────────────────────────────────────

def get_md5(body: str) -> str:
    return base64.b64encode(hashlib.md5(body.encode("utf-8")).digest()).decode("utf-8")


def get_signature(secret: str, content_md5: str, date: str, path: str) -> str:
    sts = f"POST\n{content_md5}\napplication/json\n{date}\n{path}"
    return base64.b64encode(
        hmac.new(secret.encode("utf-8"), sts.encode("utf-8"), "sha1").digest()
    ).decode("utf-8")


def _post(base_url: str, path: str, body_dict: dict) -> dict:
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
    md5  = get_md5(body)
    sig  = get_signature(API_SECRET, md5, date, path)
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Content-MD5":  md5,
        "Date":         date,
        "Authorization": f"API {API_ID}:{sig}",
    }
    try:
        r = requests.post(f"{base_url}{path}", headers=headers,
                          data=body.encode("utf-8"), timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e), "code": "ERR"}


def api_v1(path, body): return _post(API_BASE_V1, path, body)
def api_v2(path, body): return _post(API_BASE_V2, path, body)


def is_ok(result: dict) -> bool:
    # Handle both {"code":"200"} and HTTP 404 {"status":404}
    if result.get("status") in (404, 401, 403, 500):
        return False
    code = str(result.get("code", ""))
    return code in ("0", "200") or result.get("code") == 0


def print_result(label, path, body, result, ver="v1"):
    print(SEP)
    print(f"[{ver}] {label}")
    print(f"Path: {path}  Body: {json.dumps(body, ensure_ascii=False)}")
    print(SEP)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()


# ── v1 Point Analysis ─────────────────────────────────────────────────────────

def get_rt_points(result):
    raw = result.get("data", []) or []
    return {item["pointId"]: item["pointValue"]
            for item in raw if isinstance(item, dict) and "pointId" in item}


def analyze_rt_points(pts, label=""):
    if label:
        print(f"\n{SEP2}\n  Point-Analyse: {label}\n{SEP2}")
    if not pts:
        print("  ⚠️  Keine Points vorhanden.")
        return

    KNOWN = {
        "100": "Gerätename", "200": "Hersteller", "300": "Firmware-Version",
        "310": "MPPT SN", "400": "Batterieanzahl",
        "600": "Spannung (V)", "700": "Strom (A)", "800": "SOC (%)",
        "900": "Leistung (W)", "1200": "SOH (%)",
        "1300": "Zellspannung Max (V)", "1500": "Zellspannung Min (V)",
        "1800": "Temp Max (°C)", "2000": "Temp Min (°C)",
        "2300": "MOS-Temp Max (°C)", "2800": "BMS-Temp Max (°C)",
        "3200": "Alarm Status 1", "3300": "Alarm Status 2",
        "3400": "Schutz Status 1", "3500": "Schutz Status 2",
        "3600": "Lade-Spannungsgrenze (V)", "3700": "Entlade-Spannungsgrenze (V)",
        "3800": "Max. Ladestrom (A)", "3900": "Max. Entladestrom (A)",
        "4000": "Lade-/Entladestatus", "4500": "Arbeitsstatus",
        # Junior Box / MPPT-Serie
        "4600": "PV Spannung (V) [JB/MPPT]", "4700": "PV Strom (A) [JB/MPPT]",
        "4800": "PV Leistung (W) [JB/MPPT]",
        "4900": "Bat Spannung MPPT (V) [JB]", "5000": "Bat Strom MPPT (A) [JB]",
        "5100": "Bat Leistung MPPT (W) [JB]",
        "5200": "OUT1 Spannung (V)", "5300": "OUT1 Strom (A)", "5400": "OUT1 Leistung (W)",
        "5500": "OUT2 Spannung (V)", "5600": "OUT2 Strom (A)", "5700": "OUT2 Leistung (W)",
        "5800": "Bus-Spannung (V) [JB]", "5900": "PV Gesamt-Leistung (W) [JB]",
        "6000": "Bat Gesamt-Leistung (W) [JB]", "6100": "OUT Gesamt-Leistung (W) [JB]",
        "6200": "Bat State [JB]", "6300": "Error Code [JB]",
        "6400": "EMS Modus [JB]", "6500": "EMS Leistung (W) [JB]",
        "6600": "DOD (%)", "6700": "Batterie-Protokoll [JB]",
        "6900": "Heatsink-Temp (°C)", "7000": "Luft-Temp (°C)",
        "7100": "E-Laden gesamt (kWh)", "7200": "E-Laden heute (kWh)",
        "7300": "E-Entladen gesamt (kWh)", "7400": "E-Entladen heute (kWh)",
        "7500": "PV E-Gesamt (kWh)", "7600": "PV E-Heute (kWh)",
        "7700": "OUT E-Gesamt (kWh) [JB]", "7800": "OUT E-Heute (kWh) [JB]",
        "7900": "DSP1 Version [JB]", "8000": "DSP SVN Version [JB]",
        "8100": "Bat-Gruppe 1 State [JB]", "8400": "Bat-Gruppe 1 Power [JB]",
        "999999": "Gesamt-Alarm-Flag",
        # Tower / TP7 / HV
        "1400": "Tower SOC (%) / Zellspg.Min",
        "1600": "Tower Remaining kWh",
        "1700": "Tower Rated kWh",
        "2400": "Tower Zellspg.Max",
        "4400": "Alarm Flag1 [Tower/TP7]",
        "4500": "Alarm Flag2 [Tower/TP7]",
        "4900": "Alarm Flag6 [Tower/TP7] / Bat-Spg [JB]",
        "5001": "Alarm SpreadV [Tower T14]", "5002": "Alarm SpreadT [Tower T14]",
        "5003": "Alarm Insulation [Tower T14]",
        "5101": "Alarm AFE [Tower T14]", "5102": "Alarm BMS [Tower T14]",
        "5104": "Alarm SYS [Tower T14]",
        # Sub-Modul
        "10000": "Modul-SN", "10200": "Zellanzahl [DL5/JB]",
        "10300": "Cell 01 [DL5/JB]",
        "11200": "Cell 01 [Stack100/TP7/Tower]",
        "12400": "SOC (%) [G2]", "12500": "Temp1 (°C) [G2]", "12600": "Temp2 (°C) [G2]",
        "13400": "SOC genau (%) [G2]", "13500": "Spannung (V) [G2/DL5 Modul]",
        "13900": "Zyklen [G2/DL5 Modul]",
    }

    found = {k: v for k, v in KNOWN.items() if k in pts}
    if found:
        print("\n  ── Bekannte Key-Points ──")
        for pid, desc in sorted(found.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999999):
            print(f"    {pid:>7}: {str(pts[pid]):<15} ({desc})")

    print("\n  ── Alle Points ──")
    if "T" in pts:   print(f"    Zeitstempel: {pts['T']}")
    if "SUB" in pts: print(f"    SUB:         {pts['SUB']!r}")
    if "TIME" in pts: print(f"    TIME:        {pts['TIME']}")

    numeric = {k: v for k, v in pts.items() if str(k).isdigit()}
    ranges = [
        (0,     999,   "Master (0–999)"),
        (1000,  4399,  "Master (1000–4399)"),
        (4400,  9999,  "Alarm/Status/PV/Energie (4400–9999)"),
        (10000, 14499, "Sub-Modul / Zellen (10000–14499)"),
        (14500, 99999, "Sonstige (14500+)"),
    ]
    for r0, r1, rl in ranges:
        in_r = {k: v for k, v in numeric.items() if r0 <= int(k) <= r1}
        if not in_r: continue
        print(f"\n    [{rl}]")
        for pid in sorted(in_r, key=int):
            known = KNOWN.get(pid, "")
            suffix = f"  ← {known}" if known else ""
            print(f"      {pid:>7}: {str(in_r[pid]):<15}{suffix}")

    print(f"\n  ── Zusammenfassung ──")
    print(f"    Points gesamt: {len(pts)}")
    pv = [k for k in ["4600","4700","4800","5900"] if k in pts and str(pts[k]) not in ("0","0.0","","None")]
    print(f"    {'✅' if pv else '—'} PV-Daten: {', '.join(pv) if pv else 'keine'}")
    en = [k for k in ["7100","7200","7300","7400","7500","7600"] if k in pts]
    print(f"    {'✅' if en else '—'} Energie-Zähler: {', '.join(en) if en else 'keine'}")

    if "800" in pts:
        print(f"    📋 SOC-Schema: Standard (Point 800 = {pts['800']}%)")
    elif "1400" in pts and pts.get("1400") and str(pts["1400"]).replace('.','').isdigit() and float(pts["1400"]) <= 100:
        print(f"    📋 SOC-Schema: Tower/TP7 (Point 1400 = {pts['1400']}%)")
    elif "13400" in pts:
        print(f"    📋 SOC-Schema: PowerBox G2 (Point 13400 = {pts['13400']}%)")
    else:
        print(f"    ⚠️  SOC-Schema: UNBEKANNT — bitte als Issue melden!")

    if "5001" in pts:
        print(f"    📋 Alarm-Schema: Tower T14 (Bit-Points 5001+)")
    elif "4400" in pts:
        print(f"    📋 Alarm-Schema: Tower/TP7 (Flag-Register 4400–4900)")
    elif "3200" in pts:
        print(f"    📋 Alarm-Schema: Standard (Points 3200/3300)")
    print()


def analyze_running_data(result):
    print(f"\n{SEP2}\n  Analyse: getLastRunningDataBySn\n{SEP2}")
    data = result.get("data")
    if not data:
        print("  ⚠️  Keine Daten")
        return
    vals = [(k, v) for k, v in data.items() if v is not None and v != ""]
    nuls = [k for k, v in data.items() if v is None or v == ""]
    if vals:
        print("  ✅ Felder mit Werten:")
        for k, v in vals:
            print(f"    {k}: {v}")
    if len(nuls) == len(data):
        print("  ⚠️  Alle Felder null — kein Wechselrichter (normal für reine Batterien)")
    print()


# ── v2 Analysis ───────────────────────────────────────────────────────────────

def _v2_status(result, endpoint_name):
    """Returns True if v2 endpoint succeeded, prints analysis header."""
    print(f"\n{SEP2}\n  [v2] {endpoint_name}\n{SEP2}")
    if result.get("status") in (404, 401, 403):
        print(f"  ❌ HTTP {result.get('status')} — Endpunkt für dieses Gerät/Region nicht verfügbar")
        return False
    if not is_ok(result):
        code = result.get("code") or result.get("status")
        print(f"  ❌ Fehler: code={code}  info={result.get('info') or result.get('message')}")
        return False
    return True


def analyze_v2_realtime(result, device_series="unknown"):
    """Analysiert GetRealTimeDataBySN — unterschiedliche Felder je nach Serie."""
    ok = _v2_status(result, "GetRealTimeDataBySN")
    if not ok:
        return False

    data = result.get("data") or {}

    # Cygni / HT-A / AquaVolt haben Felder direkt in data (kein batteryInfo wrapper)
    # LV / JB / HV haben batteryInfo wrapper
    batt = data.get("batteryInfo") or data

    # Felder nach Serien-Dokument
    FIELDS_COMMON = {
        "batteryVoltage":   ("V",   "Batteriespannung"),
        "batteryCurrent":   ("A",   "Batteriestrom (neg=Entladen)"),
        "soc":              ("%",   "SOC"),
        "soh":              ("%",   "SOH"),
        "batteryStatus":    ("",    "Lade-/Entladestatus (0=Standby/Aus, 1=Standby, 2=Entladen, 3=Laden)"),
        "maxChargeCurrent": ("A",   "Max. Ladestrom"),
        "maxDischargeCurrent": ("A","Max. Entladestrom"),
        "cycleCount":       ("",    "Ladezyklen"),
        "cellMaxVoltage":   ("V",   "Zellspannung Max"),
        "cellMinVoltage":   ("V",   "Zellspannung Min"),
        "cellMaxTemperature":("°C", "Zell-Temp Max"),
        "cellMinTemperature":("°C", "Zell-Temp Min"),
    }
    FIELDS_LV = {  # Low-voltage (DL5, PowerDepot, PowerBox G2) + JB overlap
        "moduleHighVoltageUpperLimit": ("V",  "Modul-Hochspannungsgrenze"),
        "moduleLowVoltage":            ("V",  "Modul-Niederspannungsgrenze"),
        "moduleUnderVoltage":          ("V",  "Modul-Unterspannungsschutz"),
        "bmsBoardTemp":                ("°C", "BMS-Platinen-Temp"),
        "chargeTemperatureUpperLimit": ("°C", "Ladetemperatur Max"),
        "chargeTemperatureLowLimit":   ("°C", "Ladetemperatur Min"),
        "dischargeTemperatureUpperLimit": ("°C", "Entladetemperatur Max"),
        "dischargeTemperatureLowLimit":   ("°C", "Entladetemperatur Min"),
        "cellVoltageList":             ("V",  "Einzelzellspannungen (Liste)"),
        "cellTempList":                ("°C", "Einzelzell-Temperaturen (Liste)"),
    }
    FIELDS_JB = {  # Junior Box spezifisch
        "maxBmsTemp":  ("°C", "BMS-Temp Max [Junior Box]"),
        "minBmsTemp":  ("°C", "BMS-Temp Min [Junior Box]"),
        "maxMosTemp":  ("°C", "MOS-Temp Max [Junior Box]"),
    }
    FIELDS_HV = {  # High-Voltage spezifisch
        "batteryPower":          ("W",  "Batterieleistung"),
        "batteryTemperature":    ("°C", "Batterie-Temperatur"),
        "batteryRemainingEnergy":("Wh", "Verbleibende Kapazität"),
        "batteryRatedEnergy":    ("Wh", "Nennkapazität"),
        "batteryDiffVoltage":    ("V",  "Zellspannungs-Differenz"),
        "chargeCurrentLimit":    ("A",  "Empf. Ladestrom"),
        "dischargeCurrentLimit": ("A",  "Empf. Entladestrom"),
        "singleVoltageCount":    ("",   "Anzahl Zellspannungen"),
        "singleTemperatureCount":("",   "Anzahl Temperatur-Sensoren"),
        "cellVoltageList":       ("V",  "Einzelzellspannungen (Liste)"),
        "cellTempList":          ("°C", "Einzelzell-Temperaturen (Liste)"),
        "bmsInfoList":           ("",   "BMS Cluster-Liste (Multi-Cluster)"),
    }
    FIELDS_CYGNI = {  # Cygni / AquaVolt / HT-A (Wechselrichter)
        "pvTotalPower":          ("W",  "PV Gesamtleistung"),
        "gridStatus":            ("",   "Netz-Status (0=Standby,1=On-Grid,2=Off-Grid)"),
        "activePower":           ("W",  "Wirkleistung Netz"),
        "gridVoltage":           ("V",  "Netzspannung"),
        "gridCurrent":           ("A",  "Netzstrom"),
        "gridPower":             ("W",  "Netzleistung"),
        "gridFrequency":         ("Hz", "Netzfrequenz"),
        "inverterTotalPower":    ("W",  "Wechselrichter Gesamtleistung"),
        "TotalLoadPower":        ("W",  "Gesamte Lastleistung"),
        "homeLoad":              ("W",  "Haushalts-Last"),
        "backupLoadPower":       ("W",  "Backup-Last"),
        "batteryPower":          ("W",  "Batterieleistung"),
        "batteryCapacity":       ("Ah", "Batteriekapazität"),
        "batteryTemperature":    ("°C", "Batterie-Temperatur"),
        "chargeCurrentLimit":    ("A",  "Ladestrom-Limit"),
        "dischargeCurrentLimit": ("A",  "Entladestrom-Limit"),
        "onGridDischargeDepth":  ("%",  "On-Grid DOD"),
        "offGridDischargeDepth": ("%",  "Off-Grid DOD"),
        "bmsCommunicationStatus":("",   "BMS Kommunikation (0=Fehler,1=OK)"),
        "bmsSoftwareVersion":    ("",   "BMS Software-Version"),
        "batteryCellInfo":       ("",   "Zell-Detaildaten (Cygni-HA)"),
    }

    all_fields = {**FIELDS_COMMON, **FIELDS_LV, **FIELDS_JB, **FIELDS_HV, **FIELDS_CYGNI}

    present, missing_known = [], []
    for field, (unit, desc) in all_fields.items():
        val = batt.get(field)
        if val is not None and val != "" and val != []:
            present.append((field, val, unit, desc))
        else:
            # Only report missing if relevant to this series
            missing_known.append((field, desc))

    print(f"\n  ✅ Vorhandene Felder ({len(present)}):")
    for field, val, unit, desc in present:
        if isinstance(val, list):
            val_str = f"[{len(val)} Einträge: {val[:4]}{'...' if len(val)>4 else ''}]"
        else:
            val_str = f"{val} {unit}".strip()
        print(f"    {field:<40} = {val_str:<25} ({desc})")

    # Unbekannte Felder in der Antwort
    all_known_keys = set(all_fields.keys())
    extra = [k for k in batt.keys() if k not in all_known_keys and k not in ("batteryInfo",)]
    if extra:
        print(f"\n  🆕 Unbekannte/neue Felder in der Antwort — bitte als Issue melden:")
        for k in extra:
            print(f"    {k} = {batt[k]}")

    # Berechnete Werte
    print(f"\n  📊 Berechnete Werte:")
    v = batt.get("batteryVoltage"); a = batt.get("batteryCurrent")
    if v and a:
        try:
            power = round(float(v) * float(a), 1)
            print(f"    realTimePower (V×A) = {power} W")
        except: pass
    cell_v = batt.get("cellVoltageList") or []
    if len(cell_v) >= 2:
        try:
            floats = [float(x) for x in cell_v]
            diff = round((max(floats) - min(floats)) * 1000, 1)
            print(f"    cellVoltageDiffMv   = {diff} mV")
        except: pass

    print(f"\n  ✅ v2 GetRealTimeDataBySN: VERFÜGBAR")
    return True


def analyze_v2_device_info(result):
    ok = _v2_status(result, "GetDeviceInfBySN")
    if not ok: return False
    data = result.get("data") or {}
    print(f"  hostDeviceName:      {data.get('hostDeviceName','—')}")
    print(f"  hostSoftwareVersion: {data.get('hostSoftwareVersion','—')}")
    extra = [k for k in data if k not in ("hostDeviceName","hostSoftwareVersion")]
    if extra:
        print(f"  🆕 Weitere Felder: {', '.join(f'{k}={data[k]}' for k in extra)}")
    print(f"  ✅ verfügbar")
    return True


def analyze_v2_alarm(result):
    ok = _v2_status(result, "GetAlarmInfBySN")
    if not ok: return False
    data = result.get("data") or {}
    alarms = data.get("list") or []
    print(f"  Alarme gesamt: {data.get('total',0)}")
    for a in alarms[:5]:
        print(f"    [{a.get('eventGrade','?')}] Code={a.get('eventCode','?')} "
              f"Typ={a.get('eventType','?')} Zeit={a.get('beginTime','?')}")
    if not alarms:
        print(f"  ✅ Keine aktiven Alarme")
    print(f"  ✅ verfügbar")
    return True


def analyze_v2_parallel(result):
    ok = _v2_status(result, "GetParallelInfBySN")
    if not ok: return False
    data = result.get("data") or {}
    FIELDS = {
        "parallelPackSn":       "Battery Pack SN",
        "hostVersion":          "Host Version",
        "chargeDischargeStatus":"Lade-/Entladestatus",
        "parallelPackVoltage":  "Pack-Spannung (V)",
        "parallelPackCurrent":  "Pack-Strom (A)",
        "parallelPackSoc":      "Pack SOC (%)",
        "parallelPackSoh":      "Pack SOH (%)",
        "maxChargeCurrent":     "Max. Ladestrom (A)",
        "maxDischargeCurrent":  "Max. Entladestrom (A)",
        "cellMaxVoltage":       "Zellspannung Max (V)",
        "cellMinVoltage":       "Zellspannung Min (V)",
        "cellMaxTemperature":   "Zell-Temp Max (°C)",
        "cellMinTemperature":   "Zell-Temp Min (°C)",
        "maxBmsTemperature":    "BMS-Temp Max (°C)",
        "minBmsTemperature":    "BMS-Temp Min (°C)",
        "maxMosTemperature":    "MOS-Temp Max (°C)",
    }
    present = [(f, data[f], d) for f, d in FIELDS.items() if data.get(f) not in (None,"")]
    for f, v, d in present:
        print(f"    {f:<25} = {str(v):<15} ({d})")
    extra = [k for k in data if k not in FIELDS]
    if extra:
        print(f"  🆕 Neue Felder: {', '.join(f'{k}={data[k]}' for k in extra)}")
    print(f"  ✅ verfügbar")
    return True


def analyze_v2_device_list(result):
    ok = _v2_status(result, "GetDeviceList")
    if not ok: return False
    data = result.get("data") or []
    if isinstance(data, dict):
        data = data.get("list") or []
    print(f"  Geräte auf diesem Account: {len(data)}")
    for d in data[:10]:
        print(f"    {d.get('deviceSn','?'):35} Modell: {d.get('deviceModel','?'):20} Status: {d.get('workStatus','?')}")
    extra_fields = set()
    for d in data:
        extra_fields.update(k for k in d if k not in ("deviceSn","deviceModel","workStatus","communicationStatus"))
    if extra_fields:
        print(f"  🆕 Weitere Felder: {', '.join(sorted(extra_fields))}")
    print(f"  ✅ verfügbar")
    return True


def analyze_v2_status(result):
    ok = _v2_status(result, "GetStatusInfBySN")
    if not ok: return False
    data = result.get("data") or {}
    FIELDS = {
        "safeCountry": "Sicherheitsland/-norm Code",
        "runModel":    "Betriebsmodus",
        "workStatus":  "Arbeitsstatus",
        "sparePower":  "Backup-Leistung",
        "powerLimit":  "Leistungsbegrenzung",
    }
    for f, d in FIELDS.items():
        val = data.get(f)
        if val is not None:
            print(f"    {f:<20} = {val}  ({d})")
    extra = [k for k in data if k not in FIELDS]
    if extra:
        print(f"  🆕 Weitere Felder ({len(extra)}): {', '.join(f'{k}={data[k]}' for k in extra[:15])}")
    print(f"  ✅ verfügbar")
    return True


def analyze_v2_total_energy(result):
    ok = _v2_status(result, "GetTotalEnergyDataBySN")
    if not ok: return False
    data = result.get("data") or {}
    FIELDS = {
        # Cygni / AquaVolt / HT-A (flat structure)
        "dailyPvGeneration":    "PV heute (kWh)",
        "totalPvGeneration":    "PV gesamt (kWh)",
        "dailyBuyEnergy":       "Netzbezug heute (kWh)",
        "dailySellEnergy":      "Netzeinspeisung heute (kWh)",
        "totalBuyEnergy":       "Netzbezug gesamt (kWh)",
        "totalSellEnergy":      "Netzeinspeisung gesamt (kWh)",
        "dailyElectricity":     "Last-Verbrauch heute (kWh)",
        "totalElectricity":     "Last-Verbrauch gesamt (kWh)",
        "dailyChargeEnergy":    "Laden heute (kWh)",
        "totalChargeEnergy":    "Laden gesamt (kWh)",
        "dailyDischargeEnergy": "Entladen heute (kWh)",
        "totalDischargeEnergy": "Entladen gesamt (kWh)",
        # HT-A nested: pvInfo.dailyPvGeneration etc. — will appear as pvInfo
        "pvInfo":               "PV-Daten (nested)",
        "gridInfo":             "Grid-Daten (nested)",
        "batteryInfo":          "Batterie-Daten (nested)",
        "loadInfo":             "Last-Daten (nested)",
    }
    for f, d in FIELDS.items():
        val = data.get(f)
        if val is not None and val != "":
            if isinstance(val, dict):
                print(f"    {f}: {json.dumps(val, ensure_ascii=False)[:120]}  ({d})")
            else:
                print(f"    {f:<30} = {val}  ({d})")
    extra = [k for k in data if k not in FIELDS]
    if extra:
        print(f"  🆕 Weitere Felder: {', '.join(f'{k}={data[k]}' for k in extra[:10])}")
    print(f"  ✅ verfügbar")
    return True


def print_summary(results, device_model):
    print(SEP)
    print(f"  📋 v2 API Kompatibilitäts-Zusammenfassung")
    print(f"     Gerät: {device_model}")
    print(SEP)

    rows = [
        ("GetRealTimeDataBySN",   results.get("rt"),       "Echtzeit-Daten (Hauptquelle)"),
        ("GetDeviceInfBySN",      results.get("device"),   "Gerätename + Firmware"),
        ("GetAlarmInfBySN",       results.get("alarm"),    "Alarme"),
        ("GetParallelInfBySN",    results.get("parallel"), "Parallel-Pack (Multi-Modul)"),
        ("GetDeviceList",         results.get("devlist"),  "Geräteliste"),
        ("GetStatusInfBySN",      results.get("status"),   "Gerätestatus"),
        ("GetTotalEnergyDataBySN",results.get("energy"),   "Energie-Statistiken"),
    ]
    any_ok = False
    for name, ok, desc in rows:
        if ok is None: continue  # nicht getestet
        status = "✅ verfügbar " if ok else "❌ nicht verf."
        if ok: any_ok = True
        print(f"  {name:<28} {status}  ({desc})")

    print()
    if any_ok:
        rt_ok = results.get("rt", False)
        par_ok = results.get("parallel", False)
        en_ok = results.get("energy", False)
        print("  💡 Polling-Einschätzung:")
        if rt_ok and par_ok:
            print("     v2 kann v1 Master + Sub-Modul-Calls ersetzen → ~60% weniger Calls/Zyklus")
        elif rt_ok:
            print("     v2 kann v1 Master-Calls ersetzen → ~30% weniger Calls/Zyklus")
        if en_ok:
            print("     GetTotalEnergyDataBySN liefert Energie-Zähler → ersetzt v1 getLastPowerDataBySn")
    else:
        print("  ℹ️  v2 nicht verfügbar für dieses Gerät/Region → bleibt bei v1")

    print()
    print("  Bitte Output als Issue teilen: https://github.com/shopf/dyness_battery")
    print(SEP)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

print(SEP)
print("Dyness API Tester v4.1 — v1 + v2 Kompatibilitätstest (alle Serien)")
print(SEP)

device_sn = DEVICE_SN.strip()
dongle_sn = DONGLE_SN.strip()
device_model = "Unbekannt"

# ── Auto-Discovery ────────────────────────────────────────────────────────────
if not device_sn:
    print("► Suche Geräte (v1)...")
    sl = api_v1("/v1/device/storage/list", {})
    print_result("Storage Geräteliste", "/v1/device/storage/list", {}, sl, "v1")
    if is_ok(sl):
        devs = (sl.get("data", {}) or {}).get("list", [])
        if devs:
            bms = next((d for d in devs if str(d.get("deviceSn","")).endswith(("-BMS","-BDU"))), devs[0])
            device_sn    = bms.get("deviceSn", "")
            dongle_sn    = bms.get("collectorSn", "") or ""
            device_model = bms.get("deviceModelName", "Unbekannt")
            print(f"✅ Gerät: {device_sn}  Modell: {device_model}")
            if len(devs) > 1:
                print(f"   Weitere Geräte auf diesem Account:")
                for d in devs:
                    print(f"   - {d.get('deviceSn')} ({d.get('deviceModelName','?')})")
        else:
            print("❌ Keine Geräte — bitte DEVICE_SN eintragen."); sys.exit(1)
    else:
        print(f"❌ API Fehler: {sl.get('info')} — bitte DEVICE_SN eintragen."); sys.exit(1)
else:
    print(f"► Manuelle SN: {device_sn}")

body_sn   = {"deviceSn": device_sn}
body_full = {"deviceSn": device_sn, "collectorSn": dongle_sn} if dongle_sn else dict(body_sn)

# ── v1: Statische Daten ───────────────────────────────────────────────────────
res = api_v1("/v1/device/bindSn", body_full)
print_result("Gerät binden", "/v1/device/bindSn", body_full, res, "v1")

res = api_v1("/v1/device/household/storage/detail", body_full)
print_result("Storage Detail", "/v1/device/household/storage/detail", body_full, res, "v1")
if is_ok(res):
    device_model = (res.get("data") or {}).get("deviceModelName", device_model)

res = api_v1("/v1/device/storage/list", body_full)
print_result("Storage Liste [workStatus]", "/v1/device/storage/list", body_full, res, "v1")

res = api_v1("/v1/station/info", body_sn)
print_result("Anlageninfo", "/v1/station/info", body_sn, res, "v1")

# ── v1: Echtzeit Master ───────────────────────────────────────────────────────
res = api_v1("/v1/device/realTime/data", body_full)
print_result("Echtzeit Master", "/v1/device/realTime/data", body_full, res, "v1")
rt = get_rt_points(res)
analyze_rt_points(rt, "Master (v1)")

sub_raw = rt.get("SUB", "")
print(f"► Point 400 (Batterieanzahl): {rt.get('400','?')}")
print(f"► Point SUB (Sub-Module):     {sub_raw!r}")

sub_sns, bdu_sns = [], []
if sub_raw:
    candidates = [s.strip() for s in str(sub_raw).split(",") if s.strip()]
    bdu_sns  = [s for s in candidates if re.search(r'-BDU-\d+$', s)]
    filtered = [s for s in candidates
                if not s.endswith(("-BMS","-BDU")) and not re.search(r'-BDU-\d+$', s)]
    if len(filtered) > 1:
        sub_sns = filtered
        print(f"► {len(sub_sns)} parallele Sub-Module: {sub_sns}")
    elif len(filtered) == 1:
        print(f"► 1 Sub-Modul ({filtered[0]}) — kein separater v1-Abruf (Einzelmodul)")
print()

# ── v1: Leistungsdaten ────────────────────────────────────────────────────────
body_power = {"pageNo": 1, "pageSize": 3, "deviceSn": device_sn}
if dongle_sn: body_power["collectorSn"] = dongle_sn
res = api_v1("/v1/device/getLastPowerDataBySn", body_power)
print_result("Letzte Leistungsdaten", "/v1/device/getLastPowerDataBySn", body_power, res, "v1")

# ── v1: Sub-Module ────────────────────────────────────────────────────────────
for sn in sub_sns:
    mb = {"deviceSn": sn, "collectorSn": dongle_sn} if dongle_sn else {"deviceSn": sn}
    res = api_v1("/v1/device/realTime/data", mb)
    print_result(f"Echtzeit Sub-Modul {sn}", "/v1/device/realTime/data", mb, res, "v1")
    analyze_rt_points(get_rt_points(res), f"Sub-Modul {sn}")

for sn in bdu_sns:
    mb = {"deviceSn": sn, "collectorSn": dongle_sn} if dongle_sn else {"deviceSn": sn}
    res = api_v1("/v1/device/realTime/data", mb)
    pts = get_rt_points(res)
    if pts:
        analyze_rt_points(pts, f"BDU Sub-Modul {sn}")
    else:
        print(f"⚠️  BDU {sn}: Keine Daten")

# ── v1: Weitere Endpunkte ─────────────────────────────────────────────────────
res = api_v1("/v1/device/getLastRunningDataBySn", body_sn)
print_result("Letzte Betriebsdaten", "/v1/device/getLastRunningDataBySn", body_sn, res, "v1")
analyze_running_data(res)

for label, path, body in [
    ("Firmware-Version",    "/v1/device/checkVersion",  body_full),
    ("Alarm-/Fehlerliste",  "/v1/alarm/query",          body_full),
]:
    res = api_v1(path, body)
    print_result(label, path, body, res, "v1")

# ═══════════════════════════════════════════════════════════════════════════════
# v2 TESTS
# ═══════════════════════════════════════════════════════════════════════════════
print()
print(SEP)
print(f"  🆕 v2 API TESTS")
print(f"  Domain: {API_BASE_V2}")
print(f"  Gerät:  {device_sn}  [{device_model}]")
print(SEP)
print()
print("  Hinweis: v2-Verfügbarkeit hängt von Geräte-Serie UND Region ab.")
print("  Serien mit v2-Dokumentation: LV-Battery, HV-Battery, Junior Box,")
print("  Cygni HA/HS, HT-A/LS, AquaVolt/SolarCube")
print()

# ── v2 SN-Varianten ermitteln ─────────────────────────────────────────────────
# v1 verwendet z.B. "R07E87466813079E-BMS", v2 erwartet ggf. nur "R07E87466813079E"
# Wir testen beide Varianten und merken uns die funktionierende.
v2_sn_candidates = [device_sn]
# Füge SN ohne Suffix hinzu wenn Suffix vorhanden (z.B. -BMS, -BDU, -INV)
sn_base = re.sub(r'-(BMS|BDU|INV|EMS)$', '', device_sn)
if sn_base != device_sn:
    v2_sn_candidates.insert(0, sn_base)  # ohne Suffix zuerst testen
# Dongle-SN als weitere Variante
if dongle_sn and dongle_sn not in v2_sn_candidates:
    v2_sn_candidates.append(dongle_sn)

print(f"  SN-Varianten für v2-Test: {v2_sn_candidates}")
print()

# Teste GetDeviceInfBySN mit allen Varianten um die richtige SN zu finden
v2_sn = device_sn  # Fallback
for candidate in v2_sn_candidates:
    probe = api_v2("/v2/GetDeviceInfBySN", {"deviceSn": candidate})
    if is_ok(probe):
        v2_sn = candidate
        print(f"  ✅ v2 SN-Format gefunden: '{v2_sn}'")
        break
else:
    print(f"  ⚠️  Alle SN-Varianten gaben Fehler — v2 möglicherweise nicht aktiviert.")
    print(f"     Verwende '{v2_sn}' für alle weiteren Tests.")
print()

body_sn_v2   = {"deviceSn": v2_sn}
alarm_body_v2 = {"deviceSn": v2_sn, "pageNum": 1, "pageSize": 20}

v2_results = {}

# GetDeviceList (alle Serien außer LV/HV-pure)
res = api_v2("/v2/GetDeviceList", {})
print_result("Geräteliste", "/v2/GetDeviceList", {}, res, "v2")
v2_results["devlist"] = analyze_v2_device_list(res)

# GetDeviceInfBySN (alle Serien)
res = api_v2("/v2/GetDeviceInfBySN", body_sn_v2)
print_result("Geräteinformationen", "/v2/GetDeviceInfBySN", body_sn_v2, res, "v2")
v2_results["device"] = analyze_v2_device_info(res)

# GetRealTimeDataBySN (alle Serien — Hauptendpunkt)
res = api_v2("/v2/GetRealTimeDataBySN", body_sn_v2)
print_result("Echtzeit-Daten", "/v2/GetRealTimeDataBySN", body_sn_v2, res, "v2")
v2_results["rt"] = analyze_v2_realtime(res, device_model)

# GetAlarmInfBySN (alle Serien)
res = api_v2("/v2/GetAlarmInfBySN", alarm_body_v2)
print_result("Alarm-Informationen", "/v2/GetAlarmInfBySN", alarm_body_v2, res, "v2")
v2_results["alarm"] = analyze_v2_alarm(res)

# GetParallelInfBySN (LV-Battery, Cygni, HT-A)
res = api_v2("/v2/GetParallelInfBySN", body_sn_v2)
print_result("Parallel-Pack Daten", "/v2/GetParallelInfBySN", body_sn_v2, res, "v2")
v2_results["parallel"] = analyze_v2_parallel(res)

# GetStatusInfBySN (Cygni, HT-A, AquaVolt)
res = api_v2("/v2/GetStatusInfBySN", body_sn_v2)
print_result("Gerätestatus", "/v2/GetStatusInfBySN", body_sn_v2, res, "v2")
v2_results["status"] = analyze_v2_status(res)

# GetTotalEnergyDataBySN (Cygni, HT-A, AquaVolt)
res = api_v2("/v2/GetTotalEnergyDataBySN", body_sn_v2)
print_result("Energie-Statistiken", "/v2/GetTotalEnergyDataBySN", body_sn_v2, res, "v2")
v2_results["energy"] = analyze_v2_total_energy(res)

# ── Zusammenfassung ───────────────────────────────────────────────────────────
print_summary(v2_results, device_model)
