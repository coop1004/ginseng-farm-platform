import datetime as dt
import uuid
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_admin
from app.routers.stats import build_summary
from app.services import community_service, consultant_service
from app.services.auth_service import (
    create_admin_access_token,
    generate_temp_password,
    hash_password,
    verify_password,
)
from app.services.diagnosis_service import to_response as diagnosis_to_response

router = APIRouter(prefix="/api/admin", tags=["admin"])

# regional-stats에서 이 값 미만인 지역은 정확한 건수 대신 "N건 미만"으로 뭉개서 보여준다.
# 농가가 한 곳뿐인 지역에서 정확한 소수 건수가 노출되면 사실상 특정 농가를 지목하는
# 것과 같아지는 걸 막기 위한 최소 표본수 안전장치 - 나중에 조정할 때 이 값만 바꾸면 된다.
# 지금은 파일럿 단계라 내부 관리자만 보는 화면이라 1로 낮춰 사실상 꺼둔다(로직 자체는
# 남겨둔다 - 나중에 외부 기관용 화면을 만들 때는 더 높은 값을 넘겨 재사용할 수 있음).
REGIONAL_STATS_MIN_SAMPLE_SIZE = 1

# 지역x병해충류 증감 추이 비교 기간(최근 N일 vs 그 이전 N일) - 나중에 바꿀 때 이 값만 수정하면 됨.
REGIONAL_TREND_WINDOW_DAYS = 7


@router.post("/auth/login", response_model=schemas.AdminTokenResponse)
def admin_login(payload: schemas.AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(models.AdminUser.username == payload.username).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_admin_access_token(admin.id)
    return schemas.AdminTokenResponse(access_token=token, admin=schemas.AdminUserOut.model_validate(admin))


@router.get("/auth/me", response_model=schemas.AdminUserOut)
def admin_me(current_admin: models.AdminUser = Depends(get_current_admin)):
    return schemas.AdminUserOut.model_validate(current_admin)


@router.post("/auth/change-password")
def admin_change_password(
    payload: schemas.AdminChangePasswordRequest,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    if not verify_password(payload.current_password, current_admin.password_hash):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="새 비밀번호는 8자 이상이어야 합니다.")
    current_admin.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


@router.post("/auth/register", response_model=schemas.AdminUserOut)
def admin_register(
    payload: schemas.AdminRegisterRequest,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """신규 관리자 계정 추가. 이미 로그인된 관리자만 다른 관리자를 추가로 등록할 수 있다
    (누구나 가입 가능한 공개 가입 절차가 아님 - 사내 담당자 전용)."""
    if db.query(models.AdminUser).filter(models.AdminUser.username == payload.username).first():
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다.")
    admin = models.AdminUser(
        username=payload.username,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return schemas.AdminUserOut.model_validate(admin)


@router.get("/auth/list", response_model=List[schemas.AdminUserOut])
def admin_list(db: Session = Depends(get_db), _current_admin: models.AdminUser = Depends(get_current_admin)):
    return db.query(models.AdminUser).order_by(models.AdminUser.created_at).all()


@router.get("/organizations", response_model=List[schemas.OrganizationOut])
def list_organizations(db: Session = Depends(get_db), _current_admin: models.AdminUser = Depends(get_current_admin)):
    """처방알림 브로드캐스트의 "대상 조직" 선택 드롭다운 등에 쓰는 조직 전체 목록.
    지금은 platform_super 관리자만 존재해 전체 조회로 충분 - org_scoped 관리자가
    실제로 생기면 자기 조직 하나만 보이도록 좁히는 게 맞다(이번 범위 밖)."""
    return db.query(models.Organization).order_by(models.Organization.id).all()


@router.delete("/auth/{admin_id}")
def admin_delete(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    if admin_id == current_admin.id:
        raise HTTPException(status_code=400, detail="본인 계정은 삭제할 수 없습니다.")
    target = db.query(models.AdminUser).filter(models.AdminUser.id == admin_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="관리자를 찾을 수 없습니다.")
    if target.is_protected:
        raise HTTPException(status_code=400, detail="최초 관리자 계정은 삭제할 수 없습니다.")
    if db.query(models.AdminUser).count() <= 1:
        raise HTTPException(status_code=400, detail="마지막 남은 관리자 계정은 삭제할 수 없습니다.")
    db.delete(target)
    db.commit()
    return {"ok": True}


# ---------- 컨설턴트 계정 관리 ----------
@router.post("/consultants", response_model=schemas.ConsultantOut)
def create_consultant(
    payload: schemas.ConsultantRegisterRequest,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """신규 컨설턴트 계정 추가. AdminUser처럼 공개 가입이 아니라 관리자만 추가할 수 있다."""
    if db.query(models.ConsultantUser).filter(models.ConsultantUser.username == payload.username).first():
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다.")
    consultant = models.ConsultantUser(
        username=payload.username,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(consultant)
    db.commit()
    db.refresh(consultant)
    return schemas.ConsultantOut.model_validate(consultant)


@router.get("/consultants", response_model=List[schemas.ConsultantOut])
def list_consultants(db: Session = Depends(get_db), _current_admin: models.AdminUser = Depends(get_current_admin)):
    return db.query(models.ConsultantUser).order_by(models.ConsultantUser.created_at).all()


@router.get("/consultants/stats/summary", response_model=schemas.ConsultantActivitySummaryOut)
def admin_consultants_stats_summary(
    top_n: int = 5,
    period: str = "this_month",
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """관리자 대시보드 메인 화면(종합 현황)의 "컨설턴트 활동 실적" 요약 카드와, 좌측 메뉴의
    "컨설턴트 활동현황" 전용 화면이 함께 쓰는 엔드포인트. period 기본값을 "this_month"로 둬서
    메인 화면 카드의 기존 동작(이번 달 스냅샷, 상위 5명)을 그대로 보존하고, 전용 화면은
    period/start_date/end_date/top_n을 명시적으로 바꿔가며 같은 엔드포인트를 재사용한다.
    개별 컨설턴트 상세는 여전히 GET /consultants/{consultant_id}/stats를 그대로 쓴다."""
    start, end = consultant_service.resolve_period_range(period, start_date, end_date)
    return consultant_service.compute_all_consultants_summary(db, top_n=top_n, start=start, end=end)


@router.delete("/consultants/{consultant_id}")
def delete_consultant(
    consultant_id: int,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    target = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    db.delete(target)
    db.commit()
    return {"ok": True}


@router.patch("/consultants/{consultant_id}", response_model=schemas.ConsultantOut)
def update_consultant(
    consultant_id: int,
    payload: schemas.ConsultantUpdateRequest,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """컨설턴트 본인은 이름/연락처를 수정할 화면이 없어 관리자가 대신 고쳐주는 용도."""
    target = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    if payload.name is not None:
        target.name = payload.name
    if payload.phone is not None:
        target.phone = payload.phone
    db.commit()
    db.refresh(target)
    return target


@router.post("/consultants/{consultant_id}/reset-password", response_model=schemas.TempPasswordOut)
def reset_consultant_password(
    consultant_id: int,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """컨설턴트가 비밀번호를 잊었을 때, 자가 재설정 수단이 없어 관리자가 임시 비밀번호를
    발급해 전화 등으로 알려주는 용도. 임시 비밀번호는 여기서만 한 번 반환되고 서버에는
    해시로만 저장된다 - 평문은 어디에도 남지 않는다."""
    target = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    temp_password = generate_temp_password()
    target.password_hash = hash_password(temp_password)
    db.commit()
    return schemas.TempPasswordOut(temp_password=temp_password)


@router.get("/consultants/{consultant_id}/households", response_model=List[schemas.HouseholdOut])
def get_consultant_households(
    consultant_id: int, db: Session = Depends(get_db), _current_admin: models.AdminUser = Depends(get_current_admin)
):
    consultant = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    return consultant.households


@router.post("/consultants/{consultant_id}/households/{household_id}", response_model=List[schemas.HouseholdOut])
def assign_consultant_household(
    consultant_id: int,
    household_id: int,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """농가를 컨설턴트의 담당 범위로 배정한다. 컨설턴트는 여기에 배정된 농가만 조회/등록할
    수 있다(시스템의 모든 농가에 접근하는 게 아님 - deps.get_consultant_household_ids)."""
    consultant = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    if household.status == "withdrawn":
        raise HTTPException(status_code=400, detail="탈퇴 처리된 농가에는 컨설턴트를 배정할 수 없습니다.")

    exists = (
        db.query(models.ConsultantHousehold)
        .filter(
            models.ConsultantHousehold.consultant_id == consultant_id,
            models.ConsultantHousehold.household_id == household_id,
        )
        .first()
    )
    if not exists:
        db.add(models.ConsultantHousehold(consultant_id=consultant_id, household_id=household_id))
        db.commit()
    db.refresh(consultant)
    return consultant.households


@router.delete("/consultants/{consultant_id}/households/{household_id}", response_model=List[schemas.HouseholdOut])
def unassign_consultant_household(
    consultant_id: int,
    household_id: int,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    consultant = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    db.query(models.ConsultantHousehold).filter(
        models.ConsultantHousehold.consultant_id == consultant_id,
        models.ConsultantHousehold.household_id == household_id,
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(consultant)
    return consultant.households


@router.get("/consultants/{consultant_id}/stats", response_model=schemas.ConsultantStatsOut)
def get_consultant_stats(
    consultant_id: int,
    period: str = "all",
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    db: Session = Depends(get_db),
    _current_admin: models.AdminUser = Depends(get_current_admin),
):
    """관리자가 특정 컨설턴트의 활동 실적을 본다. 컨설턴트 본인 화면(/api/consultant/stats/summary)과
    동일한 집계 로직(consultant_service.compute_stats)을 재사용한다. period 기본값을 "all"(무제한)로
    둬서, 파라미터 없이 부르던 기존 호출부(컨설턴트 본인 화면, 계정관리에서 옮기기 전의 상세 모달)의
    동작을 그대로 보존한다 - "컨설턴트 활동현황" 화면에서는 선택한 기간을 명시적으로 넘긴다."""
    consultant = db.query(models.ConsultantUser).filter(models.ConsultantUser.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="컨설턴트를 찾을 수 없습니다.")
    start, end = consultant_service.resolve_period_range(period, start_date, end_date)
    return consultant_service.compute_stats(db, consultant, start=start, end=end)


@router.get("/households/{household_id}/consultants", response_model=List[schemas.ConsultantOut])
def get_household_consultants(
    household_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """농가 상세 화면에서 "담당 컨설턴트" 표시용. 배정/해제는 컨설턴트 쪽 엔드포인트를 쓴다
    (컨설턴트 목록 화면에서 담당 농가를 관리하는 흐름이 기본이라, 여긴 조회 전용)."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    return household.consultants


@router.get("/households/{household_id}", response_model=schemas.HouseholdDetailOut)
def get_household_detail(
    household_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """농가 상세 화면의 "정보 수정" 폼용 - 농가명과 소속 계정(대표자 등) 목록을 함께 내려준다."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    members = (
        db.query(models.User)
        .join(models.HouseholdMember, models.HouseholdMember.user_id == models.User.id)
        .filter(models.HouseholdMember.household_id == household_id)
        .all()
    )
    return schemas.HouseholdDetailOut(
        id=household.id, name=household.name, join_code=household.join_code, status=household.status, members=members
    )


@router.patch("/households/{household_id}", response_model=schemas.HouseholdOut)
def update_household(
    household_id: int,
    payload: schemas.HouseholdUpdateRequest,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """농가명은 농가 본인이 고칠 화면이 없어 관리자가 대신 고쳐주는 용도."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    if payload.name is not None:
        household.name = payload.name
    db.commit()
    db.refresh(household)
    return household


@router.post("/households/{household_id}/suspend", response_model=schemas.HouseholdOut)
def suspend_household(
    household_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """로그인만 막는 되돌릴 수 있는 조치 - 기존 데이터는 전혀 건드리지 않는다."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    if household.status == "withdrawn":
        raise HTTPException(status_code=400, detail="이미 탈퇴 처리된 농가입니다.")
    household.status = "suspended"
    db.commit()
    db.refresh(household)
    return household


@router.post("/households/{household_id}/reactivate", response_model=schemas.HouseholdOut)
def reactivate_household(
    household_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    if household.status == "withdrawn":
        raise HTTPException(status_code=400, detail="탈퇴 처리된 농가는 복구할 수 없습니다.")
    household.status = "active"
    db.commit()
    db.refresh(household)
    return household


@router.post("/households/{household_id}/withdraw", response_model=schemas.HouseholdOut)
def withdraw_household(
    household_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """농가의 탈퇴 요청을 관리자가 대신 처리한다 - 되돌릴 수 없다. 개인식별정보(농가명,
    대표자 이름/전화번호, 농장 상세주소)는 즉시 익명화하고, region(시/군)은 지역 통계
    집계를 위해 그대로 남긴다. 진단·작업일지 기록은 전혀 건드리지 않는다(삭제도, 수정도
    하지 않음) - 익명화된 이름/주소로 인해 더 이상 특정 개인을 가리키지 않게 될 뿐이다."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    if household.status == "withdrawn":
        raise HTTPException(status_code=400, detail="이미 탈퇴 처리된 농가입니다.")

    household.status = "withdrawn"
    household.name = f"탈퇴회원_{household.id}"

    members = (
        db.query(models.User)
        .join(models.HouseholdMember, models.HouseholdMember.user_id == models.User.id)
        .filter(models.HouseholdMember.household_id == household_id)
        .all()
    )
    for member in members:
        member.name = f"탈퇴회원_{member.id}"
        member.phone = f"탈퇴_{member.id}"

    farms = db.query(models.Farm).filter(models.Farm.household_id == household_id).all()
    for farm in farms:
        farm.address = "비공개(탈퇴 처리됨)"
        farm.phone = None

    db.commit()
    db.refresh(household)
    return household


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
def update_household_user(
    user_id: int,
    payload: schemas.UserUpdateRequest,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """농가 대표자(User)의 이름/전화번호를 관리자가 대신 수정한다. phone은 로그인 아이디로도
    쓰이는 값이라 다른 계정과 중복되지 않는지 확인한다."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if payload.phone is not None and payload.phone != user.phone:
        if db.query(models.User).filter(models.User.phone == payload.phone).first():
            raise HTTPException(status_code=400, detail="이미 사용 중인 전화번호입니다.")
        user.phone = payload.phone
    if payload.name is not None:
        user.name = payload.name
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", response_model=schemas.TempPasswordOut)
def reset_household_user_password(
    user_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """농가가 비밀번호를 잊었을 때, 자가 재설정 수단이 없어 관리자가 임시 비밀번호를
    발급해 전화 등으로 알려주는 용도(컨설턴트 쪽과 동일한 패턴)."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    db.commit()
    return schemas.TempPasswordOut(temp_password=temp_password)


@router.get("/stats/summary", response_model=schemas.StatsSummary)
def admin_stats_summary(
    period: str = "all",
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """관리자 대시보드용 전사(全社) 통계 - 특정 농가로 필터링하지 않고 전체 집계.
    period/start_date/end_date를 주면 진단·영농일지는 발생일(occurrence_date/work_date) 기준으로
    그 기간 안의 것만 집계한다(컨설턴트 활동현황과 같은 consultant_service.resolve_period_range를
    재사용). total_farms/total_households는 "지금 등록된 농가 수" 자체가 기간과 무관한 스냅샷
    개념이라 기간과 상관없이 항상 현재 값을 반환한다. 파라미터를 아무것도 안 주면(기본값 "all")
    기존과 동일하게 전체 기간을 집계해서 회귀가 없다."""
    start, end = consultant_service.resolve_period_range(period, start_date, end_date)

    work_query = db.query(models.WorkLog)
    diag_query = db.query(models.Diagnosis)
    if start is not None:
        work_query = work_query.filter(models.WorkLog.work_date >= start.date())
        diag_query = diag_query.filter(models.Diagnosis.occurrence_date >= start.date())
    if end is not None:
        work_query = work_query.filter(models.WorkLog.work_date <= end.date())
        diag_query = diag_query.filter(models.Diagnosis.occurrence_date <= end.date())

    summary = build_summary(db.query(models.Farm), work_query, diag_query)
    summary["total_households"] = db.query(models.Household).count()
    return summary


@router.get("/farms/overview")
def farms_overview(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """농가별 최근 활동 요약: 관리자 대시보드 메인 테이블용."""
    farms = db.query(models.Farm).all()
    result = []
    for farm in farms:
        last_diag = (
            db.query(models.Diagnosis)
            .filter(models.Diagnosis.farm_id == farm.id)
            .order_by(models.Diagnosis.occurrence_date.desc())
            .first()
        )
        last_work = (
            db.query(models.WorkLog)
            .filter(models.WorkLog.farm_id == farm.id)
            .order_by(models.WorkLog.work_date.desc())
            .first()
        )
        diag_count_30d = (
            db.query(models.Diagnosis)
            .filter(
                models.Diagnosis.farm_id == farm.id,
                models.Diagnosis.occurrence_date >= dt.date.today() - dt.timedelta(days=30),
            )
            .count()
        )
        result.append(
            {
                "farm_id": farm.id,
                "farm_name": farm.farm_name,
                "household_id": farm.household_id,
                "household_name": farm.household.name if farm.household else None,
                "household_status": farm.household.status if farm.household else None,
                "region": farm.region,
                "address": farm.address,
                "latitude": farm.latitude,
                "longitude": farm.longitude,
                "facility_type": farm.facility_type,
                "cultivation_year": farm.cultivation_year,
                "area_m2": farm.area_m2,
                "last_diagnosis": {
                    "id": last_diag.id,
                    "type": last_diag.diagnosis_type,
                    "name": last_diag.ai_disease_name,
                    "date": last_diag.occurrence_date,
                    "confidence": last_diag.ai_confidence,
                }
                if last_diag
                else None,
                "last_work_log_date": last_work.work_date if last_work else None,
                "diagnosis_count_30d": diag_count_30d,
                "risk_level": "높음" if diag_count_30d >= 3 else ("보통" if diag_count_30d >= 1 else "낮음"),
            }
        )
    result.sort(key=lambda x: x["diagnosis_count_30d"], reverse=True)
    return result


@router.get("/households/{household_id}/crops", response_model=List[schemas.CropOut])
def get_household_crops(
    household_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """이 농가에게 현재 노출된(등록된) 작물 목록. 농가 상세 화면에서 관리자가 직접
    추가/제거할 수 있도록 하기 위한 조회용 엔드포인트."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    return household.crops


@router.post("/households/{household_id}/crops/{crop_id}", response_model=List[schemas.CropOut])
def add_household_crop(
    household_id: int,
    crop_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """농가가 새로운 작물을 추가로 재배하기 시작했을 때, 관리자가 수동으로 노출 작물을
    추가한다(농가 본인이 셀프서비스로 작물을 추가하는 화면은 아직 없음)."""
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    crop = db.query(models.Crop).filter(models.Crop.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail="작물을 찾을 수 없습니다.")

    exists = (
        db.query(models.HouseholdCrop)
        .filter(models.HouseholdCrop.household_id == household_id, models.HouseholdCrop.crop_id == crop_id)
        .first()
    )
    if not exists:
        db.add(models.HouseholdCrop(household_id=household_id, crop_id=crop_id))
        db.commit()
    db.refresh(household)
    return household.crops


@router.delete("/households/{household_id}/crops/{crop_id}", response_model=List[schemas.CropOut])
def remove_household_crop(
    household_id: int,
    crop_id: int,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")

    remaining = (
        db.query(models.HouseholdCrop).filter(models.HouseholdCrop.household_id == household_id).count()
    )
    if remaining <= 1:
        raise HTTPException(status_code=400, detail="농가에는 최소 1개의 작물이 등록되어 있어야 합니다.")

    db.query(models.HouseholdCrop).filter(
        models.HouseholdCrop.household_id == household_id, models.HouseholdCrop.crop_id == crop_id
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(household)
    return household.crops


@router.get("/diagnoses", response_model=List[schemas.AdminDiagnosisOut])
def admin_diagnoses(
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    diagnosis_type: Optional[str] = None,
    farm_id: Optional[int] = None,
    region: Optional[str] = None,
    pest_name: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """병해충 사진/진단 결과 관리자 조회. status로 분석완료/분석실패/전문가검토필요를
    구분해서 필터링할 수 있다. region/pest_name은 지역별 발생 지도의 지역x병해충류
    드릴다운(진단 목록 화면)에서 쓴다."""
    query = db.query(models.Diagnosis)
    if status:
        query = query.filter(models.Diagnosis.status == status)
    if min_confidence is not None:
        query = query.filter(models.Diagnosis.ai_confidence >= min_confidence)
    if max_confidence is not None:
        query = query.filter(models.Diagnosis.ai_confidence <= max_confidence)
    if diagnosis_type:
        query = query.filter(models.Diagnosis.diagnosis_type == diagnosis_type)
    if farm_id:
        query = query.filter(models.Diagnosis.farm_id == farm_id)
    if region:
        query = query.join(models.Farm).filter(models.Farm.region == region)
    if pest_name:
        query = query.filter(models.Diagnosis.ai_disease_name == pest_name)

    diagnoses = query.order_by(models.Diagnosis.created_at.desc()).limit(limit).all()
    results = []
    for d in diagnoses:
        out = schemas.AdminDiagnosisOut.model_validate(d)
        out.farm_name = d.farm.farm_name if d.farm else None
        out.household_name = d.farm.household.name if d.farm and d.farm.household else None
        out.region = d.farm.region if d.farm else None
        out.photo_paths = [p.photo_path for p in d.photos] if d.photos else ([d.photo_path] if d.photo_path else [])
        out.created_by_consultant_name = d.created_by_consultant.name if d.created_by_consultant else None
        results.append(out)
    return results


@router.get("/diagnoses/{diagnosis_id}")
def admin_diagnosis_detail(
    diagnosis_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """농가 모니터링·실시간 진단 피드에서 항목 클릭 시 보여줄 진단 전체 상세(사진 전체,
    특징/증상, 친환경/화학 방제법 등). 농가·컨설턴트 화면과 동일한 diagnosis_service.to_response를
    재사용해 필드가 어긋나지 않게 하고, 관리자 화면에 필요한 household_name/region만 덧붙인다."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    data = diagnosis_to_response(d)
    data["household_name"] = d.farm.household.name if d.farm and d.farm.household else None
    data["region"] = d.farm.region if d.farm else None
    return data


@router.patch("/diagnoses/{diagnosis_id}/final-diagnosis", response_model=schemas.AdminDiagnosisOut)
def admin_final_diagnosis(
    diagnosis_id: int,
    payload: schemas.DiagnosisFinalRequest,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    """전문가(농자재사 담당자)가 현장 확인 결과 AI 진단과 다르다고 판단했을 때
    최종 진단명을 정정한다. 농가가 직접 입력한 값이 있어도 전문가 입력이 최종
    권위를 갖도록 덮어쓴다(현장 재확인이 더 신뢰도가 높다고 보기 때문)."""
    d = db.query(models.Diagnosis).filter(models.Diagnosis.id == diagnosis_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    d.final_disease_name = payload.disease_name
    d.final_diagnosis_source = "expert"
    d.final_diagnosis_note = payload.note
    d.final_diagnosis_by = current_admin.name
    d.final_diagnosis_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(d)
    out = schemas.AdminDiagnosisOut.model_validate(d)
    out.farm_name = d.farm.farm_name if d.farm else None
    out.household_name = d.farm.household.name if d.farm and d.farm.household else None
    out.region = d.farm.region if d.farm else None
    out.photo_paths = [p.photo_path for p in d.photos] if d.photos else ([d.photo_path] if d.photo_path else [])
    return out


@router.get("/regional-stats")
def regional_stats(
    crop_id: Optional[int] = None,
    period: str = "all",
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """지역별 병해충 발생 현황: 지도/차트용 집계. 작물별 분포(by_crop)도 함께 내려줘서
    관리자 대시보드의 지역x작물 비교 차트에 사용한다. crop_id를 주면 그 작물 소속
    필지의 진단만으로 좁혀서(예: 인삼만/고추만) 지역 통계를 볼 수 있다. period/start_date/
    end_date를 주면 발생일(occurrence_date) 기준으로 그 기간 안의 진단만 집계한다(기본값
    "all"이면 기존과 동일하게 전체 기간). 이 기간 필터는 /regional-stats/breakdown의 증감
    추이(항상 최근 7일 vs 그 이전 7일 고정)와는 완전히 별개 - 그쪽은 이 파라미터의 영향을
    받지 않는다."""
    start, end = consultant_service.resolve_period_range(period, start_date, end_date)

    farm_query = db.query(models.Farm)
    if crop_id is not None:
        farm_query = farm_query.filter(models.Farm.crop_id == crop_id)
    farms = {f.id: f for f in farm_query.all()}

    diag_query = db.query(models.Diagnosis)
    if crop_id is not None:
        diag_query = diag_query.join(models.Farm).filter(models.Farm.crop_id == crop_id)
    if start is not None:
        diag_query = diag_query.filter(models.Diagnosis.occurrence_date >= start.date())
    if end is not None:
        diag_query = diag_query.filter(models.Diagnosis.occurrence_date <= end.date())
    diagnoses = diag_query.all()

    region_data: dict = {}
    for d in diagnoses:
        farm = farms.get(d.farm_id)
        if not farm or not farm.region:
            continue
        region = farm.region
        if region not in region_data:
            region_data[region] = {
                "region": region,
                "latitude": farm.latitude,
                "longitude": farm.longitude,
                "total": 0,
                "by_type": Counter(),
                "by_name": Counter(),
                "by_crop": Counter(),
            }
        region_data[region]["total"] += 1
        region_data[region]["by_type"][d.diagnosis_type] += 1
        if d.ai_disease_name:
            region_data[region]["by_name"][d.ai_disease_name] += 1
        crop_name = farm.crop.name_kr if farm.crop else d.crop_name
        if crop_name:
            region_data[region]["by_crop"][crop_name] += 1

    output = []
    for region, data in region_data.items():
        total = data["total"]
        # 표본수가 너무 적으면(기본 3건 미만) 정확한 건수·유형별/작물별 분포·주요 병해충명을
        # 전부 뭉개서 반환한다 - 세부 항목 중 하나라도 그대로 노출되면 역산으로 전체 건수를
        # 유추할 수 있으므로 total만 감추고 나머지는 그대로 두는 방식은 쓰지 않는다.
        suppressed = total < REGIONAL_STATS_MIN_SAMPLE_SIZE
        output.append(
            {
                "region": region,
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "total": total,
                "total_display": f"{REGIONAL_STATS_MIN_SAMPLE_SIZE}건 미만" if suppressed else f"{total}건",
                "by_type": {} if suppressed else dict(data["by_type"]),
                "by_crop": {} if suppressed else dict(data["by_crop"]),
                "top_issue": None if suppressed else (data["by_name"].most_common(1)[0][0] if data["by_name"] else None),
                "suppressed": suppressed,
            }
        )
    output.sort(key=lambda x: x["total"], reverse=True)
    return output


@router.get("/regional-stats/breakdown")
def regional_stats_breakdown(
    region: str,
    crop_id: Optional[int] = None,
    min_sample_size: Optional[int] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """지역 드릴다운 1단계 - 특정 지역 안의 병해충류별 발생건수와 최근 증감 추이(최근
    REGIONAL_TREND_WINDOW_DAYS일 vs 그 이전 같은 길이 기간)를 반환한다. min_sample_size를
    생략하면 REGIONAL_STATS_MIN_SAMPLE_SIZE(지금은 1, 사실상 무시)를 쓰고, 나중에 외부
    기관용 화면에서는 더 높은 값을 넘겨 재사용할 수 있다."""
    threshold = min_sample_size if min_sample_size is not None else REGIONAL_STATS_MIN_SAMPLE_SIZE

    farm_query = db.query(models.Farm).filter(models.Farm.region == region)
    if crop_id is not None:
        farm_query = farm_query.filter(models.Farm.crop_id == crop_id)
    farm_ids = [f.id for f in farm_query.all()]
    if not farm_ids:
        return []

    diagnoses = (
        db.query(models.Diagnosis)
        .filter(models.Diagnosis.farm_id.in_(farm_ids), models.Diagnosis.ai_disease_name.isnot(None))
        .all()
    )

    today = dt.date.today()
    recent_cutoff = today - dt.timedelta(days=REGIONAL_TREND_WINDOW_DAYS)
    previous_cutoff = today - dt.timedelta(days=REGIONAL_TREND_WINDOW_DAYS * 2)

    by_name: dict = {}
    for d in diagnoses:
        name = d.ai_disease_name
        entry = by_name.setdefault(
            name, {"name": name, "diagnosis_type": d.diagnosis_type, "total": 0, "recent": 0, "previous": 0}
        )
        entry["total"] += 1
        occ = d.occurrence_date
        if occ is None:
            continue
        if recent_cutoff < occ <= today:
            entry["recent"] += 1
        elif previous_cutoff < occ <= recent_cutoff:
            entry["previous"] += 1

    output = []
    for data in by_name.values():
        total = data["total"]
        suppressed = total < threshold
        change = data["recent"] - data["previous"]
        direction = "up" if change > 0 else ("down" if change < 0 else "flat")
        output.append(
            {
                "name": data["name"],
                "diagnosis_type": data["diagnosis_type"],
                "total": total,
                "total_display": f"{threshold}건 미만" if suppressed else f"{total}건",
                "suppressed": suppressed,
                "recent_count": None if suppressed else data["recent"],
                "previous_count": None if suppressed else data["previous"],
                "change": None if suppressed else change,
                "trend_direction": None if suppressed else direction,
            }
        )
    output.sort(key=lambda x: x["total"], reverse=True)
    return output


@router.get("/feed")
def recent_activity_feed(
    limit: int = 20, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    """최근 발생 진단 실시간 피드."""
    diagnoses = (
        db.query(models.Diagnosis)
        .order_by(models.Diagnosis.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": d.id,
            "farm_id": d.farm_id,
            "farm_name": d.farm.farm_name if d.farm else None,
            "region": d.farm.region if d.farm else None,
            "diagnosis_type": d.diagnosis_type,
            "ai_disease_name": d.ai_disease_name,
            "confidence": d.ai_confidence,
            "occurrence_date": d.occurrence_date,
            "created_at": d.created_at,
        }
        for d in diagnoses
    ]


@router.post("/notifications", response_model=schemas.NotificationOut)
def send_notification(
    payload: schemas.NotificationCreate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    """농가에 친환경 자재 처방 알림 전송 (시뮬레이션 - DB 저장 후 모바일 앱에서 조회 가능)."""
    farm = db.query(models.Farm).filter(models.Farm.id == payload.farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="농장을 찾을 수 없습니다.")
    if farm.household and farm.household.status == "withdrawn":
        raise HTTPException(status_code=400, detail="탈퇴 처리된 농가에는 알림을 보낼 수 없습니다.")

    notification = models.Notification(**payload.model_dump(), organization_id=farm.organization_id)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    out = schemas.NotificationOut.model_validate(notification)
    out.farm_name = farm.farm_name
    return out


@router.post("/notifications/broadcast", response_model=schemas.NotificationBroadcastResult)
def broadcast_notification(
    payload: schemas.NotificationBroadcastRequest,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(get_current_admin),
):
    """전체 농가, 특정 지역, 또는 선택한 여러 농가에 동일한 알림을 한 번에 발송한다.
    농가별 GET /api/notifications 조회 방식(폴링)은 그대로 두고, 여기서는 대상 농가
    수만큼 Notification 행을 만들어 같은 broadcast_group으로 묶는다.

    "all"/"region"은 조직 경계를 넘나드는 대상 선정이라 role에 따라 갈린다 - org_scoped
    관리자는 자기 조직으로 강제되고(요청에 다른 값이 와도 무시), platform_super 관리자는
    조직을 넘나들 수 있는 대신 어느 조직 대상인지 반드시 화면에서 명시해야 한다(암묵적으로
    전체 조직 대상이 되는 사고를 막기 위해 생략 시 에러)."""
    if payload.target_type in ("all", "region"):
        if current_admin.role == "org_scoped":
            target_org_id = current_admin.organization_id
        else:
            if payload.organization_id is None:
                raise HTTPException(status_code=400, detail="대상 조직을 선택해주세요.")
            target_org_id = payload.organization_id
    else:
        target_org_id = None

    # 탈퇴 처리된 농가는 세 경로 모두에서 자동으로 제외한다 - "all"/"region"은 애초에 쿼리에서
    # 걸러내고, "farms"는 관리자가 명시적으로 고른 id 중 탈퇴 농가만 조용히 빠진다(에러 대신
    # 자동 제외 - 관리자가 목록을 만들 때 이미 탈퇴 여부를 몰랐을 수 있으므로).
    not_withdrawn = models.Household.status != "withdrawn"

    if payload.target_type == "all":
        farms = (
            db.query(models.Farm)
            .join(models.Household, models.Farm.household_id == models.Household.id)
            .filter(models.Farm.organization_id == target_org_id, not_withdrawn)
            .all()
        )
    elif payload.target_type == "region":
        if not payload.region:
            raise HTTPException(status_code=400, detail="지역을 선택해주세요.")
        farms = (
            db.query(models.Farm)
            .join(models.Household, models.Farm.household_id == models.Household.id)
            .filter(models.Farm.region == payload.region, models.Farm.organization_id == target_org_id, not_withdrawn)
            .all()
        )
    elif payload.target_type == "farms":
        if not payload.farm_ids:
            raise HTTPException(status_code=400, detail="대상 농가를 선택해주세요.")
        farms = (
            db.query(models.Farm)
            .join(models.Household, models.Farm.household_id == models.Household.id)
            .filter(models.Farm.id.in_(payload.farm_ids), not_withdrawn)
            .all()
        )
    else:
        raise HTTPException(status_code=400, detail="target_type은 all/region/farms 중 하나여야 합니다.")

    if not farms:
        raise HTTPException(status_code=404, detail="발송 대상 농가가 없습니다.")

    group = uuid.uuid4().hex
    for farm in farms:
        db.add(
            models.Notification(
                farm_id=farm.id,
                organization_id=farm.organization_id,
                title=payload.title,
                message=payload.message,
                recommended_product=payload.recommended_product,
                sent_by=payload.sent_by,
                broadcast_group=group,
            )
        )
    db.commit()
    return schemas.NotificationBroadcastResult(
        broadcast_group=group, sent_count=len(farms), farm_ids=[f.id for f in farms]
    )


@router.get("/notifications", response_model=List[schemas.NotificationOut])
def list_notifications(
    farm_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    query = db.query(models.Notification)
    if farm_id:
        query = query.filter(models.Notification.farm_id == farm_id)
    notifications = query.order_by(models.Notification.created_at.desc()).all()
    results = []
    for n in notifications:
        out = schemas.NotificationOut.model_validate(n)
        out.farm_name = n.farm.farm_name if n.farm else None
        results.append(out)
    return results


# ---------- Community moderation ----------
@router.get("/community/reports")
def list_community_reports(db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)):
    """신고된 게시글/댓글 목록. community_service.REPORT_HIDE_THRESHOLD 이상 쌓이면
    이미 자동으로 status=hidden 처리된 상태로 여기 보인다 - 관리자는 최종 삭제/복구만 판단하면 됨."""
    reports = db.query(models.CommunityReport).order_by(models.CommunityReport.created_at.desc()).all()
    results = []
    for r in reports:
        reporter = db.query(models.Household).filter(models.Household.id == r.reporter_household_id).first()
        if r.post_id:
            target = db.query(models.CommunityPost).filter(models.CommunityPost.id == r.post_id).first()
            target_type, preview, target_status = "post", (target.title if target else None), (target.status if target else None)
        else:
            target = db.query(models.CommunityComment).filter(models.CommunityComment.id == r.comment_id).first()
            target_type, preview, target_status = "comment", (target.body if target else None), (target.status if target else None)
        results.append(
            {
                "id": r.id,
                "post_id": r.post_id,
                "comment_id": r.comment_id,
                "target_type": target_type,
                "target_preview": preview,
                "target_status": target_status,
                "reporter_household_name": reporter.name if reporter else None,
                "reason": r.reason,
                "created_at": r.created_at,
            }
        )
    return results


@router.patch("/community/posts/{post_id}", response_model=schemas.CommunityPostOut)
def update_community_post_status(
    post_id: int,
    payload: schemas.CommunityStatusUpdate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if payload.status not in ("visible", "hidden"):
        raise HTTPException(status_code=400, detail="status는 visible 또는 hidden이어야 합니다.")
    post.status = payload.status
    db.commit()
    db.refresh(post)
    return community_service.to_post_response(post)


@router.delete("/community/posts/{post_id}")
def delete_community_post(
    post_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    db.query(models.CommunityReport).filter(models.CommunityReport.post_id == post_id).delete(synchronize_session=False)
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.patch("/community/comments/{comment_id}", response_model=schemas.CommunityCommentOut)
def update_community_comment_status(
    comment_id: int,
    payload: schemas.CommunityStatusUpdate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(get_current_admin),
):
    comment = db.query(models.CommunityComment).filter(models.CommunityComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if payload.status not in ("visible", "hidden"):
        raise HTTPException(status_code=400, detail="status는 visible 또는 hidden이어야 합니다.")
    comment.status = payload.status
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/community/comments/{comment_id}")
def delete_community_comment(
    comment_id: int, db: Session = Depends(get_db), _admin: models.AdminUser = Depends(get_current_admin)
):
    comment = db.query(models.CommunityComment).filter(models.CommunityComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    db.query(models.CommunityReport).filter(models.CommunityReport.comment_id == comment_id).delete(synchronize_session=False)
    db.delete(comment)
    db.commit()
    return {"ok": True}
