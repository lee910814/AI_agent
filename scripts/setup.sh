#!/usr/bin/env bash
# =============================================================
# 원커맨드 개발 환경 초기화 + 서버 기동 스크립트
#
# Usage:
#   bash scripts/setup.sh              # 셋업 + 서버 기동 (재실행 시 빠르게 재기동)
#   bash scripts/setup.sh --stop       # 백엔드/프론트엔드 서버 종료
#   bash scripts/setup.sh --update-deps # 의존성 재설치 후 기동
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOGS_DIR="$PROJECT_ROOT/logs"
PIDS_FILE="$PROJECT_ROOT/.dev-pids"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

UPDATE_DEPS=false
PYTHON_ARGS=""   # Windows py launcher용 (-3.12 등)

# ── 컬러 출력 ─────────────────────────────────────────────────
_green()  { printf '\033[32m[OK]\033[0m %s\n' "$*"; }
_yellow() { printf '\033[33m[WARN]\033[0m %s\n' "$*"; }
_red()    { printf '\033[31m[ERROR]\033[0m %s\n' "$*"; }
_info()   { printf '\033[36m[INFO]\033[0m %s\n' "$*"; }
_step()   { printf '\n\033[1m── %s\033[0m\n' "$*"; }

# ── OS 감지 (Python 경로는 _check_prerequisites에서 결정) ────
_detect_os() {
    if [[ "${OSTYPE:-}" == "msys" ]] || [[ "${OSTYPE:-}" == "cygwin" ]] || [[ -n "${WINDIR:-}" ]]; then
        OS_TYPE="windows"
        PYTHON_CMD="python"          # 초기값 — _find_python312에서 덮어씀
        VENV_PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"
        VENV_PIP="$BACKEND_DIR/.venv/Scripts/pip.exe"
    else
        OS_TYPE="unix"
        PYTHON_CMD="python3"         # 초기값 — _find_python312에서 덮어씀
        VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
        VENV_PIP="$BACKEND_DIR/.venv/bin/pip"
    fi
}

# ── Python 3.12+ 탐색 (venv 없을 때 호출) ────────────────────
_find_python312() {
    # Windows: Python Launcher (py -3.12) 우선 시도
    if [[ "${OS_TYPE:-}" == "windows" ]] && command -v py > /dev/null 2>&1; then
        if py -3.12 --version > /dev/null 2>&1; then
            local ver
            ver=$(py -3.12 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            _green "Python $ver (py -3.12)"
            PYTHON_CMD="py"
            PYTHON_ARGS="-3.12"
            return 0
        fi
    fi

    # 일반 후보 순서대로 탐색
    local candidates=("python3.12" "python3" "python")
    for cmd in "${candidates[@]}"; do
        command -v "$cmd" > /dev/null 2>&1 || continue
        local ver major minor
        ver=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            _green "Python $ver ($cmd)"
            PYTHON_CMD="$cmd"
            PYTHON_ARGS=""
            return 0
        fi
    done

    _red "Python 3.12 이상을 찾을 수 없습니다."
    _info "설치 확인: py -3.12 --version  (Windows Launcher)"
    _info "또는 직접 venv 생성: py -3.12 -m venv backend/.venv"
    exit 1
}

# ── 옵션 파싱 ────────────────────────────────────────────────
_parse_args() {
    for arg in "$@"; do
        case "$arg" in
            --stop)        _stop_servers; exit 0 ;;
            --update-deps) UPDATE_DEPS=true ;;
            --help|-h)     _print_help; exit 0 ;;
        esac
    done
}

_print_help() {
    echo "Usage: bash scripts/setup.sh [옵션]"
    echo ""
    echo "옵션:"
    echo "  (없음)          셋업 + 서버 기동 (재실행 시 재기동)"
    echo "  --stop          백엔드/프론트엔드 서버 종료"
    echo "  --update-deps   Python/Node 의존성 재설치 후 기동"
    echo "  --help          이 메시지 출력"
}

# ── 서버 종료 (--stop 또는 재기동 전 정리용) ─────────────────
_stop_servers() {
    [ -f "$PIDS_FILE" ] || { _yellow "실행 중인 서버 정보 없음 (.dev-pids 없음)"; return; }

    _step "기존 서버 프로세스 종료"
    while IFS='=' read -r name pid; do
        [ -z "${name:-}" ] && continue
        if kill -0 "$pid" 2>/dev/null; then
            # Windows: bash PID → Windows PID 변환 후 종료
            local win_pid
            win_pid=$(ps -p "$pid" -o pid,ppid 2>/dev/null | awk "NR>1 && \$1==$pid {print \$1}" | head -1)
            if [ -n "$win_pid" ]; then
                cmd //c "taskkill /F /T /PID $(ps -p "$pid" -o pid 2>/dev/null | tail -1 | tr -d ' ')" 2>/dev/null
            fi
            kill -9 "$pid" 2>/dev/null
            _green "$name 종료 (PID $pid)"
        else
            _info "$name (PID $pid) — 이미 종료됨"
        fi
    done < "$PIDS_FILE"
    # 남은 uvicorn/node 프로세스 정리
    cmd //c "taskkill /F /IM python.exe" 2>/dev/null || true
    rm -f "$PIDS_FILE"
}

# ── 사전 요구사항 확인 ───────────────────────────────────────
_check_prerequisites() {
    _step "사전 요구사항 확인"

    # Python — venv가 이미 있으면 그 Python을 그대로 사용 (시스템 버전 무관)
    if [ -f "$VENV_PYTHON" ]; then
        local py_ver
        py_ver=$("$VENV_PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "?")
        _green "Python $py_ver (backend/.venv 사용)"
    else
        # venv가 없으면 생성할 Python 3.12+ 탐색
        _find_python312
    fi

    # Node.js
    SKIP_FRONTEND=false
    if ! command -v node > /dev/null 2>&1; then
        _yellow "Node.js 없음 — 프론트엔드를 건너뜁니다. https://nodejs.org/"
        SKIP_FRONTEND=true
    else
        _green "Node.js $(node --version)"
    fi

    # Docker (DB+Redis 기동에 필수)
    if ! command -v docker > /dev/null 2>&1; then
        _red "Docker 없음. https://www.docker.com/products/docker-desktop/"
        exit 1
    fi
    if ! docker info > /dev/null 2>&1; then
        _red "Docker가 실행 중이지 않습니다. Docker Desktop을 먼저 실행하세요."
        exit 1
    fi
    _green "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
}

# ── Python 가상환경 + 의존성 ─────────────────────────────────
_setup_python() {
    _step "Python 가상환경 (backend/.venv)"

    if [ -f "$VENV_PYTHON" ] && [ "$UPDATE_DEPS" = false ]; then
        _green "이미 존재 — 건너뜁니다. (재설치: --update-deps)"
        return
    fi

    [ -f "$VENV_PYTHON" ] || {
        _info "가상환경 생성 중..."
        # PYTHON_ARGS: Windows py launcher용 (-3.12 등)
        # shellcheck disable=SC2086
        $PYTHON_CMD ${PYTHON_ARGS} -m venv "$BACKEND_DIR/.venv"
    }

    _info "pip install 실행 중... (처음엔 수 분 걸릴 수 있습니다)"
    "$VENV_PIP" install --quiet --upgrade pip
    "$VENV_PIP" install --quiet -r "$BACKEND_DIR/requirements.txt"
    [ -f "$BACKEND_DIR/requirements-dev.txt" ] && \
        "$VENV_PIP" install --quiet -r "$BACKEND_DIR/requirements-dev.txt"
    _green "Python 의존성 설치 완료"
}

# ── 프론트엔드 의존성 ────────────────────────────────────────
_setup_frontend() {
    _step "프론트엔드 의존성 (npm install)"

    [ "${SKIP_FRONTEND:-false}" = true ] && { _yellow "Node.js 없음 — 건너뜁니다."; return; }
    [ -f "$FRONTEND_DIR/package.json" ] || { _yellow "package.json 없음 — 건너뜁니다."; return; }

    if [ -d "$FRONTEND_DIR/node_modules" ] && [ "$UPDATE_DEPS" = false ]; then
        _green "이미 존재 — 건너뜁니다. (재설치: --update-deps)"
        return
    fi

    _info "npm install 실행 중..."
    (cd "$FRONTEND_DIR" && npm install --silent)
    _green "프론트엔드 의존성 설치 완료"
}

# ── 환경변수 파일 ────────────────────────────────────────────
_setup_env_files() {
    _step "환경변수 파일 준비"

    local env_dev="$BACKEND_DIR/.env"
    if [ ! -f "$env_dev" ]; then
        local env_example="$PROJECT_ROOT/.env.example"
        [ -f "$env_example" ] && cp "$env_example" "$env_dev" && \
            _green "backend/.env 생성 완료 (.env.example에서 복사)" || \
            _yellow ".env.example 없음 — backend/.env를 수동으로 생성하세요."
        _yellow "⚠  backend/.env의 SECRET_KEY, DB 비밀번호 등을 반드시 변경하세요."
    else
        _green "backend/.env 이미 존재"
    fi

    local env_test="$BACKEND_DIR/.env.test"
    if [ ! -f "$env_test" ]; then
        local env_test_example="$BACKEND_DIR/.env.test.example"
        [ -f "$env_test_example" ] && cp "$env_test_example" "$env_test" && \
            _green "backend/.env.test 생성 완료 (.env.test.example에서 복사)" || \
            _yellow ".env.test.example 없음"
    else
        _green "backend/.env.test 이미 존재"
    fi
}

# ── Docker 인프라 (DB + Redis만 기동) ──────────────────────────
_start_infra() {
    _step "Docker 인프라 기동 (DB + Redis)"

    # --env-file로 직접 전달 → source 없이 쉘 환경 오염 방지
    # (source 시 bash가 CORS_ORIGINS=["..."] 내부 따옴표를 제거해 pydantic JSON 파싱 실패)
    local env_file_arg=""
    [ -f "$BACKEND_DIR/.env" ] && env_file_arg="--env-file $BACKEND_DIR/.env"

    # shellcheck disable=SC2086
    docker compose -f "$COMPOSE_FILE" $env_file_arg up -d db redis

    _wait_healthy "chatbot-db"
    _wait_healthy "chatbot-redis"
}

_wait_healthy() {
    local container="$1"
    local max_wait=60
    local elapsed=0
    printf '%s %s 헬스체크 대기...' "$(printf '\033[36m[INFO]\033[0m')" "$container"
    while [ $elapsed -lt $max_wait ]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
        if [ "$status" = "healthy" ]; then
            printf ' OK\n'
            return 0
        fi
        printf '.'
        sleep 2
        elapsed=$((elapsed + 2))
    done
    printf ' TIMEOUT\n'
    _red "$container가 ${max_wait}초 내에 healthy 상태가 되지 않았습니다."
    exit 1
}

# ── Alembic 마이그레이션 ────────────────────────────────────
_run_migrations() {
    _step "Alembic 마이그레이션"
    cd "$BACKEND_DIR"
    "$VENV_PYTHON" -m alembic upgrade head
    cd "$PROJECT_ROOT"
    _green "마이그레이션 완료"
}

# ── Admin 계정 생성 ──────────────────────────────────────────
_create_admin() {
    _step "Admin 계정 생성 (admin / admin123)"
    cd "$BACKEND_DIR"
    local exit_code=0
    PYTHONPATH="$BACKEND_DIR" "$VENV_PYTHON" ../scripts/create_test_admin.py --env-file .env || exit_code=$?
    cd "$PROJECT_ROOT"
    if [ $exit_code -ne 0 ]; then
        _yellow "Admin 계정 생성 실패 — 로그를 확인하세요."
    fi
}

# ── 시드 데이터 ─────────────────────────────────────────────
_run_seed() {
    _step "시드 데이터 삽입"
    cd "$BACKEND_DIR"
    local exit_code=0
    "$VENV_PYTHON" ../scripts/seed_data.py --env-file .env || exit_code=$?
    cd "$PROJECT_ROOT"
    if [ $exit_code -ne 0 ]; then
        _yellow "시드 데이터 일부 실패 (기존 데이터 충돌 가능). 서버 기동은 계속합니다."
        _yellow "완전 초기화가 필요하면: docker compose down -v 후 재실행"
    fi
}

# ── 백엔드 + 프론트엔드 기동 (백그라운드) ───────────────────
_start_servers() {
    _step "개발 서버 기동"
    mkdir -p "$LOGS_DIR"

    # 기존 프로세스 정리
    _stop_servers 2>/dev/null || true
    rm -f "$PIDS_FILE"

    # 백엔드 — uvicorn --reload
    _info "백엔드 기동 중... (logs/backend.log)"
    cd "$BACKEND_DIR"
    "$VENV_PYTHON" -m uvicorn app.main:app \
        --reload --host 0.0.0.0 --port 8000 \
        >> "$LOGS_DIR/backend.log" 2>&1 &
    echo "backend=$!" >> "$PIDS_FILE"
    cd "$PROJECT_ROOT"

    # 프론트엔드 — npm run dev
    if [ "${SKIP_FRONTEND:-false}" = false ] && [ -f "$FRONTEND_DIR/package.json" ]; then
        _info "프론트엔드 기동 중... (logs/frontend.log)"
        cd "$FRONTEND_DIR"
        npm run dev >> "$LOGS_DIR/frontend.log" 2>&1 &
        echo "frontend=$!" >> "$PIDS_FILE"
        cd "$PROJECT_ROOT"
    fi

    # 5초 대기 후 생존 여부 확인
    _info "서버 초기화 대기 중... (5초)"
    sleep 5

    local all_ok=true
    while IFS='=' read -r name pid; do
        [ -z "${name:-}" ] && continue
        if kill -0 "$pid" 2>/dev/null; then
            _green "$name 실행 중 (PID $pid)"
        else
            _red "$name 시작 실패 — 로그 확인: tail -f logs/${name}.log"
            all_ok=false
        fi
    done < "$PIDS_FILE"

    if [ "$all_ok" = false ]; then
        exit 1
    fi
}

# ── 완료 메시지 ──────────────────────────────────────────────
_print_done() {
    echo ""
    printf '╔══════════════════════════════════════════════════════╗\n'
    printf '║               개발 환경 준비 완료!                      ║\n'
    printf '╚══════════════════════════════════════════════════════╝\n'
    echo ""
    printf '  \033[1m접근 주소\033[0m\n'
    printf '    Frontend:    http://localhost:3000\n'
    printf '    Backend API: http://localhost:8000\n'
    printf '    API 문서:    http://localhost:8000/docs\n'
    echo ""
    printf '  \033[1m테스트 계정\033[0m\n'
    printf '    admin     / admin123   (superadmin)\n'
    printf '    moderator / Mod123!    (admin)\n'
    printf '    user1     / User123!   (user)\n'
    echo ""
    printf '  \033[1m로그 확인\033[0m\n'
    printf '    tail -f logs/backend.log\n'
    printf '    tail -f logs/frontend.log\n'
    echo ""
    printf '  \033[1m서버 종료\033[0m\n'
    printf '    bash scripts/setup.sh --stop\n'
    echo ""
    printf '  \033[1m테스트 실행\033[0m\n'
    printf '    bash scripts/run-tests.sh --backend-only\n'
    echo ""
}

# ── 메인 ─────────────────────────────────────────────────────
main() {
    printf '\n\033[1m=== 개발 환경 초기화 ===\033[0m\n'

    _detect_os
    _parse_args "$@"

    _check_prerequisites   # Python / Node.js / Docker 확인
    _setup_python          # venv 생성 + pip install (이미 있으면 스킵)
    _setup_frontend        # npm install (이미 있으면 스킵)
    _setup_env_files       # .env / .env.test 파일 생성 (이미 있으면 스킵)
    _start_infra           # docker compose up -d db redis + 헬스체크
    _run_migrations        # alembic upgrade head
    _create_admin          # admin / admin123 superadmin 계정 (idempotent)
    _run_seed              # seed_data.py (idempotent)
    _start_servers         # uvicorn --reload + npm run dev (백그라운드)
    _print_done
}

main "$@"
