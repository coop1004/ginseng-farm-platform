"""TreatmentReference(병해충) <-> AgriMaterial(농자재) 연결 로직.

관리자 CMS는 여전히 [{product_name, active_ingredient, usage, note}] 형태의 배열을
그대로 주고받는다(화면 재작업 없음) — 이 모듈이 그 배열을 AgriMaterial(get-or-create)과
PestDiseaseMaterial 조인으로 정규화해서 저장하고, 조회 시 다시 동일한 배열 모양으로
복원한다. eco/chemical 구분은 AgriMaterial.category만 신뢰한다(별도 role 컬럼 없음).
"""
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app import models

ECO_CATEGORY = "친환경"
CHEMICAL_CATEGORY = "화학"


def _get_or_create_material(db: Session, item: dict, category: str) -> models.AgriMaterial:
    name = item.get("product_name", "").strip()
    material = db.query(models.AgriMaterial).filter(models.AgriMaterial.name == name).first()
    if material:
        return material
    material = models.AgriMaterial(
        name=name,
        category=category,
        active_ingredient=item.get("active_ingredient"),
        default_usage=item.get("usage"),
        note=item.get("note"),
        is_active=True,
    )
    db.add(material)
    db.flush()
    return material


def sync_pest_disease_materials(
    db: Session,
    pest_disease: models.TreatmentReference,
    eco_items: List[dict],
    chemical_items: List[dict],
) -> None:
    """저장 시 호출 — 기존 연결을 전부 지우고 전달받은 목록으로 다시 만든다(전체 교체
    방식, CMS 폼이 항상 전체 목록을 보내는 기존 방식과 동일한 시맨틱)."""
    db.query(models.PestDiseaseMaterial).filter(
        models.PestDiseaseMaterial.pest_disease_id == pest_disease.id
    ).delete(synchronize_session=False)

    sort_order = 0
    for item in eco_items:
        material = _get_or_create_material(db, item, ECO_CATEGORY)
        db.add(_build_link(pest_disease.id, material, item, sort_order))
        sort_order += 1
    for item in chemical_items:
        material = _get_or_create_material(db, item, CHEMICAL_CATEGORY)
        db.add(_build_link(pest_disease.id, material, item, sort_order))
        sort_order += 1


def _build_link(pest_disease_id: int, material: models.AgriMaterial, item: dict, sort_order: int) -> models.PestDiseaseMaterial:
    usage_override = item.get("usage") if item.get("usage") != material.default_usage else None
    note_override = item.get("note") if item.get("note") != material.note else None
    return models.PestDiseaseMaterial(
        pest_disease_id=pest_disease_id,
        agri_material_id=material.id,
        usage_override=usage_override,
        note_override=note_override,
        sort_order=sort_order,
    )


def build_treatment_lists(
    pest_disease: models.TreatmentReference, organization_id: Optional[int] = None
) -> tuple[List[dict], List[dict]]:
    """저장된 조인 데이터를 CMS/AI 프롬프트가 기대하는
    [{product_name, active_ingredient, usage, note}] 배열 모양으로 복원한다.

    organization_id를 주면 그 조직의 자재만 포함한다 - 농가/진단 등 "추천"이 실제로
    노출되는 경로에서 다른 회사 자재가 섞이지 않도록 하는 안전장치. None이면(관리자 CMS
    등 기존 호출부) 지금까지처럼 전체를 그대로 반환한다 - 기존 동작을 바꾸지 않기 위함."""
    eco, chemical = [], []
    for link in sorted(pest_disease.materials, key=lambda link: link.sort_order):
        if organization_id is not None and link.organization_id != organization_id:
            continue
        material = link.agri_material
        entry = {
            "product_name": material.name,
            "active_ingredient": material.active_ingredient or "",
            "usage": link.usage_override or material.default_usage or "",
            "note": link.note_override or material.note,
        }
        if material.category == CHEMICAL_CATEGORY:
            chemical.append(entry)
        else:
            eco.append(entry)
    return eco, chemical


def to_reference_out(r: models.TreatmentReference, organization_id: Optional[int] = None) -> dict:
    """관리자 CMS와 농가 앱의 병해충 참고자료 조회 화면이 공유하는 응답 형태.
    organization_id는 농가 앱 쪽에서만 넘겨준다(관리자 CMS는 지금까지처럼 전체 조회)."""
    eco, chemical = build_treatment_lists(r, organization_id)
    return {
        "id": r.id,
        "crop_id": r.crop_id,
        "crop_name": r.crop_name,
        "type": r.type,
        "name_kr": r.name_kr,
        "name_en": r.name_en,
        "symptoms": r.symptoms,
        "cause": r.cause,
        "favorable_temp_min": r.favorable_temp_min,
        "favorable_temp_max": r.favorable_temp_max,
        "favorable_humidity_min": r.favorable_humidity_min,
        "favorable_rainfall_note": r.favorable_rainfall_note,
        "photo_path": r.photo_path,
        "is_sample_data": r.is_sample_data,
        "eco_treatments": eco,
        "chemical_treatments": chemical,
        "is_active": r.is_active,
        "updated_by": r.updated_by,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def load_references_for_crop(db: Session, crop_id: Optional[int]) -> List[models.TreatmentReference]:
    """crop_id로 활성 참고자료를 조회한다. crop_id가 없거나 매칭되는 항목이 없으면
    (예: 아직 크롭 데이터가 없는 신규 작물) 안전장치로 전체 활성 참고자료를
    반환한다(기존 동작과 동일)."""
    query = (
        db.query(models.TreatmentReference)
        .options(selectinload(models.TreatmentReference.materials).selectinload(models.PestDiseaseMaterial.agri_material))
        .filter(models.TreatmentReference.is_active.is_(True))
    )
    rows = query.filter(models.TreatmentReference.crop_id == crop_id).all() if crop_id is not None else []
    if not rows:
        rows = query.all()
    return rows
