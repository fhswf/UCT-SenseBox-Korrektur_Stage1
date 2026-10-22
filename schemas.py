from pydantic import BaseModel, Field
from typing import Optional

class MeasurementInput(BaseModel):
    quell_id: str = ""
    messzeit_utc: str = ""
    temperature_value: float = 0.0
    
    humidity_value: Optional[float] = 0.0
    pressure_value: Optional[float] = 0.0
    lux_value: Optional[float] = 0.0
    uv_value: Optional[float] = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "quell_id": "SB024",
                "messzeit_utc": "2026-03-01T14:30:00Z",
                "temperature_value": 24.5,
                "humidity_value": 55.2,
                "pressure_value": 1013.2,
                "lux_value": 12500.0,
                "uv_value": 4.1
            }
        }

class PredictionResponse(BaseModel):
    corrected_temperature: float
    success: bool = "False"