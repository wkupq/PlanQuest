from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class UserProfile(Base):
    """사용자 프로필 (싱글 유저 로컬 앱이므로 1행)"""
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, default=1)
    hearts = Column(Integer, default=5)  # 하트 포인트
    level = Column(Integer, default=1)
    total_hearts_earned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    habits = relationship("Habit", back_populates="user")
    placed_items = relationship("PlacedItem", back_populates="user")
    owned_items = relationship("OwnedItem", back_populates="user")


class Habit(Base):
    """습관/일정 (씨앗 심기)"""
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    title = Column(String, nullable=False)
    repeat_days = Column(JSON, default=[])  # [0,1,2,3,4] = 월~금
    times = Column(JSON, default=[])  # ["14:36", "18:37"]
    alarm_enabled = Column(Boolean, default=True)
    hearts_reward = Column(Integer, default=1)  # 완료 시 받는 하트
    streak = Column(Integer, default=0)  # 연속 달성 일수
    completed_today = Column(Boolean, default=False)
    last_completed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="habits")


class ShopItem(Base):
    """상점 아이템 (캐릭터/건물/장식)"""
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # character, building, decoration
    price = Column(Integer, nullable=False)
    emoji = Column(String, nullable=False)  # 이미지 없을 때 대체용
    image_url = Column(String, default="")  # 캐릭터 이미지 경로 (예: /images/characters/cat.png)
    description = Column(String, default="")
    rarity = Column(String, default="common")  # common, rare, epic, legendary
    unlock_level = Column(Integer, default=1)


class OwnedItem(Base):
    """유저가 구매한 아이템"""
    __tablename__ = "owned_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    shop_item_id = Column(Integer, ForeignKey("shop_items.id"))
    purchased_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="owned_items")
    shop_item = relationship("ShopItem")


class PlacedItem(Base):
    """맵에 배치된 아이템 — 시간당 하트 생성 추적도 같이"""
    __tablename__ = "placed_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    owned_item_id = Column(Integer, ForeignKey("owned_items.id"))
    grid_x = Column(Integer, nullable=False)
    grid_y = Column(Integer, nullable=False)
    placed_at = Column(DateTime, default=datetime.utcnow)

    # 시간당 하트 생성용 — 마지막 수확/생성 시각
    last_heart_gen = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="placed_items")
    owned_item = relationship("OwnedItem")


class TreeOnMap(Base):
    """맵 위의 나무 (습관 완료 시 성장)"""
    __tablename__ = "trees_on_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    habit_id = Column(Integer, ForeignKey("habits.id"))
    grid_x = Column(Integer, default=3)
    grid_y = Column(Integer, default=3)
    growth_stage = Column(Integer, default=0)  # 0=씨앗, 1=새싹, 2=작은나무, 3=큰나무
    hearts_available = Column(Integer, default=0)  # 클릭으로 수확 가능한 하트
    last_harvest = Column(DateTime, nullable=True)

    habit = relationship("Habit")


class HabitCompletion(Base):
    """일정 완료 기록 — 날짜별 히트맵/통계용.

    이전에는 streak/last_completed 만 갱신했지만, 캘린더 히트맵을 위해
    매 완료 시 행 추가. 어떤 일정을 언제 완료했는지 보존.
    """
    __tablename__ = "habit_completion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    habit_id = Column(Integer, ForeignKey("habits.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    completed_at = Column(DateTime, default=datetime.utcnow)
    hearts_earned = Column(Integer, default=1)


class UserMemory(Base):
    """사용자 맥락 기억 (RAG 메모리 - ChromaDB 와 함께 사용).

    ChromaDB 가 벡터 검색을 처리하고, 이 테이블은 메타데이터/원문 보존용.
    importance_score 가 임계값 엔진의 정리 기준.
    """
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)

    # 메모리 종류
    # - "conversation" : 사용자-AI 대화 한 턴
    # - "habit"        : 사용자가 추가/완료한 습관에 대한 맥락
    # - "preference"   : 사용자 선호도 (좋아하는 캐릭터, 활동 시간 등)
    # - "game_event"   : 게임 내 이벤트 (캐릭터 구매, 큰 일정 달성 등)
    memory_type = Column(String, nullable=False, default="conversation")

    content = Column(String, nullable=False)  # 원문 텍스트
    chroma_id = Column(String, default="")    # ChromaDB 벡터 ID (참조용)

    # 임계값 엔진:
    # - 0.0 ~ 1.0 (높을수록 중요)
    # - 0.3 미만 + 30일 이상이면 자동 정리
    importance_score = Column(Float, default=0.5)

    # 자주 검색되는 메모리는 점수 가중 → 살아남음
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
