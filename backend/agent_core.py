"""Plan-Quest - AI Agent Core (LangChain ReAct Pattern)"""
import asyncio
import json
from typing import Optional, Dict, List
from langchain.agents import AgentType, initialize_agent
from langchain.chat_models import ChatOllama
from langchain.tools import Tool
from langchain.callbacks import StreamingStdOutCallbackHandler

# Tool imports
from tools.habit_tools import (
    get_habits,
    create_habit,
    complete_habit
)
from tools.calendar_tools import (
    search_calendar,
    get_today_schedule,
    get_next_events
)
from tools.email_tools import (
    search_emails,
    get_important_emails,
    classify_emails
)
from tools.game_state_tools import (
    get_user_stats,
    get_placed_characters,
    get_owned_characters,
    get_growing_trees,
    get_shop_recommendations,
    get_garden_summary,
    get_completion_history,
    get_today_progress,
    analyze_weak_pattern,
)


class PlanQuestAgent:
    """Plan-Quest AI Agent - ReAct 패턴 기반 멀티태스킹 에이전트"""

    def __init__(self, model: str = "qwen2.5:latest", base_url: str = "http://127.0.0.1:11434"):
        """
        에이전트 초기화

        Args:
            model: 사용할 Ollama 모델
            base_url: Ollama API 베이스 URL
        """
        self.model = model
        self.base_url = base_url
        self.tools = self._create_tools()
        self.agent = self._initialize_agent()

    def _create_tools(self) -> List[Tool]:
        """LangChain Tool 객체 생성"""
        tools = [
            # Habit Tools
            Tool(
                name="get_habits",
                func=get_habits,
                description="사용자의 모든 습관과 일정 목록을 조회합니다. "
                           "\"내 습관이 뭐야?\", \"등록된 일정 보여줘\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="create_habit",
                func=lambda title, repeat_days=None, times=None: create_habit(
                    title=title,
                    repeat_days=repeat_days or [0, 1, 2, 3, 4],
                    times=times or ["09:00"]
                ),
                description="새로운 습관/일정을 생성합니다. "
                           "\"운동 습관 추가해줘\", \"매일 아침 8시 명상 등록해\" 같은 요청에 사용합니다."
            ),
            Tool(
                name="complete_habit",
                func=complete_habit,
                description="특정 습관을 완료 처리합니다. "
                           "스트릭을 증가시키고 하트 보상을 줍니다. "
                           "\"운동 완료했어\", \"아침 루틴 끝났어\" 같은 요청에 사용합니다."
            ),

            # Calendar Tools
            Tool(
                name="search_calendar",
                func=search_calendar,
                description="캘린더에서 특정 날짜나 키워드로 일정을 검색합니다. "
                           "\"내일 회의 있어?\", \"다음주 스케줄 보여줘\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_today_schedule",
                func=get_today_schedule,
                description="오늘의 전체 일정(습관 + 캘린더)을 조회합니다. "
                           "\"오늘 일정 뭐야?\", \"오늘 뭘 해야 돼?\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_next_events",
                func=get_next_events,
                description="향후 N일간의 주요 일정을 조회합니다. "
                           "\"앞으로 뭐 있어?\", \"주간 일정 보여줘\" 같은 질문에 사용합니다."
            ),

            # Email Tools
            Tool(
                name="search_emails",
                func=search_emails,
                description="이메일을 검색합니다. 특정 발신자나 주제로 필터링할 수 있습니다. "
                           "\"보스한테서 온 메일 있어?\", \"프로젝트 관련 이메일 찾아줘\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_important_emails",
                func=get_important_emails,
                description="중요한 이메일만 필터링해서 보여줍니다. "
                           "\"중요한 메일 뭐가 있어?\", \"긴급 이메일 있어?\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="classify_emails",
                func=classify_emails,
                description="AI가 이메일을 카테고리별로 자동 분류합니다. "
                           "\"이메일 분류해줘\", \"업무 메일이 몇 개야?\" 같은 요청에 사용합니다."
            ),

            # ─── Game State Tools (W4 추가) ───
            Tool(
                name="get_user_stats",
                func=get_user_stats,
                description="사용자의 하트, 레벨, 누적 하트를 조회합니다. "
                           "\"내 하트 몇 개야?\", \"내 레벨이 뭐야?\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_placed_characters",
                func=get_placed_characters,
                description="배치도 위에 올라가 있는 캐릭터들을 조회합니다. "
                           "\"내 정원에 누가 있어?\", \"배치한 캐릭터 보여줘\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_owned_characters",
                func=get_owned_characters,
                description="보유했지만 아직 배치하지 않은 캐릭터들을 조회합니다. "
                           "\"보유 캐릭터 뭐있어?\", \"아직 안 놓은 애들?\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_growing_trees",
                func=get_growing_trees,
                description="배치도에 심어진 나무들과 성장 단계, 수확 가능한 하트를 조회합니다. "
                           "\"내 나무들 어떻게 자라?\", \"수확할 거 있어?\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_shop_recommendations",
                func=get_shop_recommendations,
                description="현재 보유 하트와 레벨로 살 수 있는 캐릭터를 추천합니다. "
                           "\"뭐 사면 좋을까?\", \"지금 살 수 있는 거 추천해줘\" 같은 질문에 사용합니다."
            ),
            Tool(
                name="get_garden_summary",
                func=get_garden_summary,
                description="정원의 전체 현황 (레벨, 하트, 일정, 나무, 캐릭터)을 한 번에 요약합니다. "
                           "\"내 진행 상황 어때?\", \"전체 요약 보여줘\" 같은 질문에 사용합니다."
            ),

            # ─── 완료 기록 분석 도구 (HabitCompletion 기반) ───
            Tool(
                name="get_completion_history",
                func=get_completion_history,
                description="최근 완료한 일정 기록을 조회합니다. "
                           "인자: 'today' / 'week' / 'month'. "
                           "\"이번 주 몇 번 했어?\", \"오늘 뭐 했어?\" 같은 질문에 사용."
            ),
            Tool(
                name="get_today_progress",
                func=get_today_progress,
                description="오늘 예정된 일정 중 몇 개 완료했는지 진행도를 보여줍니다. "
                           "\"오늘 몇 개 했어?\", \"남은 일정 뭐야?\" 같은 질문에 사용."
            ),
            Tool(
                name="analyze_weak_pattern",
                func=analyze_weak_pattern,
                description="완료 기록을 분석해서 강한/약한 요일과 시간대를 알려줍니다. "
                           "\"내가 언제 잘 해?\", \"패턴 분석해줘\" 같은 질문에 사용."
            ),
        ]
        return tools

    def _initialize_agent(self):
        """ReAct 패턴 에이전트 초기화"""
        try:
            # Ollama LLM 초기화
            llm = ChatOllama(
                model=self.model,
                base_url=self.base_url,
                temperature=0.7,
                top_p=0.9,
                top_k=40
            )

            # ReAct 에이전트 초기화
            agent = initialize_agent(
                tools=self.tools,
                llm=llm,
                agent=AgentType.REACT_DOCSTRING,
                verbose=True,
                max_iterations=10,
                early_stopping_method="generate",
                handle_parsing_errors=True,
            )

            return agent

        except Exception as e:
            print(f"❌ 에이전트 초기화 실패: {str(e)}")
            return None

    async def run(
        self,
        user_query: str,
        stream_callback=None,
        user_id: int = 1,
        use_memory: bool = True,
    ) -> str:
        """
        사용자 쿼리에 대해 에이전트 실행

        Args:
            user_query: 사용자의 질문/명령
            stream_callback: 스트리밍 콜백 함수
            user_id: 메모리 검색에 사용할 user_id
            use_memory: True 면 RAG 메모리에서 컨텍스트 자동 주입 + 대화 저장

        Returns:
            에이전트 응답 문자열
        """
        if not self.agent:
            return "❌ 에이전트가 초기화되지 않았습니다. Ollama를 실행해주세요."

        # ── 개인화 컨텍스트 (게임 상태 + RAG 메모리) 주입 ──
        augmented_query = user_query
        memory_engine = None
        db_session = None
        if use_memory:
            try:
                from memory_engine import get_memory_engine
                from proactive_ai import build_personalization_context
                from database import SessionLocal
                memory_engine = get_memory_engine()

                db_session = SessionLocal()
                ctx = build_personalization_context(
                    db_session, user_query, user_id=user_id, include_memory=True
                )
                if ctx:
                    augmented_query = f"{ctx}\n\n사용자: {user_query}"
            except Exception as e:
                print(f"[agent.run] 컨텍스트 주입 실패 (계속 진행): {e}")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.agent.run(augmented_query)
            )

            # ── 대화를 메모리에 저장 (낮은 importance, 임계값 엔진이 정리) ──
            if use_memory and memory_engine and memory_engine.enabled:
                try:
                    memory_engine.add(
                        user_id=user_id,
                        text=f"Q: {user_query}\nA: {result}",
                        memory_type="conversation",
                        importance=0.4,
                        db=db_session,
                    )
                except Exception as e:
                    print(f"[agent.run] 메모리 저장 실패: {e}")

            return result

        except Exception as e:
            return f"❌ 에이전트 실행 중 오류: {str(e)}"
        finally:
            if db_session is not None:
                db_session.close()

    def get_tool_list(self) -> str:
        """사용 가능한 도구 목록 반환"""
        result = "🛠️ 사용 가능한 도구:\n\n"
        for tool in self.tools:
            result += f"• {tool.name}: {tool.description}\n\n"
        return result


# 전역 에이전트 인스턴스
_agent_instance: Optional[PlanQuestAgent] = None


def get_agent() -> Optional[PlanQuestAgent]:
    """전역 에이전트 인스턴스 가져오기"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PlanQuestAgent()
    return _agent_instance


def reset_agent():
    """에이전트 인스턴스 리셋"""
    global _agent_instance
    _agent_instance = None
ools:
            result += f"• {tool.name}: {tool.description}\n\n"
        return result


# 전역 에이전트 인스턴스
_agent_instance: Optional[PlanQuestAgent] = None


def get_agent() -> Optional[PlanQuestAgent]:
    """전역 에이전트 인스턴스 가져오기"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PlanQuestAgent()
    return _agent_instance


def reset_agent():
    """에이전트 인스턴스 리셋"""
    global _agent_instance
    _agent_instance = None


if __name__ == "__main__":
    # 테스트 코드
    import asyncio

    async def test_agent():
        agent = get_agent()
        if agent:
            # 테스트 쿼리
            test_queries = [
                "내일 회의 있고, 중요한 메일 있으면 알려줘",
                "오늘 내 일정이 뭐야?",
                "명상 습관을 추가해줘 (매일 아침 6시)",
            ]

            for query in test_queries:
                print(f"\n👤 사용자: {query}")
                print("-" * 60)
                response = await agent.run(query)
                print(f"🤖 AI: {response}")
                print("-" * 60)

    asyncio.run(test_agent())
ools:
            result += f"• {tool.name}: {tool.description}\n\n"
        return result


# 전역 에이전트 인스턴스
_agent_instance: Optional[PlanQuestAgent] = None


def get_agent() -> Optional[PlanQuestAgent]:
    """전역 에이전트 인스턴스 가져오기"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PlanQuestAgent()
    return _agent_instance


def reset_agent():
    """에이전트 인스턴스 리셋"""
    global _agent_instance
    _agent_instance = None
