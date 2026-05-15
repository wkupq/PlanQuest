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
    """상점 아이템 (동물/나무/건물)"""
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # animal, tree, building
    price = Column(Integer, nullable=False)
    emoji = Column(String, nullable=False)  # 이모지로 아이콘 표현
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
    """맵에 배치된 아이템"""
    __tablename__ = "placed_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    owned_item_id = Column(Integer, ForeignKey("owned_items.id"))
    grid_x = Column(Integer, nullable=False)
    grid_y = Column(Integer, nullable=False)
    placed_at = Column(DateTime, default=datetime.utcnow)

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
