"""Plan-Quest - 나무/수확 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db
from models import UserProfile, Habit, TreeOnMap
from schemas import TreeResponse

router = APIRouter(prefix="/api", tags=["나무"])


@router.get("/trees", response_model=List[TreeResponse])
def get_trees(db: Session = Depends(get_db)):
    trees = db.query(TreeOnMap).all()
    result = []
    for tree in trees:
        habit = db.query(Habit).filter(Habit.id == tree.habit_id).first()
        result.append(TreeResponse(
            id=tree.id,
            habit_id=tree.habit_id,
            habit_title=habit.title if habit else "알 수 없음",
            grid_x=tree.grid_x,
            grid_y=tree.grid_y,
            growth_stage=tree.growth_stage,
            hearts_available=tree.hearts_available,
        ))
    return result


@router.post("/trees/{tree_id}/harvest")
def harvest_tree(tree_id: int, db: Session = Depends(get_db)):
    """나무 클릭 → 하트 수확"""
    tree = db.query(TreeOnMap).filter(TreeOnMap.id == tree_id).first()
    if not tree:
        raise HTTPException(status_code=404, detail="나무를 찾을 수 없습니다")
    if tree.hearts_available <= 0:
        raise HTTPException(status_code=400, detail="수확할 하트가 없습니다")

    harvested = tree.hearts_available
    tree.hearts_available = 0
    tree.last_harvest = datetime.utcnow()

    user = db.query(UserProfile).first()
    user.hearts += harvested
    user.total_hearts_earned += harvested
    user.level = (user.total_hearts_earned // 10) + 1

    db.commit()
    return {
        "message": f"하트 {harvested}개 수확!",
        "harvested": harvested,
        "total_hearts": user.hearts,
    }
