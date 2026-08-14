import json
import random
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.services.reference_service import build_treatment_lists, load_references_for_crop

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


def _load_active_references(db: Session, crop_id: Optional[int]) -> list:
    """관리자 CMS(TreatmentReference)에서 활성화된 참고자료를 crop_id 기준으로
    불러온다. 파일이 아니라 DB에서 매 요청 시 조회하므로, 관리자가 수정하면 서버
    재시작 없이 다음 진단부터 즉시 반영된다. crop_id가 없거나 매칭이 없으면
    load_references_for_crop이 전체 참고자료로 폴백한다(기존 안전장치와 동일)."""
    rows = load_references_for_crop(db, crop_id)

    result = []
    for r in rows:
        eco, chemical = build_treatment_lists(r)
        result.append(
            {
                "id": r.id,
                "name_kr": r.name_kr,
                "name_en": r.name_en,
                "type": r.type,
                "crop": r.crop_name,
                "symptoms": r.symptoms,
                "cause": r.cause,
                "favorable_conditions": {
                    "temp_range_c": [r.favorable_temp_min, r.favorable_temp_max]
                    if r.favorable_temp_min is not None and r.favorable_temp_max is not None
                    else None,
                    "humidity_min_percent": r.favorable_humidity_min,
                },
                "eco_treatments": eco,
                "chemical_treatments": chemical,
            }
        )
    return result


def _build_prompt(diagnosis_type: str, crop_name: str, weather: dict, reference_db: list) -> str:
    db_context = json.dumps(reference_db, ensure_ascii=False, indent=2)
    return f"""당신은 {crop_name} 재배 전문 식물병리학자입니다. 아래 첨부된 작물 피해 부위 사진과 당시 기상 조건, 그리고 회사의 친환경 방제 자재 데이터베이스를 종합적으로 분석하여 진단하세요.

[진단 유형]: {diagnosis_type}
[작물명]: {crop_name}
[촬영 당시 기상 조건]
- 기온: {weather.get('temp_c')}℃
- 습도: {weather.get('humidity_percent')}%
- 강우량: {weather.get('rainfall_mm')}mm
- 풍속: {weather.get('wind_ms')}m/s

[회사 자체 친환경 방제 자재 데이터베이스]
{db_context}

위 데이터베이스에 있는 병해충/생리장애 중 사진 증상 및 기상 조건과 가장 부합하는 항목을 우선적으로 선택하고, 데이터베이스에 없는 증상이면 일반적인 {crop_name} 병해충 지식으로 진단하세요.

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


def _demo_diagnose(diagnosis_type: str, weather: dict, reference_db: list) -> dict:
    """API 키 미설정/데모 모드일 때 참고자료 기반으로 그럴듯한 진단 결과를 생성."""
    if not reference_db:
        return {
            "disease_name_kr": "진단 불가(참고자료 없음)",
            "disease_name_en": None,
            "symptoms": "등록된 병해충 참고자료가 없어 자동 진단이 불가합니다. 관리자에게 문의해주세요.",
            "confidence": 0.0,
            "eco_treatments": [],
            "chemical_treatments": [],
            "_source": "demo",
        }

    candidates = [d for d in reference_db if d["type"] == diagnosis_type] or reference_db

    def score(entry):
        cond = entry.get("favorable_conditions", {})
        s = 0
        temp = weather.get("temp_c")
        if temp is not None and cond.get("temp_range_c"):
            lo, hi = cond["temp_range_c"]
            if lo <= temp <= hi:
                s += 2
        humidity = weather.get("humidity_percent")
        if humidity is not None and humidity >= (cond.get("humidity_min_percent") or 0):
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


def diagnose(
    image_path: str, diagnosis_type: str, crop_name: str, weather: dict, db: Session, crop_id: Optional[int] = None
) -> dict:
    """사진 + 기상데이터 + 참고자료(DB, 관리자 CMS로 관리) 기반 AI 진단. 실패/데모모드 시 폴백.
    crop_id는 참고자료 필터링(FK 매칭)에, crop_name은 프롬프트 표시 문구에 각각 쓰인다."""
    reference_db = _load_active_references(db, crop_id)

    if settings.demo_mode or not settings.gemini_api_key:
        return _demo_diagnose(diagnosis_type, weather, reference_db)

    try:
        import PIL.Image

        client = _get_client()
        prompt = _build_prompt(diagnosis_type, crop_name, weather, reference_db)
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
        result = _demo_diagnose(diagnosis_type, weather, reference_db)
        result["_source"] = "demo_fallback"
        return result
