import datetime as dt

from sqlalchemy.orm import Session

from app import models
from app.services import weather_service


async def collect_daily_weather_for_all_farms(db: Session) -> dict:
    """등록된 모든 농장의 오늘자 기상 스냅샷을 수집해 WeatherRecord로 적재한다.

    진단이 발생했는지 여부와 무관하게 매일 쌓이므로, 추후 병해충 발생일과 그 이전
    기상 패턴(고온다습 지속일수 등)을 비교하는 분석/예측에 사용할 수 있다.
    이미 오늘자 기록이 있는 농장은 건너뛴다(멱등 - 하루에 여러 번 호출해도 안전).
    """
    today = dt.date.today()
    farms = db.query(models.Farm).all()

    collected = 0
    skipped_existing = 0
    skipped_no_location = 0

    for farm in farms:
        if farm.latitude is None or farm.longitude is None:
            skipped_no_location += 1
            continue

        exists = (
            db.query(models.WeatherRecord)
            .filter(models.WeatherRecord.farm_id == farm.id, models.WeatherRecord.record_date == today)
            .first()
        )
        if exists:
            skipped_existing += 1
            continue

        weather = await weather_service.get_weather_at(farm.latitude, farm.longitude, dt.datetime.utcnow())
        db.add(
            models.WeatherRecord(
                farm_id=farm.id,
                record_date=today,
                temp_c=weather.get("temp_c"),
                humidity_percent=weather.get("humidity_percent"),
                rainfall_mm=weather.get("rainfall_mm"),
                wind_ms=weather.get("wind_ms"),
                source=weather.get("source"),
            )
        )
        collected += 1

    db.commit()

    return {
        "collected": collected,
        "skipped_existing": skipped_existing,
        "skipped_no_location": skipped_no_location,
        "total_farms": len(farms),
    }
