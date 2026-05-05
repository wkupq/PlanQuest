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

from models import (
    UserProfile,
    Habit,
    ShopItem,
    OwnedItem,
    PlacedItem,
    TreeOnMap,
    UserMemory,
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

    # 우선순위 높은 순
    suggestions.sort(key=lambda s: s["priority"], reverse=True)
    return suggestions


# ─── 2. 일정 달성 패턴 분석 ─────────────────────────────
def analyze_habit_pattern(db: Session, user_id: int = 1) -> Dict:
    """사용자의 습관 데이터에서 패턴 추출.

    반환:
        {
          "total_habits": int,
          "avg_streak": float,
          "best_habit": str,
          "weakest_time": str,   # "아침" | "낮" | "저녁" | "밤"
          "completion_rate_today": float,
        }
    """
    habits = db.query(Habit).filter_by(user_id=user_id).all()
    if not habits:
        return {"total_habits": 0}

    streaks = [h.streak or 0 for h in habits]
    avg_streak = sum(streaks) / len(streaks) if streaks else 0

    best = max(habits, key=lambda h: h.streak or 0)
    completed_today = sum(1 for h in habits if h.completed_today)

    # 시간대 분석 — habit.times 의 시간을 모음
    time_buckets = Counter()
    for h in habits:
        for t in (h.times or []):
            try:
                hh = int(str(t).split(":")[0])
                if 5 <= hh < 11:
                    time_buckets["아침"] += 1
                elif 11 <= hh < 17:
                    time_buckets["낮"] += 1
                elif 17 <= hh < 22:
                    time_buckets["저녁"] += 1
                else:
                    time_buckets["밤"] += 1
            except (ValueError, IndexError):
                pass

    weakest_time = None
    if time_buckets:
        # 가장 적은 시간대
        weakest_time = min(time_buckets, key=time_buckets.get)

    return {
        "total_habits": len(habits),
        "avg_streak": round(avg_streak, 1),
        "best_habit": best.title,
        "best_streak": best.streak,
        "weakest_time": weakest_time,
        "completed_today": completed_today,
        "completion_rate_today": round(completed_today / len(habits), 2) if habits else 0,
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
