"""Plan-Quest - 유저 프로필 라우터"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import UserProfile
from schemas import UserResponse

router = APIRouter(prefix="/api", tags=["유저"])


@router.get("/user", response_model=UserResponse)
def get_user(db: Session = Depends(get_db)):
    user = db.query(UserProfile).first()
    return user
