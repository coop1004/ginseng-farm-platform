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


class AdministrativeRegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sido: str
    sigungu: str


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
    status: str = "active"
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


class HouseholdDetailOut(BaseModel):
    """관리자 대시보드 농가 상세 패널의 "정보 수정" 폼용 - 농가명과 소속 계정(대표자 등)
    목록을 함께 내려준다."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    join_code: str
    status: str = "active"
    members: List[UserOut] = []


class HouseholdUpdateRequest(BaseModel):
    name: Optional[str] = None


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


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
    role: str = "platform_super"
    organization_id: int


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    org_type: Optional[str] = None


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
    phone: Optional[str] = None
    is_active: bool = True


class ConsultantUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class TempPasswordOut(BaseModel):
    """관리자가 비밀번호를 초기화했을 때, 화면에 한 번만 보여주고 저장하지 않는 임시
    비밀번호. 관리자가 전화로 농가/컨설턴트에 불러주는 용도."""

    temp_password: str


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


class ConsultantRankingItem(BaseModel):
    consultant_id: int
    name: str
    diagnosis_count: int  # 조회 기간 내 등록 건수
    comment_count: int  # 조회 기간 내 코멘트 수
    final_diagnosis_count: int  # 조회 기간 내 본인 최종확정 건수
    feedback_correct: int
    feedback_incorrect: int
    feedback_accuracy_percent: Optional[float] = None  # 일치/(일치+불일치)*100, 피드백 없으면 None
    total_diagnosis_count: int  # 전체 기간 누적(기간과 무관, 참고용)


class ConsultantActivitySummaryOut(BaseModel):
    consultant_count: int
    active_consultant_count: int
    diagnosis_count: int  # 조회 기간 내 전체 컨설턴트 합산 진단 건수
    ranking: List[ConsultantRankingItem]


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


class DiagnosisPhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phase: str
    photo_path: Optional[str] = None
    outcome: Optional[str] = None
    note: Optional[str] = None
    days_since_treatment: Optional[int] = None
    created_at: dt.datetime


class RecentUnresolvedDiagnosisOut(BaseModel):
    id: int
    diagnosis_type: str
    disease_name: Optional[str] = None
    occurrence_date: dt.date
    last_activity_at: dt.datetime


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
    # 초기 사진(phase=initial) + 방제 경과 기록(phase=followup)을 시간순으로 모두 담은
    # 타임라인. photo_paths는 기존 화면 호환을 위해 그대로 두고, 상세화면의 경과 타임라인
    # UI는 이 필드를 쓴다.
    photo_timeline: List[DiagnosisPhotoOut] = []
    latest_followup_outcome: Optional[str] = None

    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    gps_estimated: bool = False
    photo_taken_at: Optional[dt.datetime] = None
    photo_taken_at_estimated: bool = False

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
    # platform_super 관리자가 "all"/"region" 대상으로 보낼 때 반드시 명시해야 하는 대상 조직.
    # org_scoped 관리자는 이 값을 보내도 무시되고 자기 organization_id로 강제된다.
    organization_id: Optional[int] = None
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


class WeatherReliabilitySummary(BaseModel):
    """진단 기록의 weather_source 값 분포 - 촬영 시점 실측치(real_count)와 대체/가상값을
    한눈에 구분하기 위한 집계. 관리자 대시보드 종합 현황 카드용."""

    real_count: int  # openweather_timemachine (촬영 시점 실측)
    current_fallback_count: int  # openweather_current (조회 시점 날씨로 대체됨)
    demo_count: int  # demo 또는 값 없음(구버전 레코드) - 실제 관측치 아님
    unavailable_count: int  # unavailable (위치 정보 자체가 없어 날씨 미기록)
    total_diagnoses: int
    demo_mode: bool = False  # settings.demo_mode 그대로 - true면 실제 날씨 API를 아예
    # 호출하지 않으므로(weather_service.get_weather_at 참고) 위 집계 자체가 항상
    # 100% 가상 값으로 고정된다. 프런트가 이 값으로 통계 카드 대신 안내문을 보여준다.


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
    weather_reliability: Optional[WeatherReliabilitySummary] = None


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
