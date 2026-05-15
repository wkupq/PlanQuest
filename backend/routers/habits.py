"""Plan-Quest - 습관 CRUD 라우터"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db
from models import UserProfile, Habit, TreeOnMap
from schemas import HabitCreate, HabitResponse

router = APIRouter(prefix="/api", tags=["습관"])


@router.get("/habits", response_model=List[HabitResponse])
def get_habits(db: Session = Depends(get_db)):
    habits = db.query(Habit).all()
    return habits


@router.post("/habits", response_model=HabitResponse)
def create_habit(habit: HabitCreate, db: Session = Depends(get_db)):
    new_habit = Habit(
        title=habit.title,
        repeat_days=habit.repeat_days,
        times=habit.times,
        alarm_enabled=habit.alarm_enabled,
        hearts_reward=habit.hearts_reward,
    )
    db.add(new_habit)
    db.commit()
    db.refresh(new_habit)

    # 나무도 맵에 자동 생성
    tree = TreeOnMap(
        habit_id=new_habit.id,
        grid_x=len(db.query(TreeOnMap).all()) % 6,
        grid_y=len(db.query(TreeOnMap).all()) // 6,
        growth_stage=0,
        hearts_available=0,
    )
    db.add(tree)
    db.commit()

    return new_habit


@router.post("/habits/{habit_id}/complete")
def complete_habit(habit_id: int, db: Session = Depends(get_db)):
    """습관 완료 → 하트 지급 + 나무 성장"""
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="습관을 찾을 수 없습니다")
    if habit.completed_today:
        raise HTTPException(status_code=400, detail="오늘 이미 완료했습니다")

    habit.completed_today = True
    habit.streak += 1
    habit.last_completed = datetime.utcnow()

    user = db.query(UserProfile).first()
    earned = habit.hearts_reward
    if habit.streak % 7 == 0:
        earned += 1
    user.hearts += earned
    user.total_hearts_earned += earned
    user.level = (user.total_hearts_earned // 10) + 1

    tree = db.query(TreeOnMap).filter(TreeOnMap.habit_id == habit_id).first()
    if tree:
        if tree.growth_stage < 3:
            tree.growth_stage += 1
        tree.hearts_available += 1

    db.commit()
    return {
        "message": f"'{habit.title}' 완료! +{earned} 하트",
        "hearts_earned": earned,
        "total_hearts": user.hearts,
        "streak": habit.streak,
        "tree_growth": tree.growth_stage if tree else 0,
    }


@router.delete("/habits/{habit_id}")
def delete_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="습관을 찾을 수 없습니다")
    db.query(TreeOnMap).filter(TreeOnMap.habit_id == habit_id).delete()
    db.delete(habit)
    db.commit()
    return {"message": "삭제 완료"}


@router.post("/habits/reset-daily")
def reset_daily_habits(db: Session = Depends(get_db)):
    """매일 자정에 호출: 모든 습관의 completed_today 리셋"""
    habits = db.query(Habit).all()
    for habit in habits:
        if not habit.completed_today:
            habit.streak = 0
        habit.completed_today = False
    db.commit()
    return {"message": f"{len(habits)}개 습관 리셋 완료"}
