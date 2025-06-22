#!/bin/bash

# 티켓 알림 시스템 자동 배포 스크립트
# 사용법: ./deploy.sh [환경] [옵션]
# 환경: development, staging, production
# 옵션: --skip-backup, --force-update, --quick

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 기본 설정
ENVIRONMENT="production"
SKIP_BACKUP=false
FORCE_UPDATE=false
QUICK_DEPLOY=false
APP_DIR="/opt/ticket-alarm"
BACKUP_DIR="/opt/backups/ticket-alarm"
LOG_FILE="/var/log/ticket-alarm/deploy.log"

# 명령행 인수 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        development|staging|production)
            ENVIRONMENT="$1"
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --force-update)
            FORCE_UPDATE=true
            shift
            ;;
        --quick)
            QUICK_DEPLOY=true
            shift
            ;;
        -h|--help)
            echo "사용법: $0 [환경] [옵션]"
            echo "환경:"
            echo "  development  개발 환경 배포"
            echo "  staging      스테이징 환경 배포"
            echo "  production   운영 환경 배포 (기본값)"
            echo "옵션:"
            echo "  --skip-backup   백업 생성 건너뛰기"
            echo "  --force-update  강제 업데이트"
            echo "  --quick         빠른 배포 (테스트 건너뛰기)"
            echo "  -h, --help      도움말 표시"
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

# 배포 시작 로그
log_info "티켓 알림 시스템 배포 시작"
log_info "환경: $ENVIRONMENT"
log_info "시간: $(date)"
echo "$(date): 배포 시작 - 환경: $ENVIRONMENT" >> "$LOG_FILE"

# 사전 검사
check_prerequisites() {
    log_info "사전 검사 수행 중..."
    
    # 루트 권한 확인
    if [[ $EUID -eq 0 ]]; then
        log_error "루트 사용자로 실행하지 마세요. sudo 권한이 있는 일반 사용자로 실행하세요."
        exit 1
    fi
    
    # sudo 권한 확인
    if ! sudo -n true 2>/dev/null; then
        log_error "sudo 권한이 필요합니다."
        exit 1
    fi
    
    # 필수 명령어 확인
    local required_commands=("git" "python3" "pip" "supervisorctl" "nginx")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "필수 명령어가 설치되지 않음: $cmd"
            exit 1
        fi
    done
    
    # 디스크 공간 확인 (최소 1GB)
    local available_space=$(df "$APP_DIR" | tail -1 | awk '{print $4}')
    if [[ $available_space -lt 1048576 ]]; then  # 1GB in KB
        log_error "디스크 공간이 부족합니다. 최소 1GB가 필요합니다."
        exit 1
    fi
    
    log_success "사전 검사 완료"
}

# 백업 생성
create_backup() {
    if [[ "$SKIP_BACKUP" == true ]]; then
        log_warning "백업 생성을 건너뜁니다."
        return
    fi
    
    log_info "백업 생성 중..."
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/deploy_backup_$timestamp.tar.gz"
    
    # 백업 디렉토리 생성
    sudo mkdir -p "$BACKUP_DIR"
    
    # 현재 애플리케이션 백업
    if [[ -d "$APP_DIR" ]]; then
        sudo tar -czf "$backup_file" -C "$(dirname $APP_DIR)" "$(basename $APP_DIR)"
        log_success "백업 생성 완료: $backup_file"
    else
        log_warning "애플리케이션 디렉토리가 존재하지 않습니다: $APP_DIR"
    fi
}

# 애플리케이션 중지
stop_application() {
    log_info "애플리케이션 중지 중..."
    
    if sudo supervisorctl status ticket-alarm:* &>/dev/null; then
        sudo supervisorctl stop ticket-alarm:*
        log_success "애플리케이션 중지 완료"
    else
        log_warning "실행 중인 애플리케이션이 없습니다."
    fi
}

# 코드 업데이트
update_code() {
    log_info "코드 업데이트 중..."
    
    # 애플리케이션 디렉토리로 이동
    cd "$APP_DIR"
    
    # Git 저장소 확인
    if [[ ! -d ".git" ]]; then
        log_error "Git 저장소가 아닙니다: $APP_DIR"
        exit 1
    fi
    
    # 현재 브랜치 확인
    local current_branch=$(git branch --show-current)
    log_info "현재 브랜치: $current_branch"
    
    # 환경별 브랜치 설정
    local target_branch
    case $ENVIRONMENT in
        development)
            target_branch="develop"
            ;;
        staging)
            target_branch="staging"
            ;;
        production)
            target_branch="main"
            ;;
    esac
    
    # 브랜치 전환 (필요시)
    if [[ "$current_branch" != "$target_branch" ]]; then
        log_info "브랜치 전환: $current_branch -> $target_branch"
        git checkout "$target_branch"
    fi
    
    # 코드 업데이트
    if [[ "$FORCE_UPDATE" == true ]]; then
        git reset --hard HEAD
        git clean -fd
    fi
    
    git fetch origin
    git pull origin "$target_branch"
    
    log_success "코드 업데이트 완료"
}

# 의존성 업데이트
update_dependencies() {
    log_info "의존성 업데이트 중..."
    
    cd "$APP_DIR"
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # 의존성 설치/업데이트
    pip install -r requirements.txt --upgrade
    
    log_success "의존성 업데이트 완료"
}

# 설정 파일 검증
validate_config() {
    log_info "설정 파일 검증 중..."
    
    cd "$APP_DIR"
    
    # config.json 존재 확인
    if [[ ! -f "config.json" ]]; then
        log_warning "config.json이 없습니다. 예제 파일을 복사합니다."
        cp config.json.example config.json
        log_error "config.json을 편집한 후 다시 배포하세요."
        exit 1
    fi
    
    # JSON 문법 검증
    if ! python3 -m json.tool config.json > /dev/null; then
        log_error "config.json 문법 오류가 있습니다."
        exit 1
    fi
    
    # 필수 설정 확인
    local required_keys=("DISCORD_WEBHOOK_URL" "KEYWORDS" "interval")
    for key in "${required_keys[@]}"; do
        if ! python3 -c "import json; config=json.load(open('config.json')); assert '$key' in config" 2>/dev/null; then
            log_error "필수 설정이 누락되었습니다: $key"
            exit 1
        fi
    done
    
    log_success "설정 파일 검증 완료"
}

# 데이터베이스/파일 마이그레이션
migrate_data() {
    log_info "데이터 마이그레이션 중..."
    
    cd "$APP_DIR"
    
    # 데이터 디렉토리 생성
    mkdir -p data
    chmod 755 data
    
    # 기존 데이터 파일 권한 수정
    if [[ -f "data/notification_history.json" ]]; then
        chmod 644 data/notification_history.json
    fi
    
    if [[ -f "data/sent_notifications.json" ]]; then
        chmod 644 data/sent_notifications.json
    fi
    
    log_success "데이터 마이그레이션 완료"
}

# 테스트 실행
run_tests() {
    if [[ "$QUICK_DEPLOY" == true ]]; then
        log_warning "빠른 배포 모드: 테스트를 건너뜁니다."
        return
    fi
    
    log_info "테스트 실행 중..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # 크롤러 테스트
    if [[ -f "test_crawlers.py" ]]; then
        python3 test_crawlers.py
        if [[ $? -ne 0 ]]; then
            log_error "크롤러 테스트 실패"
            exit 1
        fi
    fi
    
    # 설정 테스트
    python3 -c "import json; config=json.load(open('config.json')); print('설정 파일 로드 성공')"
    
    # 모듈 import 테스트
    python3 -c "import monitor, discord_notifier; print('모듈 import 성공')"
    
    log_success "테스트 완료"
}

# 애플리케이션 시작
start_application() {
    log_info "애플리케이션 시작 중..."
    
    # Supervisor 설정 다시 읽기
    sudo supervisorctl reread
    sudo supervisorctl update
    
    # 애플리케이션 시작
    sudo supervisorctl start ticket-alarm:*
    
    # 시작 확인
    sleep 5
    if sudo supervisorctl status ticket-alarm:* | grep -q RUNNING; then
        log_success "애플리케이션 시작 완료"
    else
        log_error "애플리케이션 시작 실패"
        sudo supervisorctl status ticket-alarm:*
        exit 1
    fi
}

# 헬스 체크
health_check() {
    log_info "헬스 체크 수행 중..."
    
    # 프로세스 상태 확인
    local status_output=$(sudo supervisorctl status ticket-alarm:*)
    echo "$status_output"
    
    if echo "$status_output" | grep -q RUNNING; then
        log_success "모든 프로세스가 정상 실행 중입니다."
    else
        log_error "일부 프로세스가 실행되지 않고 있습니다."
        return 1
    fi
    
    # 웹 서비스 확인 (포트 8000)
    if curl -s http://localhost:8000 > /dev/null; then
        log_success "웹 서비스가 정상 응답합니다."
    else
        log_warning "웹 서비스 응답을 확인할 수 없습니다."
    fi
    
    # 로그 파일 확인
    if [[ -f "/var/log/ticket-alarm/monitor.out.log" ]]; then
        local recent_logs=$(tail -5 /var/log/ticket-alarm/monitor.out.log)
        if echo "$recent_logs" | grep -q ERROR; then
            log_warning "최근 로그에 에러가 있습니다:"
            echo "$recent_logs" | grep ERROR
        else
            log_success "최근 로그에 에러가 없습니다."
        fi
    fi
}

# 배포 완료 알림
send_notification() {
    log_info "배포 완료 알림 발송 중..."
    
    local deploy_message="🚀 티켓 알림 시스템 배포 완료\n환경: $ENVIRONMENT\n시간: $(date)\n상태: 성공"
    
    # 디스코드 웹훅으로 알림 (설정된 경우)
    if [[ -f "$APP_DIR/config.json" ]]; then
        local webhook_url=$(python3 -c "import json; config=json.load(open('$APP_DIR/config.json')); print(config.get('DISCORD_WEBHOOK_URL', ''))" 2>/dev/null)
        if [[ -n "$webhook_url" ]]; then
            curl -X POST -H "Content-Type: application/json" \
                -d "{\"content\":\"$deploy_message\"}" \
                "$webhook_url" &>/dev/null
            log_success "디스코드 알림 발송 완료"
        fi
    fi
}

# 롤백 함수
rollback() {
    log_error "배포 실패. 롤백을 수행합니다."
    
    # 최신 백업 파일 찾기
    local latest_backup=$(ls -t "$BACKUP_DIR"/deploy_backup_*.tar.gz 2>/dev/null | head -1)
    
    if [[ -n "$latest_backup" ]]; then
        log_info "백업에서 복원 중: $latest_backup"
        
        # 애플리케이션 중지
        sudo supervisorctl stop ticket-alarm:* || true
        
        # 현재 디렉토리 백업
        sudo mv "$APP_DIR" "${APP_DIR}_failed_$(date +%Y%m%d_%H%M%S)" || true
        
        # 백업에서 복원
        sudo tar -xzf "$latest_backup" -C "$(dirname $APP_DIR)"
        
        # 애플리케이션 시작
        sudo supervisorctl start ticket-alarm:*
        
        log_success "롤백 완료"
    else
        log_error "백업 파일을 찾을 수 없습니다. 수동 복구가 필요합니다."
    fi
}

# 메인 배포 함수
main() {
    # 에러 발생 시 롤백 수행
    trap 'rollback' ERR
    
    check_prerequisites
    create_backup
    stop_application
    update_code
    update_dependencies
    validate_config
    migrate_data
    run_tests
    start_application
    
    # 헬스 체크
    if health_check; then
        send_notification
        log_success "배포가 성공적으로 완료되었습니다!"
        echo "$(date): 배포 완료 - 환경: $ENVIRONMENT" >> "$LOG_FILE"
    else
        log_error "헬스 체크 실패. 시스템을 확인하세요."
        exit 1
    fi
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi