import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name_kr: str
    name_en: Optional[str] = None
    icon_emoji: Optional[str] = None
    is_active: bool
    is_sample_data: bool
    sort_order: int


# ---------- Auth / Household ----------
class RegisterNewHousehold(BaseModel):
    phone: str
    password: str
    name: str
    household_name: str  # 새로 만들 농가명
    crop_ids: List[int] = []  # 등록할 재배 작물(복수 선택 가능). 생략 시(구버전 클라이언트) 인삼으로 기본 등록


class RegisterJoinHousehold(BaseModel):
    phone: str
    password: str
    name: str
    join_code: str  # 기존 농가에 합류할 때 입력하는 코드


class LoginRequest(BaseModel):
    phone: str
    password: str


class HouseholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    join_code: str
    crops: List[CropOut] = []  # 이 농가가 등록한(=화면에 노출할) 작물 목록


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone: str
    name: str


class MeResponse(BaseModel):
    user: UserOut
    household: HouseholdOut
    members: List[UserOut] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    household: HouseholdOut


# ---------- Admin Auth ----------
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    name: str
    is_protected: bool = False


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminUserOut


class AdminChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminRegisterRequest(BaseModel):
    username: str
    password: str
    name: str


# ---------- Consultant Auth ----------
class ConsultantLoginRequest(BaseModel):
    username: str
    password: str


class ConsultantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    name: str
    is_active: bool = True


class ConsultantTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    consultant: ConsultantOut


class ConsultantRegisterRequest(BaseModel):
    username: str
    password: str
    name: str


class ConsultantStatsOut(BaseModel):
    household_count: int
    farm_count: int
    total_diagnosis_count: int
    my_diagnosis_count: int
    my_final_diagnosis_count: int
    my_comment_count: int
    farmer_feedback_correct: int
    farmer_feedback_incorrect: int
    farmer_feedback_pending: int


# ---------- Crop ----------
class GrowthStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    crop_id: int
    name_kr: str
    sort_order: int
    description: Optional[str] = None


# ---------- Farm ----------
class FarmBase(BaseModel):
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
    # 생략 시 서버가 인삼으로 기본 채움(구버전 모바일 클라이언트 호환)
    crop_id: Optional[int] = None
    growth_stage_id: Optional[int] = None


class FarmUpdate(BaseModel):
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
    crop_id: Optional[int] = None
    growth_stage_id: Optional[int] = None


class FarmOut(FarmBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    household_id: int
    household_name: Optional[str] = None
    crop_id: Optional[int] = None
    crop_name: Optional[str] = None
    growth_stage_id: Optional[int] = None
    growth_stage_name: Optional[str] = None
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
    photo_paths: List[str] = []

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
    farmer_confirmed_correct: Optional[bool] = None

    final_disease_name: Optional[str] = None
    final_diagnosis_source: Optional[str] = None
    final_diagnosis_note: Optional[str] = None
    final_diagnosis_by: Optional[str] = None
    final_diagnosis_at: Optional[dt.datetime] = None

    # 진단이 속한 농장의 작물이 실 학습 데이터 없는 파일럿(샘플) 작물인지 —
    # 모바일 진단 결과 화면의 "베타/프로토타입 모델" 안내 문구 표시 기준.
    crop_is_sample_data: bool = False

    # 이 진단을 최초 등록한 주체 - household(농가 본인) 또는 consultant(컨설턴트 현장 방문 등록).
    created_by_type: str = "household"
    created_by_consultant_name: Optional[str] = None

    created_at: dt.datetime


class DiagnosisFeedbackRequest(BaseModel):
    correct: bool


class DiagnosisFinalRequest(BaseModel):
    disease_name: str
    note: Optional[str] = None


class DiagnosisCommentCreate(BaseModel):
    body: str


class DiagnosisCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    diagnosis_id: int
    author_type: str
    author_name: str
    body: str
    created_at: dt.datetime


class AdminDiagnosisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farm_id: int
    farm_name: Optional[str] = None
    household_name: Optional[str] = None
    region: Optional[str] = None
    diagnosis_type: str
    crop_name: str
    occurrence_date: dt.date
    photo_path: Optional[str] = None
    photo_paths: List[str] = []
    ai_disease_name: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_source: Optional[str] = None
    status: str
    farmer_confirmed_correct: Optional[bool] = None
    final_disease_name: Optional[str] = None
    final_diagnosis_source: Optional[str] = None
    final_diagnosis_note: Optional[str] = None
    final_diagnosis_by: Optional[str] = None
    final_diagnosis_at: Optional[dt.datetime] = None
    created_by_type: str = "household"
    created_by_consultant_name: Optional[str] = None
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
    broadcast_group: Optional[str] = None


class NotificationBroadcastRequest(BaseModel):
    target_type: str  # "all" | "region" | "farms"
    region: Optional[str] = None
    farm_ids: Optional[List[int]] = None
    title: str
    message: str
    recommended_product: Optional[str] = None
    sent_by: str = "관리자"


class NotificationBroadcastResult(BaseModel):
    broadcast_group: str
    sent_count: int
    farm_ids: List[int]


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
    total_households: Optional[int] = None
    total_work_logs: int
    total_diagnoses: int
    diagnoses_by_type: dict
    top_pests: List[TopPest]
    monthly_diagnoses: List[MonthlyCount]
    diagnoses_by_farm: List[FarmStatCount]
    ai_vs_actual: dict


# ---------- Weather ----------
class WeatherRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farm_id: int
    farm_name: Optional[str] = None
    record_date: dt.date
    temp_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    rainfall_mm: Optional[float] = None
    wind_ms: Optional[float] = None
    source: Optional[str] = None


class WeatherCollectResult(BaseModel):
    collected: int
    skipped_existing: int
    skipped_no_location: int
    total_farms: int


# ---------- Treatment Reference (CMS) ----------
class TreatmentReferenceCreate(BaseModel):
    crop_id: int
    type: str  # 병해 / 해충 / 생리장애
    name_kr: str
    name_en: Optional[str] = None
    symptoms: Optional[str] = None
    cause: Optional[str] = None
    favorable_temp_min: Optional[float] = None
    favorable_temp_max: Optional[float] = None
    favorable_humidity_min: Optional[float] = None
    favorable_rainfall_note: Optional[str] = None
    photo_path: Optional[str] = None
    eco_treatments: List[TreatmentItem] = []
    chemical_treatments: List[TreatmentItem] = []
    is_active: bool = True


class TreatmentReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    crop_id: Optional[int] = None
    crop_name: str
    type: str
    name_kr: str
    name_en: Optional[str] = None
    symptoms: Optional[str] = None
    cause: Optional[str] = None
    favorable_temp_min: Optional[float] = None
    favorable_temp_max: Optional[float] = None
    favorable_humidity_min: Optional[float] = None
    favorable_rainfall_note: Optional[str] = None
    photo_path: Optional[str] = None
    is_sample_data: bool = False
    eco_treatments: List[TreatmentItem] = []
    chemical_treatments: List[TreatmentItem] = []
    is_active: bool
    updated_by: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime


class AgriMaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    active_ingredient: Optional[str] = None
    default_usage: Optional[str] = None
    note: Optional[str] = None
    is_active: bool


# ---------- Community ----------
class CommunityPostCreate(BaseModel):
    title: str
    body: Optional[str] = None
    crop_id: Optional[int] = None
    visibility: str = "public"  # public / consultant_scope


class CommunityDiagnosisShareCreate(BaseModel):
    diagnosis_id: int
    title: str
    body: Optional[str] = None
    visibility: str = "public"


class CommunityCommentCreate(BaseModel):
    body: str


class CommunityReportCreate(BaseModel):
    reason: Optional[str] = None


class CommunityStatusUpdate(BaseModel):
    status: str  # visible / hidden


class CommunityCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    author_type: str
    author_name: str
    body: str
    status: str
    created_at: dt.datetime


class CommunityPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: Optional[str] = None
    photo_paths: List[str] = []
    kind: str
    crop_id: Optional[int] = None
    crop_name: Optional[str] = None
    diagnosis_id: Optional[int] = None
    visibility: str
    author_type: str
    author_name: str
    status: str
    comment_count: int = 0
    created_at: dt.datetime


class CommunityPostDetailOut(CommunityPostOut):
    comments: List[CommunityCommentOut] = []


class CommunityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    reporter_household_id: int
    reason: Optional[str] = None
    created_at: dt.datetime
