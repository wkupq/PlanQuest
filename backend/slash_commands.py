"""Plan-Quest — 챗봇 슬래시 커맨드 처리.

자연어 + LLM 보다 빠르고 정확. "/" 로 시작하는 메시지는 즉시 실행.

지원 명령:
  /help                       — 도움말
  /hearts                     — 현재 하트 조회
  /summary                    — 정원 요약
  /today                      — 오늘 진행도
  /history [week|month]       — 완료 기록
  /pattern                    — 약한 요일/시간 분석
  /add <제목>                 — 일정 추가 (시간/요일 기본값)
  /complete <제목 일부>       — 일정 완료 처리
  /list                       — 모든 일정 목록
  /suggest                    — 추천 일정 보기
  /stats                      — 종합 통계

사용:
  routers/chat.py 에서 user 메시지가 "/" 로 시작하면 dispatch_command() 호출.
"""
import re
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Habit, UserProfile


HELP_TEXT = """💬 사용 가능한 명령어:

📊 조회
  /hearts            현재 하트 개수
  /summary           정원 한 줄 요약
  /today             오늘 일정 진행도
  /list              등록된 모든 일정
  /history [week]    최근 완료 기록 (기본: week)
  /pattern           강한/약한 요일·시간 분석
  /stats             종합 통계
  /suggest           AI 추천 일정

✏️ 조작
  /add <제목>        새 일정 추가 (매일 09:00)
  /complete <키워드> 일정 완료 처리

💡 자유 대화는 그냥 입력하면 AI 가 답해줍니다.
"""


def is_command(text: str) -> bool:
    return text and text.lstrip().startswith("/")


def dispatch_command(text: str, user_id: int = 1) -> Optional[str]:
    """슬래시 커맨드 실행. 결과 문자열 반환. 매칭 안 되면 None."""
    text = text.strip()
    if not text.startswith("/"):
        return None

    # 첫 단어 = 명령, 나머지 = 인자
    parts = text[1:].split(maxsplit=1)
    if not parts:
        return HELP_TEXT
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handler = HANDLERS.get(cmd)
    if not handler:
        return f"❓ 알 수 없는 명령: /{cmd}\n\n{HELP_TEXT}"
    try:
        return handler(args, user_id)
    except Exception as e:
        return f"⚠️ 명령 실행 중 오류: {type(e).__name__}: {e}"


# ─── 명령 핸들러 ────────────────────────────────────────
def _cmd_help(args: str, user_id: int) -> str:
    return HELP_TEXT


def _cmd_hearts(args: str, user_id: int) -> str:
    db = SessionLocal()
    try:
        user = db.query(UserProfile).filter_by(id=user_id).first()
        if not user:
            return "❌ 사용자 정보 없음"
        return f"❤️ 현재 하트: {user.hearts}  (Lv.{user.level} · 누적 {user.total_hearts_earned})"
    finally:
        db.close()


def _cmd_summary(args: str, user_id: int) -> str:
    from tools.game_state_tools import get_garden_summary
    return get_garden_summary("")


def _cmd_today(args: str, user_id: int) -> str:
    from tools.game_state_tools import get_today_progress
    return get_today_progress("")


def _cmd_history(args: str, user_id: int) -> str:
    period = (args or "week").lower().strip()
    if period not in ("today", "week", "month"):
        period = "week"
    from tools.game_state_tools import get_completion_history
    return get_completion_history(period)


def _cmd_pattern(args: str, user_id: int) -> str:
    from tools.game_state_tools import analyze_weak_pattern
    return analyze_weak_pattern("")


def _cmd_list(args: str, user_id: int) -> str:
    db = SessionLocal()
    try:
        habits = db.query(Habit).filter_by(user_id=user_id).all()
        if not habits:
            return "📋 등록된 일정이 없습니다. `/add 운동` 같이 추가해보세요."
        lines = [f"📋 등록된 일정 ({len(habits)}개):"]
        DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
        for h in habits:
            days = ",".join(DAY_NAMES[i] for i in (h.repeat_days or [])) or "(요일 없음)"
            times = ",".join(h.times or []) or "(시간 없음)"
            streak = f" 🔥{h.streak}" if h.streak else ""
            check = "✅" if h.completed_today else "  "
            lines.append(f"  {check} {h.title}  [{days} · {times}]{streak}")
        return "\n".join(lines)
    finally:
        db.close()


def _cmd_add(args: str, user_id: int) -> str:
    title = args.strip()
    if not title:
        return "❌ 일정 제목이 필요해요. 예: `/add 운동`"

    db = SessionLocal()
    try:
        # 중복 체크
        if db.query(Habit).filter_by(title=title).first():
            return f"⚠️ 이미 '{title}' 일정이 등록되어 있어요."

        # 라이브러리에 있으면 기본값 사용
        from routers.suggestions import HABIT_LIBRARY
        time = "09:00"
        days = [0, 1, 2, 3, 4]
        for cat, habits in HABIT_LIBRARY.items():
            for lib_h in habits:
                if lib_h["title"] == title:
                    time = lib_h["default_time"]
                    days = lib_h["days"]
                    break

        from models import TreeOnMap, PlacedItem
        habit = Habit(
            title=title,
            user_id=user_id,
            repeat_days=days,
            times=[time],
            alarm_enabled=True,
            hearts_reward=1,
        )
        db.add(habit)
        db.commit()
        db.refresh(habit)

        # 나무 자동 배치 (빈 칸 찾기)
        used = set()
        for t in db.query(TreeOnMap).all():
            used.add((t.grid_x, t.grid_y))
        for p in db.query(PlacedItem).all():
            used.add((p.grid_x, p.grid_y))
        px, py = 0, 0
        for y in range(5):
            for x in range(7):
                if (x, y) not in used:
                    px, py = x, y
                    break
            else:
                continue
            break
        tree = TreeOnMap(habit_id=habit.id, grid_x=px, grid_y=py, growth_stage=0, hearts_available=0)
        db.add(tree)
        db.commit()

        DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
        day_str = ",".join(DAY_NAMES[d] for d in days)
        return f"✅ 일정 추가됨: '{title}' [{day_str} · {time}]\n🌱 씨앗이 ({px},{py}) 에 심어졌어요."
    finally:
        db.close()


def _cmd_complete(args: str, user_id: int) -> str:
    keyword = args.strip().lower()
    if not keyword:
        return "❌ 일정 키워드가 필요해요. 예: `/complete 운동`"

    db = SessionLocal()
    try:
        habits = db.query(Habit).filter_by(user_id=user_id).all()
        matches = [h for h in habits if keyword in h.title.lower()]
        if not matches:
            return f"❌ '{keyword}' 와 일치하는 일정 없음."
        if len(matches) > 1:
            titles = ", ".join(h.title for h in matches)
            return f"⚠️ 여러 일정이 매치됩니다: {titles}\n더 구체적으로 입력해주세요."

        habit = matches[0]
        if habit.completed_today:
            return f"⚠️ '{habit.title}' 는 이미 오늘 완료됐어요."

        from models import HabitCompletion, TreeOnMap
        habit.completed_today = True
        habit.streak = (habit.streak or 0) + 1
        habit.last_completed = datetime.utcnow()

        user = db.query(UserProfile).first()
        earned = habit.hearts_reward or 1
        if habit.streak % 7 == 0:
            earned += 1
        user.hearts += earned
        user.total_hearts_earned += earned
        user.level = (user.total_hearts_earned // 10) + 1

        tree = db.query(TreeOnMap).filter_by(habit_id=habit.id).first()
        if tree:
            if tree.growth_stage < 3:
                tree.growth_stage += 1
            tree.hearts_available += 1

        db.add(HabitCompletion(habit_id=habit.id, user_id=user_id, hearts_earned=earned))
        db.commit()

        return (f"✅ '{habit.title}' 완료!\n"
                f"  +{earned} 하트 · 🔥 streak {habit.streak}일\n"
                f"  🌱 나무 성장: {tree.growth_stage if tree else '?'}/3")
    finally:
        db.close()


def _cmd_suggest(args: str, user_id: int) -> str:
    db = SessionLocal()
    try:
        from routers.suggestions import suggest_habits
        result = suggest_habits(limit=5, db=db)
        sugs = result.get("suggestions", [])
        if not sugs:
            return "💡 추천할 일정이 없어요. (모두 등록됐거나 라이브러리가 비었음)"

        lines = ["💡 AI 추천 일정 Top 5:"]
        for i, s in enumerate(sugs, 1):
            days = "·".join(s["suggested_days_label"])
            lines.append(f"  {i}. [{s['category']}] {s['title']} ({days} {s['suggested_time']})")
            if s.get("reason"):
                lines.append(f"     → {s['reason']}")
        lines.append("\n원하는 일정은 `/add 제목` 으로 추가하세요.")
        return "\n".join(lines)
    finally:
        db.close()


def _cmd_stats(args: str, user_id: int) -> str:
    db = SessionLocal()
    try:
        from proactive_ai import analyze_habit_pattern
        from tools.game_state_tools import get_user_stats
        user_info = get_user_stats("")
        pattern = analyze_habit_pattern(db, user_id)
        lines = ["📊 종합 통계:", "", user_info, ""]
        if pattern.get("total_habits"):
            lines.append(f"📋 등록된 일정: {pattern['total_habits']}개")
            lines.append(f"   오늘 달성률: {int(pattern['completion_rate_today']*100)}%")
            lines.append(f"   최고 streak: {pattern.get('best_streak', 0)}일")
            if pattern.get("best_dow"):
                lines.append(f"   강한 요일: {pattern['best_dow']}, 약한 요일: {pattern.get('weak_dow', '-')}")
            lines.append(f"   지난 30일 활동: {pattern.get('month_completed_days', 0)}일")
        return "\n".join(lines)
    finally:
        db.close()


HANDLERS = {
    "help":     _cmd_help,
    "hearts":   _cmd_hearts,
    "heart":    _cmd_hearts,
    "summary":  _cmd_summary,
    "today":    _cmd_today,
    "history":  _cmd_history,
    "pattern":  _cmd_pattern,
    "list":     _cmd_list,
    "add":      _cmd_add,
    "complete": _cmd_complete,
    "done":     _cmd_complete,
    "suggest":  _cmd_suggest,
    "stats":    _cmd_stats,
}
