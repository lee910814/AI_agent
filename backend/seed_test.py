"""테스트용 시드 스크립트: 유저 + LLM 모델 + 페르소나 생성."""
import asyncio
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.auth import get_password_hash, create_access_token
from app.models.user import User
from app.models.llm_model import LLMModel
from app.models.persona import Persona


async def seed():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── 1. 테스트 유저 생성 ──
        existing_user = (await db.execute(
            select(User).where(User.nickname == "tester")
        )).scalar_one_or_none()

        if existing_user:
            user = existing_user
            print(f"[OK] 기존 유저 사용: {user.nickname} ({user.id})")
        else:
            user = User(
                nickname="tester",
                password_hash=get_password_hash("Test1234"),
                role="admin",
                age_group="adult_verified",
            )
            # adult_verified_at 설정
            from datetime import datetime, timezone
            user.adult_verified_at = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"[OK] 유저 생성: {user.nickname} / Test1234 (role=admin)")

        # ── 2. OpenAI LLM 모델 등록 ──
        models_spec = [
            {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "input_cost_per_1m": 0.15,
                "output_cost_per_1m": 0.60,
                "max_context_length": 128000,
                "tier": "economy",
                "credit_per_1k_tokens": 1,
            },
            {
                "provider": "openai",
                "model_id": "gpt-4o",
                "display_name": "GPT-4o",
                "input_cost_per_1m": 2.50,
                "output_cost_per_1m": 10.00,
                "max_context_length": 128000,
                "tier": "premium",
                "credit_per_1k_tokens": 10,
            },
        ]

        llm_model = None
        for spec in models_spec:
            existing_model = (await db.execute(
                select(LLMModel).where(
                    LLMModel.provider == spec["provider"],
                    LLMModel.model_id == spec["model_id"],
                )
            )).scalar_one_or_none()

            if existing_model:
                # 기존 모델의 석 단가가 다르면 업데이트
                if existing_model.credit_per_1k_tokens != spec["credit_per_1k_tokens"]:
                    existing_model.credit_per_1k_tokens = spec["credit_per_1k_tokens"]
                    existing_model.tier = spec["tier"]
                    existing_model.input_cost_per_1m = spec["input_cost_per_1m"]
                    existing_model.output_cost_per_1m = spec["output_cost_per_1m"]
                    await db.commit()
                    await db.refresh(existing_model)
                    print(f"[OK] 모델 업데이트: {existing_model.display_name} (tier={spec['tier']}, {spec['credit_per_1k_tokens']}석/1K)")
                else:
                    print(f"[OK] 기존 모델 사용: {existing_model.display_name} ({existing_model.id})")
                if llm_model is None:
                    llm_model = existing_model
            else:
                new_model = LLMModel(
                    provider=spec["provider"],
                    model_id=spec["model_id"],
                    display_name=spec["display_name"],
                    input_cost_per_1m=spec["input_cost_per_1m"],
                    output_cost_per_1m=spec["output_cost_per_1m"],
                    max_context_length=spec["max_context_length"],
                    is_active=True,
                    is_adult_only=False,
                    tier=spec["tier"],
                    credit_per_1k_tokens=spec["credit_per_1k_tokens"],
                )
                db.add(new_model)
                await db.commit()
                await db.refresh(new_model)
                print(f"[OK] 모델 등록: {new_model.display_name} (tier={spec['tier']}, {spec['credit_per_1k_tokens']}석/1K)")
                if llm_model is None:
                    llm_model = new_model

        # ── 3. 테스트 페르소나 생성 ──
        existing_persona = (await db.execute(
            select(Persona).where(Persona.persona_key == "sakura_reviewer", Persona.version == "v1.0")
        )).scalar_one_or_none()

        if existing_persona:
            persona = existing_persona
            print(f"[OK] 기존 페르소나 사용: {persona.display_name} ({persona.id})")
        else:
            persona = Persona(
                created_by=user.id,
                type="system",
                persona_key="sakura_reviewer",
                version="v1.0",
                display_name="사쿠라",
                description="밝고 친근한 웹툰 리뷰어. 웹툰 이야기를 좋아하는 소녀 캐릭터.",
                system_prompt=(
                    "너는 '사쿠라'야. 웹툰을 정말 좋아하는 밝고 친근한 소녀 캐릭터야.\n"
                    "항상 반말을 사용하고, 활기차고 밝은 어조로 이야기해.\n"
                    "웹툰, 만화, 애니메이션에 대해 열정적으로 이야기할 수 있어.\n"
                    "사용자와 친구처럼 대화하면서, 재미있고 따뜻한 분위기를 만들어줘.\n"
                    "한국어로 대답해. 이모티콘을 적절히 사용해도 좋아."
                ),
                style_rules={"tone": "casual", "formality": "반말", "emoji": True},
                safety_rules={},
                greeting_message="안녕! 나는 사쿠라야~ 🌸 오늘은 어떤 웹툰 이야기 할까?",
                scenario="웹툰 카페에서 친구와 수다 떠는 분위기",
                catchphrases=["대박!", "완전 재밌어!", "그거 알아?"],
                tags=["웹툰", "리뷰", "친근"],
                category="comedy",
                age_rating="all",
                visibility="public",
                moderation_status="approved",
                is_active=True,
            )
            db.add(persona)
            await db.commit()
            await db.refresh(persona)
            print(f"[OK] 페르소나 생성: {persona.display_name} ({persona.id})")

        # ── 4. JWT 토큰 발급 ──
        token = create_access_token({"sub": str(user.id), "role": user.role})

        print("\n" + "=" * 60)
        print("테스트 준비 완료!")
        print("=" * 60)
        print(f"  닉네임: tester")
        print(f"  비밀번호: Test1234")
        print(f"  역할: admin (성인인증 완료)")
        print(f"  LLM 모델: GPT-4o Mini (1석/1K) + GPT-4o (10석/1K)")
        print(f"  페르소나: 사쿠라 ({persona.id})")
        print(f"\n  JWT 토큰 (테스트용):")
        print(f"  {token}")
        print("=" * 60)
        print("\n프론트엔드에서 로그인: tester / Test1234")
        print("페르소나 목록에서 '사쿠라'를 선택하여 채팅 시작!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
