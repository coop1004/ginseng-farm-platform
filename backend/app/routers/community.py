from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import ensure_farm_access, get_current_household_id
from app.services import community_service

router = APIRouter(prefix="/api/community", tags=["community"])


def _get_household(db: Session, household_id: int) -> models.Household:
    household = db.query(models.Household).filter(models.Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="농가를 찾을 수 없습니다.")
    return household


def _ensure_post_visible_to_household(db: Session, post: models.CommunityPost, household_id: int) -> None:
    if not community_service.ensure_post_visible_to_household(db, post, household_id):
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")


@router.get("", response_model=List[schemas.CommunityPostOut])
def list_posts(
    crop_id: Optional[int] = None,
    kind: Optional[str] = None,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    posts = community_service.list_posts_for_household(db, household_id, crop_id=crop_id, kind=kind)
    return [community_service.to_post_response(p) for p in posts]


@router.get("/{post_id}", response_model=schemas.CommunityPostDetailOut)
def get_post(post_id: int, household_id: int = Depends(get_current_household_id), db: Session = Depends(get_db)):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post or post.status != "visible":
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    _ensure_post_visible_to_household(db, post, household_id)
    return community_service.to_post_response(post, include_comments=True)


@router.post("/diagnosis-share", response_model=schemas.CommunityPostOut)
def create_diagnosis_share(
    payload: schemas.CommunityDiagnosisShareCreate,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    """농가가 본인 진단을 옵트인으로 커뮤니티에 공유한다 - 이 엔드포인트를 호출하기
    전까지 어떤 진단도 커뮤니티에 노출되지 않는다."""
    diagnosis = db.query(models.Diagnosis).filter(models.Diagnosis.id == payload.diagnosis_id).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")
    ensure_farm_access(diagnosis.farm, household_id)

    household = _get_household(db, household_id)
    post = community_service.create_diagnosis_share(
        db, household, diagnosis, payload.title, payload.body, payload.visibility
    )
    return community_service.to_post_response(post)


@router.post("/{post_id}/comments", response_model=schemas.CommunityCommentOut)
def create_comment(
    post_id: int,
    payload: schemas.CommunityCommentCreate,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post or post.status != "visible":
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    _ensure_post_visible_to_household(db, post, household_id)

    household = _get_household(db, household_id)
    return community_service.add_comment(
        db, post, "household", household.name, payload.body, author_household_id=household_id
    )


@router.post("/{post_id}/report")
def report_post(
    post_id: int,
    payload: schemas.CommunityReportCreate,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    post = db.query(models.CommunityPost).filter(models.CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    community_service.report_post(db, post, household_id, payload.reason)
    return {"ok": True}


@router.post("/comments/{comment_id}/report")
def report_comment(
    comment_id: int,
    payload: schemas.CommunityReportCreate,
    household_id: int = Depends(get_current_household_id),
    db: Session = Depends(get_db),
):
    comment = db.query(models.CommunityComment).filter(models.CommunityComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    community_service.report_comment(db, comment, household_id, payload.reason)
    return {"ok": True}
