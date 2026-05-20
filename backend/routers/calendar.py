"""Plan-Quest — 캘린더 API.

엔드포인트:
  GET /api/calendar/month?year=2026&month=5
    → 그 달 날짜별 완료 수 + 받은 하트 + 통계 (히트맵용)

  GET /api/calendar/day?date=2026-05-07
    → 그날의 자세한 정보 (완료한 일정, 받은 하트, 그날 예정이었던 일정)
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Habit, HabitCompletion

router = APIRouter(prefix="/api/calendar", tags=["캘린더"])


# ─── 유틸 ────────────────────────────────────────────────
def _month_range(year: int, month: int):
    """해당 월의 [시작, 끝) datetime 반환."""
    if not (1 <= month <= 12):
        raise HTTPException(400, "month 는 1~12 사이")
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _scheduled_on(d: date, habits: List[Habit]) -> List[Habit]:
    """그 날짜에 예정되어 있던 (또는 있을) 일정.
    repeat_days 가 비었으면 매일, 아니면 해당 요일 (0=월 ... 6=일)만."""
    # JS Date.getDay() 같은 변환: Python date.weekday()는 0=월 ... 6=일 이미 한국식.
    krDow = d.weekday()
    out = []
    for h in habits:
        rd = h.repeat_days or []
        if not rd or krDow in rd:
            out.append(h)
    return out


# ─── 1. 월별 통계 + 히트맵 ───────────────────────────────
@router.get("/month")
def get_month(
    year: int = Query(..., description="연도"),
    month: int = Query(..., ge=1, le=12, description="월 (1~12)"),
    db: Session = Depends(get_db),
):
    """그 달의 날짜별 완료수 + 하트, 월/연속 통계."""
    start, end = _month_range(year, month)

    # 그 달의 모든 완료 기록
    rows = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.completed_at >= start)
        .filter(HabitCompletion.completed_at < end)
        .all()
    )

    # 날짜별 집계
    days: Dict[str, Dict] = {}
    for r in rows:
        date_key = r.completed_at.strftime("%Y-%m-%d")
        if date_key not in days:
            days[date_key] = {"date": date_key, "completions": 0, "hearts": 0}
        days[date_key]["completions"] += 1
        days[date_key]["hearts"] += r.hearts_earned or 0

    # 일정이 있던 날 (예정만 있고 완료는 없을 수도)
    habits = db.query(Habit).all()
    cur = start.date()
    end_date = end.date()
    while cur < end_date:
        scheduled = _scheduled_on(cur, habits)
        date_key = cur.strftime("%Y-%m-%d")
        if scheduled and date_key not in days:
            days[date_key] = {"date": date_key, "completions": 0, "hearts": 0}
        if date_key in days:
            days[date_key]["scheduled"] = len(scheduled)
        cur += timedelta(days=1)

    # 통계
    total_completions = sum(d["completions"] for d in days.values())
    total_hearts = sum(d["hearts"] for d in days.values())
    completed_days = sum(1 for d in days.values() if d["completions"] > 0)

    # 현재 streak — 오늘부터 거꾸로 가면서 매일 1개 이상 완료된 날 카운트
    today = datetime.now().date()
    current_streak = _calc_current_streak(db, today)

    # 베스트 streak (이번 달 안에서)
    best_streak = _calc_best_streak_in_month(days, year, month)

    return {
        "year": year,
        "month": month,
        "days": list(days.values()),
        "stats": {
            "total_completions": total_completions,
            "total_hearts": total_hearts,
            "completed_days": completed_days,
            "current_streak": current_streak,
            "best_streak": best_streak,
        },
    }


def _calc_current_streak(db: Session, today: date) -> int:
    """오늘부터 거꾸로 매일 완료가 있는지 확인."""
    streak = 0
    for offset in range(0, 365):
        d = today - timedelta(days=offset)
        start = datetime(d.year, d.month, d.day)
        end = start + timedelta(days=1)
        cnt = (
            db.query(func.count(HabitCompletion.id))
            .filter(HabitCompletion.completed_at >= start)
            .filter(HabitCompletion.completed_at < end)
            .scalar()
        )
        if cnt and cnt > 0:
            streak += 1
        else:
            # 오늘은 아직 안 했어도 streak 깨진 건 아님 — 어제부터 카운트 시작
            if offset == 0:
                continue
            break
    return streak


def _calc_best_streak_in_month(days: Dict[str, Dict], year: int, month: int) -> int:
    """그달 안에서 연속 완료된 최장 일수."""
    from datetime import datetime as DT, timedelta as TD
    start_d = DT(year, month, 1).date()
    if month == 12:
        end_d = DT(year + 1, 1, 1).date()
    else:
        end_d = DT(year, month + 1, 1).date()

    best = 0
    cur = 0
    d = start_d
    while d < end_d:
        key = d.strftime("%Y-%m-%d")
        if key in days and days[key]["completions"] > 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
        d += TD(days=1)
    return best


# ─── 2. 날짜별 디테일 ────────────────────────────────────
@router.get("/day")
def get_day(
    date: str = Query(..., description="YYYY-MM-DD 형식"),
    db: Session = Depends(get_db),
):
    """특정 날짜의 자세한 정보."""
    try:
        d = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "date 형식은 YYYY-MM-DD")

    start = d
    end = d + timedelta(days=1)

    # 그날 완료한 일정들
    completions = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.completed_at >= start)
        .filter(HabitCompletion.completed_at < end)
        .all()
    )

    # 완료 정보 (habit 제목 join)
    completed_list = []
    for c in completions:
        h = db.query(Habit).filter(Habit.id == c.habit_id).first()
        completed_list.append({
            "habit_id": c.habit_id,
            "title": h.title if h else "(삭제된 일정)",
            "completed_at": c.completed_at.strftime("%H:%M"),
            "hearts_earned": c.hearts_earned,
        })

    # 그날 예정이었던 일정들 (현재 habit 기준 — 과거 habit 변경 이력은 없음)
    habits = db.query(Habit).all()
    scheduled = _scheduled_on(d.date(), habits)
    completed_habit_ids = {c.habit_id for c in completions}
    scheduled_list = []
    for h in scheduled:
        scheduled_list.append({
            "habit_id": h.id,
            "title": h.title,
            "times": h.times or [],
            "completed": h.id in completed_habit_ids,
        })

    total_hearts = sum(c.hearts_earned for c in completions)

    return {
        "date": date,
        "completed": completed_list,
        "scheduled": scheduled_list,
        "total_hearts": total_hearts,
        "completion_count": len(completed_list),
        "scheduled_count": len(scheduled_list),
    }
