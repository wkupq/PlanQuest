"""Plan-Quest - 유저 프로필 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import UserProfile
from schemas import UserResponse

router = APIRouter(prefix="/api", tags=["유저"])


@router.get("/user", response_model=UserResponse)
def get_user(db: Session = Depends(get_db)):
    user = db.query(UserProfile).first()
    return user


# ─── 테스트용 디버그 엔드포인트 (배포 시 제거 권장) ─────
@router.post("/user/dev/add-hearts")
def dev_add_hearts(count: int = 10, db: Session = Depends(get_db)):
    """테스트용 — 하트 N개 즉시 지급. count 음수면 차감.

    예:
      POST /api/user/dev/add-hearts?count=50   → 하트 +50
      POST /api/user/dev/add-hearts?count=-5   → 하트 -5
    """
    user = db.query(UserProfile).first()
    if not user:
        raise HTTPException(404, "사용자 정보 없음")

    user.hearts = max(0, user.hearts + count)
    if count > 0:
        user.total_hearts_earned += count
        user.level = (user.total_hearts_earned // 10) + 1

    db.commit()
    return {
        "message": f"하트 {count:+}개 적용",
        "hearts": user.hearts,
        "total_hearts_earned": user.total_hearts_earned,
        "level": user.level,
    }


@router.post("/user/dev/set-level")
def dev_set_level(level: int = 1, db: Session = Depends(get_db)):
    """테스트용 — 레벨 직접 설정."""
    user = db.query(UserProfile).first()
    if not user:
        raise HTTPException(404, "사용자 정보 없음")
    user.level = max(1, level)
    db.commit()
    return {"hearts": user.hearts, "level": user.level}


@router.post("/user/dev/reset")
def dev_reset_user(db: Session = Depends(get_db)):
    """테스트용 — 하트 0, 레벨 1로 리셋."""
    user = db.query(UserProfile).first()
    if not user:
        raise HTTPException(404, "사용자 정보 없음")
    user.hearts = 0
    user.total_hearts_earned = 0
    user.level = 1
    db.commit()
    return {"message": "리셋 완료", "hearts": 0, "level": 1}
