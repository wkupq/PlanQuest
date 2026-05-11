"""Plan-Quest — AI 인사이트 리포트.

LLM (Ollama) 으로 자연어 분석 보고서 자동 생성.

엔드포인트:
  GET /api/insights/weekly        — 지난 7일 분석
  GET /api/insights/monthly       — 지난 30일 분석
  GET /api/insights/quick         — 짧은 한 줄 요약 (LLM 없이도 동작)

리포트 구성:
  - 통계 요약 (완료수, 하트, 연속, 강한/약한 요일/시간)
  - AI 자연어 인사이트 (격려 + 패턴 지적 + 다음주 제안)
  - 추천 행동 3가지

LLM 미설치 시:
  - 통계만 반환, AI 인사이트는 템플릿 기반 자동 생성
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Habit, HabitCompletion, UserProfile

router = APIRouter(prefix="/api/insights", tags=["인사이트"])


DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


# ─── 1. 통계 집계 ────────────────────────────────────────
def _gather_stats(db: Session, days: int) -> Dict:
    """지난 N일 데이터 집계."""
    now = datetime.now()
    start = now - timedelta(days=days)

    rows = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.completed_at >= start)
        .all()
    )

    by_dow = Counter()
    by_hour_bucket = Counter()
    by_day = Counter()
    by_habit = Counter()
    total_hearts = 0

    for r in rows:
        dt = r.completed_at
        by_dow[dt.weekday()] += 1
        h = dt.hour
        if 5 <= h < 11: bucket = "아침"
        elif 11 <= h < 17: bucket = "낮"
        elif 17 <= h < 22: bucket = "저녁"
        else: bucket = "밤"
        by_hour_bucket[bucket] += 1
        by_day[dt.strftime("%Y-%m-%d")] += 1
        habit = db.query(Habit).filter_by(id=r.habit_id).first()
        if habit:
            by_habit[habit.title] += 1
        total_hearts += r.hearts_earned or 0

    # 강한/약한 요일
    best_dow = max(by_dow, key=by_dow.get) if by_dow else None
    weak_dow = min(by_dow, key=by_dow.get) if len(by_dow) >= 2 else None
    best_hour = max(by_hour_bucket, key=by_hour_bucket.get) if by_hour_bucket else None
    weak_hour = min(by_hour_bucket, key=by_hour_bucket.get) if len(by_hour_bucket) >= 2 else None

    # 연속 달성 (오늘부터 거꾸로)
    streak = 0
    for offset in range(0, days):
        d = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        if by_day.get(d, 0) > 0:
            streak += 1
        else:
            if offset == 0:
                continue
            break

    return {
        "period_days": days,
        "total_completions": len(rows),
        "total_hearts": total_hearts,
        "active_days": len(by_day),
        "completion_rate": round(len(by_day) / days, 2),
        "best_dow": DAY_NAMES[best_dow] if best_dow is not None else None,
        "weak_dow": DAY_NAMES[weak_dow] if weak_dow is not None else None,
        "best_hour_bucket": best_hour,
        "weak_hour_bucket": weak_hour,
        "current_streak": streak,
        "top_habits": dict(by_habit.most_common(3)),
        "by_dow_counts": {DAY_NAMES[d]: c for d, c in by_dow.items()},
        "by_hour_counts": dict(by_hour_bucket),
    }


# ─── 2. 템플릿 기반 인사이트 (LLM 없이) ────────────────
def _template_insight(stats: Dict, period_label: str) -> str:
    """LLM 없을 때 사용. 통계 → 자연어 변환."""
    lines = []
    n = stats["total_completions"]
    days = stats["period_days"]
    active = stats["active_days"]
    pct = int(stats["completion_rate"] * 100)

    if n == 0:
        return f"{period_label} 동안 완료한 일정이 없어요. 작은 일정부터 시작해보세요!"

    # 격려
    if pct >= 80:
        lines.append(f"🔥 정말 잘하고 계세요! {days}일 중 {active}일이나 활동하셨네요 ({pct}%).")
    elif pct >= 50:
        lines.append(f"👏 {period_label} 동안 {active}일 활동 ({pct}%). 꾸준한 페이스에요.")
    else:
        lines.append(f"💪 {period_label} 동안 {active}일 활동했어요. 한 번에 다 못 해도 괜찮아요.")

    # streak
    if stats["current_streak"] >= 3:
        lines.append(f"현재 {stats['current_streak']}일 연속 달성 중! 이 흐름 유지하세요.")

    # 강한/약한 요일
    if stats["best_dow"]:
        if stats["weak_dow"] and stats["weak_dow"] != stats["best_dow"]:
            lines.append(
                f"가장 잘하시는 요일은 **{stats['best_dow']}요일**이고, "
                f"{stats['weak_dow']}요일은 상대적으로 적었어요."
            )
        else:
            lines.append(f"가장 활발한 요일은 **{stats['best_dow']}요일** 이에요.")

    # 시간대
    if stats["best_hour_bucket"]:
        lines.append(f"주로 **{stats['best_hour_bucket']}** 시간대에 활동하시네요.")

    # 인기 일정
    if stats["top_habits"]:
        top1 = list(stats["top_habits"].items())[0]
        lines.append(f"가장 자주 완료한 일정: **{top1[0]}** ({top1[1]}회).")

    # 다음 단계 제안
    if stats["weak_dow"] and stats["weak_dow"] != stats["best_dow"]:
        lines.append(
            f"\n💡 다음 주는 {stats['weak_dow']}요일에 한 개라도 완료해보세요. "
            f"패턴이 더 균형 잡힐 거예요."
        )

    return "\n".join(lines)


# ─── 3. LLM 인사이트 (Ollama) ─────────────────────────
def _llm_insight(stats: Dict, period_label: str) -> Optional[str]:
    """Ollama 로 자연어 리포트 생성. 실패 시 None."""
    try:
        from langchain_community.llms import Ollama
    except ImportError:
        try:
            from langchain.llms import Ollama
        except ImportError:
            return None

    try:
        llm = Ollama(model="qwen2.5:latest", base_url="http://127.0.0.1:11434", temperature=0.7)
        prompt = f"""당신은 사용자의 습관 관리 코치입니다. 아래 데이터를 보고 친근하고 격려하는 어조로 한국어 리포트를 작성하세요.

[{period_label} 통계]
- 총 완료 일정: {stats['total_completions']}건
- 활동한 일수: {stats['active_days']}일 / {stats['period_days']}일 ({int(stats['completion_rate']*100)}%)
- 받은 하트: {stats['total_hearts']}개
- 현재 연속 달성: {stats['current_streak']}일
- 가장 잘하는 요일: {stats['best_dow'] or '데이터 부족'}
- 약한 요일: {stats['weak_dow'] or '데이터 부족'}
- 활발한 시간대: {stats['best_hour_bucket'] or '데이터 부족'}
- 가장 자주 한 일정: {', '.join(list(stats['top_habits'].keys())[:3]) or '없음'}

다음 형식으로 작성:
1. 격려 한 마디 (1-2문장)
2. 발견한 패턴 (1-2문장)
3. 다음 주를 위한 구체적인 제안 1가지

전체 4-6문장 이내. 너무 길지 않게. 이모지 적절히 활용."""

        response = llm.invoke(prompt)
        return response.strip() if response else None
    except Exception as e:
        print(f"[insights] LLM 실패: {e}")
        return None


# ─── 4. 추천 행동 ────────────────────────────────────────
def _action_recommendations(stats: Dict) -> List[str]:
    """통계 기반 구체적 행동 추천 3가지."""
    recs = []

    if stats["total_completions"] == 0:
        return ["새 일정 1개 추가하기", "씨앗을 심고 첫 완료 해보기", "AI 챗봇과 대화해보기"]

    # 약한 요일 보강
    if stats["weak_dow"] and stats["weak_dow"] != stats["best_dow"]:
        recs.append(f"이번 {stats['weak_dow']}요일에 작은 일정 1개 완료하기")

    # streak 유지
    if stats["current_streak"] >= 3:
        recs.append(f"{stats['current_streak']+1}일째 연속 달성 도전")
    elif stats["current_streak"] == 0:
        recs.append("오늘 1개 완료해서 streak 다시 시작하기")
    else:
        recs.append(f"내일도 1개 완료해서 {stats['current_streak']+1}일 연속 만들기")

    # 시간대 다변화
    if stats["best_hour_bucket"] and len(stats["by_hour_counts"]) < 2:
        recs.append(f"평소 시간대({stats['best_hour_bucket']}) 외에 다른 시간대 일정 추가하기")
    else:
        recs.append("새 캐릭터 모으기 — 상점 둘러보기")

    return recs[:3]


# ─── 5. API 엔드포인트 ──────────────────────────────────
@router.get("/weekly")
def weekly_insight(use_llm: bool = Query(True), db: Session = Depends(get_db)):
    """지난 7일 인사이트 리포트."""
    stats = _gather_stats(db, days=7)
    period_label = "지난 7일"

    insight = None
    if use_llm:
        insight = _llm_insight(stats, period_label)
    if not insight:
        insight = _template_insight(stats, period_label)

    return {
        "period": "weekly",
        "period_label": period_label,
        "stats": stats,
        "insight": insight,
        "recommendations": _action_recommendations(stats),
        "llm_used": insight is not None and use_llm and bool(_llm_insight(stats, period_label)),
    }


@router.get("/monthly")
def monthly_insight(use_llm: bool = Query(True), db: Session = Depends(get_db)):
    """지난 30일 인사이트 리포트."""
    stats = _gather_stats(db, days=30)
    period_label = "지난 30일"

    insight = None
    if use_llm:
        insight = _llm_insight(stats, period_label)
    if not insight:
        insight = _template_insight(stats, period_label)

    return {
        "period": "monthly",
        "period_label": period_label,
        "stats": stats,
        "insight": insight,
        "recommendations": _action_recommendations(stats),
    }


@router.get("/quick")
def quick_summary(db: Session = Depends(get_db)):
    """LLM 없이 즉시 동작 — 한 줄 요약."""
    stats = _gather_stats(db, days=7)
    if stats["total_completions"] == 0:
        return {"summary": "이번 주 아직 완료한 일정이 없어요. 시작해볼까요? 🌱"}

    parts = []
    parts.append(f"이번 주 {stats['total_completions']}건 완료 (활동 {stats['active_days']}/7일)")
    if stats["current_streak"] >= 2:
        parts.append(f"🔥 {stats['current_streak']}일 연속")
    if stats["best_dow"]:
        parts.append(f"강한 요일: {stats['best_dow']}")
    return {"summary": " · ".join(parts), "stats": stats}
