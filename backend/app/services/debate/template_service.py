"""템플릿 서비스. 관리자 제공 에이전트 템플릿 목록 조회, 프롬프트 조립."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent_template import DebateAgentTemplate
from app.schemas.debate_agent import AgentTemplateCreate, AgentTemplateUpdate

# 프롬프트 인젝션 의심 패턴 — free_text 입력에만 적용
_INJECTION_PATTERNS = re.compile(
    r"(<\|im_end\|>|<\|endoftext\|>|</s>|\[INST\]|\[/INST\]"
    r"|###\s*(Human|Assistant|System)"
    r"|IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS"
    r"|<!--.*?-->)",
    re.IGNORECASE | re.DOTALL,
)


class DebateTemplateService:
    """에이전트 템플릿 CRUD, 커스터마이징 검증, 프롬프트 조립 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------

    async def list_active_templates(self) -> list[DebateAgentTemplate]:
        """활성 템플릿 목록 (sort_order 오름차순)."""
        result = await self.db.execute(
            select(DebateAgentTemplate)
            .where(DebateAgentTemplate.is_active == True)  # noqa: E712
            .order_by(DebateAgentTemplate.sort_order)
        )
        return list(result.scalars().all())

    async def list_all_templates(self) -> list[DebateAgentTemplate]:
        """전체 템플릿 목록 (관리자용, 비활성 포함)."""
        result = await self.db.execute(
            select(DebateAgentTemplate).order_by(DebateAgentTemplate.sort_order)
        )
        return list(result.scalars().all())

    async def get_template(self, template_id: str | uuid.UUID) -> DebateAgentTemplate | None:
        """단일 템플릿을 ID로 조회한다.

        Args:
            template_id: 조회할 템플릿 UUID 또는 문자열.

        Returns:
            DebateAgentTemplate 객체. 미존재 시 None.
        """
        result = await self.db.execute(
            select(DebateAgentTemplate).where(DebateAgentTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # 커스터마이징 검증 + 프롬프트 조립
    # ------------------------------------------------------------------

    def validate_customizations(
        self,
        template: DebateAgentTemplate,
        customizations: dict | None,
        enable_free_text: bool = False,
    ) -> dict:
        """커스터마이징 값을 검증하고 누락 키는 기본값으로 채운다.

        Args:
            template: 검증 기준 템플릿
            customizations: 사용자 입력 (None이면 기본값만 반환)
            enable_free_text: True여야 free_text 필드를 포함

        Returns:
            검증 완료된 flat dict

        Raises:
            ValueError: 유효하지 않은 값 (범위 초과, 허용되지 않은 옵션 등)
        """
        schema = template.customization_schema
        defaults = template.default_values
        result: dict = dict(defaults)  # 기본값으로 초기화

        if customizations:
            result.update(customizations)

        # 슬라이더 범위 검증
        for slider in schema.get("sliders", []):
            key = slider["key"]
            val = result.get(key, slider["default"])
            try:
                val = int(val)
            except (TypeError, ValueError) as err:
                raise ValueError(f"슬라이더 '{key}' 값은 정수여야 합니다.") from err
            if not (slider["min"] <= val <= slider["max"]):
                raise ValueError(
                    f"슬라이더 '{key}' 값 {val}은 {slider['min']}~{slider['max']} 범위여야 합니다."
                )
            result[key] = val

        # 셀렉트 옵션 검증
        for sel in schema.get("selects", []):
            key = sel["key"]
            val = result.get(key, sel["default"])
            valid_values = [opt["value"] for opt in sel["options"]]
            if val not in valid_values:
                raise ValueError(
                    f"'{key}' 값 '{val}'은 허용된 옵션({valid_values})이 아닙니다."
                )
            result[key] = val

        # free_text 처리
        ft = schema.get("free_text")
        if ft:
            ft_key = ft["key"]
            ft_val = result.get(ft_key)
            if not enable_free_text:
                # 체크박스 비활성 시 제거
                result.pop(ft_key, None)
            elif ft_val is not None:
                ft_val = str(ft_val)
                max_len = ft.get("max_length", 500)
                if len(ft_val) > max_len:
                    raise ValueError(
                        f"추가 지시사항은 {max_len}자를 초과할 수 없습니다."
                    )
                # 프롬프트 인젝션 패턴 스캔
                if _INJECTION_PATTERNS.search(ft_val):
                    raise ValueError("추가 지시사항에 허용되지 않는 패턴이 포함되어 있습니다.")
                result[ft_key] = ft_val

        return result

    def assemble_prompt(
        self, template: DebateAgentTemplate, customizations: dict
    ) -> str:
        """검증된 customizations로 {customization_block}을 치환하여 최종 프롬프트를 반환한다.

        슬라이더·셀렉트·free_text 값을 한국어 라벨 텍스트로 변환해
        base_system_prompt의 {customization_block} 자리에 삽입한다.

        Args:
            template: 프롬프트 베이스를 포함하는 템플릿 객체.
            customizations: validate_customizations()로 검증·보정된 커스터마이징 dict.

        Returns:
            {customization_block}이 치환된 최종 시스템 프롬프트 문자열.
        """
        schema = template.customization_schema
        lines: list[str] = ["[커스터마이징 설정]"]

        # 슬라이더 → 텍스트 표현
        slider_labels = {s["key"]: s["label"] for s in schema.get("sliders", [])}
        for key, label in slider_labels.items():
            val = customizations.get(key)
            if val is not None:
                lines.append(f"- {label}: {val}/5")

        # 셀렉트 → 텍스트 표현
        for sel in schema.get("selects", []):
            key = sel["key"]
            val = customizations.get(key)
            if val is not None:
                label_map = {opt["value"]: opt["label"] for opt in sel["options"]}
                lines.append(f"- {sel['label']}: {label_map.get(val, val)}")

        # free_text
        ft = schema.get("free_text")
        if ft:
            ft_val = customizations.get(ft["key"])
            if ft_val:
                lines.append(f"- {ft['label']}: {ft_val}")

        customization_block = "\n".join(lines)
        return template.base_system_prompt.replace("{customization_block}", customization_block)

    # ------------------------------------------------------------------
    # 관리자 CRUD
    # ------------------------------------------------------------------

    async def create_template(self, data: AgentTemplateCreate) -> DebateAgentTemplate:
        """템플릿 생성 (superadmin)."""
        tmpl = DebateAgentTemplate(
            slug=data.slug,
            display_name=data.display_name,
            description=data.description,
            icon=data.icon,
            base_system_prompt=data.base_system_prompt,
            customization_schema=data.customization_schema,
            default_values=data.default_values,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.db.add(tmpl)
        await self.db.commit()
        await self.db.refresh(tmpl)
        return tmpl

    async def update_template(
        self, template_id: str | uuid.UUID, data: AgentTemplateUpdate
    ) -> DebateAgentTemplate:
        """템플릿 수정 (superadmin)."""
        tmpl = await self.get_template(template_id)
        if tmpl is None:
            raise ValueError("Template not found")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(tmpl, field, value)

        await self.db.commit()
        await self.db.refresh(tmpl)
        return tmpl
