import datetime as dt
import random
from typing import Optional

import httpx

from app.config import settings

ONECALL_TIMEMACHINE_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def _seasonal_demo_weather(at: Optional[dt.datetime]) -> dict:
    """API 키가 없거나 호출 실패 시, 계절에 맞는 그럴듯한 기상 데이터를 생성 (데모/오프라인 폴백)."""
    month = (at or dt.datetime.utcnow()).month
    random.seed(f"{month}-{(at or dt.datetime.utcnow()).day}")

    if month in (6, 7, 8):  # 여름 - 인삼 병해 다발기
        temp = round(random.uniform(24, 31), 1)
        humidity = round(random.uniform(75, 95), 1)
        rainfall = round(random.uniform(0, 25), 1)
        wind = round(random.uniform(0.5, 3.5), 1)
    elif month in (3, 4, 5):
        temp = round(random.uniform(12, 22), 1)
        humidity = round(random.uniform(50, 75), 1)
        rainfall = round(random.uniform(0, 10), 1)
        wind = round(random.uniform(1, 4), 1)
    elif month in (9, 10, 11):
        temp = round(random.uniform(10, 20), 1)
        humidity = round(random.uniform(45, 70), 1)
        rainfall = round(random.uniform(0, 8), 1)
        wind = round(random.uniform(1, 4), 1)
    else:
        temp = round(random.uniform(-5, 5), 1)
        humidity = round(random.uniform(30, 55), 1)
        rainfall = 0.0
        wind = round(random.uniform(1, 5), 1)

    return {
        "temp_c": temp,
        "humidity_percent": humidity,
        "rainfall_mm": rainfall,
        "wind_ms": wind,
        "source": "demo",
    }


async def get_weather_at(
    lat: Optional[float],
    lng: Optional[float],
    at: Optional[dt.datetime] = None,
) -> dict:
    """사진 촬영 시점/위치 기준 기상 데이터 조회. 데모 모드이거나 실패 시 시뮬레이션 값 반환."""
    if settings.demo_mode or not settings.openweather_api_key or lat is None or lng is None:
        return _seasonal_demo_weather(at)

    timestamp = int((at or dt.datetime.utcnow()).timestamp())

    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(
                ONECALL_TIMEMACHINE_URL,
                params={
                    "lat": lat,
                    "lon": lng,
                    "dt": timestamp,
                    "appid": settings.openweather_api_key,
                    "units": "metric",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                point = (data.get("data") or [{}])[0]
                rain = point.get("rain", {})
                rainfall = rain.get("1h", 0.0) if isinstance(rain, dict) else 0.0
                return {
                    "temp_c": point.get("temp"),
                    "humidity_percent": point.get("humidity"),
                    "rainfall_mm": rainfall,
                    "wind_ms": point.get("wind_speed"),
                    "source": "openweather_timemachine",
                }
        except httpx.HTTPError:
            pass

        try:
            resp = await client.get(
                CURRENT_WEATHER_URL,
                params={
                    "lat": lat,
                    "lon": lng,
                    "appid": settings.openweather_api_key,
                    "units": "metric",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                rain = data.get("rain", {})
                rainfall = rain.get("1h", 0.0) if isinstance(rain, dict) else 0.0
                return {
                    "temp_c": data.get("main", {}).get("temp"),
                    "humidity_percent": data.get("main", {}).get("humidity"),
                    "rainfall_mm": rainfall,
                    "wind_ms": data.get("wind", {}).get("speed"),
                    "source": "openweather_current",
                }
        except httpx.HTTPError:
            pass

    return _seasonal_demo_weather(at)
