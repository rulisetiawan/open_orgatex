"""
OpenOrgaTEX SETEX Alarm Catalog & Explanation Service
Resolves SETEX 777/797 alarm codes to human-readable titles and descriptions
from each machine's decoded CONFTEXT.CNF (conftext_aligned.json -> Cat_8_Grp_0),
with automatic fallback to baseline conftext_aligned.json and system codes.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger("orgatex.alarm_catalog")

SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(SERVICES_DIR, ".."))
BACKEND_DATA_DIR = os.path.join(BACKEND_DIR, "data")
DA_TEX_ROOT = (
    "/app/sc777ce_root"
    if os.path.isdir("/app/sc777ce_root/WORKSPACE_PROGRAM_MESIN")
    else os.path.abspath(os.path.join(BACKEND_DIR, "..", ".."))
)
WORKSPACE_BASE = os.path.join(DA_TEX_ROOT, "WORKSPACE_PROGRAM_MESIN")
BASELINE_CONFTEXT = os.path.join(BACKEND_DATA_DIR, "conftext_aligned.json")

# System / controller-level codes not present in CONFTEXT Cat_8_Grp_0
SYSTEM_ALARM_FALLBACK: Dict[int, Dict[str, str]] = {
    0: {
        "title": "Alarm Normal / Cleared",
        "detail": "Tidak ada alarm aktif pada kontroler.",
        "severity": "INFO",
    },
    20: {
        "title": "Operator Confirmation Required",
        "detail": "Menunggu konfirmasi operator pada HMI.",
        "severity": "WARNING",
    },
    256: {
        "title": "Call-Off / Operator Intervention Request",
        "detail": "Permintaan call-off atau intervensi operator.",
        "severity": "WARNING",
    },
    1548: {
        "title": "Level Error / Water Level Threshold Exceeded",
        "detail": "Batas level air terlampaui.",
        "severity": "WARNING",
    },
    2060: {
        "title": "Temperature Ramp Rate Deviation Warning",
        "detail": "Deviasi laju pemanasan/pendinginan suhu.",
        "severity": "WARNING",
    },
    2572: {
        "title": "Circulation Differential Pressure Low",
        "detail": "Tekanan diferensial sirkulasi rendah.",
        "severity": "WARNING",
    },
    3851: {
        "title": "Dye Kitchen Chemical Addition Incomplete",
        "detail": "Penambahan bahan kimia dari dye kitchen belum selesai.",
        "severity": "WARNING",
    },
    4619: {
        "title": "Steam Flow Low / Heating Inefficiency",
        "detail": "Aliran steam rendah / pemanasan tidak efisien.",
        "severity": "WARNING",
    },
    5131: {
        "title": "Dosing Valve Limit Switch Timeout",
        "detail": "Timeout limit switch katup dosing.",
        "severity": "WARNING",
    },
    5643: {
        "title": "Drain Cycle Timeout / Filter Clogged",
        "detail": "Timeout siklus drain atau filter tersumbat.",
        "severity": "WARNING",
    },
    5899: {
        "title": "Program Hold / Operator Pause",
        "detail": "Program ditahan (hold/pause) oleh operator.",
        "severity": "INFO",
    },
}

_CRITICAL_KEYWORDS = (
    "emergency",
    "e-stop",
    "not-aus",
    "overload",
    "overtemp",
    "overpressure",
    "interlock",
    "safety",
    "trip",
    "thermic",
    "motor protection",
    "pump fault",
)


def _clean_conftext_str(raw: Optional[str]) -> str:
    """Removes binary decompression artifacts (e.g. control bytes \\x01...) from CONFTEXT strings."""
    if not raw:
        return ""
    s = str(raw)
    # Truncate trailing garbage if binary control marker appears (e.g. '\x01')
    ctrl_idx = re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", s)
    if ctrl_idx:
        # Remove the corrupted character immediately preceding \x01 as well if non-ASCII artifact
        prefix = s[: ctrl_idx.start()]
        prefix = re.sub(r"[^\x20-\x7eÄÖÜäöüß°]+$", "", prefix)
        s = prefix
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_machine_folder(machine_no: str) -> str:
    clean = machine_no.strip().upper().replace(" ", "_")
    return clean if clean.startswith("MESIN_") else f"MESIN_{clean}"


def _infer_severity(code: int, text: str) -> str:
    if code == 0:
        return "INFO"
    lower = (text or "").lower()
    if any(kw in lower for kw in _CRITICAL_KEYWORDS):
        return "CRITICAL"
    return "WARNING"


class AlarmCatalog:
    """
    Kamus & penjelas kode alarm SETEX berbasis CONFTEXT.CNF (conftext_aligned.json -> Cat_8_Grp_0).

    Contoh pemakaian:
        catalog = AlarmCatalog(machine_no="1A")
        info = catalog.explain(151)
        print(info["title"], "-", info["detail"])
        print(catalog.get_text(151))
    """

    _CACHE: Dict[str, "AlarmCatalog"] = {}

    def __init__(self, machine_no: Optional[str] = None, conftext_path: Optional[str] = None):
        self.machine_no: Optional[str] = machine_no.strip().upper() if machine_no else None
        self.source_path: Optional[str] = None
        self.source_label: str = "fallback"
        self._entries: Dict[int, Dict[str, str]] = {}
        self._load(conftext_path=conftext_path)

    @classmethod
    def for_machine(cls, machine_no: Optional[str] = None, force_reload: bool = False) -> "AlarmCatalog":
        key = machine_no.strip().upper() if machine_no else "__BASELINE__"
        if force_reload or key not in cls._CACHE:
            cls._CACHE[key] = cls(machine_no=machine_no)
        return cls._CACHE[key]

    @classmethod
    def clear_cache(cls) -> None:
        cls._CACHE.clear()

    def _resolve_conftext_path(self, explicit_path: Optional[str] = None) -> Optional[str]:
        candidates: List[str] = []
        if explicit_path:
            candidates.append(explicit_path)

        if self.machine_no:
            folder = _normalize_machine_folder(self.machine_no)
            candidates.append(
                os.path.join(WORKSPACE_BASE, folder, "02_CONFIG_SIAP_PAKAI", "conftext_aligned.json")
            )
            # Also check open_orgatex/backend/data/machine_configs/<folder>/decoded/conftext_aligned.json
            candidates.append(
                os.path.join(BACKEND_DATA_DIR, "machine_configs", folder, "decoded", "conftext_aligned.json")
            )

        candidates.append(BASELINE_CONFTEXT)

        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    def _load(self, conftext_path: Optional[str] = None) -> None:
        resolved = self._resolve_conftext_path(explicit_path=conftext_path)
        self._entries = {}
        if not resolved:
            logger.warning("conftext_aligned.json tidak ditemukan; menggunakan SYSTEM_ALARM_FALLBACK.")
            return

        try:
            with open(resolved, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Gagal membaca {resolved}: {e}")
            return

        cat8 = data.get("Cat_8_Grp_0", [])
        grouped: Dict[int, Dict[int, Dict[str, str]]] = {}
        for row in cat8:
            item_no = row.get("item")
            rec_type = row.get("type", 0)
            if item_no is None:
                continue
            try:
                code = int(item_no)
            except (TypeError, ValueError):
                continue
            grouped.setdefault(code, {})[int(rec_type)] = {
                "en": _clean_conftext_str(row.get("en")),
                "de": _clean_conftext_str(row.get("de")),
            }

        for code, types_map in grouped.items():
            title_en = types_map.get(0, {}).get("en", "")
            title_de = types_map.get(0, {}).get("de", "")
            line1_en = types_map.get(3, {}).get("en", "")
            line2_en = types_map.get(4, {}).get("en", "")
            line1_de = types_map.get(3, {}).get("de", "")
            line2_de = types_map.get(4, {}).get("de", "")

            detail_en = " ".join(p for p in (line1_en, line2_en) if p).strip()
            detail_de = " ".join(p for p in (line1_de, line2_de) if p).strip()

            self._entries[code] = {
                "title_en": title_en,
                "detail_en": detail_en,
                "title_de": title_de,
                "detail_de": detail_de,
            }

        self.source_path = resolved
        if self.machine_no and _normalize_machine_folder(self.machine_no) in resolved:
            self.source_label = f"{_normalize_machine_folder(self.machine_no)}/conftext_aligned.json (Cat_8_Grp_0)"
        else:
            self.source_label = "baseline/conftext_aligned.json (Cat_8_Grp_0)"

    def explain(self, alarm_code: Union[int, str], lang: str = "en") -> Dict[str, Any]:
        """
        Mengembalikan penjelasan lengkap untuk satu kode alarm.

        Parameters:
            alarm_code: Kode alarm (int atau string numerik, misal 151 atau "151").
            lang: Bahasa utama ("en" atau "de"). Default "en".

        Returns:
            Dict berisi alarm_code, found, title, detail, full_text, severity, source,
            serta teks versi Inggris & Jerman (title_en, detail_en, title_de, detail_de).
        """
        lang_clean = (lang or "en").strip().lower()
        if lang_clean not in ("en", "de"):
            lang_clean = "en"

        try:
            code_int = int(str(alarm_code).strip())
        except (TypeError, ValueError):
            return {
                "alarm_code": alarm_code,
                "found": False,
                "title": f"Alarm Code #{alarm_code}",
                "detail": "Kode alarm tidak valid.",
                "full_text": f"Alarm Code #{alarm_code}",
                "lang": lang_clean,
                "title_en": "",
                "detail_en": "",
                "title_de": "",
                "detail_de": "",
                "severity": "WARNING",
                "source": "invalid",
            }

        entry = self._entries.get(code_int)
        if entry:
            title_primary = entry.get(f"title_{lang_clean}") or entry.get("title_en") or entry.get("title_de") or ""
            detail_primary = entry.get(f"detail_{lang_clean}") or entry.get("detail_en") or entry.get("detail_de") or ""

            if not title_primary and detail_primary:
                title_primary = detail_primary

            if detail_primary and detail_primary.lower() != title_primary.lower():
                full_text = f"{title_primary} ({detail_primary})"
            else:
                full_text = title_primary or f"Alarm Code #{code_int}"

            return {
                "alarm_code": code_int,
                "found": True,
                "title": title_primary or f"Alarm Code #{code_int}",
                "detail": detail_primary,
                "full_text": full_text,
                "lang": lang_clean,
                "title_en": entry.get("title_en", ""),
                "detail_en": entry.get("detail_en", ""),
                "title_de": entry.get("title_de", ""),
                "detail_de": entry.get("detail_de", ""),
                "severity": _infer_severity(code_int, f"{title_primary} {detail_primary}"),
                "source": self.source_label,
            }

        sys_entry = SYSTEM_ALARM_FALLBACK.get(code_int)
        if sys_entry:
            title = sys_entry["title"]
            detail = sys_entry["detail"]
            return {
                "alarm_code": code_int,
                "found": True,
                "title": title,
                "detail": detail,
                "full_text": title,
                "lang": lang_clean,
                "title_en": title,
                "detail_en": detail,
                "title_de": "",
                "detail_de": "",
                "severity": sys_entry.get("severity", "WARNING"),
                "source": "SYSTEM_ALARM_FALLBACK",
            }

        return {
            "alarm_code": code_int,
            "found": False,
            "title": f"Alarm Code #{code_int}",
            "detail": "",
            "full_text": f"Alarm Code #{code_int}",
            "lang": lang_clean,
            "title_en": "",
            "detail_en": "",
            "title_de": "",
            "detail_de": "",
            "severity": "WARNING",
            "source": "unknown",
        }

    def get_text(self, alarm_code: Union[int, str], lang: str = "en", include_detail: bool = True) -> str:
        """Mengembalikan teks penjelasan ringkas untuk satu kode alarm."""
        info = self.explain(alarm_code, lang=lang)
        if include_detail:
            return info["full_text"]
        return info["title"]

    def list_all(self, lang: str = "en") -> List[Dict[str, Any]]:
        """Mengembalikan seluruh daftar definisi alarm dari Cat_8_Grp_0 terurut berdasarkan kode."""
        return [self.explain(code, lang=lang) for code in sorted(self._entries.keys())]


def explain_alarm(
    alarm_code: Union[int, str],
    machine_no: Optional[str] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Fungsi praktis untuk mendapatkan penjelasan lengkap sebuah kode alarm.

    Contoh:
        explain_alarm(151, machine_no="1A")
    """
    return AlarmCatalog.for_machine(machine_no=machine_no).explain(alarm_code, lang=lang)


def get_alarm_text(
    alarm_code: Union[int, str],
    machine_no: Optional[str] = None,
    lang: str = "en",
    include_detail: bool = True,
) -> str:
    """
    Fungsi praktis untuk mendapatkan string penjelasan sebuah kode alarm.

    Contoh:
        get_alarm_text(1, machine_no="1A")
        -> "AT1 not ready ! (addition tank 1 not ready !)"
    """
    return AlarmCatalog.for_machine(machine_no=machine_no).get_text(
        alarm_code, lang=lang, include_detail=include_detail
    )
