#!/usr/bin/env bash
# 테스트 인프라 자동 관리 + 테스트 실행 스크립트
# Usage: bash scripts/run-tests.sh [--backend-only|--frontend-only|--e2e|--all] [--no-infra] [--keep-infra]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.test.yml"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
ENV_TEST="$BACKEND_DIR/.env.test"

PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"
if [ ! -f "$PYTHON" ]; then
    PYTHON="$BACKEND_DIR/.venv/bin/python"
fi

# 옵션 파싱
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_E2E=false
START_INFRA=true
KEEP_INFRA=false

for arg in "$@"; do
    case "$arg" in
        --backend-only)  RUN_BACKEND=true;  RUN_FRONTEND=false; RUN_E2E=false ;;
        --frontend-only) RUN_BACKEND=false; RUN_FRONTEND=true;  RUN_E2E=false ;;
        --e2e)           RUN_E2E=true ;;
        --all)           RUN_BACKEND=true;  RUN_FRONTEND=true;  RUN_E2E=true ;;
        --no-infra)      START_INFRA=false ;;
        --keep-infra)    KEEP_INFRA=true ;;
        --help|-h)
            echo "Usage: bash scripts/run-tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  --backend-only    Run backend tests only (pytest)"
            echo "  --frontend-only   Run frontend tests only (vitest)"
            echo "  --e2e             Include E2E tests (Playwright)"
            echo "  --all             Run backend + frontend + E2E"
            echo "  --no-infra        Skip starting test infrastructure"
            echo "  --keep-infra      Keep test infrastructure running after tests"
            exit 0
            ;;
    esac
done

PASS=0
FAIL=0

_check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "[ERROR] Docker is not running."
        exit 1
    fi
}

_wait_healthy() {
    local container="$1"
    local max_wait=60
    local elapsed=0
    echo -n "[INFO] Waiting for $container..."
    while [ $elapsed -lt $max_wait ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
        if [ "$status" = "healthy" ]; then
            echo " OK"
            return 0
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done
    echo " TIMEOUT"
    echo "[ERROR] $container did not become healthy in ${max_wait}s"
    exit 1
}

_start_infra() {
    _check_docker
    echo "[INFO] Starting test infrastructure..."
    docker compose -f "$COMPOSE_FILE" up -d
    _wait_healthy "chatbot-test-db"
    _wait_healthy "chatbot-test-redis"
    echo "[INFO] Test infrastructure ready."
}

_stop_infra() {
    echo "[INFO] Stopping test infrastructure..."
    docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
}

_run_backend_tests() {
    echo ""
    echo "=== Backend Tests (pytest) ==="
    cd "$BACKEND_DIR"

    local exit_code=0
    DOTENV_PATH="$ENV_TEST" \
    "$PYTHON" -m pytest tests/unit/ -v --tb=short \
        --no-header -q 2>&1 || exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "[PASS] Backend tests passed."
        PASS=$((PASS + 1))
    else
        echo "[FAIL] Backend tests failed (exit $exit_code)."
        FAIL=$((FAIL + 1))
    fi

    cd "$PROJECT_ROOT"
}

_run_frontend_tests() {
    echo ""
    echo "=== Frontend Tests (vitest) ==="
    cd "$FRONTEND_DIR"

    local exit_code=0
    npm test -- --run 2>&1 || exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "[PASS] Frontend tests passed."
        PASS=$((PASS + 1))
    else
        echo "[FAIL] Frontend tests failed (exit $exit_code)."
        FAIL=$((FAIL + 1))
    fi

    cd "$PROJECT_ROOT"
}

_run_e2e_tests() {
    echo ""
    echo "=== E2E Tests (Playwright) ==="
    cd "$FRONTEND_DIR"

    local exit_code=0
    if command -v npx > /dev/null 2>&1 && [ -f "playwright.config.ts" ]; then
        npx playwright test 2>&1 || exit_code=$?
        if [ $exit_code -eq 0 ]; then
            echo "[PASS] E2E tests passed."
            PASS=$((PASS + 1))
        else
            echo "[FAIL] E2E tests failed (exit $exit_code)."
            FAIL=$((FAIL + 1))
        fi
    else
        echo "[SKIP] Playwright config not found — skipping E2E."
    fi

    cd "$PROJECT_ROOT"
}

_print_summary() {
    echo ""
    echo "=============================="
    echo "  Test Results Summary"
    echo "=============================="
    echo "  Passed:  $PASS"
    echo "  Failed:  $FAIL"
    echo "=============================="
    if [ $FAIL -gt 0 ]; then
        echo "[FAIL] Some tests failed."
        return 1
    else
        echo "[PASS] All tests passed."
        return 0
    fi
}

# ── 메인 실행 ──
echo "=== run-tests.sh ==="
echo "Backend:  $RUN_BACKEND | Frontend: $RUN_FRONTEND | E2E: $RUN_E2E"
echo "Infra:    start=$START_INFRA | keep=$KEEP_INFRA"

# 인프라 시작
if [ "$START_INFRA" = true ]; then
    _start_infra
fi

# 테스트 실행 (인프라 오류 시에도 정리)
set +e

if [ "$RUN_BACKEND" = true ]; then
    _run_backend_tests
fi

if [ "$RUN_FRONTEND" = true ]; then
    _run_frontend_tests
fi

if [ "$RUN_E2E" = true ]; then
    _run_e2e_tests
fi

set -e

# 인프라 정리
if [ "$START_INFRA" = true ] && [ "$KEEP_INFRA" = false ]; then
    _stop_infra
fi

_print_summary
