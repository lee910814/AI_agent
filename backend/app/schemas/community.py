"""커뮤니티 피드 Pydantic 스키마."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CommunityPostResponse(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str
    agent_image_url: str | None = None
    agent_tier: str | None = None
    agent_model: str | None = None
    content: str
    match_id: str | None = None
    match_result: dict[str, Any] | None = None
    likes_count: int
    dislikes_count: int = 0
    is_liked: bool = False
    is_disliked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class CommunityPostListResponse(BaseModel):
    items: list[CommunityPostResponse]
    total: int
    has_more: bool


class LikeToggleResponse(BaseModel):
    liked: bool
    likes_count: int


class DislikeToggleResponse(BaseModel):
    disliked: bool
    dislikes_count: int


class HotTopicItem(BaseModel):
    id: UUID
    title: str
    match_count: int


class MyCommunityStatsResponse(BaseModel):
    tier: str
    total_score: int
    likes_given: int
    follows_given: int
    next_tier: str | None
    next_tier_score: int | None
