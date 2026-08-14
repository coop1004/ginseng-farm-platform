"""고추/배추 파일럿 작물 병해충 참고자료 시드 데이터.

실제 학습된 진단 모델이나 농가 데이터 없이, "구조가 다른 작물로 확장 가능하다"는
것을 보여주기 위한 샘플이다. 증상/원인/방제 정보는 일반적으로 공개된 농촌진흥청
수준의 병해충 정보를 참고해 작성했으며, 각 작물은 Crop.is_sample_data=True로
표시되어 모바일 앱/관리자 대시보드에서 "샘플 데이터" 안내가 함께 뜬다.
"""
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.reference_service import sync_pest_disease_materials

_TYPE_COLORS = {"병해": (198, 40, 40), "해충": (239, 108, 0), "생리장애": (21, 101, 192)}


def _generate_placeholder_image(filename: str, type_: str) -> None:
    """실제 촬영 사진이 없으므로, 한글 폰트 의존성 없이(운영 서버에 한글 폰트가
    없을 수 있음) 도형만으로 구성된 자리표시자 이미지를 생성한다. 이미 있으면
    다시 만들지 않는다."""
    path = Path(settings.upload_dir) / filename
    if path.exists():
        return
    color = _TYPE_COLORS.get(type_, (100, 100, 100))
    img = Image.new("RGB", (600, 450), color=color)
    draw = ImageDraw.Draw(img)
    draw.ellipse((190, 115, 410, 335), outline="white", width=8)
    draw.line((160, 380, 440, 380), fill="white", width=5)
    img.save(path, format="JPEG", quality=80)


PEPPER_PESTS = [
    dict(
        type="병해",
        name_kr="고추 탄저병",
        name_en="Anthracnose",
        symptoms="과실에 오목하게 들어간 원형 병반이 생기고 병반 위에 검은색 분생포자층이 형성된다. 심하면 과실 전체가 물러지며 낙과한다.",
        cause="Colletotrichum acutatum/gloeosporioides 곰팡이. 고온다습(25~30℃) 조건에서 강우 직후 급속히 확산된다.",
        favorable_temp_min=25,
        favorable_temp_max=30,
        favorable_humidity_min=80,
        eco=[
            {
                "product_name": "자닮유황 친환경 방제액",
                "active_ingredient": "석회유황합제 대체 자재",
                "usage": "500배 희석 엽면살포, 7일 간격",
                "note": "예방 및 초기 방제에 효과적",
            }
        ],
        chemical=[
            {
                "product_name": "아족시스트로빈 수화제",
                "active_ingredient": "아족시스트로빈 21.7%",
                "usage": "2000배 희석 살포, 수확 3일 전까지",
                "note": "친환경 자재 효과 미흡 시 보조 사용",
            }
        ],
    ),
    dict(
        type="병해",
        name_kr="고추 역병",
        name_en="Phytophthora Blight",
        symptoms="잎·줄기·뿌리가 수침상으로 변하며 급격히 시드는 청고 증상이 나타나고, 지제부가 흑갈색으로 변한다. 과실에도 수침상 병반이 생긴다.",
        cause="Phytophthora capsici 곰팡이. 배수 불량 토양에서 과습 조건이 지속될 때 급속히 발생한다.",
        favorable_temp_min=28,
        favorable_temp_max=32,
        favorable_humidity_min=85,
        eco=[
            {
                "product_name": "트리코더마 친환경 토양미생물제",
                "active_ingredient": "트리코더마 하지아눔(Trichoderma harzianum)",
                "usage": "정식 전 토양관주 300L/10a",
                "note": "예방적 토양 처리가 핵심, 발병 후 효과 제한적",
            }
        ],
        chemical=[
            {
                "product_name": "메타락실 입제",
                "active_ingredient": "메타락실 5%",
                "usage": "토양 처리 3kg/10a, 정식 전 1회",
                "note": "친환경 자재로 예방 실패 시에만 제한적 사용",
            }
        ],
    ),
    dict(
        type="해충",
        name_kr="담배나방(고추)",
        name_en="Pepper Fruit Borer",
        symptoms="유충이 과실 속을 파먹어 구멍을 내고 그 안에서 서식하며, 과실 내부가 부패하고 낙과가 발생한다.",
        cause="나방 유충. 여름철 고온기에 발생이 증가하며 과실 성숙기에 피해가 집중된다.",
        favorable_temp_min=25,
        favorable_temp_max=30,
        favorable_humidity_min=50,
        eco=[
            {
                "product_name": "비티쿠르스타키 미생물 살충제",
                "active_ingredient": "Bacillus thuringiensis subsp. kurstaki",
                "usage": "1000배 희석, 유충 초기 발생 시 5일 간격 살포",
                "note": "유충 초기 단계에 처리 시 방제 효과 우수",
            }
        ],
        chemical=[
            {
                "product_name": "클로란트라닐리프롤 액상수화제",
                "active_ingredient": "클로란트라닐리프롤 5%",
                "usage": "2000배 희석, 수확 7일 전까지",
                "note": "밀도가 높아 친환경 자재로 제어 어려운 경우 사용",
            }
        ],
    ),
]

CABBAGE_PESTS = [
    dict(
        type="병해",
        name_kr="배추 노균병",
        name_en="Downy Mildew",
        symptoms="잎 표면에 황색 반점이 생기고 뒷면에 흰색~회백색 곰팡이가 형성된다. 심하면 잎 전체가 황화되어 고사한다.",
        cause="Hyaloperonospora parasitica 곰팡이. 서늘하고 습한 날씨(15~20℃)와 밤사이 이슬이 맺히는 조건에서 다발한다.",
        favorable_temp_min=15,
        favorable_temp_max=20,
        favorable_humidity_min=85,
        eco=[
            {
                "product_name": "친환경 님오일 방제액",
                "active_ingredient": "님(Neem) 추출물 0.3%",
                "usage": "1000배 희석 후 엽면살포, 5일 간격 반복",
                "note": "예방 위주 사용 시 효과 극대화",
            }
        ],
        chemical=[
            {
                "product_name": "메탈락실-엠 수화제",
                "active_ingredient": "메탈락실-엠 35%",
                "usage": "1000배 희석 살포, 수확 7일 전까지",
                "note": "연속 사용 시 저항성 유발 가능, 교차사용 권장",
            }
        ],
    ),
    dict(
        type="병해",
        name_kr="배추 무름병",
        name_en="Bacterial Soft Rot",
        symptoms="줄기 기부와 잎자루가 물러지며 악취가 나는 연부 증상이 나타나고, 심하면 포기 전체가 물러 주저앉는다.",
        cause="Pectobacterium carotovorum(구 Erwinia) 세균. 고온다습 조건에서 상처 부위를 통해 침입하며 배수 불량 시 다발한다.",
        favorable_temp_min=25,
        favorable_temp_max=30,
        favorable_humidity_min=85,
        eco=[
            {
                "product_name": "바실러스 길항미생물제",
                "active_ingredient": "바실러스 서브틸리스(Bacillus subtilis)",
                "usage": "정식 후 토양관주 및 엽면살포 병행, 7일 간격",
                "note": "상처 최소화 등 경종적 방제와 병행 시 효과 상승",
            }
        ],
        chemical=[
            {
                "product_name": "옥솔린산 수화제",
                "active_ingredient": "옥솔린산 20%",
                "usage": "1000배 희석 살포, 수확 5일 전까지",
                "note": "친환경 자재 효과 미흡 시 보조 사용",
            }
        ],
    ),
    dict(
        type="해충",
        name_kr="배추좀나방",
        name_en="Diamondback Moth",
        symptoms="유충이 잎 뒷면에서 잎살만 갉아먹어 반투명한 창문 모양 흔적을 남기고, 심하면 그물 모양으로 잎이 뚫린다.",
        cause="나방 유충. 약제 저항성 발달이 빨라 동일 계통 약제의 연속 사용을 피해야 한다. 고온 건조기에 발생이 증가한다.",
        favorable_temp_min=20,
        favorable_temp_max=28,
        favorable_humidity_min=40,
        eco=[
            {
                "product_name": "비티쿠르스타키 미생물 살충제",
                "active_ingredient": "Bacillus thuringiensis subsp. kurstaki",
                "usage": "1000배 희석, 유충 초기 발생 시 5일 간격 살포",
                "note": "저항성 우려가 적어 우선 권장",
            }
        ],
        chemical=[
            {
                "product_name": "클로르페나피르 유제",
                "active_ingredient": "클로르페나피르 10%",
                "usage": "2000배 희석, 수확 3일 전까지",
                "note": "동일 계통 약제 연속 사용 자제(저항성 관리)",
            }
        ],
    ),
]


def seed_pilot_crop_pest_diseases_if_empty(db: Session):
    """고추/배추는 실제 학습 데이터 없이 구조 시연용으로 등록되는 파일럿 작물이다.
    작물별로 이미 참고자료가 있으면 건너뛴다(관리자가 CMS에서 직접 수정한 내용을
    서버 재시작할 때마다 덮어쓰지 않기 위함)."""
    for crop_name_kr, pests in [("고추", PEPPER_PESTS), ("배추", CABBAGE_PESTS)]:
        crop = db.query(models.Crop).filter(models.Crop.name_kr == crop_name_kr).first()
        if not crop:
            continue
        if db.query(models.TreatmentReference).filter(models.TreatmentReference.crop_id == crop.id).count() > 0:
            continue

        for i, p in enumerate(pests):
            filename = f"sample_{crop_name_kr}_{i}.jpg"
            _generate_placeholder_image(filename, p["type"])
            row = models.TreatmentReference(
                crop_id=crop.id,
                crop_name=crop.name_kr,
                type=p["type"],
                name_kr=p["name_kr"],
                name_en=p["name_en"],
                symptoms=p["symptoms"],
                cause=p["cause"],
                favorable_temp_min=p["favorable_temp_min"],
                favorable_temp_max=p["favorable_temp_max"],
                favorable_humidity_min=p["favorable_humidity_min"],
                photo_path=filename,
                is_sample_data=True,
                is_active=True,
                updated_by="샘플 데이터(파일럿)",
            )
            db.add(row)
            db.flush()
            sync_pest_disease_materials(db, row, p["eco"], p["chemical"])
    db.commit()
