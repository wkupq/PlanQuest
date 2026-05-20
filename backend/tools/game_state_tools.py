"""Plan-Quest - 게임 상태 인식 AI 도구.

새 게임 흐름 (하트 → 나무 → 캐릭터 배치) 에 맞춰 AI 가 게임 데이터를 조회할 수 있게 한다.

도구:
  - get_user_stats          : 하트, 레벨, 누적 하트
  - get_placed_characters   : 배치도에 배치된 캐릭터들
  - get_owned_characters    : 보유 (배치 안 된) 캐릭터들
  - get_growing_trees       : 자라는 나무들 + 진행도
  - get_shop_recommendations: 살 만한 캐릭터 추천 (보유 안 한 + 가격 적당한 것)
  - get_garden_summary      : 정원 한 줄 요약

모든 함수는 사람이 읽기 좋은 한국어 문자열 반환 (LLM 이 그대로 응답에 활용).
"""
from typing import List
from datetime import datetime, timedelta
from collections import Counter

from database import SessionLocal
from models import (
    UserProfile,
    Habit,
    ShopItem,
    OwnedItem,
    PlacedItem,
    TreeOnMap,
    HabitCompletion,
)


# ─── 1. 사용자 기본 통계 ────────────────────────────────
def get_user_stats(_: str = "") -> str:
    """사용자 통계 (하트, 레벨, 누적 하트)."""
    db = SessionLocal()
    try:
        user = db.query(UserProfile).first()
        if not user:
            return "사용자 정보가 없습니다."
        return (
            f"❤️ 하트: {user.hearts}\n"
            f"⭐ 레벨: {user.level}\n"
            f"📊 누적 획득 하트: {user.total_hearts_earned}"
        )
    finally:
        db.close()


# ─── 2. 배치된 캐릭터 ──────────────────────────────────
def get_placed_characters(_: str = "") -> str:
    """배치도 위에 올라가 있는 캐릭터 목록."""
    db = SessionLocal()
    try:
        rows = db.query(PlacedItem).filter_by(user_id=1).all()
        if not rows:
            return "배치된 캐릭터가 없습니다. 상점에서 사서 배치도에 올려보세요!"

        lines = [f"🌱 배치된 캐릭터 {len(rows)}마리:"]
        for r in rows:
            owned = r.owned_item
            if owned and owned.shop_item:
                item = owned.shop_item
                lines.append(
                    f"- {item.emoji} {item.name} "
                    f"(타일 {r.grid_x},{r.grid_y}) [{item.rarity}]"
                )
        return "\n".join(lines)
    finally:
        db.close()


# ─── 3. 보유 캐릭터 (배치 안 된) ───────────────────────
def get_owned_characters(_: str = "") -> str:
    """보유했지만 아직 배치 안 한 캐릭터."""
    db = SessionLocal()
    try:
        owned = db.query(OwnedItem).filter_by(user_id=1).all()
        placed_ids = {p.owned_item_id for p in db.query(PlacedItem).filter_by(user_id=1).all()}

        unplaced = [o for o in owned if o.id not in placed_ids]
        if not unplaced:
            return "모든 보유 캐릭터가 배치되어 있습니다."

        lines = [f"🎒 미배치 캐릭터 {len(unplaced)}마리:"]
        for o in unplaced:
            if o.shop_item:
                lines.append(f"- {o.shop_item.emoji} {o.shop_item.name}")
        return "\n".join(lines)
    finally:
        db.close()


# ─── 4. 자라는 나무 ───────────────────────────────────
GROWTH_NAMES = ["씨앗", "새싹", "작은나무", "큰나무"]


def get_growing_trees(_: str = "") -> str:
    """배치도에 심어진 나무들 + 성장 단계 + 수확 가능 하트."""
    db = SessionLocal()
    try:
        trees = db.query(TreeOnMap).all()
        if not trees:
            return "심어진 나무가 없습니다. 일정을 추가하면 씨앗이 심어집니다."

        lines = [f"🌳 나무 {len(trees)}그루:"]
        total_hearts = 0
        for t in trees:
            stage = GROWTH_NAMES[min(t.growth_stage, 3)]
            habit_title = t.habit.title if t.habit else "(연결 끊김)"
            heart_str = f" 💗{t.hearts_available} 수확가능" if t.hearts_available else ""
            lines.append(f"- '{habit_title}' → {stage}{heart_str}")
            total_hearts += t.hearts_available or 0

        if total_hearts > 0:
            lines.append(f"\n💡 지금 수확하면 하트 {total_hearts}개 받을 수 있어요!")
        return "\n".join(lines)
    finally:
        db.close()


# ─── 5. 상점 추천 ─────────────────────────────────────
def get_shop_recommendations(_: str = "") -> str:
    """현재 하트로 살 수 있는 + 아직 보유 안 한 캐릭터 추천."""
    db = SessionLocal()
    try:
        user = db.query(UserProfile).first()
        if not user:
            return "사용자 정보 없음."

        owned_ids = {o.shop_item_id for o in db.query(OwnedItem).filter_by(user_id=1).all()}

        # 살 수 있는 것: 보유 안 함 + 레벨 충족 + 하트 충분
        all_items = db.query(ShopItem).filter(ShopItem.category == "character").all()
        affordable = [
            it for it in all_items
            if it.id not in owned_ids
            and it.unlock_level <= user.level
            and it.price <= user.hearts
        ]

        if not affordable:
            # 곧 살 수 있는 것 (가격은 안 닿지만 레벨 OK)
            soon = sorted(
                [it for it in all_items if it.id not in owned_ids and it.unlock_level <= user.level],
                key=lambda x: x.price,
            )[:3]
            if soon:
                lines = [f"❤️ {user.hearts}하트로 지금 살 수 있는 캐릭터는 없어요."]
                lines.append("조금 더 모으면 살 수 있는 친구들:")
                for it in soon:
                    short = (it.price - user.hearts)
                    lines.append(f"- {it.emoji} {it.name} ({it.price}H, {short}하트 더 필요)")
                return "\n".join(lines)
            return "모든 캐릭터를 보유 중이거나 아직 잠겨 있어요."

        # 가격 낮은 순 + 가장 비싼 affordable 도 추천
        affordable.sort(key=lambda x: x.price)
        picks = affordable[:3]
        if len(affordable) > 3:
            picks.append(affordable[-1])  # 가장 비싼 affordable 도 같이

        lines = [f"🛍️ {user.hearts}하트로 살 수 있는 캐릭터 추천:"]
        for it in picks:
            lines.append(f"- {it.emoji} {it.name} ({it.price}H, {it.rarity})")
        return "\n".join(lines)
    finally:
        db.close()


# ─── 6.5 완료 기록 (HabitCompletion) ─────────────────
DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


def get_completion_history(period: str = "week") -> str:
    """최근 일정 완료 기록.

    period: "today" | "week" | "month"
    """
    db = SessionLocal()
    try:
        now = datetime.now()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now - timedelta(days=30)
        else:  # week
            start = now - timedelta(days=7)

        rows = (
            db.query(HabitCompletion)
            .filter(HabitCompletion.completed_at >= start)
            .all()
        )
        if not rows:
            return f"📊 최근 {period}: 완료한 일정이 없어요."

        # 일정 제목별 집계
        by_habit = Counter()
        for r in rows:
            h = db.query(Habit).filter(Habit.id == r.habit_id).first()
            title = h.title if h else "(삭제됨)"
            by_habit[title] += 1

        total_hearts = sum(r.hearts_earned or 0 for r in rows)
        period_label = {"today": "오늘", "week": "지난 7일", "month": "지난 30일"}[period]

        lines = [f"📊 {period_label} 완료 기록:"]
        lines.append(f"- 총 완료: {len(rows)}건")
        lines.append(f"- 받은 하트: {total_hearts}개")
        lines.append(f"- 일정별:")
        for title, cnt in by_habit.most_common(5):
            lines.append(f"   • {title}: {cnt}회")
        return "\n".join(lines)
    finally:
        db.close()


def get_today_progress(_: str = "") -> str:
    """오늘 완료한 일정 vs 예정된 일정 진행도."""
    db = SessionLocal()
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        # 오늘 예정 (현재 habit + 요일 매칭)
        krDow = datetime.now().weekday()
        habits = db.query(Habit).all()
        scheduled = [h for h in habits
                     if not (h.repeat_days or []) or krDow in (h.repeat_days or [])]

        # 오늘 완료
        completions = (
            db.query(HabitCompletion)
            .filter(HabitCompletion.completed_at >= today)
            .filter(HabitCompletion.completed_at < tomorrow)
            .all()
        )
        completed_ids = {c.habit_id for c in completions}

        if not scheduled:
            return "📅 오늘 예정된 일정이 없어요."

        done = [h for h in scheduled if h.id in completed_ids]
        pending = [h for h in scheduled if h.id not in completed_ids]
        pct = int(len(done) / len(scheduled) * 100)

        lines = [f"📅 오늘 진행도: {len(done)}/{len(scheduled)} ({pct}%)"]
        if done:
            lines.append("✅ 완료:")
            for h in done:
                lines.append(f"   - {h.title}")
        if pending:
            lines.append("⏳ 남은 일정:")
            for h in pending:
                t = ", ".join(h.times or [])
                lines.append(f"   - {h.title}{f' ({t})' if t else ''}")
        return "\n".join(lines)
    finally:
        db.close()


def analyze_weak_pattern(_: str = "") -> str:
    """완료 기록에서 약한 요일/시간대 분석."""
    db = SessionLocal()
    try:
        # 지난 30일 기록
        start = datetime.now() - timedelta(days=30)
        rows = (
            db.query(HabitCompletion)
            .filter(HabitCompletion.completed_at >= start)
            .all()
        )
        if len(rows) < 5:
            return "📊 분석할 기록이 부족해요. 일정을 더 완료하면 패턴이 보일 거예요."

        # 요일별 완료 수 (0=월 ... 6=일)
        by_dow = Counter()
        # 시간대별 완료 수
        by_hour_bucket = Counter()  # "아침"/"낮"/"저녁"/"밤"

        for r in rows:
            dt = r.completed_at
            by_dow[dt.weekday()] += 1
            h = dt.hour
            if 5 <= h < 11: by_hour_bucket["아침"] += 1
            elif 11 <= h < 17: by_hour_bucket["낮"] += 1
            elif 17 <= h < 22: by_hour_bucket["저녁"] += 1
            else: by_hour_bucket["밤"] += 1

        lines = ["📊 최근 30일 패턴 분석:"]

        # 강한/약한 요일
        if by_dow:
            best_dow = max(by_dow, key=by_dow.get)
            worst_dow = min(by_dow, key=by_dow.get)
            lines.append(f"- 가장 잘하는 요일: {DAY_NAMES[best_dow]} ({by_dow[best_dow]}회)")
            if by_dow[worst_dow] < by_dow[best_dow]:
                lines.append(f"- 약한 요일: {DAY_NAMES[worst_dow]} ({by_dow[worst_dow]}회)")

        # 강한/약한 시간대
        if by_hour_bucket:
            best_h = max(by_hour_bucket, key=by_hour_bucket.get)
            lines.append(f"- 주로 활동 시간대: {best_h} ({by_hour_bucket[best_h]}회)")

        return "\n".join(lines)
    finally:
        db.close()


# ─── 6. 정원 한 줄 요약 ───────────────────────────────
def get_garden_summary(_: str = "") -> str:
    """전체 게임 진행 상황을 한 줄로."""
    db = SessionLocal()
    try:
        user = db.query(UserProfile).first()
        n_trees = db.query(TreeOnMap).count()
        n_placed = db.query(PlacedItem).filter_by(user_id=1).count()
        n_owned = db.query(OwnedItem).filter_by(user_id=1).count()
        n_habits = db.query(Habit).count()
        ready_hearts = sum(
            t.hearts_available or 0 for t in db.query(TreeOnMap).all()
        )

        return (
            f"📊 정원 현황:\n"
            f"  Lv.{user.level} • ❤️{user.hearts} • 누적❤️{user.total_hearts_earned}\n"
            f"  일정 {n_habits}개 / 나무 {n_trees}그루 / 보유 캐릭터 {n_owned}마리 / 배치 {n_placed}마리\n"
            f"  지금 수확 가능: {ready_hearts}하트"
        )
    finally:
        db.close()
