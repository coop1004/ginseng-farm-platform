"""농장의 재배연차 계산 공용 로직. "N년근" 문자열 자체는 어디에도 저장하지 않고,
화면/리포트에 보여줄 때마다 이 함수로 계산한다 - 해가 바뀌어도 값을 수동으로
갱신할 필요가 없다."""
import datetime as dt
from typing import Optional


def compute_cultivation_year(
    start_date: Optional[dt.date], legacy_cultivation_year: Optional[int] = None
) -> int:
    """재배연차 = (오늘 연도 - 정식연도) + 1 (달력 기준 - 1월 1일이 지나면 실제 경과일수와
    무관하게 1년차씩 올라간다). start_date가 없는 예외 케이스(아직 마이그레이션 백필 전이거나
    데이터 누락)에는 레거시 cultivation_year로 폴백하고, 그것도 없으면 1년차로 취급한다."""
    if start_date is not None:
        return (dt.date.today().year - start_date.year) + 1
    if legacy_cultivation_year is not None:
        return legacy_cultivation_year
    return 1
