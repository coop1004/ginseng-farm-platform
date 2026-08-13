import json
import random
import re
from pathlib import Path
from typing import Optional

from app.config import settings

ECO_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "eco_treatment_db.json"

with open(ECO_DB_PATH, "r", encoding="utf-8") as f:
    ECO_DB = json.load(f)["diseases"]

_TYPE_MAP = {"병해": "병해", "해충": "해충", "생리장애": "생리장애"}

_client = None


def _get_client():
    """google-genai 클라이언트를 지연 초기화한다."""
    global _client
    if _client is not None:
        return _client
    from google import genai

    _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _build_prompt(diagnosis_type: str, crop_name: str, weather: dict) -> str:
    db_context = json.dumps(ECO_DB, ensure_ascii=False, indent=2)
    return f"""당신은 인삼 재배 전문 식물병리학자입니다. 아래 첨부된 작물 피해 부위 사진과 당시 기상 조건, 그리고 회사의 친환경 방제 자재 데이터베이스를 종합적으로 분석하여 진단하세요.

[진단 유형]: {diagnosis_type}
[작물명]: {crop_name}
[촬영 당시 기상 조건]
- 기온: {weather.get('temp_c')}℃
- 습도: {weather.get('humidity_percent')}%
- 강우량: {weather.get('rainfall_mm')}mm
- 풍속: {weather.get('wind_ms')}m/s

[회사 자체 친환경 방제 자재 데이터베이스]
{db_context}

위 데이터베이스에 있는 병해충/생리장애 중 사진 증상 및 기상 조건과 가장 부합하는 항목을 우선적으로 선택하고, 데이터베이스에 없는 증상이면 일반적인 인삼 병해충 지식으로 진단하세요.

다음 JSON 형식으로만 답변하세요 (다른 설명 텍스트 없이 JSON만 출력):
{{
  "disease_name_kr": "병해충/생리장애 한글명",
  "disease_name_en": "영문명",
  "symptoms": "관찰되는 특징 및 증상 설명 (2~3문장)",
  "confidence": 0.0~1.0 사이 확신도,
  "eco_treatments": [
    {{"product_name": "...", "active_ingredient": "...", "usage": "...", "note": "..."}}
  ],
  "chemical_treatments": [
    {{"product_name": "...", "active_ingredient": "...", "usage": "...", "note": "..."}}
  ]
}}
친환경 자재를 반드시 최우선으로 1개 이상 추천하고, 화학적 관리법은 보조 정보로 1개 제공하세요."""


def _parse_json_response(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _demo_diagnose(diagnosis_type: str, weather: dict) -> dict:
    """API 키 미설정/데모 모드일 때 DB 기반으로 그럴듯한 진단 결과를 생성."""
    candidates = [d for d in ECO_DB if d["type"] == diagnosis_type] or ECO_DB

    def score(entry):
        cond = entry.get("favorable_conditions", {})
        s = 0
        temp = weather.get("temp_c")
        if temp is not None and cond.get("temp_range_c"):
            lo, hi = cond["temp_range_c"]
            if lo <= temp <= hi:
                s += 2
        humidity = weather.get("humidity_percent")
        if humidity is not None and humidity >= cond.get("humidity_min_percent", 0):
            s += 1
        return s

    candidates = sorted(candidates, key=score, reverse=True)
    top = candidates[: max(1, min(3, len(candidates)))]
    chosen = random.choice(top)

    return {
        "disease_name_kr": chosen["name_kr"],
        "disease_name_en": chosen["name_en"],
        "symptoms": chosen["symptoms"],
        "confidence": round(random.uniform(0.72, 0.94), 2),
        "eco_treatments": chosen["eco_treatments"],
        "chemical_treatments": chosen["chemical_treatments"],
        "_source": "demo",
    }


def diagnose(image_path: str, diagnosis_type: str, crop_name: str, weather: dict) -> dict:
    """사진 + 기상데이터 + 친환경DB 기반 AI 진단. 실패/데모모드 시 DB 기반 폴백."""
    if settings.demo_mode or not settings.gemini_api_key:
        return _demo_diagnose(diagnosis_type, weather)

    try:
        import PIL.Image

        client = _get_client()
        prompt = _build_prompt(diagnosis_type, crop_name, weather)
        image = PIL.Image.open(image_path)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[prompt, image],
        )
        parsed = _parse_json_response(response.text)
        if not parsed:
            raise ValueError("Gemini 응답 파싱 실패")
        parsed["_source"] = "gemini"
        parsed["_raw"] = response.text
        return parsed
    except Exception:
        result = _demo_diagnose(diagnosis_type, weather)
        result["_source"] = "demo_fallback"
        return result
