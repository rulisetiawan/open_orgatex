"""
Recipes & Lab Automation Route
Folder write operations are disabled (Read-Only Mode)
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import os
import json

router = APIRouter(prefix="/api/recipes", tags=["Recipes"])

RECIPES_PATH = os.path.abspath("./open_orgatex/backend/data/recipes.json")
os.makedirs(os.path.dirname(RECIPES_PATH), exist_ok=True)

class ChemicalItem(BaseModel):
    name: str
    code: str
    amount: float
    unit: str = "g/l"
    tank: int = 1

class RecipeSchema(BaseModel):
    id: Optional[str] = None
    name: str
    chemicals: List[ChemicalItem]

@router.get("", include_in_schema=False)
@router.get("/")
def get_recipes():
    if os.path.exists(RECIPES_PATH):
        try:
            with open(RECIPES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {
            "id": "rec-1",
            "name": "Reactive Blue Cotton 60C",
            "chemicals": [
                {"name": "Reactive Blue BF", "code": "DYE-BL-01", "amount": 25.0, "unit": "g/l", "tank": 2},
                {"name": "Glauber Salt", "code": "SALT-GL-01", "amount": 50.0, "unit": "g/l", "tank": 1},
                {"name": "Soda Ash", "code": "ALK-SA-01", "amount": 15.0, "unit": "g/l", "tank": 1}
            ]
        }
    ]

@router.post("/export-la")
def export_la_dosing_order(batch_no: str, machine_name: str, water_liters: float, items: List[ChemicalItem]):
    """
    Computes dosing order calculations.
    NOTE: Writing .DOS to shared folder is DISABLED in read-only mode.
    """
    tank1 = [it.dict() for it in items if it.tank == 1]
    tank2 = [it.dict() for it in items if it.tank == 2]

    return {
        "status": "calculated_virtual",
        "write_mode": "DISABLED (Read-Only Mode Active)",
        "message": f"Kalkulasi Dosing untuk batch {batch_no} selesai. Penulisan ke folder sharing /OT/DOSING dinonaktifkan.",
        "batch_no": batch_no,
        "machine_name": machine_name,
        "water_liters": water_liters,
        "tank_1_items": tank1,
        "tank_2_items": tank2
    }
