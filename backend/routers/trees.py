"""Plan-Quest - 나무/수확 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from pydantic import BaseModel

from database import get_db
from models import UserProfile, Habit, TreeOnMap, PlacedItem
from schemas import TreeResponse


GRID_COLS = 7
GRID_ROWS = 5


class TreePositionRequest(BaseModel):
    grid_x: int
    grid_y: int

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
            # 일정 정보 (씨앗 클릭 정보 팝업용)
            repeat_days=(habit.repeat_days if habit else []) or [],
            times=(habit.times if habit else []) or [],
            alarm_enabled=habit.alarm_enabled if habit else True,
            hearts_reward=habit.hearts_reward if habit else 1,
            streak=habit.streak if habit else 0,
            completed_today=habit.completed_today if habit else False,
        ))
    return result


@router.patch("/trees/{tree_id}/position")
def move_tree(tree_id: int, req: TreePositionRequest, db: Session = Depends(get_db)):
    """나무 위치 이동."""
    if not (0 <= req.grid_x < GRID_COLS and 0 <= req.grid_y < GRID_ROWS):
        raise HTTPException(400, f"좌표가 그리드 밖입니다 ({GRID_COLS}x{GRID_ROWS})")

    tree = db.query(TreeOnMap).filter(TreeOnMap.id == tree_id).first()
    if not tree:
        raise HTTPException(404, "나무를 찾을 수 없습니다")

    # 이미 다른 나무/캐릭터가 그 자리에 있으면 거부 (또는 swap 가능, 일단 거부)
    other_tree = db.query(TreeOnMap).filter(
        TreeOnMap.id != tree_id,
        TreeOnMap.grid_x == req.grid_x,
        TreeOnMap.grid_y == req.grid_y,
    ).first()
    placed = db.query(PlacedItem).filter(
        PlacedItem.grid_x == req.grid_x,
        PlacedItem.grid_y == req.grid_y,
    ).first()
    if other_tree or placed:
        raise HTTPException(409, "이미 다른 항목이 있는 자리입니다")

    tree.grid_x = req.grid_x
    tree.grid_y = req.grid_y
    db.commit()
    return {"message": "위치 변경 완료", "grid_x": tree.grid_x, "grid_y": tree.grid_y}


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
