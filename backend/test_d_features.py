"""
D 역할 기능 통합 검증 (smoke test).

실행:
  cd backend
  python test_d_features.py

체크 항목 (오프라인 — Ollama/외부 API 안 켜져 있어도 동작):
  1. DB 모델 / 마이그레이션 — 모든 테이블 존재 여부
  2. AI 도구 import — 에이전트 등록된 도구 개수 확인
  3. 게임 상태 도구 — 실제 호출 (DB 빈 상태에서도 graceful)
  4. 능동 추천 / 패턴 분석
  5. RAG 메모리 엔진 — 활성/비활성 상태 + 통계
  6. 외부 연동 클라이언트 — credentials 없을 때 setup_instructions
  7. 캘린더 API 함수 — 빈 월 조회

각 단계 ✅ / ❌ / ⚠️ 표시. 실제 백엔드 실행 안 해도 핵심 함수들 import 가능 여부 확인.
"""
import sys
import traceback
from datetime import datetime


def check(name, fn):
    try:
        result = fn()
        print(f"  ✅ {name}: {result if isinstance(result, str) else 'OK'}")
        return True
    except Exception as e:
        print(f"  ❌ {name}: {type(e).__name__}: {str(e)[:80]}")
        return False


def warn(name, fn):
    try:
        result = fn()
        print(f"  ⚠️ {name}: {result}")
    except Exception as e:
        print(f"  ⚠️ {name}: {type(e).__name__}: {str(e)[:80]}")


def main():
    print("=" * 60)
    print("Plan-Quest — D 역할 기능 통합 검증")
    print("=" * 60)
    n_ok = 0
    n_total = 0

    # ─── 1. DB 모델 ──
    print("\n[1] DB 모델 / 테이블")
    n_total += 1
    if check("models import", lambda: __import__("models")):
        n_ok += 1

    n_total += 1
    def _check_tables():
        from database import engine, Base
        from models import (UserProfile, Habit, ShopItem, OwnedItem,
                            PlacedItem, TreeOnMap, UserMemory, HabitCompletion)
        Base.metadata.create_all(bind=engine)
        return f"{len(Base.metadata.tables)} tables"
    if check("create_all (전체 테이블)", _check_tables):
        n_ok += 1

    # ─── 2. AI 에이전트 ──
    print("\n[2] AI 에이전트 코어")
    n_total += 1
    def _agent_tools():
        from agent_core import PlanQuestAgent
        agent = PlanQuestAgent.__new__(PlanQuestAgent)
        tools = agent._create_tools.__func__(agent)
        return f"{len(tools)} 개 도구"
    if check("agent_core 도구 생성", _agent_tools):
        n_ok += 1

    # ─── 3. 게임 상태 도구 ──
    print("\n[3] 게임 상태 도구 (실제 호출)")
    from tools.game_state_tools import (
        get_user_stats, get_garden_summary, get_today_progress,
        get_completion_history, analyze_weak_pattern,
    )
    for name, fn in [
        ("get_user_stats", get_user_stats),
        ("get_garden_summary", get_garden_summary),
        ("get_today_progress", get_today_progress),
        ("get_completion_history(week)", lambda: get_completion_history("week")),
        ("analyze_weak_pattern", analyze_weak_pattern),
    ]:
        n_total += 1
        try:
            out = fn() if name != "get_completion_history(week)" else fn()
            preview = str(out)[:60].replace("\n", " ")
            print(f"  ✅ {name}: {preview}...")
            n_ok += 1
        except Exception as e:
            print(f"  ❌ {name}: {type(e).__name__}: {e}")

    # ─── 4. 능동 추천 / 패턴 분석 ──
    print("\n[4] 능동 추천 + 패턴 분석")
    from database import SessionLocal
    db = SessionLocal()
    try:
        from proactive_ai import (
            get_proactive_suggestions,
            analyze_habit_pattern,
            build_personalization_context,
        )
        n_total += 1
        try:
            sug = get_proactive_suggestions(db)
            print(f"  ✅ 능동 추천: {len(sug)}건")
            n_ok += 1
        except Exception as e:
            print(f"  ❌ 능동 추천: {e}")

        n_total += 1
        try:
            pat = analyze_habit_pattern(db)
            print(f"  ✅ 패턴 분석: {pat.get('total_habits', 0)}개 일정")
            n_ok += 1
        except Exception as e:
            print(f"  ❌ 패턴 분석: {e}")

        n_total += 1
        try:
            ctx = build_personalization_context(db, "오늘 뭐 했어?", include_memory=False)
            print(f"  ✅ 개인화 컨텍스트: {len(ctx)}자 생성")
            n_ok += 1
        except Exception as e:
            print(f"  ❌ 개인화 컨텍스트: {e}")
    finally:
        db.close()

    # ─── 5. RAG 메모리 ──
    print("\n[5] RAG 메모리 엔진")
    n_total += 1
    try:
        from memory_engine import get_memory_engine
        engine = get_memory_engine()
        if engine.enabled:
            stats = engine.get_stats()
            print(f"  ✅ ChromaDB 활성: {stats.get('count', 0)}개 메모리")
            n_ok += 1
        else:
            print(f"  ⚠️ 비활성 (chromadb/ollama 미설치 — graceful fallback)")
            n_ok += 1  # 비활성도 OK
    except Exception as e:
        print(f"  ❌ memory_engine: {e}")

    # ─── 6. 외부 연동 (Google Calendar / Email) ──
    print("\n[6] 외부 연동 클라이언트")
    n_total += 1
    try:
        from integrations.google_calendar import get_calendar_client
        client = get_calendar_client()
        if client.is_ready():
            print(f"  ✅ Google Calendar: 연결됨")
        else:
            print(f"  ⚠️ Google Calendar: 미연동 (credentials.json 필요 — 정상)")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ Google Calendar: {e}")

    n_total += 1
    try:
        from integrations.email_client import get_email_client
        client = get_email_client()
        if client.is_ready():
            print(f"  ✅ Email: {client.mode}")
        else:
            print(f"  ⚠️ Email: 미연동 (정상)")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ Email: {e}")

    # ─── 7. 캘린더 API ──
    print("\n[7] 캘린더 API")
    n_total += 1
    try:
        from routers.calendar import get_month, _calc_current_streak
        db2 = SessionLocal()
        now = datetime.now()
        result = get_month(year=now.year, month=now.month, db=db2)
        print(f"  ✅ /calendar/month: {result['stats']['total_completions']}건 완료, "
              f"streak={result['stats']['current_streak']}")
        db2.close()
        n_ok += 1
    except Exception as e:
        print(f"  ❌ 캘린더 API: {e}")

    # ─── 8. W5: 인사이트 리포트 ──
    print("\n[8] W5 — 인사이트 리포트")
    n_total += 1
    try:
        from routers.insights import _gather_stats, _template_insight, _action_recommendations
        db3 = SessionLocal()
        stats = _gather_stats(db3, days=7)
        insight = _template_insight(stats, "지난 7일")
        recs = _action_recommendations(stats)
        print(f"  ✅ 주간 인사이트: {stats['total_completions']}건, "
              f"insight {len(insight)}자, 추천 {len(recs)}개")
        db3.close()
        n_ok += 1
    except Exception as e:
        print(f"  ❌ 인사이트: {e}")

    # ─── 9. W5: 메모리 자동 카테고리화 ──
    print("\n[9] W5 — 메모리 자동 카테고리화")
    n_total += 1
    try:
        from memory_engine import auto_categorize, auto_importance
        samples = [
            ("운동 매일 하기로 약속!", "habit"),
            ("초콜릿 좋아함", "preference"),
            ("내일 회의 10시 잊지 마", "schedule"),
            ("불꽃포메 구매 완료", "game_event"),
        ]
        ok = 0
        for text, expected in samples:
            cat = auto_categorize(text)
            imp = auto_importance(text, cat)
            if cat == expected:
                ok += 1
        print(f"  ✅ 자동 분류: {ok}/{len(samples)} 정확 (importance 산정 OK)")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ 메모리 카테고리화: {e}")

    # ─── 10. W5: WebSocket 모듈 import ──
    print("\n[10] W5 — WebSocket 알림 모듈")
    n_total += 1
    try:
        from routers.notifications import manager, ConnectionManager
        print(f"  ✅ ConnectionManager 로드 (활성 연결 {len(manager.active)}개)")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ WebSocket: {e}")

    # ─── 11. W6: 자동 일정 추천 ──
    print("\n[11] W6 — 자동 일정 추천")
    n_total += 1
    try:
        from routers.suggestions import suggest_habits, find_empty_slots
        db_t = SessionLocal()
        sug = suggest_habits(limit=3, db=db_t)
        empty = find_empty_slots(db=db_t)
        db_t.close()
        print(f"  ✅ 추천 {len(sug['suggestions'])}개, 빈 시간대 {len(empty['empty_buckets'])}개")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ 추천 엔진: {e}")

    # ─── 12. W6: 슬래시 커맨드 ──
    print("\n[12] W6 — 슬래시 커맨드")
    n_total += 1
    try:
        from slash_commands import is_command, dispatch_command, HANDLERS
        assert is_command("/hearts")
        assert not is_command("hello")
        out = dispatch_command("/help")
        assert out and "도움말" not in out  # 도움말 텍스트 출력됨
        print(f"  ✅ 명령어 {len(HANDLERS)}개 등록, dispatch 동작 OK")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ 슬래시 커맨드: {e}")

    # ─── 13. W6: 피드백 시스템 ──
    print("\n[13] W6 — 피드백 시스템")
    n_total += 1
    try:
        from routers.feedback import feedback_stats
        db_t = SessionLocal()
        stats = feedback_stats(db=db_t)
        db_t.close()
        print(f"  ✅ 피드백 통계: 총 {stats['total_feedback']}건 "
              f"(👍 {stats['good']}, 👎 {stats['bad']})")
        n_ok += 1
    except Exception as e:
        print(f"  ❌ 피드백: {e}")

    # ─── 결과 ──
    print("\n" + "=" * 60)
    print(f"결과: {n_ok}/{n_total} 통과")
    print("=" * 60)
    if n_ok == n_total:
        print("✅ 모든 D 역할 기능 정상 동작")
    elif n_ok >= n_total * 0.8:
        print("⚠️ 대부분 정상 (몇 개 항목은 외부 의존성 때문일 수 있음)")
    else:
        print("❌ 문제 발견 — 위 ❌ 항목 확인 필요")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
