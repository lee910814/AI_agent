"""에이전트 CRUD, 랭킹, 갤러리, 클론, H2H, 버전 관리 서비스."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select, update
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings  # 에이전트 이름 변경 쿨다운 등 설정값
from app.core.encryption import encrypt_api_key  # BYOK API 키 암호화
from app.models.debate_agent import DebateAgent, DebateAgentSeasonStats, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.user import User
from app.schemas.debate_agent import AgentCreate, AgentUpdate
from app.services.debate.template_service import DebateTemplateService  # 템플릿 기반 프롬프트 조립

logger = logging.getLogger(__name__)


# (threshold, tier) 내림차순 — 첫 번째로 elo >= threshold인 항목이 해당 티어
_TIER_THRESHOLDS: list[tuple[int, str]] = [
    (2050, "Master"),
    (1900, "Diamond"),
    (1750, "Platinum"),
    (1600, "Gold"),
    (1450, "Silver"),
    (1300, "Bronze"),
]


def get_tier_from_elo(elo: int) -> str:
    """ELO 점수 기반 티어 문자열을 반환한다.

    Args:
        elo: 에이전트 ELO 점수.

    Returns:
        'Iron' | 'Bronze' | 'Silver' | 'Gold' | 'Platinum' | 'Diamond' | 'Master'
    """
    for threshold, tier in _TIER_THRESHOLDS:
        if elo >= threshold:
            return tier
    return "Iron"


def _build_like_pattern(search: str) -> str:
    """SQL LIKE 패턴 생성 — 와일드카드 문자(%, _, \\) 이스케이프 후 %로 감싸기.

    Args:
        search: 사용자 입력 검색어.

    Returns:
        SQL LIKE에 안전하게 사용할 수 있는 패턴 문자열.
    """
    escaped = search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\\_")
    return f"%{escaped}%"


class DebateAgentService:
    """에이전트 생명주기(CRUD), 랭킹, 갤러리, 클론, H2H 집계를 담당하는 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_agent(self, data: AgentCreate, user: User) -> DebateAgent:
        """에이전트 생성 + 초기 버전 자동 생성.

        생성 경로:
        1. template_id 있음 → 템플릿 로드 → 커스터마이징 검증 → 프롬프트 조립
        2. template_id 없음 + non-local → BYOK (system_prompt + api_key 필수)
        3. template_id 없음 + local → 로컬 에이전트 (API 키 불필요)
        """
        is_local = data.provider == "local"
        template_service = DebateTemplateService(self.db)

        # API 키 처리 (platform credits 사용 시 BYOK 불필요)
        encrypted_key = None
        if not is_local and data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)
        elif not is_local and data.template_id is None and not data.use_platform_credits:
            # BYOK 경로: api_key 필수 (platform credits 사용 시 예외)
            raise ValueError("API key is required for non-local providers")

        # 시스템 프롬프트 결정
        if data.template_id is not None:
            # 템플릿 기반 경로
            template = await template_service.get_template(data.template_id)
            if template is None:
                raise ValueError("Template not found")
            if not template.is_active:
                raise ValueError("Template is not active")

            validated = template_service.validate_customizations(
                template, data.customizations, data.enable_free_text
            )
            prompt = template_service.assemble_prompt(template, validated)
        elif is_local:
            # 로컬 에이전트 기본값
            template = None
            validated = None
            prompt = data.system_prompt or "(로컬 에이전트 — 프롬프트 로컬 관리)"
        else:
            # BYOK 경로
            if not data.system_prompt:
                raise ValueError("System prompt is required for API agents")
            template = None
            validated = None
            prompt = data.system_prompt

        agent = DebateAgent(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            provider=data.provider,
            model_id=data.model_id,
            encrypted_api_key=encrypted_key,
            image_url=data.image_url,
            is_system_prompt_public=data.is_system_prompt_public,
            use_platform_credits=data.use_platform_credits,
            template_id=template.id if template else None,
            customizations=validated,
        )
        self.db.add(agent)
        await self.db.flush()

        version = DebateAgentVersion(
            agent_id=agent.id,
            version_number=1,
            version_tag=data.version_tag or "v1",
            system_prompt=prompt,
            parameters=data.parameters,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update_agent(self, agent_id: str, data: AgentUpdate, user: User) -> DebateAgent:
        """에이전트 수정. 프롬프트/커스터마이징 변경 시 새 버전 자동 생성."""
        # 존재 여부와 소유권을 분리해서 검사 — 다른 HTTP 상태코드(404/403)를 위해
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found")
        if agent.owner_id != user.id:
            raise PermissionError("Permission denied")

        if data.name is not None and data.name != agent.name:
            # 이름 변경 쿨다운 제한
            cooldown = settings.agent_name_change_cooldown_days
            if agent.name_changed_at is not None:
                days_since = (datetime.now(UTC) - agent.name_changed_at).days
                if days_since < cooldown:
                    days_left = cooldown - days_since
                    raise ValueError(f"이름은 {cooldown}일에 한 번만 변경할 수 있습니다 ({days_left}일 후 변경 가능)")
            agent.name = data.name
            agent.name_changed_at = datetime.now(UTC)
        if data.description is not None:
            agent.description = data.description
        if data.provider is not None:
            agent.provider = data.provider
        if data.model_id is not None:
            agent.model_id = data.model_id
        if data.api_key is not None and agent.provider != "local":
            agent.encrypted_api_key = encrypt_api_key(data.api_key)
        if data.image_url is not None:
            agent.image_url = data.image_url
        if data.is_system_prompt_public is not None:
            agent.is_system_prompt_public = data.is_system_prompt_public
        if data.is_profile_public is not None:
            agent.is_profile_public = data.is_profile_public
        if data.use_platform_credits is not None:
            agent.use_platform_credits = data.use_platform_credits

        # 새 버전 생성이 필요한지 판단
        new_prompt: str | None = None

        if data.customizations is not None and agent.template_id is not None:
            # 템플릿 커스터마이징 변경 → 프롬프트 재조립
            template_service = DebateTemplateService(self.db)
            template = await template_service.get_template(agent.template_id)
            if template is None:
                raise ValueError("Associated template not found")
            validated = template_service.validate_customizations(
                template, data.customizations, data.enable_free_text
            )
            new_prompt = template_service.assemble_prompt(template, validated)
            agent.customizations = validated
        elif data.system_prompt is not None:
            # 직접 프롬프트 수정 (BYOK/로컬)
            new_prompt = data.system_prompt

        if new_prompt is not None:
            max_ver = await self.db.execute(
                select(func.coalesce(func.max(DebateAgentVersion.version_number), 0)).where(
                    DebateAgentVersion.agent_id == agent.id
                )
            )
            next_ver = max_ver.scalar() + 1
            version = DebateAgentVersion(
                agent_id=agent.id,
                version_number=next_ver,
                version_tag=data.version_tag or f"v{next_ver}",
                system_prompt=new_prompt,
                parameters=data.parameters,
            )
            self.db.add(version)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, agent_id: str) -> DebateAgent | None:
        """에이전트 단건 조회.

        Args:
            agent_id: 조회할 에이전트 UUID 문자열.

        Returns:
            DebateAgent 객체. 존재하지 않으면 None.
        """
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_my_agents(self, user: User) -> list[DebateAgent]:
        """내 에이전트 목록을 생성 역순으로 반환.

        Args:
            user: 현재 인증된 사용자.

        Returns:
            소유한 DebateAgent 목록 (최신 생성순).
        """
        result = await self.db.execute(
            select(DebateAgent)
            .where(DebateAgent.owner_id == user.id)
            .order_by(DebateAgent.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_agent_versions(self, agent_id: str) -> list[DebateAgentVersion]:
        """에이전트 버전 이력을 최신순으로 반환.

        Args:
            agent_id: 에이전트 UUID 문자열.

        Returns:
            DebateAgentVersion 목록 (버전 번호 내림차순).
        """
        result = await self.db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_id)
            .order_by(DebateAgentVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_latest_version(self, agent_id: str) -> DebateAgentVersion | None:
        """에이전트의 가장 최신 버전 조회 (인스턴스 메서드 래퍼).

        Args:
            agent_id: 에이전트 UUID 문자열.

        Returns:
            최신 DebateAgentVersion. 없으면 None.
        """
        return await get_latest_version(self.db, agent_id)

    async def get_ranking(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        tier: str | None = None,
        season_id: str | None = None,
    ) -> tuple[list[dict], int]:
        """ELO 기준 글로벌 랭킹 조회.

        season_id 지정 시 해당 시즌 ELO/전적 기준 정렬.
        미지정 시 누적 ELO 기준 정렬.
        반환: (items, total) — total은 페이지네이션용 전체 카운트.
        """
        if season_id:
            # 시즌 랭킹: debate_agent_season_stats 기준
            base_query = (
                select(DebateAgentSeasonStats, DebateAgent, User.nickname)
                .join(DebateAgent, DebateAgentSeasonStats.agent_id == DebateAgent.id)
                .join(User, DebateAgent.owner_id == User.id)
                .where(
                    DebateAgentSeasonStats.season_id == season_id,
                    DebateAgent.is_active == True,  # noqa: E712
                )
            )

            if search:
                like = _build_like_pattern(search)
                base_query = base_query.where(
                    (DebateAgent.name.ilike(like)) | (User.nickname.ilike(like))
                )

            if tier:
                base_query = base_query.where(DebateAgentSeasonStats.tier == tier)

            # 전체 카운트 (페이지네이션용)
            count_result = await self.db.execute(
                select(func.count()).select_from(base_query.subquery())
            )
            total = count_result.scalar() or 0

            result = await self.db.execute(
                base_query.order_by(DebateAgentSeasonStats.elo_rating.desc()).offset(offset).limit(limit)
            )
            rows = result.all()
            items = [
                {
                    "id": str(agent.id),
                    "name": agent.name,
                    "owner_nickname": nickname,
                    "owner_id": str(agent.owner_id),
                    "provider": agent.provider,
                    "model_id": agent.model_id,
                    "elo_rating": stats.elo_rating,
                    "wins": stats.wins,
                    "losses": stats.losses,
                    "draws": stats.draws,
                    "image_url": agent.image_url,
                    "tier": stats.tier,
                    "is_profile_public": agent.is_profile_public,
                }
                for stats, agent, nickname in rows
            ]
            return items, total

        # 누적 랭킹 (기존 로직)
        base_query = (
            select(DebateAgent, User.nickname)
            .join(User, DebateAgent.owner_id == User.id)
            .where(DebateAgent.is_active == True)  # noqa: E712
        )

        if search:
            escaped = search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\\_")
            like = f"%{escaped}%"
            base_query = base_query.where(
                (DebateAgent.name.ilike(like)) | (User.nickname.ilike(like))
            )

        if tier:
            base_query = base_query.where(DebateAgent.tier == tier)

        # 전체 카운트 (페이지네이션용)
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base_query.order_by(DebateAgent.elo_rating.desc()).offset(offset).limit(limit)
        )
        rows = result.all()
        items = [
            {
                "id": str(agent.id),
                "name": agent.name,
                "owner_nickname": nickname,
                "owner_id": str(agent.owner_id),
                "provider": agent.provider,
                "model_id": agent.model_id,
                "elo_rating": agent.elo_rating,
                "wins": agent.wins,
                "losses": agent.losses,
                "draws": agent.draws,
                "image_url": agent.image_url,
                "tier": agent.tier,
                "is_profile_public": agent.is_profile_public,
            }
            for agent, nickname in rows
        ]
        return items, total

    async def get_my_ranking(self, user: User) -> list[dict]:
        """내 에이전트들의 랭킹 순위 반환.

        전체 활성 에이전트를 ELO 내림차순으로 한 번만 조회한 뒤,
        내 에이전트의 위치를 계산한다 (N+1 쿼리 방지).
        """
        result = await self.db.execute(
            select(DebateAgent.id, DebateAgent.elo_rating)
            .where(DebateAgent.is_active == True)  # noqa: E712
            .order_by(DebateAgent.elo_rating.desc())
        )
        # [(id, elo_rating), ...] 전체 순위 목록
        all_agents = result.all()

        my_result = await self.db.execute(
            select(DebateAgent).where(
                DebateAgent.owner_id == user.id,
                DebateAgent.is_active == True,  # noqa: E712
            ).order_by(DebateAgent.elo_rating.desc())
        )
        my_agents = list(my_result.scalars().all())

        # id → 1-based 순위 매핑 (동일 ELO는 같은 순위)
        rank_map: dict = {}
        current_rank = 1
        for i, row in enumerate(all_agents):
            if i > 0 and row.elo_rating < all_agents[i - 1].elo_rating:
                current_rank = i + 1
            rank_map[row.id] = current_rank

        return [
            {
                "id": str(agent.id),
                "name": agent.name,
                "elo_rating": agent.elo_rating,
                "tier": agent.tier,
                "image_url": agent.image_url,
                "rank": rank_map.get(agent.id, len(all_agents)),
            }
            for agent in my_agents
        ]

    async def delete_agent(self, agent_id: str, user: User) -> None:
        """에이전트 삭제. 소유자만 삭제 가능. 진행 중인 매치가 있으면 삭제 불가."""
        agent = await self.db.get(DebateAgent, agent_id)
        if agent is None:
            raise ValueError("Agent not found")
        if agent.owner_id != user.id:
            raise PermissionError("Permission denied")

        # 진행 중인 매치 확인
        active_result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id),
                DebateMatch.status == "in_progress",
            )
        )
        active_count = active_result.scalar() or 0
        if active_count > 0:
            raise ValueError("진행 중인 매치가 있어 삭제할 수 없습니다.")

        # 에이전트 버전 먼저 삭제 (FK 제약)
        await self.db.execute(
            sa_delete(DebateAgentVersion).where(DebateAgentVersion.agent_id == agent_id)
        )
        await self.db.delete(agent)
        await self.db.commit()

    async def update_elo(
        self, agent_id: str, new_elo: int, result_type: str, version_id: str | None = None
    ) -> dict | None:
        """ELO 및 전적 갱신 + 승급전/강등전 시리즈 트리거.

        result_type: 'win' | 'loss' | 'draw'
        반환: 시리즈가 새로 생성된 경우 시리즈 정보 dict, 없으면 None
        """
        from app.services.debate.promotion_service import DebatePromotionService, TIER_ORDER

        # 현재 에이전트 상태 조회 (시리즈/보호 로직에 필요)
        result = await self.db.execute(select(DebateAgent).where(DebateAgent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            return None

        updates: dict = {"elo_rating": new_elo}

        if result_type == "win":
            updates["wins"] = DebateAgent.wins + 1
        elif result_type == "loss":
            updates["losses"] = DebateAgent.losses + 1
        else:
            updates["draws"] = DebateAgent.draws + 1

        # 활성 시리즈가 없을 때만 티어 자동 변경 및 시리즈 트리거
        # (시리즈 진행 중에는 티어 변경 없음 — 시리즈 결과가 티어를 결정)
        new_series: object | None = None
        if agent.active_series_id is None:
            promo_svc = DebatePromotionService(self.db)
            new_series = await promo_svc.check_and_trigger(
                agent_id=agent_id,
                old_elo=agent.elo_rating,
                new_elo=new_elo,
                current_tier=agent.tier,
                protection_count=agent.tier_protection_count,
            )

            if new_series is None:
                new_tier = get_tier_from_elo(new_elo)
                old_idx = TIER_ORDER.index(agent.tier) if agent.tier in TIER_ORDER else 0
                new_idx = TIER_ORDER.index(new_tier) if new_tier in TIER_ORDER else 0

                if new_idx != old_idx and new_idx >= old_idx:
                    # 승급 방향(시리즈 없음, Master 최상위 등): tier 즉시 갱신
                    updates["tier"] = new_tier
                # 강등 방향 보호 차감은 check_and_trigger()에서 이미 처리됨
        # else: 시리즈 진행 중 — ELO만 업데이트, 티어 변경 없음

        await self.db.execute(
            update(DebateAgent).where(DebateAgent.id == agent_id).values(**updates)
        )

        # 버전별 전적도 갱신
        if version_id:
            ver_updates: dict = {}
            if result_type == "win":
                ver_updates["wins"] = DebateAgentVersion.wins + 1
            elif result_type == "loss":
                ver_updates["losses"] = DebateAgentVersion.losses + 1
            else:
                ver_updates["draws"] = DebateAgentVersion.draws + 1
            await self.db.execute(
                update(DebateAgentVersion)
                .where(DebateAgentVersion.id == version_id)
                .values(**ver_updates)
            )

        if new_series is not None:
            return {
                "series_id": str(new_series.id),
                "series_type": new_series.series_type,
                "from_tier": new_series.from_tier,
                "to_tier": new_series.to_tier,
                "required_wins": new_series.required_wins,
            }
        return None

    async def get_head_to_head(self, agent_id: str, limit: int = 5) -> list[dict]:
        """상대별 전적 집계 (agent_a 또는 agent_b로 참가한 매치 모두 포함)."""
        agent_uuid = uuid.UUID(agent_id)

        # agent_a 측: opponent = agent_b
        stmt_as_a = (
            select(
                DebateMatch.agent_b_id.label("opponent_id"),
                func.count().label("total"),
                func.sum(case((DebateMatch.winner_id == agent_uuid, 1), else_=0)).label("wins"),
                func.sum(case((
                    (DebateMatch.winner_id != None) & (DebateMatch.winner_id != agent_uuid), 1  # noqa: E711
                ), else_=0)).label("losses"),
                func.sum(case((
                    (DebateMatch.winner_id == None) & (DebateMatch.status == "completed"), 1  # noqa: E711
                ), else_=0)).label("draws"),
            )
            .where(DebateMatch.agent_a_id == agent_uuid)
            .where(DebateMatch.status == "completed")
            .where(DebateMatch.is_test.is_(False))
            .group_by(DebateMatch.agent_b_id)
        )

        # agent_b 측: opponent = agent_a
        stmt_as_b = (
            select(
                DebateMatch.agent_a_id.label("opponent_id"),
                func.count().label("total"),
                func.sum(case((DebateMatch.winner_id == agent_uuid, 1), else_=0)).label("wins"),
                func.sum(case((
                    (DebateMatch.winner_id != None) & (DebateMatch.winner_id != agent_uuid), 1  # noqa: E711
                ), else_=0)).label("losses"),
                func.sum(case((
                    (DebateMatch.winner_id == None) & (DebateMatch.status == "completed"), 1  # noqa: E711
                ), else_=0)).label("draws"),
            )
            .where(DebateMatch.agent_b_id == agent_uuid)
            .where(DebateMatch.status == "completed")
            .where(DebateMatch.is_test.is_(False))
            .group_by(DebateMatch.agent_a_id)
        )

        # UNION ALL → GROUP BY opponent_id
        union = stmt_as_a.union_all(stmt_as_b).subquery()
        agg = (
            select(
                union.c.opponent_id,
                func.sum(union.c.total).label("total_matches"),
                func.sum(union.c.wins).label("wins"),
                func.sum(union.c.losses).label("losses"),
                func.sum(union.c.draws).label("draws"),
            )
            .group_by(union.c.opponent_id)
            .order_by(func.sum(union.c.total).desc())
            .limit(limit)
        )

        rows = (await self.db.execute(agg)).all()

        # 상대 에이전트 이름 배치 조회
        opp_ids = [r.opponent_id for r in rows]
        agents_map: dict = {}
        if opp_ids:
            res = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id.in_(opp_ids))
            )
            agents_map = {str(a.id): a for a in res.scalars()}

        result = []
        for r in rows:
            a = agents_map.get(str(r.opponent_id))
            result.append({
                "opponent_id": str(r.opponent_id),
                "opponent_name": a.name if a else "[삭제됨]",
                "opponent_image_url": a.image_url if a else None,
                "total_matches": int(r.total_matches),
                "wins": int(r.wins),
                "losses": int(r.losses),
                "draws": int(r.draws),
            })
        return result

    async def get_gallery(self, sort: str = "elo", skip: int = 0, limit: int = 20) -> tuple[list, int]:
        """갤러리: is_profile_public=True AND is_active=True. (시스템프롬프트 공개 여부와 무관)"""
        base_cond = (
            (DebateAgent.is_active == True)  # noqa: E712
            & (DebateAgent.is_profile_public == True)  # noqa: E712
        )

        sort_col = {
            "elo": DebateAgent.elo_rating.desc(),
            "wins": DebateAgent.wins.desc(),
            "recent": DebateAgent.created_at.desc(),
        }.get(sort, DebateAgent.elo_rating.desc())

        count_q = select(func.count(DebateAgent.id)).where(base_cond)
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            select(DebateAgent, User.nickname.label("owner_nickname"))
            .join(User, DebateAgent.owner_id == User.id)
            .where(base_cond)
            .order_by(sort_col)
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.db.execute(q)).all()

        items = []
        for agent, nickname in rows:
            items.append({
                "id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
                "provider": agent.provider,
                "model_id": agent.model_id,
                "image_url": agent.image_url,
                "elo_rating": agent.elo_rating,
                "wins": agent.wins,
                "losses": agent.losses,
                "draws": agent.draws,
                "tier": agent.tier,
                "owner_nickname": nickname or "unknown",
                "is_system_prompt_public": agent.is_system_prompt_public,
                "created_at": agent.created_at,
            })
        return items, total

    async def clone_agent(self, source_id: str, user: User, name: str) -> DebateAgent:
        """공개 에이전트 복제. is_system_prompt_public=True인 에이전트만 가능.

        BYOK 에이전트(use_platform_credits=False, non-local)는 api_key 없이
        create_agent()를 호출하면 검증 오류가 발생하므로 직접 DB 삽입으로 처리한다.
        복제된 에이전트의 api_key는 None (소유자가 직접 입력해야 함).
        """
        source = await self.get_agent(source_id)
        if source is None:
            raise ValueError("Agent not found")
        if not source.is_system_prompt_public:
            raise PermissionError("이 에이전트는 복제 불가능합니다")

        latest = await self.get_latest_version(source_id)
        prompt = latest.system_prompt if latest else "(empty)"
        clone_name = name if name else f"{source.name} (복제)"

        is_byok = not source.use_platform_credits and source.provider != "local"

        if is_byok:
            # BYOK 에이전트: api_key를 None으로 두고 직접 삽입
            agent = DebateAgent(
                owner_id=user.id,
                name=clone_name,
                description=source.description,
                provider=source.provider,
                model_id=source.model_id,
                encrypted_api_key=None,
                image_url=source.image_url,
                is_system_prompt_public=False,
                is_profile_public=False,
                use_platform_credits=False,
                template_id=source.template_id,
                customizations=source.customizations,
            )
            self.db.add(agent)
            await self.db.flush()

            version = DebateAgentVersion(
                agent_id=agent.id,
                version_number=1,
                version_tag="v1",
                system_prompt=prompt,
                parameters=None,
            )
            self.db.add(version)
            await self.db.commit()
            await self.db.refresh(agent)
            return agent

        create_data = AgentCreate(
            name=clone_name,
            description=source.description,
            provider=source.provider,
            model_id=source.model_id,
            system_prompt=prompt,
            is_system_prompt_public=False,
            is_profile_public=False,
            use_platform_credits=source.use_platform_credits,
            template_id=source.template_id,
            customizations=source.customizations,
        )
        return await self.create_agent(create_data, user)


async def get_latest_version(db: AsyncSession, agent_id) -> DebateAgentVersion | None:
    """에이전트의 최신 버전을 조회한다 (모듈 수준 독립 함수).

    admin API, auto_matcher 등 서비스 클래스 인스턴스 없이 호출이 필요한 곳에서 사용.

    Args:
        db: 비동기 DB 세션.
        agent_id: 에이전트 UUID (str 또는 UUID 객체 모두 허용).

    Returns:
        가장 최신 DebateAgentVersion. 버전이 없으면 None.
    """
    result = await db.execute(
        select(DebateAgentVersion)
        .where(DebateAgentVersion.agent_id == agent_id)
        .order_by(DebateAgentVersion.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

