#!/bin/bash
# ==============================================================
# EC2 배포 스크립트 (Ubuntu 22.04 / Amazon Linux 2023)
#
# 사용법: bash deploy.sh [mode] [env]
#   mode: fresh (기본) | update
#   env:  prod (기본) | dev
#
# 예시:
#   bash deploy.sh                   # prod 최초 배포
#   bash deploy.sh update            # prod 코드 업데이트
#   bash deploy.sh fresh dev         # dev 최초 배포
#   bash deploy.sh update dev        # dev 코드 업데이트
# ==============================================================
set -e

MODE="${1:-fresh}"
ENV="${2:-prod}"

# 환경별 설정
if [ "$ENV" = "staging" ]; then
  REPO_DIR="/opt/chatbot"
  COMPOSE_FILE="docker-compose.staging.yml"
  ENV_FILE=".env.staging"
  PROJECT_NAME="chatbot-staging"
elif [ "$ENV" = "dev" ]; then
  REPO_DIR="/opt/chatbot"
  COMPOSE_FILE="docker-compose.dev.yml"
  ENV_FILE=".env.dev"
  PROJECT_NAME="chatbot-dev"
else
  REPO_DIR="/opt/chatbot"
  COMPOSE_FILE="docker-compose.prod.yml"
  ENV_FILE=".env"
  PROJECT_NAME="chatbot"
fi

COMPOSE_CMD="docker compose -p $PROJECT_NAME -f $COMPOSE_FILE --env-file $ENV_FILE"

# 스크립트 내 모든 docker compose 호출이 반드시 -p $PROJECT_NAME을 포함하는지 보장하기 위해
# raw `docker compose` 직접 호출을 금지하는 alias — 실수로 프로젝트명 없이 호출 시 즉시 오류
docker() {
  if [ "$1" = "compose" ] && [ "$2" != "-p" ] && [ "$2" != "--project-name" ]; then
    err "docker compose 직접 호출 금지. 반드시 \$COMPOSE_CMD 변수를 사용하세요. (프로젝트 격리 보장)"
  fi
  command docker "$@"
}

# ────────────────────────────────────────────────────────────
# 함수 정의
# ────────────────────────────────────────────────────────────
log() { echo -e "\033[1;32m[DEPLOY:$ENV]\033[0m $1"; }
err() { echo -e "\033[1;31m[ERROR]\033[0m $1" >&2; exit 1; }

require_root() {
  [ "$EUID" -eq 0 ] || err "root 권한으로 실행하세요: sudo bash deploy.sh"
}

install_docker() {
  if command -v docker &>/dev/null; then
    log "Docker 이미 설치됨: $(docker --version)"
    return
  fi

  log "Docker 설치 중..."
  if command -v apt-get &>/dev/null; then
    apt-get update -q
    apt-get install -y ca-certificates curl gnupg lsb-release
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  elif command -v yum &>/dev/null; then
    yum update -y -q
    yum install -y docker
    systemctl enable docker
    systemctl start docker
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  else
    err "지원하지 않는 OS입니다."
  fi

  systemctl enable docker
  systemctl start docker
  log "Docker 설치 완료: $(docker --version)"
}

check_env() {
  [ -f "$REPO_DIR/$ENV_FILE" ] || err "$ENV_FILE 파일이 없습니다. .env.development.example 또는 .env.production.example을 복사하여 설정하세요."

  local required_vars=("SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "CORS_ORIGINS")
  for var in "${required_vars[@]}"; do
    local val
    val=$(grep -E "^${var}=" "$REPO_DIR/$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
    [ -n "$val" ] || err "$ENV_FILE에 ${var}가 설정되지 않았습니다."
    [[ "$val" == "CHANGE_ME"* ]] && err "$ENV_FILE의 ${var}를 실제 값으로 변경하세요."
  done
  log "$ENV_FILE 검증 통과"
}

run_migrations() {
  log "Alembic 마이그레이션 실행 중..."
  $COMPOSE_CMD run --rm backend \
    sh -c "PYTHONPATH=/app alembic upgrade heads"
  log "마이그레이션 완료"
}

verify_service_running() {
  local service="$1"
  local max_wait="${2:-30}"
  local elapsed=0

  log "$service 시작 확인 중 (최대 ${max_wait}초)..."
  while [ "$elapsed" -lt "$max_wait" ]; do
    local state
    state=$(docker inspect --format '{{.State.Status}}' "${PROJECT_NAME}-${service}" 2>/dev/null || echo "missing")
    if [ "$state" = "running" ]; then
      log "$service 정상 기동 확인"
      return 0
    fi
    if [ "$state" = "exited" ] || [ "$state" = "dead" ]; then
      err "$service 컨테이너가 종료됨 (state=$state). 로그 확인: docker logs ${PROJECT_NAME}-${service}"
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  err "$service 시작 타임아웃 (${max_wait}초 초과). 수동 확인 필요."
}

cleanup_containers() {
  # 1) 종료/생성만 된 컨테이너 제거 (created 상태도 포함 — orphan 충돌 방지)
  local stopped
  stopped=$(docker ps -aq --filter "status=exited" --filter "status=dead" --filter "status=created" 2>/dev/null)
  [ -n "$stopped" ] && echo "$stopped" | xargs docker rm -f 2>/dev/null || true

  # 2) 실행 중인 docker compose run 잔재(-run- 패턴) 제거
  #    `docker compose run`이 --rm 없이 실행되면 *-run-숫자 이름의 컨테이너가 남음
  local run_containers
  run_containers=$(docker ps -a --format "{{.ID}} {{.Names}}" 2>/dev/null \
    | awk '/-run-/{print $1}')
  [ -n "$run_containers" ] && echo "$run_containers" | xargs docker rm -f 2>/dev/null || true

  log "컨테이너 정리 완료"
}

create_superadmin() {
  log "슈퍼어드민 계정 확인..."
  $COMPOSE_CMD run --rm backend python3 -c "
import asyncio, os, sys
sys.path.insert(0, '/app')
from app.core.database import AsyncSessionLocal
from app.core.auth import get_password_hash
from app.models.user import User
from sqlalchemy import select
from datetime import datetime, timezone

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == 'superadmin'))
        if result.scalar_one_or_none():
            print('슈퍼어드민 이미 존재 — 건너뜀')
            return
        import uuid
        admin = User(
            id=uuid.uuid4(),
            login_id='admin',
            nickname='admin',
            password_hash=get_password_hash(os.environ.get('ADMIN_INIT_PASSWORD', 'ChangeMe123!')),
            role='superadmin',
            age_group='adult_verified',
            adult_verified_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
        print('슈퍼어드민 생성: login_id=admin')

asyncio.run(main())
" || true
}

# ────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────
cd "$REPO_DIR" || err "$REPO_DIR 디렉토리가 없습니다."

if [ "$MODE" = "update" ]; then
  # ── 코드 업데이트 배포 ──
  log "=== 업데이트 배포 시작 (환경: $ENV) ==="
  check_env
  cleanup_containers  # 빌드 전 좀비 컨테이너 선제 정리

  # git diff로 변경된 서비스 감지 — 변경이 없는 서비스는 빌드 스킵
  CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "backend/")
  BUILD_TARGETS=""
  UP_TARGETS=""
  if echo "$CHANGED" | grep -q "^backend/"; then
    BUILD_TARGETS="$BUILD_TARGETS backend"
    UP_TARGETS="$UP_TARGETS backend"
  fi
  if echo "$CHANGED" | grep -q "^frontend/"; then
    BUILD_TARGETS="$BUILD_TARGETS frontend"
    UP_TARGETS="$UP_TARGETS frontend"
  fi
  # 감지 실패 또는 변경 없을 때 backend 기본 빌드
  [ -z "$BUILD_TARGETS" ] && BUILD_TARGETS="backend" && UP_TARGETS="backend"

  log "변경 감지: 빌드 대상 →${BUILD_TARGETS}"
  log "이미지 빌드 중 (레이어 캐시 활용)..."
  DOCKER_BUILDKIT=1 $COMPOSE_CMD build $BUILD_TARGETS
  log "서비스 재시작 중..."
  cleanup_containers  # 빌드 후 up 직전 재정리 — 이름 충돌 방지
  $COMPOSE_CMD up -d --no-deps $UP_TARGETS nginx
  for svc in $UP_TARGETS; do
    verify_service_running "$svc" 30
  done
  # 재시작 후 컨테이너 IP가 바뀔 수 있으므로 nginx도 강제 재시작
  $COMPOSE_CMD restart nginx
  run_migrations
  cleanup_containers
  log "=== 업데이트 완료 (환경: $ENV) ==="

else
  # ── 최초 배포 ──
  log "=== 최초 배포 시작 (환경: $ENV) ==="
  require_root
  install_docker
  check_env

  log "모든 서비스 빌드 및 시작..."
  DOCKER_BUILDKIT=1 $COMPOSE_CMD up -d --build

  log "DB 준비 대기 중 (최대 30초)..."
  sleep 15

  run_migrations
  create_superadmin
  cleanup_containers

  log ""
  log "=== 배포 완료 (환경: $ENV) ==="
  if [ "$ENV" = "staging" ]; then
    log "스테이징 서버: http://$(curl -s ifconfig.me 2>/dev/null || echo 'EC2_IP'):8080"
  elif [ "$ENV" = "dev" ]; then
    log "개발 서버: http://$(curl -s ifconfig.me 2>/dev/null || echo 'DEV_EC2_IP'):8080"
  else
    log "운영 서버: http://$(curl -s ifconfig.me 2>/dev/null || echo 'PROD_EC2_IP')"
  fi
  log "슈퍼어드민: nickname=admin / PW=ChangeMe123! (즉시 변경하세요)"
  log ""
  log "서비스 상태 확인: $COMPOSE_CMD ps"
  log "백엔드 로그:      $COMPOSE_CMD logs -f backend"
fi
