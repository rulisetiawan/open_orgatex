"""
Typeconf IW Service
Decodes and translates SETEX Controller IW Registers (Object 1025 / Info Words)
using each machine's specific TYPECONF.CNF configuration and linear calibration formula.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("orgatex.typeconf_iw")

# Base directories to search for machine specific TYPECONF configurations
_SEARCH_PATHS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../WORKSPACE_PROGRAM_MESIN")),
    "/app/sc777ce_root/WORKSPACE_PROGRAM_MESIN",
    "/WORKSPACE_PROGRAM_MESIN",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
]

_DEFAULT_MAP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/typeconf_iw_map_default.json"))

# In-memory cache for fast sub-millisecond lookups
_CACHE_IW_MAPS: Dict[str, Dict[str, Any]] = {}

class TypeconfIwService:
    @classmethod
    def get_machine_iw_map(cls, machine_no: str) -> Dict[str, Dict[str, Any]]:
        clean_mach = str(machine_no or "").strip().upper()
        if clean_mach in _CACHE_IW_MAPS:
            return _CACHE_IW_MAPS[clean_mach]

        # Look for machine specific typeconf_iw_map.json
        folder_names = [f"MESIN_{clean_mach}", clean_mach]
        for base in _SEARCH_PATHS:
            for fn in folder_names:
                candidate = os.path.join(base, fn, "02_CONFIG_SIAP_PAKAI", "typeconf_iw_map.json")
                if os.path.exists(candidate):
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            _CACHE_IW_MAPS[clean_mach] = data
                            logger.info(f"Loaded custom TYPECONF IW map for {clean_mach} from {candidate} ({len(data)} registers)")
                            return data
                    except Exception as e:
                        logger.warning(f"Failed to load {candidate}: {e}")

        # Fallback to default map
        if os.path.exists(_DEFAULT_MAP_PATH):
            try:
                with open(_DEFAULT_MAP_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _CACHE_IW_MAPS[clean_mach] = data
                    return data
            except Exception as e:
                logger.error(f"Failed to load default IW map: {e}")

        return {}

    UNIT_NORMALIZATION = {
        "dak": "min",
        "dk": "min",
        "dak.": "min",
        "dk.": "min",
        "m/dak": "m/min",
        "m/dk": "m/min",
        "d/dak": "rpm",
        "d/dk": "rpm",
        "Lt": "L",
        "lt": "L",
        "LT": "L",
        "Bar": "bar",
        "%!": "%",
        ".ZG": "",
        ".zg": "",
    }

    @classmethod
    def convert_register(cls, machine_no: str, index: int, raw_value: int) -> Dict[str, Any]:
        """
        Converts a raw uint16 register value to engineering units using the machine's TYPECONF calibration.
        Formula: x1 + (raw_value - y1) * (x2 - x1) / (y2 - y1)
        """
        catalog = cls.get_machine_iw_map(machine_no)
        idx_key = str(index)
        meta = catalog.get(idx_key)

        if not meta:
            return {
                "index": index,
                "name": f"IW {index}",
                "unit": "",
                "raw_val": raw_value,
                "conv_val": float(raw_value),
                "formatted": str(raw_value)
            }

        x1 = float(meta.get("x1", 0.0))
        x2 = float(meta.get("x2", 1.0))
        y1 = float(meta.get("y1", 0.0))
        y2 = float(meta.get("y2", 1.0))
        digits_after = int(meta.get("digits_after", 0))

        if abs(y2 - y1) > 0.0001:
            conv = x1 + (float(raw_value) - y1) * (x2 - x1) / (y2 - y1)
        else:
            conv = float(raw_value)

        raw_unit = meta.get("unit", "").strip()
        unit = cls.UNIT_NORMALIZATION.get(raw_unit, raw_unit)
        name = meta.get("name", f"IW {index}")

        # Formatting
        if digits_after > 0:
            formatted = f"{conv:.{digits_after}f}"
        elif conv.is_integer():
            formatted = f"{int(conv)}"
        else:
            formatted = f"{conv:.1f}"

        if raw_unit in (".ZG", ".zg") or name.lower() == "active tank" or index == 39:
            unit = ""
            formatted = f"Tank {int(conv)}" if conv > 0 else "-"
        elif unit:
            formatted = f"{formatted} {unit}"

        return {
            "index": index,
            "name": name,
            "unit": unit,
            "raw_val": raw_value,
            "conv_val": round(conv, 2),
            "formatted": formatted
        }
