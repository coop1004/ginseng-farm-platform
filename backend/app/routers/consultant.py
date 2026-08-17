import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import (
    ensure_consultant_farm_access,
    get_consultant_household_ids,
    get_current_consultant,
)
from app.routers.admin import compute_regional_stats, compute_stats_summary
from app.services import community_service, consultant_service, reference_service
from app.services.auth_service import create_consultant_access_token, verify_password
from app.services.diagnosis_service import add_comment, build_corrected_reference, create_diagnosis_record, to_response

router = APIRouter(prefix="/api/consultant", tags=["consultant"])


@router.post("/auth/login", response_model=schemas.ConsultantTokenResponse)
def consultant_login(payload: schemas.ConsultantLoginRequest, db: Session = Depends(get_db)):
    consultant = (
        db.query(models.ConsultantUser).filter(models.ConsultantUser.username == payload.username).first()
    )
    if not consultant or not consultant.is_active or not verify_password(payload.password, consultant.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_consultant_access_token(consultant.id)
    return schemas.ConsultantTokenResponse(
        access_token=token, consultant=schemas.ConsultantOut.model_validate(consultant)
    )


@router.get("/auth/me", response_model=schemas.ConsultantOut)
def consultant_me(current_consultant: models.ConsultantUser = Depends(get_current_consultant)):
    return schemas.ConsultantOut.model_validate(current_consultant)


@router.get("/households")
def list_my_households(
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """담당 농가와 그 소속 농장 목록. 시스템 전체 농가가 아니라 배정받은 농가로만
    범위가 제한된다(get_consultant_household_ids). members(대표자 계정 목록)는
    "담당 농가" 화면에서 농가정보 수정 폼을 채우는 데 쓴다."""
    if not consultant_household_ids:
        return []
    households = db.query(models.Household).filter(models.Household.id.in_(consultant_household_ids)).all()
    result = []
    for h in households:
        farms = db.query(models.Farm).filter(models.Farm.household_id == h.id).all()
        members = (
            db.query(models.User)
            .join(models.HouseholdMember, models.HouseholdMember.user_id == models.User.id)
            .filter(models.HouseholdMember.household_id == h.id)
            .all()
        )
        result.append(
            {
                "id": h.id,
                "name": h.name,
                "join_code": h.join_code,
                "members": [{"id": m.id, "name": m.name, "phone": m.phone} for m in members],
                "farms": [
                    {
                        "id": f.id,
                        "farm_name": f.farm_name,
                        "address": f.address,
                        "region": f.region,
                        "crop_id": f.crop_id,
                        "crop_name": f.crop.name_kr if f.crop else None,
                    }
                    for f in farms
                ],
            }
        )
    return result


@router.patch("/households/{household_id}", response_model=schemas.HouseholdOut)
def update_my_household(
    household_id: int,
    payload: schemas.HouseholdUpdateRequest,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 담당 농가의 농가명을 직접 수정한다. 관리자용 update_household와
    동일한 로직이나, 배정받은(ConsultantHousehold) 농가에 대해서만 허용한다."""
    if household_id not in consultant_household_ids:
        raise HTTPException(status_code=403, detail="담당 농가가 아닙니다.")
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    if payload.name is not None:
        household.name = payload.name
    db.commit()
    db.refresh(household)
    return household


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
def update_my_household_user(
    user_id: int,
    payload: schemas.UserUpdateRequest,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 담당 농가 대표자의 이름/전화번호를 직접 수정한다. 관리자용
    update_household_user와 동일한 로직이나, 그 계정이 배정받은 농가 소속인지
    HouseholdMember로 확인한 뒤에만 허용한다."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    membership = db.query(models.HouseholdMember).filter(models.HouseholdMember.user_id == user_id).first()
    if not membership or membership.household_id not in consultant_household_ids:
        raise HTTPException(status_code=403, detail="담당 농가의 대표자가 아닙니다.")
    if payload.phone is not None and payload.phone != user.phone:
        if db.query(models.User).filter(models.User.phone == payload.phone).first():
            raise HTTPException(status_code=400, detail="이미 사용 중인 전화번호입니다.")
        user.phone = payload.phone
    if payload.name is not None:
        user.name = payload.name
    db.commit()
    db.refresh(user)
    return user


@router.get("/diagnoses", response_model=List[schemas.DiagnosisCreateResponse])
def list_consultant_diagnoses(
    household_id: Optional[int] = None,
    farm_id: Optional[int] = None,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    if not consultant_household_ids:
        return []
    query = (
        db.query(models.Diagnosis)
        .join(models.Farm, models.Diagnosis.farm_id == models.Farm.id)
        .filter(models.Farm.household_id.in_(consultant_household_ids))
    )
    if household_id:
        if household_id not in consultant_household_ids:
            raise HTTPException(status_code=403, detail="담당 농가가 아닙니다.")
        query = query.filter(models.Farm.household_id == household_id)
    if farm_id:
        query = query.filter(models.Diagnosis.farm_id == farm_id)
    results = query.order_by(models.Diagnosis.occurrence_date.desc()).all()
    return [to_response(d) for d in results]


@router.get("/diagnoses/{diagnosis_id}")
def get_consultant_diagnosis(
    diagnosis_id: int,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """담당 농가 화면에서 진단 행 클릭 시 쓰는 상세 조회. 관리자용 admin_diagnosis_detail과
    동일하게 diagnosis_service.to_response를 재사용하고 household_name/region만 덧붙인다
    (response_model을 강제하지 않은 것도 admin_diagnosis_detail과 동일한 이유 - 추가
    필드가 잘리지 않게)."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_consultant_farm_access(d.farm, consultant_household_ids)
    data = to_response(d)
    data["household_name"] = d.farm.household.name if d.farm and d.farm.household else None
    data["region"] = d.farm.region if d.farm else None
    data["corrected_reference"] = build_corrected_reference(db, d)
    return data


@router.post("/diagnoses", response_model=schemas.DiagnosisCreateResponse)
async def create_consultant_diagnosis(
    farm_id: int = Form(...),
    diagnosis_type: str = Form(...),
    crop_name: str = Form("인삼"),
    occurrence_date: Optional[dt.date] = Form(None),
    photos: List[UploadFile] = File(...),
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 현장 방문 중 담당 농가의 필지에 새 진단을 등록한다. 담당 농가가
    아니면 접근할 수 없고(ensure_consultant_farm_access), 등록된 진단은
    created_by_type="consultant"로 표시되어 농가 쪽 화면에서도 누가 등록했는지
    구분해서 보여줄 수 있다."""
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    ensure_consultant_farm_access(farm, consultant_household_ids)

    try:
        diagnosis = await create_diagnosis_record(
            db,
            farm,
            diagnosis_type,
            crop_name,
            occurrence_date,
            photos,
            created_by_type="consultant",
            created_by_consultant_id=current_consultant.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return to_response(diagnosis)


@router.patch("/diagnoses/{diagnosis_id}/final-diagnosis", response_model=schemas.DiagnosisCreateResponse)
def submit_consultant_final_diagnosis(
    diagnosis_id: int,
    payload: schemas.DiagnosisFinalRequest,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 담당 농가의 진단을 현장 확인 후 정정한다. admin_final_diagnosis와
    동일한 방식이나 final_diagnosis_source가 "consultant"로 남아 누구의 정정인지
    구분된다(농가 본인 정정은 "farmer", 회사 관리자 정정은 "expert")."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_consultant_farm_access(d.farm, consultant_household_ids)
    d.final_disease_name = payload.disease_name
    d.final_diagnosis_source = "consultant"
    d.final_diagnosis_note = payload.note
    d.final_diagnosis_by = current_consultant.name
    d.final_diagnosis_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(d)
    return to_response(d)


@router.get("/reference", response_model=List[schemas.TreatmentReferenceOut])
def list_consultant_reference(
    crop_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _consultant: models.ConsultantUser = Depends(get_current_consultant),
):
    """현장 확인 정정 폼에서 진단명을 마스터 참고자료 목록 중에서 고를 수 있도록 하는
    읽기 전용 조회. 관리자용 /api/admin/reference와 같은 reference_service를 재사용하되,
    컨설턴트에게는 활성 항목만 노출한다(비활성 자료를 정정 후보로 보여줄 이유가 없음)."""
    rows = reference_service.load_references_for_crop(db, crop_id)
    return [reference_service.to_reference_out(r) for r in rows]


@router.get("/diagnoses/{diagnosis_id}/comments", response_model=List[schemas.DiagnosisCommentOut])
def list_consultant_diagnosis_comments(
    diagnosis_id: int,
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_consultant_farm_access(d.farm, consultant_household_ids)
    return d.comments


@router.post("/diagnoses/{diagnosis_id}/comments", response_model=schemas.DiagnosisCommentOut)
def create_consultant_diagnosis_comment(
    diagnosis_id: int,
    payload: schemas.DiagnosisCommentCreate,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    """컨설턴트가 담당 농가의 진단(농가 본인이 등록했든, 다른 방문에서 본인이
    등록했든)에 추가 설명/방제방법/공지 성격의 코멘트를 남긴다."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_consultant_farm_access(d.farm, consultant_household_ids)
    return add_comment(
        db, d, "consultant", current_consultant.name, payload.body, author_consultant_id=current_consultant.id
    )


@router.get("/overview/summary")
def consultant_overview_summary(
    crop_id: Optional[int] = None,
    _current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    db: Session = Depends(get_db),
):
    """"지역/현황 통계" 화면용 - 관리자 대시보드 종합현황과 완전히 동일한 집계 로직
    (compute_stats_summary)을 재사용한다. 담당 농가로 범위를 좁히지 않고 시스템 전체
    통계를 그대로 보여준다 - 담당 지역 밖에서 번지는 병해충 추이까지 참고해 현장
    대응하는 데 도움이 되도록 하기 위함(본인 실적은 기존 /stats/summary를 그대로 쓴다)."""
    return compute_stats_summary(db, crop_id=crop_id)


@router.get("/overview/regional-stats")
def consultant_overview_regional_stats(
    crop_id: Optional[int] = None,
    _current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    db: Session = Depends(get_db),
):
    """"지역/현황 통계" 화면용 - 관리자 대시보드 지역별발생현황과 완전히 동일한 집계
    로직(compute_regional_stats)을 재사용한다."""
    return compute_regional_stats(db, crop_id=crop_id)


@router.get("/stats/summary", response_model=schemas.ConsultantStatsOut)
def get_my_stats(
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    db: Session = Depends(get_db),
):
    """담당 농가 수, 본인이 등록/최종확정한 진단 실적, 남긴 코멘트 수, 담당 농가의
    AI 진단 대비 실제 발생 피드백 현황을 집계한다."""
    return consultant_service.compute_stats(db, current_consultant)


# ---------- 커뮤니티 ----------
@router.get("/community/posts", response_model=List[schemas.CommunityPostOut])
def list_community_posts(
    crop_id: Optional[int] = None,
    kind: Optional[str] = None,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    posts = community_service.list_posts_for_consultant(
        db, current_consultant.id, consultant_household_ids, crop_id=crop_id, kind=kind
    )
    return [community_service.to_post_response(p) for p in posts]


@router.get("/community/posts/{post_id}", response_model=schemas.CommunityPostDetailOut)
def get_community_post(
    post_id: int,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post or post.status != "visible":
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if not community_service.is_post_visible_to_consultant(post, current_consultant.id, consultant_household_ids):
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return community_service.to_post_response(post, include_comments=True)


@router.post("/community/posts", response_model=schemas.CommunityPostOut)
def create_channel_post(
    payload: schemas.CommunityPostCreate,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    db: Session = Depends(get_db),
):
    """컨설턴트가 담당 농가에 공지/방제 팁을 올린다. 기본 공개범위는 본인 담당
    농가로만 제한되는 consultant_scope - 전체 공개하려면 visibility="public"을 보낸다."""
    post = community_service.create_channel_post(
        db, current_consultant, payload.title, payload.body, payload.crop_id, payload.visibility
    )
    return community_service.to_post_response(post)


@router.post("/community/posts/{post_id}/comments", response_model=schemas.CommunityCommentOut)
def create_community_comment(
    post_id: int,
    payload: schemas.CommunityCommentCreate,
    current_consultant: models.ConsultantUser = Depends(get_current_consultant),
    consultant_household_ids: List[int] = Depends(get_consultant_household_ids),
    db: Session = Depends(get_db),
):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post or post.status != "visible":
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if not community_service.is_post_visible_to_consultant(post, current_consultant.id, consultant_household_ids):
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return community_service.add_comment(
        db, post, "consultant", current_consultant.name, payload.body, author_consultant_id=current_consultant.id
    )
