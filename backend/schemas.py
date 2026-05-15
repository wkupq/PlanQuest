"""Plan-Quest - Pydantic 스키마 모음"""
from pydantic import BaseModel
from typing import List


# ============ 유저 ============

class UserResponse(BaseModel):
    hearts: int
    level: int
    total_hearts_earned: int


# ============ 습관 ============

class HabitCreate(BaseModel):
    title: str
    repeat_days: List[int] = []
    times: List[str] = []
    alarm_enabled: bool = True
    hearts_reward: int = 1


class HabitResponse(BaseModel):
    id: int
    title: str
    repeat_days: List[int]
    times: List[str]
    alarm_enabled: bool
    hearts_reward: int
    streak: int
    completed_today: bool

    class Config:
        from_attributes = True


# ============ 나무 ============

class TreeResponse(BaseModel):
    id: int
    habit_id: int
    habit_title: str
    grid_x: int
    grid_y: int
    growth_stage: int
    hearts_available: int


# ============ 상점 ============

class ShopItemResponse(BaseModel):
    id: int
    name: str
    category: str
    price: int
    emoji: str
    description: str
    rarity: str
    unlock_level: int
    owned: bool = False

    class Config:
        from_attributes = True


# ============ 배치 ============

class PlaceItemRequest(BaseModel):
    owned_item_id: int
    grid_x: int
    grid_y: int


class PlacedItemResponse(BaseModel):
    id: int
    owned_item_id: int
    grid_x: int
    grid_y: int
    item_name: str
    item_emoji: str
    item_category: str
