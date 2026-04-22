#!/bin/bash
# 로컬에서 실행하는 원격 배포 스크립트
# 사용법: bash scripts/remote-deploy.sh [prod|dev]
# 전제: EC2에 git + /opt/chatbot이 git repo로 설정된 상태
#
# 예시:
#   export EC2_IP=43.202.215.18
#   bash scripts/remote-deploy.sh prod

set -e

ENV="${1:-prod}"
EC2_USER="ubuntu"
EC2_KEY="${SSH_KEY:-$HOME/.ssh/chatbot-prod.pem}"
EC2_IP="${EC2_IP:-}"
DEPLOY_PATH="/opt/chatbot"

# ── 검증 ──────────────────────────────────────────────────────
[ -z "$EC2_IP" ] && { echo "[ERROR] EC2_IP 환경변수를 설정하세요: export EC2_IP=<서버IP>"; exit 1; }
[ -f "$EC2_KEY" ] || { echo "[ERROR] SSH 키 파일 없음: $EC2_KEY"; exit 1; }

SSH="ssh -i $EC2_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 $EC2_USER@$EC2_IP"
log() { echo -e "\033[1;32m[REMOTE-DEPLOY]\033[0m $1"; }

# ── 접속 확인 ─────────────────────────────────────────────────
log "EC2 접속 확인 ($EC2_IP)..."
$SSH "echo ok" > /dev/null || { echo "[ERROR] EC2 접속 실패"; exit 1; }

# ── 배포 전 DB 백업 (마이그레이션 여부와 무관하게 항상 실행) ──
log "배포 전 DB 스냅샷..."
$SSH "mkdir -p $DEPLOY_PATH/backups && \
  docker exec chatbot-db pg_dump -U chatbot chatbot 2>/dev/null | \
  gzip > $DEPLOY_PATH/backups/pre-deploy-\$(date +%Y%m%d-%H%M%S).sql.gz && \
  echo '백업 완료' || echo '[WARN] DB 백업 실패 (계속 진행)'"

# ── git pull ──────────────────────────────────────────────────
log "코드 업데이트 (git pull)..."
$SSH "cd $DEPLOY_PATH && git pull origin main" || {
  echo "[ERROR] git pull 실패. GitHub PAT 인증이 필요할 수 있습니다."
  echo "  EC2 접속 후: cd /opt/chatbot && git pull origin main"
  echo "  username: GitHub 사용자명, password: Personal Access Token"
  exit 1
}

# ── 빌드 + 재시작 + 마이그레이션 ─────────────────────────────
log "이미지 빌드 및 배포..."
$SSH "cd $DEPLOY_PATH && bash deploy.sh update $ENV"

# ── 헬스체크 ──────────────────────────────────────────────────
log "헬스체크..."
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://$EC2_IP/health" 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
  log "헬스체크 통과 (HTTP $HTTP_STATUS)"
else
  echo "[WARN] 헬스체크 응답: HTTP $HTTP_STATUS (서버가 아직 기동 중일 수 있음)"
fi

log "=== 배포 완료 ==="
log "서버: http://$EC2_IP"
log "로그 확인: ssh -i $EC2_KEY $EC2_USER@$EC2_IP 'cd $DEPLOY_PATH && docker compose -f docker-compose.prod.yml logs -f backend'"
