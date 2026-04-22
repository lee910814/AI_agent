"""EvidenceSearchService 단위 테스트. URL fetch·합성 결과 및 raw_content 보존 검증."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.debate.evidence_search import EvidenceResult, EvidenceSearchService


def _make_ddg_result(url: str = "https://example.com/page", title: str = "Test", body: str = "snippet text") -> dict:
    return {"href": url, "title": title, "body": body}


class TestEvidenceResult:
    def test_format_includes_text_and_sources(self):
        result = EvidenceResult(text="근거 내용", sources=["https://a.com"])
        formatted = result.format()
        assert "근거 내용" in formatted
        assert "https://a.com" in formatted

    def test_format_no_sources(self):
        result = EvidenceResult(text="근거 내용")
        assert "출처 없음" in result.format()

    def test_raw_content_default_empty(self):
        result = EvidenceResult(text="근거 내용")
        assert result.raw_content == ""

    def test_raw_content_stored_separately_from_format(self):
        """raw_content는 format() 출력에 포함되지 않아야 한다 — 에이전트에겐 미노출."""
        raw = "[출처 1] Example (https://example.com)\n실제 페이지 본문 내용"
        result = EvidenceResult(text="합성된 요약", sources=["https://example.com"], raw_content=raw)
        formatted = result.format()
        assert "합성된 요약" in formatted
        assert raw not in formatted  # 에이전트에게 raw_content가 노출되지 않음

    def test_raw_content_preserved_with_multiple_sources(self):
        content1 = "[출처 1] Page1 (https://a.com)\n내용1"
        content2 = "[출처 2] Page2 (https://b.com)\n내용2"
        joined = content1 + "\n\n" + content2
        result = EvidenceResult(
            text="합성된 요약",
            sources=["https://a.com", "https://b.com"],
            raw_content=joined,
        )
        assert "내용1" in result.raw_content
        assert "내용2" in result.raw_content
        assert "https://a.com" in result.raw_content


class TestEvidenceSearchServiceRawContent:
    @pytest.mark.asyncio
    async def test_fetch_and_synthesize_sets_raw_content(self):
        """fetch 성공 시 raw_content에 page_contents가 저장되어야 한다."""
        service = EvidenceSearchService()

        ddg_results = [_make_ddg_result(url="https://example.com/ai")]
        fetched_body = "실제 페이지 본문 — AI 관련 정보 포함"
        synthesized_text = "AI는 위험하다는 연구 결과가 있다."

        with (
            patch.object(service, "_fetch_url", new=AsyncMock(return_value=fetched_body)),
            patch.object(service, "_synthesize", new=AsyncMock(return_value=synthesized_text)),
            patch("app.services.debate.evidence_search.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = "sk-test"
            result = await service._fetch_and_synthesize(
                claim="AI는 위험한가",
                topic="AI 안전성",
                results=ddg_results,
                exclude_urls=None,
            )

        assert result is not None
        assert result.text == synthesized_text
        assert result.raw_content != ""
        # fetch된 본문이 raw_content에 포함되어야 함
        assert fetched_body in result.raw_content

    @pytest.mark.asyncio
    async def test_raw_content_present_even_on_snippet_fallback(self):
        """URL fetch 실패 시 snippet fallback 경로에서도 raw_content가 설정되어야 한다."""
        service = EvidenceSearchService()

        ddg_results = [_make_ddg_result(url="https://example.com/ai", body="DDG snippet 내용")]

        with (
            patch.object(service, "_fetch_url", new=AsyncMock(return_value=None)),
            patch.object(service, "_synthesize", new=AsyncMock(return_value="합성 요약")),
            patch("app.services.debate.evidence_search.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = "sk-test"
            result = await service._fetch_and_synthesize(
                claim="AI는 위험한가",
                topic="AI 안전성",
                results=ddg_results,
                exclude_urls=None,
            )

        assert result is not None
        # snippet fallback 경로에서도 raw_content가 빈 문자열이 아닌 값을 가져야 함
        assert result.raw_content != ""
        assert "DDG snippet 내용" in result.raw_content

    @pytest.mark.asyncio
    async def test_snippet_fallback_when_synthesis_says_irrelevant(self):
        """LLM 합성 결과가 '관련 근거 없음'이어도 snippet이 있으면 폴백 반환한다.

        URL fetch와 합성까지 수행했더라도 무관 판정이 나면, snippet 원문을 대신 반환.
        검색 결과 자체는 있으므로 사용자에게 최소한의 정보를 제공한다.
        """
        service = EvidenceSearchService()

        ddg_results = [_make_ddg_result(url="https://unrelated.com/page")]

        with (
            patch.object(service, "_fetch_url", new=AsyncMock(return_value="무관한 본문 내용")),
            patch.object(service, "_synthesize", new=AsyncMock(return_value="관련 근거 없음")),
            patch("app.services.debate.evidence_search.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = "sk-test"
            result = await service._fetch_and_synthesize(
                claim="AI는 위험한가",
                topic="AI 안전성",
                results=ddg_results,
                exclude_urls=None,
            )

        # snippet이 존재하므로 폴백 반환
        assert result is not None
        assert "snippet text" in result.text

    @pytest.mark.asyncio
    async def test_returns_none_when_synthesis_irrelevant_and_no_snippets(self):
        """LLM 합성이 '관련 근거 없음'이고 snippet도 없으면 None을 반환한다."""
        service = EvidenceSearchService()

        ddg_results = [_make_ddg_result(url="https://unrelated.com/page", body="")]

        with (
            patch.object(service, "_fetch_url", new=AsyncMock(return_value="무관한 본문 내용")),
            patch.object(service, "_synthesize", new=AsyncMock(return_value="관련 근거 없음")),
            patch("app.services.debate.evidence_search.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = "sk-test"
            result = await service._fetch_and_synthesize(
                claim="AI는 위험한가",
                topic="AI 안전성",
                results=ddg_results,
                exclude_urls=None,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_raw_content_not_in_format_output(self):
        """format() 메서드는 raw_content를 노출하지 않아야 한다."""
        service = EvidenceSearchService()

        ddg_results = [_make_ddg_result(url="https://example.com/ai", body="DDG snippet")]

        with (
            patch.object(service, "_fetch_url", new=AsyncMock(return_value="실제 페이지 본문")),
            patch.object(service, "_synthesize", new=AsyncMock(return_value="합성된 요약")),
            patch("app.services.debate.evidence_search.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = "sk-test"
            result = await service._fetch_and_synthesize(
                claim="AI는 위험한가",
                topic="AI 안전성",
                results=ddg_results,
                exclude_urls=None,
            )

        assert result is not None
        formatted = result.format()
        assert "실제 페이지 본문" not in formatted
        assert "합성된 요약" in formatted
