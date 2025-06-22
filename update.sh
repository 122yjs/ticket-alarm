#!/bin/bash

# 티켓 알림 시스템 업데이트 스크립트
# 기존 설치된 시스템을 안전하게 업데이트합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
APP_NAME="ticket-alarm"
APP_DIR="/opt/$APP_NAME"
LOG_DIR="/var/log/$APP_NAME"
BACKUP_DIR="/opt/backups/$APP_NAME"
SYSTEM_USER="www-data"
SYSTEM_GROUP="www-data"
GIT_REPO="https://github.com/yourusername/ticket-alarm.git"  # 실제 저장소로 변경
BRANCH="main"

# 업데이트 옵션
FORCE_UPDATE=false
SKIP_BACKUP=false
SKIP_DEPENDENCIES=false
SKIP_RESTART=false
DRY_RUN=false
QUIET=false
ROLLBACK_VERSION=""
UPDATE_BRANCH=""

# 명령행 인수 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-dir)
            APP_DIR="$2"
            shift 2
            ;;
        --git-repo)
            GIT_REPO="$2"
            shift 2
            ;;
        --branch)
            UPDATE_BRANCH="$2"
            shift 2
            ;;
        --rollback)
            ROLLBACK_VERSION="$2"
            shift 2
            ;;
        --force)
            FORCE_UPDATE=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPENDENCIES=true
            shift
            ;;
        --skip-restart)
            SKIP_RESTART=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        -h|--help)
            echo "사용법: $0 [옵션]"
            echo "옵션:"
            echo "  --app-dir DIR        애플리케이션 디렉토리 (기본: /opt/ticket-alarm)"
            echo "  --git-repo URL       Git 저장소 URL"
            echo "  --branch BRANCH      업데이트할 Git 브랜치"
            echo "  --rollback VERSION   특정 버전으로 롤백"
            echo "  --force              강제 업데이트 (변경사항 무시)"
            echo "  --skip-backup        백업 건너뛰기"
            echo "  --skip-deps          의존성 업데이트 건너뛰기"
            echo "  --skip-restart       서비스 재시작 건너뛰기"
            echo "  --dry-run            실제 변경 없이 시뮬레이션만 실행"
            echo "  --quiet              최소한의 출력만 표시"
            echo "  -h, --help           도움말 표시"
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

# 조용한 모드 설정
if [[ "$QUIET" == true ]]; then
    exec 1>/dev/null 2>&1
fi

# 루트 권한 확인
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "이 스크립트는 루트 권한으로 실행해야 합니다"
        log_info "다음 명령어로 실행하세요: sudo $0"
        exit 1
    fi
}

# 설치 상태 확인
check_installation() {
    log_info "기존 설치 확인 중..."
    
    if [[ ! -d "$APP_DIR" ]]; then
        log_error "애플리케이션이 설치되어 있지 않습니다: $APP_DIR"
        log_info "먼저 install.sh를 실행하여 설치하세요"
        exit 1
    fi
    
    if [[ ! -f "$APP_DIR/monitor.py" ]]; then
        log_error "애플리케이션 파일이 없습니다: $APP_DIR/monitor.py"
        exit 1
    fi
    
    log_success "기존 설치 확인 완료"
}

# 현재 버전 정보 확인
get_current_version() {
    log_info "현재 버전 정보 확인 중..."
    
    cd "$APP_DIR"
    
    if [[ -d ".git" ]]; then
        local current_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        local current_branch=$(git branch --show-current 2>/dev/null || echo "unknown")
        local current_date=$(git show -s --format=%ci HEAD 2>/dev/null || echo "unknown")
        
        log_info "현재 커밋: $current_commit"
        log_info "현재 브랜치: $current_branch"
        log_info "커밋 날짜: $current_date"
        
        # 전역 변수에 저장
        CURRENT_COMMIT="$current_commit"
        CURRENT_BRANCH="$current_branch"
    else
        log_warning "Git 저장소가 아닙니다. 버전 정보를 확인할 수 없습니다."
        CURRENT_COMMIT="unknown"
        CURRENT_BRANCH="unknown"
    fi
}

# 업데이트 가능 여부 확인
check_updates_available() {
    log_info "업데이트 확인 중..."
    
    cd "$APP_DIR"
    
    if [[ ! -d ".git" ]]; then
        log_warning "Git 저장소가 아닙니다. 수동 업데이트가 필요합니다."
        return 1
    fi
    
    # 원격 저장소 정보 가져오기
    git fetch origin
    
    # 업데이트할 브랜치 결정
    local target_branch="${UPDATE_BRANCH:-$CURRENT_BRANCH}"
    
    # 로컬과 원격 커밋 비교
    local local_commit=$(git rev-parse HEAD)
    local remote_commit=$(git rev-parse "origin/$target_branch" 2>/dev/null || echo "")
    
    if [[ -z "$remote_commit" ]]; then
        log_error "원격 브랜치를 찾을 수 없습니다: origin/$target_branch"
        return 1
    fi
    
    if [[ "$local_commit" == "$remote_commit" ]]; then
        log_info "이미 최신 버전입니다"
        
        if [[ "$FORCE_UPDATE" != true ]]; then
            log_info "업데이트가 필요하지 않습니다"
            return 1
        else
            log_info "강제 업데이트를 진행합니다"
        fi
    else
        log_info "업데이트가 가능합니다"
        log_info "로컬: $local_commit"
        log_info "원격: $remote_commit"
    fi
    
    # 변경사항 확인
    local changes=$(git status --porcelain)
    if [[ -n "$changes" && "$FORCE_UPDATE" != true ]]; then
        log_error "로컬 변경사항이 있습니다:"
        git status --short
        log_error "변경사항을 커밋하거나 --force 옵션을 사용하세요"
        return 1
    fi
    
    return 0
}

# 서비스 상태 확인
check_service_status() {
    log_info "서비스 상태 확인 중..."
    
    # Supervisor 상태 확인
    if command -v supervisorctl >/dev/null 2>&1; then
        local supervisor_status=$(supervisorctl status "$APP_NAME:*" 2>/dev/null || echo "not found")
        log_info "Supervisor 상태: $supervisor_status"
        
        if echo "$supervisor_status" | grep -q "RUNNING"; then
            SERVICE_RUNNING=true
        else
            SERVICE_RUNNING=false
        fi
    else
        log_warning "Supervisor가 설치되어 있지 않습니다"
        SERVICE_RUNNING=false
    fi
    
    # Nginx 상태 확인
    if systemctl is-active --quiet nginx 2>/dev/null; then
        log_info "Nginx 상태: 실행 중"
        NGINX_RUNNING=true
    else
        log_info "Nginx 상태: 중지됨"
        NGINX_RUNNING=false
    fi
}

# 백업 생성
create_backup() {
    if [[ "$SKIP_BACKUP" == true ]]; then
        log_info "백업을 건너뜁니다"
        return 0
    fi
    
    log_info "업데이트 전 백업 생성 중..."
    
    local backup_name="update_backup_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 백업 생성: $backup_path"
        return 0
    fi
    
    # 백업 디렉토리 생성
    mkdir -p "$backup_path"
    
    # 애플리케이션 파일 백업
    cp -r "$APP_DIR" "$backup_path/app"
    
    # 설정 파일 백업
    if [[ -f "$APP_DIR/config.json" ]]; then
        cp "$APP_DIR/config.json" "$backup_path/"
    fi
    
    if [[ -f "$APP_DIR/.env" ]]; then
        cp "$APP_DIR/.env" "$backup_path/"
    fi
    
    # 데이터 파일 백업
    if [[ -d "$APP_DIR/data" ]]; then
        cp -r "$APP_DIR/data" "$backup_path/"
    fi
    
    # 백업 정보 저장
    cat > "$backup_path/backup_info.txt" << EOF
백업 생성 시간: $(date)
백업 유형: 업데이트 전 백업
애플리케이션 디렉토리: $APP_DIR
현재 커밋: $CURRENT_COMMIT
현재 브랜치: $CURRENT_BRANCH
EOF
    
    # 권한 설정
    chown -R "$SYSTEM_USER:$SYSTEM_GROUP" "$backup_path"
    
    # 전역 변수에 백업 경로 저장
    BACKUP_PATH="$backup_path"
    
    log_success "백업 생성 완료: $backup_path"
}

# 서비스 중지
stop_services() {
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 서비스 중지"
        return 0
    fi
    
    log_info "서비스 중지 중..."
    
    # Supervisor 서비스 중지
    if [[ "$SERVICE_RUNNING" == true ]]; then
        supervisorctl stop "$APP_NAME:*" || log_warning "Supervisor 서비스 중지 실패"
        log_success "Supervisor 서비스 중지 완료"
    fi
    
    # 추가 프로세스 확인 및 종료
    local pids=$(pgrep -f "$APP_DIR" || true)
    if [[ -n "$pids" ]]; then
        log_info "남은 프로세스 종료 중..."
        echo "$pids" | xargs kill -TERM || true
        sleep 3
        
        # 강제 종료가 필요한 경우
        pids=$(pgrep -f "$APP_DIR" || true)
        if [[ -n "$pids" ]]; then
            echo "$pids" | xargs kill -KILL || true
        fi
    fi
    
    log_success "서비스 중지 완료"
}

# 코드 업데이트
update_code() {
    log_info "코드 업데이트 중..."
    
    cd "$APP_DIR"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Git pull 실행"
        return 0
    fi
    
    # 롤백 모드인 경우
    if [[ -n "$ROLLBACK_VERSION" ]]; then
        log_info "버전 롤백 중: $ROLLBACK_VERSION"
        
        git checkout "$ROLLBACK_VERSION"
        
        log_success "롤백 완료: $ROLLBACK_VERSION"
        return 0
    fi
    
    # 일반 업데이트
    local target_branch="${UPDATE_BRANCH:-$CURRENT_BRANCH}"
    
    # 로컬 변경사항 처리
    if [[ "$FORCE_UPDATE" == true ]]; then
        git reset --hard HEAD
        git clean -fd
    fi
    
    # 브랜치 전환 (필요한 경우)
    if [[ "$target_branch" != "$CURRENT_BRANCH" ]]; then
        git checkout "$target_branch"
    fi
    
    # 최신 코드 가져오기
    git pull origin "$target_branch"
    
    # 업데이트된 버전 정보
    local new_commit=$(git rev-parse HEAD)
    local new_date=$(git show -s --format=%ci HEAD)
    
    log_success "코드 업데이트 완료"
    log_info "새 커밋: $new_commit"
    log_info "커밋 날짜: $new_date"
    
    # 전역 변수 업데이트
    NEW_COMMIT="$new_commit"
}

# 의존성 업데이트
update_dependencies() {
    if [[ "$SKIP_DEPENDENCIES" == true ]]; then
        log_info "의존성 업데이트를 건너뜁니다"
        return 0
    fi
    
    log_info "의존성 업데이트 중..."
    
    cd "$APP_DIR"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] pip install -r requirements.txt"
        return 0
    fi
    
    # 가상환경 활성화 및 의존성 업데이트
    if [[ -f "requirements.txt" ]]; then
        sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && pip install --upgrade pip"
        sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && pip install -r requirements.txt --upgrade"
        
        log_success "Python 의존성 업데이트 완료"
    else
        log_warning "requirements.txt 파일이 없습니다"
    fi
    
    # 시스템 패키지 업데이트 (선택적)
    if [[ "$FORCE_UPDATE" == true ]]; then
        log_info "시스템 패키지 업데이트 중..."
        apt-get update -qq
        apt-get upgrade -y -qq
        log_success "시스템 패키지 업데이트 완료"
    fi
}

# 설정 파일 업데이트
update_configuration() {
    log_info "설정 파일 확인 중..."
    
    cd "$APP_DIR"
    
    # 새로운 설정 파일 예제가 있는지 확인
    if [[ -f "config.json.example" ]]; then
        if [[ ! -f "config.json" ]]; then
            log_info "config.json 파일이 없습니다. 예제에서 생성합니다."
            
            if [[ "$DRY_RUN" != true ]]; then
                cp "config.json.example" "config.json"
                chown "$SYSTEM_USER:$SYSTEM_GROUP" "config.json"
                chmod 600 "config.json"
            fi
        else
            # 설정 파일 차이점 확인
            if ! diff -q "config.json" "config.json.example" >/dev/null 2>&1; then
                log_warning "설정 파일에 새로운 옵션이 있을 수 있습니다"
                log_info "config.json.example과 config.json을 비교해보세요"
            fi
        fi
    fi
    
    # .env 파일 확인
    if [[ -f "production.env.example" && ! -f ".env" ]]; then
        log_info ".env 파일이 없습니다. 예제에서 생성합니다."
        
        if [[ "$DRY_RUN" != true ]]; then
            cp "production.env.example" ".env"
            chown "$SYSTEM_USER:$SYSTEM_GROUP" ".env"
            chmod 600 ".env"
        fi
    fi
    
    # 설정 파일 유효성 검사
    if [[ -f "config.json" && "$DRY_RUN" != true ]]; then
        if ! python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
            log_error "config.json 파일이 유효하지 않습니다"
            
            if [[ -n "$BACKUP_PATH" ]]; then
                log_info "백업에서 설정 파일을 복원합니다"
                cp "$BACKUP_PATH/config.json" "config.json"
            fi
        else
            log_success "설정 파일 유효성 검사 통과"
        fi
    fi
}

# 데이터베이스 마이그레이션
run_migrations() {
    log_info "데이터 마이그레이션 확인 중..."
    
    cd "$APP_DIR"
    
    # 마이그레이션 스크립트가 있는지 확인
    if [[ -f "migrate.py" ]]; then
        log_info "데이터 마이그레이션 실행 중..."
        
        if [[ "$DRY_RUN" != true ]]; then
            sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && python migrate.py"
            log_success "데이터 마이그레이션 완료"
        else
            log_info "[DRY RUN] 데이터 마이그레이션 실행"
        fi
    else
        log_info "마이그레이션 스크립트가 없습니다"
    fi
}

# 서비스 시작
start_services() {
    if [[ "$SKIP_RESTART" == true ]]; then
        log_info "서비스 재시작을 건너뜁니다"
        return 0
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 서비스 시작"
        return 0
    fi
    
    log_info "서비스 시작 중..."
    
    # Supervisor 설정 재로드
    if command -v supervisorctl >/dev/null 2>&1; then
        supervisorctl reread
        supervisorctl update
        
        # 서비스 시작
        supervisorctl start "$APP_NAME:*"
        
        # 시작 대기
        sleep 5
        
        # 상태 확인
        local status=$(supervisorctl status "$APP_NAME:*")
        if echo "$status" | grep -q "RUNNING"; then
            log_success "Supervisor 서비스 시작 완료"
        else
            log_error "Supervisor 서비스 시작 실패"
            log_error "상태: $status"
            return 1
        fi
    fi
    
    # Nginx 재시작 (필요한 경우)
    if [[ "$NGINX_RUNNING" == true ]]; then
        systemctl reload nginx
        log_success "Nginx 설정 재로드 완료"
    fi
}

# 업데이트 후 테스트
post_update_test() {
    log_info "업데이트 후 테스트 수행 중..."
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 업데이트 후 테스트"
        return 0
    fi
    
    cd "$APP_DIR"
    
    # Python 모듈 import 테스트
    if sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && python -c 'import monitor'"; then
        log_success "Python 모듈 import 테스트 통과"
    else
        log_error "Python 모듈 import 테스트 실패"
        return 1
    fi
    
    # 설정 파일 로드 테스트
    if sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && python -c 'import json; json.load(open(\"config.json\"))'"; then
        log_success "설정 파일 로드 테스트 통과"
    else
        log_error "설정 파일 로드 테스트 실패"
        return 1
    fi
    
    # 웹 서버 응답 테스트
    sleep 10  # 서비스 완전 시작 대기
    
    local web_port=$(grep -o '"WEB_PORT":[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*' || echo "8000")
    
    if curl -s "http://localhost:$web_port/health" >/dev/null; then
        log_success "웹 서버 응답 테스트 통과"
    else
        log_warning "웹 서버 응답 테스트 실패 (서비스가 아직 시작 중일 수 있음)"
    fi
    
    log_success "업데이트 후 테스트 완료"
}

# 업데이트 요약 출력
print_update_summary() {
    log_success "=== 업데이트 완료 ==="
    echo
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 실제 변경사항은 적용되지 않았습니다"
        echo
    fi
    
    log_info "애플리케이션 디렉토리: $APP_DIR"
    
    if [[ -n "$ROLLBACK_VERSION" ]]; then
        log_info "롤백된 버전: $ROLLBACK_VERSION"
    else
        log_info "이전 커밋: ${CURRENT_COMMIT:0:8}"
        log_info "새 커밋: ${NEW_COMMIT:0:8}"
    fi
    
    if [[ -n "$BACKUP_PATH" ]]; then
        log_info "백업 위치: $BACKUP_PATH"
    fi
    
    echo
    log_info "다음 단계:"
    log_info "1. 서비스 상태 확인: supervisorctl status"
    log_info "2. 로그 확인: tail -f $LOG_DIR/*.log"
    log_info "3. 웹 접속 테스트: curl http://localhost:8000/health"
    
    if [[ "$DRY_RUN" != true ]]; then
        echo
        log_info "유용한 명령어:"
        log_info "- 서비스 재시작: supervisorctl restart $APP_NAME:*"
        log_info "- 로그 실시간 확인: tail -f $LOG_DIR/supervisor.log"
        log_info "- 헬스 체크: cd $APP_DIR && ./health_check.sh"
        
        if [[ -n "$BACKUP_PATH" ]]; then
            log_info "- 롤백: $0 --rollback $CURRENT_COMMIT"
        fi
    fi
}

# 롤백 함수
rollback_update() {
    log_error "업데이트 실패. 롤백을 시도합니다..."
    
    if [[ -z "$BACKUP_PATH" ]]; then
        log_error "백업이 없어 롤백할 수 없습니다"
        return 1
    fi
    
    # 서비스 중지
    supervisorctl stop "$APP_NAME:*" || true
    
    # 백업에서 복원
    rm -rf "$APP_DIR.failed"
    mv "$APP_DIR" "$APP_DIR.failed"
    cp -r "$BACKUP_PATH/app" "$APP_DIR"
    
    # 권한 복원
    chown -R "$SYSTEM_USER:$SYSTEM_GROUP" "$APP_DIR"
    
    # 서비스 시작
    supervisorctl start "$APP_NAME:*"
    
    log_success "롤백 완료"
    log_info "실패한 업데이트는 $APP_DIR.failed에 보관되었습니다"
}

# 메인 업데이트 함수
main() {
    log_info "티켓 알림 시스템 업데이트를 시작합니다"
    
    # 사전 검사
    check_root
    check_installation
    get_current_version
    
    # 업데이트 필요성 확인
    if ! check_updates_available; then
        if [[ "$FORCE_UPDATE" != true && -z "$ROLLBACK_VERSION" ]]; then
            log_info "업데이트가 필요하지 않습니다"
            exit 0
        fi
    fi
    
    # 서비스 상태 확인
    check_service_status
    
    # 업데이트 실행
    if create_backup && \
       stop_services && \
       update_code && \
       update_dependencies && \
       update_configuration && \
       run_migrations && \
       start_services && \
       post_update_test; then
        
        print_update_summary
        log_success "업데이트가 성공적으로 완료되었습니다!"
    else
        log_error "업데이트 중 오류가 발생했습니다"
        
        if [[ "$DRY_RUN" != true ]]; then
            rollback_update
        fi
        
        exit 1
    fi
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi