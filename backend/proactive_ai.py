"""
Plan-Quest — 능동적 AI / 개인화 엔진.

사용자가 묻기 전에 AI 가 패턴을 보고 먼저 제안하는 로직.

기능:
  1) get_proactive_suggestions() — 지금 사용자에게 알려주면 좋을 것들 모음
  2) analyze_habit_pattern()     — 일정 달성 패턴 분석 (약한 시간대 등)
  3) build_personalization_context() — 메모리 + 게임 상태 결합한 AI 프롬프트 컨텍스트

엔드포인트(라우터에서 노출):
  GET /api/proactive/suggestions  — JSON 배열로 반환
  GET /api/proactive/insights     — 패턴 분석 결과
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

DAY_NAMES_KR = ["월", "화", "수", "목", "금", "토", "일"]

from models import (
    UserProfile,
    Habit,
    ShopItem,
    OwnedItem,
    PlacedItem,
    TreeOnMap,
    UserMemory,
    HabitCompletion,
)


# ─── 1. 능동적 제안 ─────────────────────────────────────
def get_proactive_suggestions(db: Session, user_id: int = 1) -> List[Dict]:
    """지금 사용자에게 알려줄 만한 것들.

    반환:
        [{"type": "harvest" | "shop" | "habit_streak" | "place_character" | "encouragement",
          "priority": 1-5,
          "title": "...",
          "message": "...",
          "action_hint": "..."}]
    """
    user = db.query(UserProfile).filter_by(id=user_id).first()
    if not user:
        return []

    suggestions: List[Dict] = []

    # ① 수확 가능한 하트 있음 → 알려주기
    trees = db.query(TreeOnMap).all()
    pending_hearts = sum(t.hearts_available or 0 for t in trees)
    if pending_hearts >= 3:
        suggestions.append({
            "type": "harvest",
            "priority": 5,
            "title": f"💗 수확 가능한 하트 {pending_hearts}개!",
            "message": f"나무들에서 하트 {pending_hearts}개를 수확할 수 있어요. 지금 클릭해서 받아가세요.",
            "action_hint": "배치도의 큰 나무를 클릭",
        })

    # ② 보유했는데 안 배치한 캐릭터 있음
    owned = db.query(OwnedItem).filter_by(user_id=user_id).all()
    placed_ids = {p.owned_item_id for p in db.query(PlacedItem).filter_by(user_id=user_id).all()}
    unplaced = [o for o in owned if o.id not in placed_ids]
    if unplaced:
        names = [o.shop_item.name for o in unplaced[:3] if o.shop_item]
        suggestions.append({
            "type": "place_character",
            "priority": 3,
            "title": f"🎒 배치 안 한 캐릭터 {len(unplaced)}마리",
            "message": f"{', '.join(names)} 등이 가방에서 기다리고 있어요. 정원에 올려보세요.",
            "action_hint": "인벤토리에서 '배치' 클릭",
        })

    # ③ 살 수 있는 새 캐릭터
    owned_ids = {o.shop_item_id for o in owned}
    affordable = db.query(ShopItem).filter(
        ShopItem.category == "character",
        ShopItem.price <= user.hearts,
        ShopItem.unlock_level <= user.level,
    ).all()
    new_affordable = [it for it in affordable if it.id not in owned_ids]
    if new_affordable and user.hearts >= 3:
        cheapest = min(new_affordable, key=lambda x: x.price)
        suggestions.append({
            "type": "shop",
            "priority": 2,
            "title": f"🛍️ 새 캐릭터 살 수 있어요",
            "message": f"{cheapest.emoji} {cheapest.name} ({cheapest.price}H) 부터 시작해보면 어때요?",
            "action_hint": "상점 열기",
        })

    # ④ 연속 달성 격려 (streak 높은 습관)
    habits = db.query(Habit).filter_by(user_id=user_id).all()
    if habits:
        best_streak = max(habits, key=lambda h: h.streak or 0)
        if (best_streak.streak or 0) >= 3:
            suggestions.append({
                "type": "habit_streak",
                "priority": 4,
                "title": f"🔥 {best_streak.streak}일 연속!",
                "message": f"'{best_streak.title}' 습관을 {best_streak.streak}일째 이어가고 있어요. 멋져요!",
                "action_hint": None,
            })

    # ⑤ 일정이 너무 적으면 격려
    if len(habits) < 2:
        suggestions.append({
            "type": "encouragement",
            "priority": 1,
            "title": "🌱 새 습관 추가해보세요",
            "message": "일정을 추가하면 씨앗이 심어지고, 완료하면 나무가 자라서 하트를 줘요.",
            "action_hint": "일정 → 새로 추가",
        })

    # ⑥ 약한 요일 알림 (지난 30일 완료 기록 기반)
    start = datetime.utcnow() - timedelta(days=30)
    completions = db.query(HabitCompletion).filter(
        HabitCompletion.completed_at >= start
    ).all()
    if len(completions) >= 10:  # 최소 데이터 있을 때만
        by_dow = Counter()
        for c in completions:
            by_dow[c.completed_at.weekday()] += 1
        if len(by_dow) >= 2:
            weak_dow = min(by_dow, key=by_dow.get)
            today_dow = datetime.now().weekday()
            if today_dow == weak_dow:
                suggestions.append({
                    "type": "weak_day_today",
                    "priority": 4,
                    "title": f"💪 {DAY_NAMES_KR[weak_dow]}요일 약점 극복!",
                    "message": f"지난 30일간 {DAY_NAMES_KR[weak_dow]}요일에 다른 요일보다 적게 완료하셨어요. 오늘 한 개라도 완료하면 패턴이 바뀝니다.",
                    "action_hint": None,
                })

    # 우선순위 높은 순
    suggestions.sort(key=lambda s: s["priority"], reverse=True)
    return suggestions


# ─── 2. 일정 달성 패턴 분석 ─────────────────────────────
def analyze_habit_pattern(db: Session, user_id: int = 1) -> Dict:
    """사용자의 습관 데이터 + 실제 완료 기록에서 패턴 추출.

    반환:
        {
          "total_habits": int,
          "avg_streak": float,
          "best_habit": str,
          "best_dow": "월" | ...        # 잘 달성하는 요일 (실제 완료 기록 기반)
          "weak_dow": "월" | ...        # 약한 요일
          "best_time_bucket": "아침"... # 잘 활동하는 시간대
          "completion_rate_today": float,
          "month_completed_days": int,  # 지난 30일 중 1건이라도 완료한 일수
        }
    """
    habits = db.query(Habit).filter_by(user_id=user_id).all()
    if not habits:
        return {"total_habits": 0}

    streaks = [h.streak or 0 for h in habits]
    avg_streak = sum(streaks) / len(streaks) if streaks else 0

    best = max(habits, key=lambda h: h.streak or 0)
    completed_today = sum(1 for h in habits if h.completed_today)

    # ── 실제 완료 기록 기반 분석 (지난 30일) ──
    DAY_NAMES_KR = ["월", "화", "수", "목", "금", "토", "일"]
    start = datetime.utcnow() - timedelta(days=30)
    completions = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.completed_at >= start)
        .all()
    )

    by_dow = Counter()
    by_hour = Counter()
    completed_days = set()
    for c in completions:
        by_dow[c.completed_at.weekday()] += 1
        h = c.completed_at.hour
        if 5 <= h < 11: by_hour["아침"] += 1
        elif 11 <= h < 17: by_hour["낮"] += 1
        elif 17 <= h < 22: by_hour["저녁"] += 1
        else: by_hour["밤"] += 1
        completed_days.add(c.completed_at.strftime("%Y-%m-%d"))

    best_dow = DAY_NAMES_KR[max(by_dow, key=by_dow.get)] if by_dow else None
    weak_dow = DAY_NAMES_KR[min(by_dow, key=by_dow.get)] if len(by_dow) >= 2 else None
    best_time = max(by_hour, key=by_hour.get) if by_hour else None

    return {
        "total_habits": len(habits),
        "avg_streak": round(avg_streak, 1),
        "best_habit": best.title,
        "best_streak": best.streak,
        "best_dow": best_dow,
        "weak_dow": weak_dow,
        "best_time_bucket": best_time,
        "completed_today": completed_today,
        "completion_rate_today": round(completed_today / len(habits), 2) if habits else 0,
        "month_completed_days": len(completed_days),
        "month_total_completions": len(completions),
    }


# ─── 3. 개인화 컨텍스트 (AI 프롬프트 주입용) ──────────
def build_personalization_context(
    db: Session,
    query: str,
    user_id: int = 1,
    include_memory: bool = True,
) -> str:
    """사용자 게임 상태 + 과거 메모리 결합한 컨텍스트.

    AI 가 응답할 때 "지금 사용자가 어떤 상태인지" 알 수 있게 주입.
    너무 길면 모델이 혼란스러우므로 핵심만.
    """
    user = db.query(UserProfile).filter_by(id=user_id).first()
    if not user:
        return ""

    pattern = analyze_habit_pattern(db, user_id)
    n_owned = db.query(OwnedItem).filter_by(user_id=user_id).count()
    n_placed = db.query(PlacedItem).filter_by(user_id=user_id).count()

    lines = [
        "[사용자 현재 상태]",
        f"- Lv.{user.level}, 하트 {user.hearts}",
        f"- 보유 캐릭터 {n_owned}, 배치 {n_placed}",
    ]
    if pattern.get("total_habits"):
        lines.append(
            f"- 일정 {pattern['total_habits']}개, 오늘 달성률 {int(pattern['completion_rate_today']*100)}%, "
            f"최고 연속 {pattern.get('best_streak', 0)}일"
        )

    # 메모리에서 관련 과거 맥락
    if include_memory:
        try:
            from memory_engine import get_memory_engine
            engine = get_memory_engine()
            if engine.enabled:
                ctx = engine.build_context(user_id=user_id, query=query, top_k=2, db=db)
                if ctx:
                    lines.append("")
                    lines.append(ctx)
        except Exception:
            pass


    return "\n".join(lines)
