import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------- Farm ----------
class FarmBase(BaseModel):
    owner_name: str
    farm_name: str
    address: str
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_pyeong: float = 0
    area_m2: float = 0
    facility_type: str = "노지"
    cultivation_year: int = 1
    phone: Optional[str] = None
    memo: Optional[str] = None


class FarmCreate(FarmBase):
    pass


class FarmUpdate(BaseModel):
    owner_name: Optional[str] = None
    farm_name: Optional[str] = None
    address: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_pyeong: Optional[float] = None
    area_m2: Optional[float] = None
    facility_type: Optional[str] = None
    cultivation_year: Optional[int] = None
    phone: Optional[str] = None
    memo: Optional[str] = None


class FarmOut(FarmBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: dt.datetime


# ---------- WorkLog ----------
class WorkLogBase(BaseModel):
    farm_id: int
    work_date: Optional[dt.date] = None
    work_area_m2: float = 0
    content: str


class WorkLogCreate(WorkLogBase):
    pass


class WorkLogOut(WorkLogBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    photo_path: Optional[str] = None
    created_at: dt.datetime
    farm_name: Optional[str] = None


# ---------- Diagnosis ----------
class TreatmentItem(BaseModel):
    product_name: str
    active_ingredient: str
    usage: str
    note: Optional[str] = None


class DiagnosisCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farm_id: int
    farm_name: Optional[str] = None
    diagnosis_type: str
    crop_name: str
    occurrence_date: dt.date
    photo_path: Optional[str] = None

    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    photo_taken_at: Optional[dt.datetime] = None

    weather_temp_c: Optional[float] = None
    weather_humidity_percent: Optional[float] = None
    weather_rainfall_mm: Optional[float] = None
    weather_wind_ms: Optional[float] = None
    weather_source: Optional[str] = None

    ai_disease_name: Optional[str] = None
    ai_disease_name_en: Optional[str] = None
    ai_symptoms: Optional[str] = None
    ai_confidence: Optional[float] = None
    eco_treatments: List[TreatmentItem] = []
    chemical_treatments: List[TreatmentItem] = []
    ai_source: Optional[str] = None

    status: str
    created_at: dt.datetime


# ---------- Notification ----------
class NotificationCreate(BaseModel):
    farm_id: int
    diagnosis_id: Optional[int] = None
    title: str
    message: str
    recommended_product: Optional[str] = None
    sent_by: str = "관리자"


class NotificationOut(NotificationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: dt.datetime
    farm_name: Optional[str] = None


# ---------- Stats ----------
class TopPest(BaseModel):
    name: str
    count: int


class MonthlyCount(BaseModel):
    month: str
    count: int


class FarmStatCount(BaseModel):
    farm_id: int
    farm_name: str
    count: int


class StatsSummary(BaseModel):
    total_farms: int
    total_work_logs: int
    total_diagnoses: int
    diagnoses_by_type: dict
    top_pests: List[TopPest]
    monthly_diagnoses: List[MonthlyCount]
    diagnoses_by_farm: List[FarmStatCount]
    ai_vs_actual: dict
