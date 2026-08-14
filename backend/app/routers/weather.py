import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.deps import get_current_admin, get_current_household_id
from app.services.weather_collector import collect_daily_weather_for_all_farms

router = APIRouter(prefix="/api/admin/weather", tags=["weather"])
farmer_router = APIRouter(prefix="/api/weather", tags=["weather"])


def _to_weather_out(r: models.WeatherRecord) -> dict:
    return {
        "id": r.id,
        "farm_id": r.farm_id,
        "farm_name": r.farm.farm_name if r.farm else None,
        "record_date": r.record_date,
        "temp_c": r.temp_c,
        "humidity_percent": r.humidity_percent,
        "rainfall_mm": r.rainfall_mm,
        "wind_ms": r.wind_ms,
        "source": r.source,
    }


def _check_cron_secret(x_cron_secret: Optional[str] = Header(None)):
    """CRON_SECRET이 설정되어 있으면, 배치 수집 엔드포인트는 이 값이 일치해야 호출 가능
    (누구나 호출 가능한 공개 엔드포인트라 무제한 외부 API 호출을 유발하지 않도록 보호)."""
    if settings.cron_secret and x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=401, detail="유효하지 않은 요청입니다.")


@router.post("/collect", response_model=schemas.WeatherCollectResult, dependencies=[Depends(_check_cron_secret)])
async def collect_weather(db: Session = Depends(get_db)):
    """등록된 전체 농장의 오늘자 기상 스냅샷을 수집한다. 매일 1회 외부 스케줄러(예: GitHub Actions
    cron)가 호출하도록 구성한다. 이미 오늘 수집했다면 안전하게 건너뛴다."""
    result = await collect_daily_weather_for_all_farms(db)
    return result


@router.get("/history", response_model=List[schemas.WeatherRecordOut])
def get_weather_history(
    farm_id: Optional[int] = None,
    days: int = 30,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """축적된 일별 기상 기록 조회 (상관관계 분석/그래프용)."""
    since = dt.date.today() - dt.timedelta(days=days)
    query = db.query(models.WeatherRecord).filter(models.WeatherRecord.record_date >= since)
    if farm_id:
        query = query.filter(models.WeatherRecord.farm_id == farm_id)
    records = query.order_by(models.WeatherRecord.record_date.desc()).all()
    return [_to_weather_out(r) for r in records]


@farmer_router.get("/history", response_model=List[schemas.WeatherRecordOut])
def get_my_weather_history(
    farm_id: Optional[int] = None,
    days: int = 30,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """농가 본인 소유 농장의 축적된 기상 기록 조회."""
    since = dt.date.today() - dt.timedelta(days=days)
    query = (
        db.query(models.WeatherRecord)
        .join(models.Farm, models.WeatherRecord.farm_id == models.Farm.id)
        .filter(models.Farm.household_id == household_id)
        .filter(models.WeatherRecord.record_date >= since)
    )
    if farm_id:
        query = query.filter(models.WeatherRecord.farm_id == farm_id)
    records = query.order_by(models.WeatherRecord.record_date.desc()).all()
    return [_to_weather_out(r) for r in records]
