"""Plan-Quest - Habit/Schedule Tool Functions"""
from typing import List, Dict
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Habit, UserProfile
from datetime import datetime


def get_habits(user_id: int = 1) -> str:
    """
    사용자의 모든 습관/일정 조회

    Args:
        user_id: 사용자 ID (기본값: 1)

    Returns:
        습관 목록을 문자열로 반환
    """
    db = SessionLocal()
    try:
        habits = db.query(Habit).filter(Habit.user_id == user_id).all()

        if not habits:
            return "등록된 습관이 없습니다."

        result = "현재 등록된 습관:\n"
        for habit in habits:
            days_str = ["월", "화", "수", "목", "금", "토", "일"]
            repeat_days = [days_str[d] for d in habit.repeat_days if 0 <= d <= 6]
            times_str = ", ".join(habit.times) if habit.times else "시간 미지정"

            result += f"- {habit.title}: {','.join(repeat_days)} / {times_str} (연속: {habit.streak}일)\n"

        return result
    finally:
        db.close()


def create_habit(
    title: str,
    repeat_days: List[int] = None,
    times: List[str] = None,
    hearts_reward: int = 1,
    user_id: int = 1
) -> str:
    """
    새로운 습관/일정 생성

    Args:
        title: 습관 제목
        repeat_days: 반복 요일 [0=월, 1=화, ..., 6=일]
        times: 실행 시간 ["14:30", "18:00"]
        hearts_reward: 완료 시 받는 하트
        user_id: 사용자 ID

    Returns:
        생성 결과 메시지
    """
    db = SessionLocal()
    try:
        if not title:
            return "습관 제목이 필요합니다."

        # 중복 확인
        existing = db.query(Habit).filter(
            Habit.user_id == user_id,
            Habit.title == title
        ).first()

        if existing:
            return f"'{title}' 습관이 이미 존재합니다."

        new_habit = Habit(
            user_id=user_id,
            title=title,
            repeat_days=repeat_days or [0, 1, 2, 3, 4],  # 기본: 월~금
            times=times or ["09:00"],
            hearts_reward=hearts_reward
        )

        db.add(new_habit)
        db.commit()

        days_str = ["월", "화", "수", "목", "금", "토", "일"]
        repeat_days_display = [days_str[d] for d in new_habit.repeat_days if 0 <= d <= 6]
        times_display = ", ".join(new_habit.times)

        return f"✅ '{title}' 습관이 생성되었습니다.\n({','.join(repeat_days_display)} / {times_display})"
    except Exception as e:
        return f"❌ 습관 생성 실패: {str(e)}"
    finally:
        db.close()


def complete_habit(habit_id: int, user_id: int = 1) -> str:
    """
    습관 완료 처리 (스트릭 증가, 하트 획득)

    Args:
        habit_id: 습관 ID
        user_id: 사용자 ID

    Returns:
        완료 결과 메시지
    """
    db = SessionLocal()
    try:
        habit = db.query(Habit).filter(
            Habit.id == habit_id,
            Habit.user_id == user_id
        ).first()

        if not habit:
            return f"습관 ID {habit_id}를 찾을 수 없습니다."

        # 오늘 이미 완료했으면 스킵
        if habit.completed_today:
            return f"'{habit.title}' 은(는) 오늘 이미 완료했습니다."

        # 스트릭 및 보상 업데이트
        habit.completed_today = True
        habit.streak += 1
        habit.last_completed = datetime.utcnow()

        # 사용자 하트 추가
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if user:
            user.hearts += habit.hearts_reward
            user.total_hearts_earned += habit.hearts_reward

        db.commit()

        return f"✅ '{habit.title}' 완료! (+{habit.hearts_reward}💗, 연속: {habit.streak}일)"
    except Exception as e:
        return f"❌ 습관 완료 처리 실패: {str(e)}"
    finally:
        db.close()
