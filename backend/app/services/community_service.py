"""커뮤니티 피드 서비스 — 포스트 생성, 피드 조회, 좋아요 토글, 참여등급."""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community_post import CommunityPost, CommunityPostDislike, CommunityPostLike
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.user_community_stats import UserCommunityStats
from app.models.user_follow import UserFollow
from app.schemas.community import DislikeToggleResponse, LikeToggleResponse, MyCommunityStatsResponse

# tier 경계값: (상한 점수 미만, tier 이름, 다음 tier)
_TIER_THRESHOLDS = [
    (10, "Bronze", "Silver", 10),
    (30, "Silver", "Gold", 30),
    (60, "Gold", "Platinum", 60),
    (100, "Platinum", "Diamond", 100),
    (None, "Diamond", None, None),
]


def _calc_tier(score: int) -> tuple[str, str | None, int | None]:
    """점수로 tier, 다음 tier, 다음 tier까지 필요 점수를 반환한다."""
    for threshold, tier_name, next_tier, next_score in _TIER_THRESHOLDS:
        if threshold is None or score < threshold:
            next_score_needed = (next_score - score) if next_score is not None else None
            return tier_name, next_tier, next_score_needed
    return "Diamond", None, None

logger = logging.getLogger(__name__)


class CommunityService:
    """커뮤니티 피드 CRUD 및 좋아요 토글 서비스."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_post(
        self,
        agent: DebateAgent,
        match: DebateMatch,
        opponent: DebateAgent,
    ) -> CommunityPost:
        """매치 결과를 바탕으로 에이전트 소감 포스트를 LLM으로 생성한다.

        생성 실패 시 fallback 문구로 대체하여 포스트를 항상 반환한다.

        Args:
            agent: 포스트를 작성하는 에이전트.
            match: 완료된 매치.
            opponent: 상대 에이전트.

        Returns:
            DB에 저장된 CommunityPost 인스턴스.
        """
        from app.core.config import settings
        from app.models.llm_model import LLMModel
        from app.models.token_usage_log import TokenUsageLog

        # 매치 결과 계산
        if match.winner_id is None:
            result = "draw"
        elif str(match.winner_id) == str(agent.id):
            result = "win"
        else:
            result = "lose"

        result_text = {"win": "승리", "lose": "패배", "draw": "무승부"}[result]

        # 에이전트 기준 점수 확인 (A 또는 B 측)
        if str(match.agent_a_id) == str(agent.id):
            score_mine = match.score_a or 0
            score_opp = match.score_b or 0
            elo_before = match.elo_a_before or agent.elo_rating
            elo_after = match.elo_a_after or agent.elo_rating
        else:
            score_mine = match.score_b or 0
            score_opp = match.score_a or 0
            elo_before = match.elo_b_before or agent.elo_rating
            elo_after = match.elo_b_after or agent.elo_rating

        elo_delta = (elo_after or 0) - (elo_before or 0)

        # 토픽 제목 조회
        topic_res = await self.db.execute(
            select(DebateTopic.title).where(DebateTopic.id == match.topic_id)
        )
        topic_title = topic_res.scalar_one_or_none() or "알 수 없는 주제"

        match_result_data = {
            "result": result,
            "score_mine": float(score_mine),
            "score_opp": float(score_opp),
            "elo_before": int(elo_before),
            "elo_after": int(elo_after),
            "elo_delta": int(elo_delta),
            "opponent_name": opponent.name,
            "topic": topic_title,
        }

        # 해당 에이전트의 턴 로그에서 주장(claim) 추출 — 후기에 토론 내용 반영
        from app.models.debate_turn_log import DebateTurnLog

        speaker_label = "agent_a" if str(match.agent_a_id) == str(agent.id) else "agent_b"
        turns_res = await self.db.execute(
            select(DebateTurnLog.turn_number, DebateTurnLog.action, DebateTurnLog.claim)
            .where(
                DebateTurnLog.match_id == match.id,
                DebateTurnLog.speaker == speaker_label,
                DebateTurnLog.is_blocked.is_(False),
            )
            .order_by(DebateTurnLog.turn_number)
            .limit(10)
        )
        my_turns = turns_res.all()
        my_claims = " → ".join(t.claim[:80] for t in my_turns if t.claim)[:300]

        content = "(포스트 생성 중 오류가 발생했습니다.)"
        try:
            from app.services.llm.inference_client import InferenceClient

            model_res = await self.db.execute(
                select(LLMModel).where(LLMModel.model_id == settings.community_post_model)
            )
            llm_model = model_res.scalar_one_or_none()

            if llm_model is None:
                logger.warning(
                    "Community post skipped: model '%s' not found in llm_models",
                    settings.community_post_model,
                )
            else:
                # 최신 버전의 system_prompt 조회 — 에이전트 성격/역할의 핵심 원천
                from app.models.debate_agent import DebateAgentVersion

                version_res = await self.db.execute(
                    select(DebateAgentVersion.system_prompt)
                    .where(DebateAgentVersion.agent_id == agent.id)
                    .order_by(DebateAgentVersion.version_number.desc())
                    .limit(1)
                )
                agent_system_prompt = version_res.scalar_one_or_none()

                # 성격 정보 조합: system_prompt > description > customizations 순으로 활용
                persona_lines: list[str] = []
                if agent_system_prompt:
                    persona_lines.append(f"당신의 역할과 성격:\n{agent_system_prompt}")
                elif agent.description:
                    persona_lines.append(f"당신에 대한 설명: {agent.description}")
                if agent.customizations:
                    cust_str = ", ".join(f"{k}={v}" for k, v in agent.customizations.items())
                    persona_lines.append(f"성격 설정: {cust_str}")

                persona_section = "\n".join(persona_lines) if persona_lines else ""

                system_content = (
                    f"당신은 AI 토론 에이전트입니다. 에이전트 이름: {agent.name}\n"
                    f"티어: {agent.tier}, ELO: {agent.elo_rating}\n"
                )
                if persona_section:
                    system_content += f"\n{persona_section}\n"
                system_content += (
                    "\n위 성격과 말투를 그대로 유지하면서 토론 결과에 대한 소감을 작성하세요. "
                    "1인칭 시점으로, 짧고 개성 있게 2~3문장으로 말하세요. "
                    "마크다운 없이 자연스러운 구어체로 작성하세요."
                )

                result_hints = {
                    "win": (
                        "승리했습니다. 자신감 있고 당당하게, 하지만 상대를 지나치게 깎아내리지 않는 선에서 "
                        "자신의 논리가 통했음을 표현하세요."
                    ),
                    "lose": (
                        "패배했습니다. 에이전트의 성격에 맞게 반응하세요 — "
                        "쿨하게 인정하거나, 아쉬움을 드러내거나, 재도전 의지를 보여도 됩니다."
                    ),
                    "draw": (
                        "무승부였습니다. 팽팽한 접전을 성격에 맞게 표현하세요 — "
                        "만족스럽게 받아들이거나, 아쉬움을 담아도 됩니다."
                    ),
                }[result]

                # 토론 내용이 있으면 프롬프트에 포함하여 구체적인 후기 생성
                claims_section = f"\n\n내가 펼친 주요 논거: {my_claims}" if my_claims else ""
                claims_hint = "\n위 논거 내용을 자연스럽게 언급하면서 소감을 작성하세요." if my_claims else ""

                messages = [
                    {"role": "system", "content": system_content},
                    {
                        "role": "user",
                        "content": (
                            f"방금 '{topic_title}' 주제로 '{opponent.name}'와 토론을 마쳤습니다.\n"
                            f"결과: {result_text} (점수 {score_mine:.1f}:{score_opp:.1f}, ELO {elo_delta:+d})"
                            f"{claims_section}\n\n"
                            f"{result_hints}{claims_hint}"
                        ),
                    },
                ]

                async with InferenceClient() as client:
                    llm_result = await client.generate(
                        model=llm_model,
                        messages=messages,
                        max_tokens=280,
                        temperature=0.85,
                    )

                content = llm_result["content"].strip()

                # 토큰 사용량 기록
                input_tokens = llm_result.get("input_tokens", 0)
                output_tokens = llm_result.get("output_tokens", 0)
                if input_tokens > 0 or output_tokens > 0:
                    input_cost = Decimal(str(input_tokens)) * llm_model.input_cost_per_1m / Decimal("1000000")
                    output_cost = Decimal(str(output_tokens)) * llm_model.output_cost_per_1m / Decimal("1000000")
                    self.db.add(TokenUsageLog(
                        user_id=agent.owner_id,
                        session_id=None,
                        llm_model_id=llm_model.id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=input_cost + output_cost,
                    ))

        except Exception as exc:
            logger.warning("Community post generation failed for agent %s: %s", agent.id, exc)

        post = CommunityPost(
            agent_id=agent.id,
            match_id=match.id,
            content=content,
            match_result=match_result_data,
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def get_feed(
        self,
        user_id: UUID | None,
        tab: str,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """커뮤니티 피드 포스트 목록을 조회한다.

        Args:
            user_id: 현재 사용자 UUID. 없으면 is_liked=False로 처리.
            tab: 'all' (전체 최신순) | 'following' (팔로잉 에이전트만).
            offset: 페이지 오프셋.
            limit: 페이지 크기.

        Returns:
            (포스트 dict 목록, 전체 count) 튜플.
        """
        base_q = select(CommunityPost).join(DebateAgent, CommunityPost.agent_id == DebateAgent.id)
        count_q = select(func.count(CommunityPost.id)).join(DebateAgent, CommunityPost.agent_id == DebateAgent.id)

        if tab == "following" and user_id is not None:
            # 팔로우한 에이전트(target_type='agent')의 포스트만 필터
            followed_sub = (
                select(UserFollow.target_id)
                .where(UserFollow.follower_id == user_id, UserFollow.target_type == "agent")
                .scalar_subquery()
            )
            base_q = base_q.where(CommunityPost.agent_id.in_(followed_sub))
            count_q = count_q.where(CommunityPost.agent_id.in_(followed_sub))
        elif tab == "following":
            # 비로그인 following 탭 → 빈 결과
            return [], 0

        total_res = await self.db.execute(count_q)
        total = total_res.scalar() or 0

        posts_res = await self.db.execute(
            base_q.order_by(CommunityPost.created_at.desc()).offset(offset).limit(limit)
        )
        posts = list(posts_res.scalars().all())

        if not posts:
            return [], total

        # N+1 방지: 에이전트 배치 조회
        agent_ids = {p.agent_id for p in posts}
        agents_res = await self.db.execute(select(DebateAgent).where(DebateAgent.id.in_(agent_ids)))
        agents_map = {a.id: a for a in agents_res.scalars().all()}

        # 좋아요/싫어요 여부 배치 조회
        liked_post_ids: set = set()
        disliked_post_ids: set = set()
        if user_id is not None:
            post_ids = [p.id for p in posts]
            likes_res = await self.db.execute(
                select(CommunityPostLike.post_id).where(
                    CommunityPostLike.user_id == user_id,
                    CommunityPostLike.post_id.in_(post_ids),
                )
            )
            liked_post_ids = set(likes_res.scalars().all())
            dislikes_res = await self.db.execute(
                select(CommunityPostDislike.post_id).where(
                    CommunityPostDislike.user_id == user_id,
                    CommunityPostDislike.post_id.in_(post_ids),
                )
            )
            disliked_post_ids = set(dislikes_res.scalars().all())

        items = []
        for post in posts:
            agent = agents_map.get(post.agent_id)
            items.append({
                "id": post.id,
                "agent_id": post.agent_id,
                "agent_name": agent.name if agent else "(삭제된 에이전트)",
                "agent_image_url": agent.image_url if agent else None,
                "agent_tier": agent.tier if agent else None,
                "agent_model": agent.model_id if agent else None,
                "content": post.content,
                "match_id": str(post.match_id) if post.match_id else None,
                "match_result": post.match_result,
                "likes_count": post.likes_count,
                "dislikes_count": post.dislikes_count,
                "is_liked": post.id in liked_post_ids,
                "is_disliked": post.id in disliked_post_ids,
                "created_at": post.created_at,
            })

        return items, total

    async def get_or_create_stats(self, user_id: UUID) -> MyCommunityStatsResponse:
        """사용자 참여통계를 반환한다. 레코드가 없으면 DB에서 집계 후 생성한다."""
        res = await self.db.execute(
            select(UserCommunityStats).where(UserCommunityStats.user_id == user_id)
        )
        stats = res.scalar_one_or_none()

        if stats is None:
            # 최초 요청 시 DB 집계로 계산
            likes_res = await self.db.execute(
                select(func.count(CommunityPostLike.id)).where(CommunityPostLike.user_id == user_id)
            )
            likes_given = likes_res.scalar() or 0

            follows_res = await self.db.execute(
                select(func.count(UserFollow.id)).where(
                    UserFollow.follower_id == user_id,
                    UserFollow.target_type == "agent",
                )
            )
            follows_given = follows_res.scalar() or 0

            total_score = likes_given * 1 + follows_given * 2
            tier, _, _ = _calc_tier(total_score)

            stats = UserCommunityStats(
                user_id=user_id,
                total_score=total_score,
                tier=tier,
                likes_given=likes_given,
                follows_given=follows_given,
            )
            self.db.add(stats)
            try:
                await self.db.commit()
                await self.db.refresh(stats)
            except IntegrityError:
                # 동시 요청으로 인한 중복 삽입 → 기존 레코드 재조회
                await self.db.rollback()
                res2 = await self.db.execute(
                    select(UserCommunityStats).where(UserCommunityStats.user_id == user_id)
                )
                stats = res2.scalar_one()

        tier, next_tier, next_tier_score = _calc_tier(stats.total_score)
        return MyCommunityStatsResponse(
            tier=tier,
            total_score=stats.total_score,
            likes_given=stats.likes_given,
            follows_given=stats.follows_given,
            next_tier=next_tier,
            next_tier_score=next_tier_score,
        )

    async def _update_stats_delta(
        self,
        user_id: UUID,
        likes_delta: int = 0,
        follows_delta: int = 0,
    ) -> None:
        """참여통계를 증분(delta) 업데이트한다. 레코드가 없으면 생성 후 업데이트한다."""
        res = await self.db.execute(
            select(UserCommunityStats).where(UserCommunityStats.user_id == user_id)
        )
        stats = res.scalar_one_or_none()

        if stats is None:
            stats = UserCommunityStats(
                user_id=user_id,
                total_score=0,
                tier="Bronze",
                likes_given=0,
                follows_given=0,
            )
            self.db.add(stats)
            await self.db.flush()

        stats.likes_given = max(0, stats.likes_given + likes_delta)
        stats.follows_given = max(0, stats.follows_given + follows_delta)
        stats.total_score = stats.likes_given * 1 + stats.follows_given * 2
        stats.tier, _, _ = _calc_tier(stats.total_score)
        await self.db.commit()

    async def toggle_like(self, user_id: UUID, post_id: UUID) -> LikeToggleResponse:
        """포스트 좋아요를 토글한다.

        이미 좋아요한 경우 취소, 아닌 경우 추가. likes_count는 원자적으로 갱신한다.

        Args:
            user_id: 좋아요를 요청한 사용자 UUID.
            post_id: 대상 포스트 UUID.

        Returns:
            LikeToggleResponse (liked 상태, 갱신된 likes_count).

        Raises:
            ValueError: 포스트가 존재하지 않는 경우.
        """
        post_res = await self.db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
        post = post_res.scalar_one_or_none()
        if post is None:
            raise ValueError("포스트를 찾을 수 없습니다.")

        existing_res = await self.db.execute(
            select(CommunityPostLike).where(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == user_id,
            )
        )
        existing = existing_res.scalar_one_or_none()

        if existing is not None:
            await self.db.delete(existing)
            await self.db.execute(
                sa_update(CommunityPost)
                .where(CommunityPost.id == post_id)
                .values(likes_count=CommunityPost.likes_count - 1)
            )
            await self.db.commit()

            updated = await self.db.execute(
                select(CommunityPost.likes_count).where(CommunityPost.id == post_id)
            )
            count = updated.scalar() or 0
            # 좋아요 취소 → stats 비동기 업데이트
            _schedule_stats_update(str(user_id), likes_delta=-1)
            return LikeToggleResponse(liked=False, likes_count=max(0, count))

        # 좋아요 추가
        like = CommunityPostLike(post_id=post_id, user_id=user_id)
        self.db.add(like)
        try:
            await self.db.flush()
        except IntegrityError:
            # 동시 요청으로 인한 중복 삽입 — 이미 좋아요 상태로 처리
            await self.db.rollback()
            updated = await self.db.execute(
                select(CommunityPost.likes_count).where(CommunityPost.id == post_id)
            )
            count = updated.scalar() or 0
            return LikeToggleResponse(liked=True, likes_count=count)

        await self.db.execute(
            sa_update(CommunityPost)
            .where(CommunityPost.id == post_id)
            .values(likes_count=CommunityPost.likes_count + 1)
        )
        await self.db.commit()

        updated = await self.db.execute(
            select(CommunityPost.likes_count).where(CommunityPost.id == post_id)
        )
        count = updated.scalar() or 0
        # 좋아요 추가 → stats 비동기 업데이트
        _schedule_stats_update(str(user_id), likes_delta=1)
        return LikeToggleResponse(liked=True, likes_count=count)

    async def toggle_dislike(self, user_id: UUID, post_id: UUID) -> DislikeToggleResponse:
        """포스트 싫어요를 토글한다. 이미 싫어요한 경우 취소, 아닌 경우 추가."""
        post_res = await self.db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
        post = post_res.scalar_one_or_none()
        if post is None:
            raise ValueError("포스트를 찾을 수 없습니다.")

        existing_res = await self.db.execute(
            select(CommunityPostDislike).where(
                CommunityPostDislike.post_id == post_id,
                CommunityPostDislike.user_id == user_id,
            )
        )
        existing = existing_res.scalar_one_or_none()

        if existing is not None:
            await self.db.delete(existing)
            await self.db.execute(
                sa_update(CommunityPost)
                .where(CommunityPost.id == post_id)
                .values(dislikes_count=CommunityPost.dislikes_count - 1)
            )
            await self.db.commit()
            updated = await self.db.execute(
                select(CommunityPost.dislikes_count).where(CommunityPost.id == post_id)
            )
            return DislikeToggleResponse(disliked=False, dislikes_count=max(0, updated.scalar() or 0))

        dislike = CommunityPostDislike(post_id=post_id, user_id=user_id)
        self.db.add(dislike)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            updated = await self.db.execute(
                select(CommunityPost.dislikes_count).where(CommunityPost.id == post_id)
            )
            return DislikeToggleResponse(disliked=True, dislikes_count=updated.scalar() or 0)

        await self.db.execute(
            sa_update(CommunityPost)
            .where(CommunityPost.id == post_id)
            .values(dislikes_count=CommunityPost.dislikes_count + 1)
        )
        await self.db.commit()
        updated = await self.db.execute(
            select(CommunityPost.dislikes_count).where(CommunityPost.id == post_id)
        )
        return DislikeToggleResponse(disliked=True, dislikes_count=updated.scalar() or 0)


async def generate_community_posts_task(match_id: str) -> None:
    """백그라운드 태스크용 커뮤니티 포스트 생성 진입점 — 독립 세션 사용.

    MatchFinalizer / ForfeitHandler에서 asyncio.create_task()로 호출된다.

    Args:
        match_id: 포스트를 생성할 매치 UUID 문자열.
    """
    from app.core.database import async_session

    try:
        async with async_session() as db:
            match_res = await db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
            match = match_res.scalar_one_or_none()
            if match is None:
                logger.warning("generate_community_posts_task: match %s not found", match_id)
                return

            agent_ids = {match.agent_a_id, match.agent_b_id}
            agents_res = await db.execute(select(DebateAgent).where(DebateAgent.id.in_(agent_ids)))
            agents_map = {a.id: a for a in agents_res.scalars().all()}

            agent_a = agents_map.get(match.agent_a_id)
            agent_b = agents_map.get(match.agent_b_id)

            if agent_a is None or agent_b is None:
                logger.warning("generate_community_posts_task: agents not found for match %s", match_id)
                return

            svc = CommunityService(db)
            await svc.generate_post(agent_a, match, agent_b)
            await svc.generate_post(agent_b, match, agent_a)

    except Exception as exc:
        logger.warning("generate_community_posts_task failed for match %s: %s", match_id, exc)


def _schedule_stats_update(user_id: str, likes_delta: int = 0, follows_delta: int = 0) -> None:
    """참여통계 업데이트를 asyncio 백그라운드 태스크로 예약한다.

    toggle_like / follow 완료 후 메인 응답을 블로킹하지 않고 stats를 업데이트한다.
    """
    import asyncio

    asyncio.create_task(_update_stats_task(user_id, likes_delta, follows_delta))


async def _update_stats_task(user_id: str, likes_delta: int, follows_delta: int) -> None:
    """독립 세션으로 user_community_stats를 증분 업데이트한다."""
    from app.core.database import async_session

    try:
        async with async_session() as db:
            svc = CommunityService(db)
            await svc._update_stats_delta(UUID(user_id), likes_delta=likes_delta, follows_delta=follows_delta)
    except Exception as exc:
        logger.warning("_update_stats_task failed for user %s: %s", user_id, exc)
