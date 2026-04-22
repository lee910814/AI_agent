"""claim → LLM 키워드 추출 → DuckDuckGo 검색 → URL 본문 fetch → LLM 합성 → 출처 포함 근거 반환.

Tool Use 흐름:
  1. LLM이 topic + claim 기반으로 검색 키워드 추출
  2. DuckDuckGo로 후보 URL 수집
  3. 상위 URL에 실제 HTTP fetch → HTML 본문 파싱
  4. 실제 본문 텍스트로 LLM 합성 → 근거 생성
  5. fetch 실패한 URL은 DDG snippet으로 fallback
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from app.core.config import settings

logger = logging.getLogger(__name__)

# fetch 시 사용할 User-Agent — 주요 사이트의 봇 차단 우회
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# URL 본문을 합성에 사용할 최대 글자 수
_FETCH_BODY_MAX = 3000

# fetch 대상 URL 최대 수 — 레이턴시 예산 고려
_MAX_FETCH_URLS = 2

KEYWORD_PROMPT = """다음 토론 주제와 주장에서 웹 검색 키워드를 추출하세요.
- 토론 주제의 핵심 고유명사(브랜드명, 제품명, 인물명 등)를 반드시 포함하세요
- 영어 키워드 2~3개 + 한국어 키워드 1~2개를 함께 추출
- JSON 배열만 출력, 설명 없이

토론 주제: {topic}
주장: {claim}

출력 예시: ["새콤달콤 Korean candy snack", "Saekcomdalcom vs Maychew", "새콤달콤 마이쮸 비교"]"""

SYNTHESIS_PROMPT = """당신은 토론 근거 검증자입니다. 아래 주장에 대해 실제 웹 페이지 본문에서 찾은 사실만을 사용해 한국어 2~3문장의 근거를 작성하세요.

엄격한 규칙:
- 아래 [웹 페이지 본문]에 실제로 존재하는 사실·수치·사례만 인용하세요
- 본문에 없는 내용을 추론하거나 만들어내지 마세요
- 수치나 통계는 반드시 어느 출처에서 왔는지 "(출처 N번)" 형식으로 표시하세요
- 본문 전체가 주장과 무관하면 반드시 "관련 근거 없음"만 반환하세요
- 부분적으로 관련 있으면, 관련 있는 내용만 인용하고 나머지는 무시하세요

토론 주제: {topic}
주장: {claim}

[웹 페이지 본문]
{page_contents}

근거 (한국어, 2~3문장 또는 "관련 근거 없음"):"""


@dataclass
class EvidenceResult:
    text: str
    sources: list[str] = field(default_factory=list)
    raw_content: str = ""  # fetch한 실제 페이지 본문 — 오케스트레이터 교차검증용 (에이전트에겐 미노출)

    def format(self) -> str:
        """evidence 필드에 삽입할 텍스트를 반환한다."""
        sources_line = " | ".join(self.sources) if self.sources else "출처 없음"
        return f"{self.text}\n\n[출처: {sources_line}]"


class EvidenceSearchService:
    """claim에 대한 웹 근거를 검색·fetch·합성해 반환한다.

    1. LLM(gpt-4o-mini)으로 topic + claim → 검색 키워드 추출
    2. 키워드별 DuckDuckGo 검색 (병렬)
    3. 상위 URL을 httpx로 실제 fetch → BeautifulSoup 본문 파싱
    4. 실제 본문 텍스트를 LLM으로 합성 → 근거 생성
    5. fetch 실패 URL은 DDG snippet으로 대체
    """

    def __init__(self) -> None:
        self._client: "InferenceClient | None" = None
        self._owns_client = False

    def _get_client(self) -> "InferenceClient":
        if self._client is None:
            from app.services.llm.inference_client import InferenceClient

            self._client = InferenceClient()
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    async def search(
        self,
        claim: str,
        topic: str = "",
        exclude_urls: set[str] | None = None,
    ) -> "EvidenceResult | None":
        """claim에 대한 웹 근거를 검색·fetch·합성한다. 실패 시 None을 반환한다."""
        if not settings.debate_evidence_search_enabled:
            return None

        try:
            async with asyncio.timeout(settings.debate_evidence_search_timeout):
                keywords = await self._extract_keywords(claim, topic)
                if not keywords:
                    return None

                results = await self._search_all(keywords)
                if not results:
                    return None

                return await self._fetch_and_synthesize(claim, topic, results, exclude_urls)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Evidence search timed out for claim: %.60s...", claim)
            return None
        except Exception as exc:
            logger.warning("Evidence search failed: %s", exc)
            return None

    async def search_by_query(
        self,
        query: str,
        claim: str | None = None,
        topic: str = "",
        exclude_urls: set[str] | None = None,
    ) -> "EvidenceResult | None":
        """tool_call.query로 직접 DuckDuckGo 검색 후 URL fetch·합성해 반환한다."""
        if not settings.debate_evidence_search_enabled:
            return None
        # 빈 query면 claim 또는 topic으로 대체하여 최소 검색 시도
        if not query or not query.strip():
            query = claim or topic
        if not query or not query.strip():
            return None

        try:
            async with asyncio.timeout(settings.debate_evidence_search_timeout):
                results = await self._search_all([query.strip()])
                if not results:
                    return None
                return await self._fetch_and_synthesize(
                    claim or query, topic, results, exclude_urls
                )
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Evidence search_by_query timed out for query: %.60s...", query)
            return None
        except Exception as exc:
            logger.warning("Evidence search_by_query failed: %s", exc)
            return None

    async def _extract_keywords(self, claim: str, topic: str) -> list[str]:
        """topic + claim으로 검색 키워드를 추출한다."""
        api_key = settings.openai_api_key
        if not api_key:
            return []

        claim = claim.strip()
        if not claim or len(claim) > 2000:
            return []

        try:
            client = self._get_client()
            result = await asyncio.wait_for(
                client.generate_byok(
                    provider="openai",
                    model_id=settings.debate_evidence_keyword_model,
                    api_key=api_key,
                    messages=[
                        {
                            "role": "user",
                            "content": KEYWORD_PROMPT.format(
                                topic=topic or "일반 토론",
                                claim=claim,
                            ),
                        }
                    ],
                    max_tokens=100,
                    temperature=0,
                ),
                timeout=8.0,
            )
            content = result.get("content", "").strip()
            if not content:
                return []
            parsed = json.loads(content)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            logger.warning("Keyword extraction failed", exc_info=True)
            return []

    async def _fetch_url(self, url: str) -> str | None:
        """URL에 HTTP 접속해 HTML 본문 텍스트를 추출한다.

        Wikipedia, 뉴스, 블로그 등 일반 웹 페이지를 대상으로 함.
        paywall·봇 차단·타임아웃 시 None 반환 → DDG snippet으로 fallback.
        """
        # 미디어/파일 URL 스킵
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|mp4|zip|exe)(\?|$)", url, re.IGNORECASE):
            return None

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": _UA},
                follow_redirects=True,
                timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0),
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type:
                    return None

                soup = BeautifulSoup(response.text, "html.parser")
                # 불필요한 태그 제거
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                    tag.decompose()

                # 본문 텍스트 추출 — <article>, <main>, <p> 우선순위
                body = ""
                for selector in ("article", "main", '[role="main"]'):
                    el = soup.select_one(selector)
                    if el:
                        body = el.get_text(separator=" ", strip=True)
                        break
                if not body:
                    body = soup.get_text(separator=" ", strip=True)

                # 연속 공백/줄바꿈 정리
                body = re.sub(r"\s{2,}", " ", body).strip()
                return body[:_FETCH_BODY_MAX] if body else None

        except Exception as exc:
            logger.warning("URL fetch failed (%s): %s", url, exc)
            return None

    async def _fetch_and_synthesize(
        self,
        claim: str,
        topic: str,
        results: list[dict],
        exclude_urls: set[str] | None = None,
    ) -> "EvidenceResult | None":
        """DDG 결과에서 URL을 fetch해 본문 기반으로 근거를 합성한다.

        fetch 성공 URL은 실제 본문을, 실패 URL은 DDG snippet을 사용.
        모든 URL fetch 실패 시 snippet 기반 합성으로 전체 fallback.
        """
        seen: set[str] = set(exclude_urls) if exclude_urls else set()
        candidates: list[dict] = []
        for r in results:
            url = r.get("href", "")
            if not url or url in seen:
                continue
            seen.add(url)
            candidates.append(r)
            if len(candidates) >= 5:
                break

        if not candidates:
            return None

        # 상위 _MAX_FETCH_URLS개 URL 병렬 fetch
        fetch_targets = candidates[:_MAX_FETCH_URLS]
        fetch_results = await asyncio.gather(
            *[self._fetch_url(r["href"]) for r in fetch_targets],
            return_exceptions=True,
        )

        # 페이지 콘텐츠 조합: fetch 성공 → 본문, 실패 → snippet fallback
        page_contents: list[str] = []
        sources: list[str] = []

        for i, r in enumerate(candidates):
            url = r["href"]
            title = r.get("title", url)
            body_snippet = r.get("body", "")[:400]

            if i < _MAX_FETCH_URLS:
                fetched = fetch_results[i]
                if isinstance(fetched, str) and fetched:
                    page_contents.append(f"[출처 {i+1}] {title} ({url})\n{fetched}")
                    sources.append(url)
                    continue
                # fetch 실패 — snippet fallback
                logger.debug("URL fetch failed, using snippet: %s", url)

            if body_snippet:
                page_contents.append(f"[출처 {len(sources)+1}] {title} ({url})\n{body_snippet}")
                sources.append(url)

        if not page_contents:
            return None

        joined_content = "\n\n".join(page_contents)
        api_key = settings.openai_api_key
        if not api_key:
            # LLM 합성 불가 — 첫 번째 출처 snippet만 반환
            first = page_contents[0] if page_contents else ""
            return EvidenceResult(text=first[:500], sources=sources[:1], raw_content=joined_content) if first else None

        # snippet 폴백용 — 모든 candidate의 snippet을 합쳐서 최대 500자
        all_snippets = " / ".join(
            r.get("body", "").strip() for r in candidates if r.get("body", "").strip()
        )[:500]

        try:
            synthesized = await self._synthesize(claim, topic, joined_content, api_key)
            if synthesized == "관련 근거 없음":
                # LLM이 관련 없다고 판단해도 snippet 원문이 있으면 폴백 반환
                if all_snippets:
                    logger.warning("Synthesis judged irrelevant, falling back to snippets")
                    return EvidenceResult(text=all_snippets, sources=sources, raw_content=joined_content)
                return None
            return EvidenceResult(text=synthesized, sources=sources, raw_content=joined_content)
        except Exception as exc:
            logger.warning("Evidence synthesis failed: %s", exc)
            # 합성 실패 — 다중 snippet 폴백
            return (
                EvidenceResult(text=all_snippets, sources=sources, raw_content=joined_content)
                if all_snippets
                else None
            )

    async def _synthesize(self, claim: str, topic: str, page_contents: str, api_key: str) -> str:
        """실제 fetch한 웹 페이지 본문을 기반으로 근거를 합성한다."""
        client = self._get_client()
        prompt = SYNTHESIS_PROMPT.format(
            topic=topic or "일반 토론",
            claim=claim[:800],
            page_contents=page_contents[:4000],
        )
        result = await asyncio.wait_for(
            client.generate_byok(
                provider="openai",
                model_id=settings.debate_evidence_synthesis_model,
                api_key=api_key,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.debate_evidence_synthesis_max_tokens,
                temperature=0.2,
            ),
            timeout=8.0,
        )
        synthesized = result.get("content", "").strip()
        if not synthesized:
            raise ValueError("LLM returned empty synthesis")
        return synthesized

    async def _search_all(self, keywords: list[str]) -> list[dict]:
        """키워드별 DuckDuckGo 검색을 병렬 실행한다."""
        loop = asyncio.get_running_loop()
        capped = [kw.strip() for kw in keywords if kw.strip()][:10]

        async def _run_with_timeout(kw: str) -> list[dict]:
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, self._ddg_search, kw),
                    timeout=8.0,
                )
            except TimeoutError:
                logger.warning("DDG search timed out: %s", kw)
                return []
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("DDG search error (kw=%s): %s", kw, exc)
                return []

        nested = await asyncio.gather(*[_run_with_timeout(kw) for kw in capped])

        seen_urls: set[str] = set()
        flat: list[dict] = []
        for result in nested:
            for item in result:
                url = item.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    flat.append(item)
        return flat

    def _ddg_search(self, query: str) -> list[dict]:
        """DuckDuckGo 텍스트 검색 (동기). run_in_executor로 호출된다."""
        if not query.strip():
            return []
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=settings.debate_evidence_search_max_results))
        except Exception as exc:
            logger.warning("DDG '%s' failed: %s", query, exc)
            return []
