"""Plan-Quest — AI 자동 일정 추천.

엔드포인트:
  GET /api/suggestions/habits         — 추천할 새 일정 목록 (사용자 패턴 기반)
  GET /api/suggestions/empty-slots    — 비어있는 시간대 (요일별 + 시간대별)
  GET /api/suggestions/best-time?habit_title=...
      — 특정 일정에 가장 적합한 시간 추천 (사용자 패턴 기반)

전략:
  - 사용자가 자주 완료하는 요일 / 시간대 분석 (HabitCompletion)
  - 등록된 일정의 시간대 vs 실제 완료 패턴 비교
  - 빈 시간대 + 유사 사용자 라이브러리에서 추천 일정 골라줌
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Habit, HabitCompletion

router = APIRouter(prefix="/api/suggestions", tags=["자동추천"])

DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
HOUR_BUCKETS = {
    "아침": list(range(5, 11)),
    "낮":   list(range(11, 17)),
    "저녁": list(range(17, 22)),
    "밤":   list(range(22, 24)) + list(range(0, 5)),
}


# ─── 추천할 일정 라이브러리 (카테고리별) ──────────────
HABIT_LIBRARY = {
    "건강": [
        {"title": "물 2L 마시기", "default_time": "09:00", "days": [0, 1, 2, 3, 4, 5, 6]},
        {"title": "스트레칭 10분", "default_time": "08:00", "days": [0, 1, 2, 3, 4]},
        {"title": "유산소 운동", "default_time": "18:00", "days": [1, 3, 5]},
        {"title": "근력 운동", "default_time": "19:00", "days": [0, 2, 4]},
        {"title": "산책 30분", "default_time": "18:30", "days": [0, 1, 2, 3, 4, 5, 6]},
    ],
    "공부": [
        {"title": "독서 30분", "default_time": "21:00", "days": [0, 1, 2, 3, 4]},
        {"title": "영어 단어 외우기", "default_time": "07:30", "days": [0, 1, 2, 3, 4]},
        {"title": "강의 듣기", "default_time": "20:00", "days": [1, 3, 5]},
        {"title": "복습 정리", "default_time": "22:00", "days": [0, 1, 2, 3, 4]},
    ],
    "마음": [
        {"title": "명상 10분", "default_time": "07:00", "days": [0, 1, 2, 3, 4, 5, 6]},
        {"title": "일기 쓰기", "default_time": "22:30", "days": [0, 1, 2, 3, 4, 5, 6]},
        {"title": "감사 3가지 적기", "default_time": "21:30", "days": [0, 1, 2, 3, 4, 5, 6]},
    ],
    "생활": [
        {"title": "방 정리 5분", "default_time": "08:30", "days": [0, 1, 2, 3, 4, 5, 6]},
        {"title": "장보기", "default_time": "10:00", "days": [5]},
        {"title": "이불 개기", "default_time": "07:00", "days": [0, 1, 2, 3, 4, 5, 6]},
    ],
}


def _gather_user_pattern(db: Session, days: int = 30) -> Dict:
    """최근 N일 사용자 완료 패턴 집계."""
    start = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.completed_at >= start)
        .all()
    )

    by_dow = Counter()
    by_hour = Counter()
    by_bucket = Counter()

    for r in rows:
        dt = r.completed_at
        by_dow[dt.weekday()] += 1
        by_hour[dt.hour] += 1
        for bucket, hours in HOUR_BUCKETS.items():
            if dt.hour in hours:
                by_bucket[bucket] += 1
                break

    return {
        "total": len(rows),
        "by_dow": dict(by_dow),
        "by_hour": dict(by_hour),
        "by_bucket": dict(by_bucket),
    }


def _existing_habit_titles(db: Session) -> set:
    return {h.title for h in db.query(Habit).all()}


# ─── 1. 추천 일정 목록 ──────────────────────────────────
@router.get("/habits")
def suggest_habits(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """라이브러리에서 사용자 패턴에 맞는 새 일정 추천.

    이미 등록된 일정은 제외.
    사용자의 강한 요일/시간대에 맞는 일정 우선.
    """
    pattern = _gather_user_pattern(db)
    existing = _existing_habit_titles(db)

    # 사용자의 강한 시간대
    best_bucket = (
        max(pattern["by_bucket"], key=pattern["by_bucket"].get)
        if pattern["by_bucket"] else None
    )

    # 모든 후보 일정 (이미 등록된 것 제외)
    candidates = []
    for category, habits in HABIT_LIBRARY.items():
        for h in habits:
            if h["title"] in existing:
                continue

            # 점수 계산
            score = 1.0
            # default_time 이 사용자의 강한 시간대에 속하면 +
            try:
                hour = int(h["default_time"].split(":")[0])
                for bucket, hours in HOUR_BUCKETS.items():
                    if hour in hours:
                        if bucket == best_bucket:
                            score += 2.0
                        break
            except (ValueError, IndexError):
                pass

            # 카테고리 다양성 보너스 (사용자가 다른 카테고리 일정 적게 가졌으면 +)
            existing_cats = sum(1 for e in existing if any(lh["title"] == e for lh in HABIT_LIBRARY.get(category, [])))
            if existing_cats == 0:
                score += 1.5  # 해당 카테고리 일정이 0개면 가중치

            candidates.append({
                "category": category,
                "title": h["title"],
                "suggested_time": h["default_time"],
                "suggested_days": h["days"],
                "suggested_days_label": [DAY_NAMES[d] for d in h["days"]],
                "score": round(score, 2),
                "reason": _build_reason(score, best_bucket, h),
            })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return {
        "user_pattern": {
            "best_bucket": best_bucket,
            "total_completions_30d": pattern["total"],
        },
        "suggestions": candidates[:limit],
    }


def _build_reason(score: float, best_bucket: str, habit: Dict) -> str:
    """추천 이유 텍스트."""
    parts = []
    if score >= 3:
        parts.append("✨ 강력 추천")
    if best_bucket:
        try:
            hour = int(habit["default_time"].split(":")[0])
            for bucket, hours in HOUR_BUCKETS.items():
                if hour in hours and bucket == best_bucket:
                    parts.append(f"평소 {bucket} 시간대 활동 많음")
                    break
        except Exception:
            pass
    days = habit.get("days", [])
    if len(days) == 7:
        parts.append("매일")
    elif len(days) == 5 and set(days) == {0, 1, 2, 3, 4}:
        parts.append("평일")
    return " · ".join(parts) if parts else "균형있는 일정"


# ─── 2. 빈 시간대 탐지 ─────────────────────────────────
@router.get("/empty-slots")
def find_empty_slots(db: Session = Depends(get_db)):
    """현재 등록된 일정의 시간대 분포 + 비어있는 시간대.

    응답:
      {
        "busy_hours":  {0: 0, 1: 0, ..., 9: 2, ...},   # 시간별 등록 일정 수
        "busy_buckets": {"아침": 3, "낮": 1, ...},
        "empty_buckets": ["밤"],  # 일정 0인 시간대
        "weakly_used":  ["낮"],   # 일정 적은 시간대
      }
    """
    habits = db.query(Habit).all()
    by_hour = Counter()
    by_bucket = Counter()

    for h in habits:
        for t in (h.times or []):
            try:
                hour = int(str(t).split(":")[0])
                by_hour[hour] += 1
                for bucket, hours in HOUR_BUCKETS.items():
                    if hour in hours:
                        by_bucket[bucket] += 1
                        break
            except (ValueError, IndexError):
                pass

    all_buckets = list(HOUR_BUCKETS.keys())
    empty = [b for b in all_buckets if by_bucket.get(b, 0) == 0]
    weakly = [b for b in all_buckets if 0 < by_bucket.get(b, 0) <= 1]

    return {
        "busy_hours": {h: by_hour.get(h, 0) for h in range(24)},
        "busy_buckets": dict(by_bucket),
        "empty_buckets": empty,
        "weakly_used": weakly,
        "advice": _build_slot_advice(empty, weakly),
    }


def _build_slot_advice(empty: List[str], weakly: List[str]) -> str:
    if not empty and not weakly:
        return "시간대 골고루 잘 분산되어 있어요!"
    parts = []
    if empty:
        parts.append(f"{', '.join(empty)} 시간대가 비어있어요. 일정 추가 추천.")
    if weakly:
        parts.append(f"{', '.join(weakly)} 는 일정이 적어요.")
    return " ".join(parts)


# ─── 3. 특정 일정의 최적 시간 추천 ─────────────────────
@router.get("/best-time")
def best_time_for_habit(
    habit_title: str = Query(..., description="일정 제목"),
    db: Session = Depends(get_db),
):
    """주어진 일정 제목에 가장 적합한 시간 추천.

    - 라이브러리에 있으면 default_time 사용
    - 없으면 사용자의 활동 가장 많은 시간 추천
    """
    # 라이브러리 매칭
    for category, habits in HABIT_LIBRARY.items():
        for h in habits:
            if h["title"] == habit_title:
                return {
                    "habit_title": habit_title,
                    "suggested_time": h["default_time"],
                    "suggested_days": h["days"],
                    "source": "library",
                    "category": category,
                }

    # 사용자 패턴 기반
    pattern = _gather_user_pattern(db)
    if pattern["by_hour"]:
        best_hour = max(pattern["by_hour"], key=pattern["by_hour"].get)
        return {
            "habit_title": habit_title,
            "suggested_time": f"{best_hour:02d}:00",
            "suggested_days": [0, 1, 2, 3, 4],
            "source": "user_pattern",
        }

    # 기본값
    return {
        "habit_title": habit_title,
        "suggested_time": "09:00",
        "suggested_days": [0, 1, 2, 3, 4],
        "source": "default",
    }
