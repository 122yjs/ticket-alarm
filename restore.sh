#!/bin/bash

# 티켓 알림 시스템 복원 스크립트
# 백업된 데이터를 사용하여 시스템을 복원합니다.

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
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" >> "$RESTORE_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1" >> "$RESTORE_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1" >> "$RESTORE_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >> "$RESTORE_LOG"
}

# 기본 설정
APP_DIR="/opt/ticket-alarm"
BACKUP_BASE_DIR="/opt/backups"
BACKUP_DIR="$BACKUP_BASE_DIR/ticket-alarm"
LOG_DIR="/var/log/ticket-alarm"
RESTORE_LOG="$LOG_DIR/restore.log"
DATE=$(date +%Y%m%d_%H%M%S)

# 복원 옵션
BACKUP_FILE=""
BACKUP_TYPE="daily"
FORCE_RESTORE=false
SKIP_BACKUP=false
RESTORE_LOGS=true
RESTORE_CONFIG=true
RESTORE_DATA=true
DRY_RUN=false
VERIFY_ONLY=false

# 명령행 인수 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--file)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --type)
            BACKUP_TYPE="$2"
            shift 2
            ;;
        --force)
            FORCE_RESTORE=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --no-logs)
            RESTORE_LOGS=false
            shift
            ;;
        --no-config)
            RESTORE_CONFIG=false
            shift
            ;;
        --no-data)
            RESTORE_DATA=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        -h|--help)
            echo "사용법: $0 [옵션]"
            echo "옵션:"
            echo "  -f, --file FILE    복원할 백업 파일 지정"
            echo "  --type TYPE        백업 타입 (daily, weekly, monthly)"
            echo "  --force            강제 복원 (확인 없이)"
            echo "  --skip-backup      복원 전 현재 상태 백업 건너뛰기"
            echo "  --no-logs          로그 파일 복원 제외"
            echo "  --no-config        설정 파일 복원 제외"
            echo "  --no-data          데이터 파일 복원 제외"
            echo "  --dry-run          실제 복원 없이 시뮬레이션만"
            echo "  --verify           백업 파일 검증만 수행"
            echo "  -h, --help         도움말 표시"
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

# 사용자 확인
confirm_action() {
    local message="$1"
    
    if [[ "$FORCE_RESTORE" == true ]]; then
        return 0
    fi
    
    echo -e "${YELLOW}[확인]${NC} $message"
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "사용자가 작업을 취소했습니다"
        exit 0
    fi
}

# 백업 파일 목록 표시
list_available_backups() {
    log_info "사용 가능한 백업 파일:"
    
    echo
    echo "=== 일일 백업 ==="
    find "$BACKUP_DIR/daily" -name "*.tar*" -type f -exec ls -lh {} \; 2>/dev/null | \
        awk '{print $9 " (" $5 ", " $6 " " $7 " " $8 ")"}' | sort -r | head -10
    
    echo
    echo "=== 주간 백업 ==="
    find "$BACKUP_DIR/weekly" -name "*.tar*" -type f -exec ls -lh {} \; 2>/dev/null | \
        awk '{print $9 " (" $5 ", " $6 " " $7 " " $8 ")"}' | sort -r | head -5
    
    echo
    echo "=== 월간 백업 ==="
    find "$BACKUP_DIR/monthly" -name "*.tar*" -type f -exec ls -lh {} \; 2>/dev/null | \
        awk '{print $9 " (" $5 ", " $6 " " $7 " " $8 ")"}' | sort -r | head -5
    
    echo
}

# 백업 파일 자동 선택
select_backup_file() {
    if [[ -n "$BACKUP_FILE" ]]; then
        if [[ ! -f "$BACKUP_FILE" ]]; then
            log_error "지정된 백업 파일이 존재하지 않습니다: $BACKUP_FILE"
            exit 1
        fi
        return 0
    fi
    
    log_info "최신 $BACKUP_TYPE 백업 파일을 찾는 중..."
    
    # 최신 백업 파일 찾기
    local latest_backup=$(find "$BACKUP_DIR/$BACKUP_TYPE" -name "app_data_*.tar*" -type f | sort -r | head -1)
    
    if [[ -z "$latest_backup" ]]; then
        log_error "$BACKUP_TYPE 백업 파일을 찾을 수 없습니다"
        list_available_backups
        exit 1
    fi
    
    BACKUP_FILE="$latest_backup"
    log_info "선택된 백업 파일: $BACKUP_FILE"
}

# 백업 파일 검증
verify_backup_file() {
    local backup_file="$1"
    
    log_info "백업 파일 검증 중: $(basename $backup_file)"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "백업 파일이 존재하지 않습니다: $backup_file"
        return 1
    fi
    
    # 파일 크기 확인
    local file_size=$(stat -c%s "$backup_file" 2>/dev/null || echo "0")
    if [[ $file_size -eq 0 ]]; then
        log_error "백업 파일이 비어있습니다: $backup_file"
        return 1
    fi
    
    # 압축 파일 무결성 검사
    if [[ "$backup_file" == *.tar.gz ]]; then
        if ! gzip -t "$backup_file" 2>/dev/null; then
            log_error "압축 파일이 손상되었습니다: $backup_file"
            return 1
        fi
        
        # tar 내용 검사
        if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
            log_error "tar 파일 내용이 손상되었습니다: $backup_file"
            return 1
        fi
    elif [[ "$backup_file" == *.tar ]]; then
        if ! tar -tf "$backup_file" >/dev/null 2>&1; then
            log_error "tar 파일이 손상되었습니다: $backup_file"
            return 1
        fi
    else
        log_error "지원하지 않는 백업 파일 형식: $backup_file"
        return 1
    fi
    
    log_success "백업 파일 검증 완료"
    
    # 백업 파일 내용 미리보기
    log_info "백업 파일 내용:"
    if [[ "$backup_file" == *.tar.gz ]]; then
        tar -tzf "$backup_file" | head -20
    else
        tar -tf "$backup_file" | head -20
    fi
    
    local total_files=$(tar -tf "$backup_file" 2>/dev/null | wc -l)
    log_info "총 파일 수: $total_files"
    
    return 0
}

# 현재 상태 백업
backup_current_state() {
    if [[ "$SKIP_BACKUP" == true ]]; then
        log_info "현재 상태 백업을 건너뜁니다"
        return 0
    fi
    
    log_info "복원 전 현재 상태 백업 중..."
    
    local pre_restore_backup="$BACKUP_DIR/pre_restore_$DATE.tar.gz"
    
    if [[ -d "$APP_DIR" ]]; then
        cd "$(dirname $APP_DIR)"
        tar -czf "$pre_restore_backup" "$(basename $APP_DIR)" 2>/dev/null
        
        if [[ $? -eq 0 ]]; then
            local file_size=$(du -h "$pre_restore_backup" | cut -f1)
            log_success "현재 상태 백업 완료: $pre_restore_backup ($file_size)"
        else
            log_warning "현재 상태 백업 실패, 계속 진행합니다"
        fi
    else
        log_info "애플리케이션 디렉토리가 존재하지 않습니다: $APP_DIR"
    fi
}

# 서비스 중지
stop_services() {
    log_info "서비스 중지 중..."
    
    # Supervisor 서비스 중지
    if command -v supervisorctl >/dev/null 2>&1; then
        if supervisorctl status ticket-alarm >/dev/null 2>&1; then
            supervisorctl stop ticket-alarm
            log_success "Supervisor 서비스 중지됨"
        else
            log_info "Supervisor 서비스가 실행 중이 아닙니다"
        fi
    fi
    
    # 직접 실행 중인 프로세스 종료
    local pids=$(pgrep -f "python.*monitor.py" || true)
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill -TERM
        sleep 5
        
        # 강제 종료가 필요한 경우
        local remaining_pids=$(pgrep -f "python.*monitor.py" || true)
        if [[ -n "$remaining_pids" ]]; then
            echo "$remaining_pids" | xargs kill -KILL
            log_warning "프로세스를 강제 종료했습니다"
        fi
        
        log_success "애플리케이션 프로세스 종료됨"
    else
        log_info "실행 중인 애플리케이션 프로세스가 없습니다"
    fi
}

# 애플리케이션 데이터 복원
restore_application_data() {
    if [[ "$RESTORE_DATA" != true ]]; then
        log_info "데이터 복원을 건너뜁니다"
        return 0
    fi
    
    log_info "애플리케이션 데이터 복원 중..."
    
    # 임시 디렉토리 생성
    local temp_dir="/tmp/restore_$DATE"
    mkdir -p "$temp_dir"
    
    # 백업 파일 압축 해제
    cd "$temp_dir"
    
    if [[ "$BACKUP_FILE" == *.tar.gz ]]; then
        tar -xzf "$BACKUP_FILE"
    else
        tar -xf "$BACKUP_FILE"
    fi
    
    if [[ $? -ne 0 ]]; then
        log_error "백업 파일 압축 해제 실패"
        rm -rf "$temp_dir"
        return 1
    fi
    
    # 애플리케이션 디렉토리 생성
    mkdir -p "$APP_DIR"
    
    # 파일 복사
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 다음 파일들이 복원됩니다:"
        find "$temp_dir" -type f | sed "s|$temp_dir|$APP_DIR|"
    else
        cp -r "$temp_dir"/* "$APP_DIR/" 2>/dev/null || true
        
        # 권한 설정
        chown -R www-data:www-data "$APP_DIR" 2>/dev/null || true
        chmod -R 755 "$APP_DIR"
        chmod 644 "$APP_DIR"/*.py 2>/dev/null || true
        chmod 600 "$APP_DIR/config.json" 2>/dev/null || true
        
        log_success "애플리케이션 데이터 복원 완료"
    fi
    
    # 임시 디렉토리 정리
    rm -rf "$temp_dir"
}

# 로그 파일 복원
restore_logs() {
    if [[ "$RESTORE_LOGS" != true ]]; then
        log_info "로그 복원을 건너뜁니다"
        return 0
    fi
    
    log_info "로그 파일 복원 중..."
    
    # 로그 백업 파일 찾기
    local log_backup_file=$(echo "$BACKUP_FILE" | sed 's/app_data/logs/')
    
    if [[ ! -f "$log_backup_file" ]]; then
        log_warning "로그 백업 파일을 찾을 수 없습니다: $log_backup_file"
        return 0
    fi
    
    # 임시 디렉토리 생성
    local temp_dir="/tmp/restore_logs_$DATE"
    mkdir -p "$temp_dir"
    
    # 로그 백업 파일 압축 해제
    cd "$temp_dir"
    
    if [[ "$log_backup_file" == *.tar.gz ]]; then
        tar -xzf "$log_backup_file"
    else
        tar -xf "$log_backup_file"
    fi
    
    if [[ $? -eq 0 ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_info "[DRY RUN] 로그 파일들이 복원됩니다"
        else
            # 로그 디렉토리 생성
            mkdir -p "$LOG_DIR"
            
            # 로그 파일 복사
            if [[ -d "$temp_dir/var/log/ticket-alarm" ]]; then
                cp -r "$temp_dir/var/log/ticket-alarm"/* "$LOG_DIR/" 2>/dev/null || true
            elif [[ -d "$temp_dir/ticket-alarm" ]]; then
                cp -r "$temp_dir/ticket-alarm"/* "$LOG_DIR/" 2>/dev/null || true
            fi
            
            # 권한 설정
            chown -R www-data:www-data "$LOG_DIR" 2>/dev/null || true
            chmod -R 644 "$LOG_DIR"/*.log 2>/dev/null || true
            
            log_success "로그 파일 복원 완료"
        fi
    else
        log_warning "로그 백업 파일 압축 해제 실패"
    fi
    
    # 임시 디렉토리 정리
    rm -rf "$temp_dir"
}

# 시스템 설정 복원
restore_system_config() {
    if [[ "$RESTORE_CONFIG" != true ]]; then
        log_info "시스템 설정 복원을 건너뜁니다"
        return 0
    fi
    
    log_info "시스템 설정 복원 중..."
    
    # 시스템 설정 백업 파일 찾기
    local config_backup_file=$(echo "$BACKUP_FILE" | sed 's/app_data/system_config/')
    
    if [[ ! -f "$config_backup_file" ]]; then
        log_warning "시스템 설정 백업 파일을 찾을 수 없습니다: $config_backup_file"
        return 0
    fi
    
    # 임시 디렉토리 생성
    local temp_dir="/tmp/restore_config_$DATE"
    mkdir -p "$temp_dir"
    
    # 설정 백업 파일 압축 해제
    cd "$temp_dir"
    
    if [[ "$config_backup_file" == *.tar.gz ]]; then
        tar -xzf "$config_backup_file"
    else
        tar -xf "$config_backup_file"
    fi
    
    if [[ $? -eq 0 ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_info "[DRY RUN] 시스템 설정 파일들이 복원됩니다"
            find "$temp_dir" -type f
        else
            # 설정 파일들을 원래 위치로 복사
            find "$temp_dir" -type f | while read file; do
                local relative_path=${file#$temp_dir}
                local dest_file="$relative_path"
                local dest_dir=$(dirname "$dest_file")
                
                # 디렉토리 생성
                mkdir -p "$dest_dir"
                
                # 파일 복사
                cp "$file" "$dest_file"
                
                log_info "복원됨: $dest_file"
            done
            
            log_success "시스템 설정 복원 완료"
        fi
    else
        log_warning "시스템 설정 백업 파일 압축 해제 실패"
    fi
    
    # 임시 디렉토리 정리
    rm -rf "$temp_dir"
}

# 의존성 설치
install_dependencies() {
    log_info "의존성 설치 중..."
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 의존성이 설치됩니다"
        return 0
    fi
    
    cd "$APP_DIR"
    
    # Python 가상환경 생성 (없는 경우)
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log_success "Python 가상환경 생성됨"
    fi
    
    # 가상환경 활성화 및 의존성 설치
    source venv/bin/activate
    
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "Python 의존성 설치 완료"
    else
        log_warning "requirements.txt 파일이 없습니다"
    fi
}

# 설정 파일 검증
validate_config() {
    log_info "설정 파일 검증 중..."
    
    local config_file="$APP_DIR/config.json"
    
    if [[ ! -f "$config_file" ]]; then
        log_error "설정 파일이 없습니다: $config_file"
        return 1
    fi
    
    # JSON 문법 검사
    if ! python3 -m json.tool "$config_file" >/dev/null 2>&1; then
        log_error "설정 파일 JSON 문법 오류: $config_file"
        return 1
    fi
    
    # 필수 설정 확인
    local required_keys=("DISCORD_WEBHOOK_URL" "KEYWORDS" "CHECK_INTERVAL")
    
    for key in "${required_keys[@]}"; do
        if ! python3 -c "import json; config=json.load(open('$config_file')); exit(0 if '$key' in config else 1)" 2>/dev/null; then
            log_error "필수 설정이 없습니다: $key"
            return 1
        fi
    done
    
    log_success "설정 파일 검증 완료"
}

# 서비스 시작
start_services() {
    log_info "서비스 시작 중..."
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 서비스가 시작됩니다"
        return 0
    fi
    
    # Supervisor 서비스 시작
    if command -v supervisorctl >/dev/null 2>&1; then
        if [[ -f "/etc/supervisor/conf.d/ticket-alarm.conf" ]]; then
            supervisorctl reread
            supervisorctl update
            supervisorctl start ticket-alarm
            
            # 서비스 상태 확인
            sleep 5
            if supervisorctl status ticket-alarm | grep -q "RUNNING"; then
                log_success "Supervisor 서비스 시작됨"
            else
                log_error "Supervisor 서비스 시작 실패"
                return 1
            fi
        else
            log_warning "Supervisor 설정 파일이 없습니다"
        fi
    fi
    
    # Nginx 재시작 (필요한 경우)
    if command -v nginx >/dev/null 2>&1; then
        if [[ -f "/etc/nginx/sites-available/ticket-alarm" ]]; then
            nginx -t && systemctl reload nginx
            log_success "Nginx 설정 재로드됨"
        fi
    fi
}

# 복원 후 테스트
post_restore_test() {
    log_info "복원 후 테스트 수행 중..."
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] 복원 후 테스트가 수행됩니다"
        return 0
    fi
    
    cd "$APP_DIR"
    
    # 가상환경 활성화
    source venv/bin/activate 2>/dev/null || true
    
    # 기본 import 테스트
    if python3 -c "import monitor, discord_notifier" 2>/dev/null; then
        log_success "Python 모듈 import 테스트 통과"
    else
        log_error "Python 모듈 import 테스트 실패"
        return 1
    fi
    
    # 설정 파일 로드 테스트
    if python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
        log_success "설정 파일 로드 테스트 통과"
    else
        log_error "설정 파일 로드 테스트 실패"
        return 1
    fi
    
    # 디스코드 웹훅 테스트 (옵션)
    local webhook_url=$(python3 -c "import json; config=json.load(open('config.json')); print(config.get('DISCORD_WEBHOOK_URL', ''))" 2>/dev/null)
    if [[ -n "$webhook_url" ]]; then
        local test_message="🔄 시스템 복원 완료 테스트\n시간: $(date)\n상태: 정상"
        if curl -s -X POST -H "Content-Type: application/json" \
            -d "{\"content\":\"$test_message\"}" \
            "$webhook_url" &>/dev/null; then
            log_success "디스코드 웹훅 테스트 통과"
        else
            log_warning "디스코드 웹훅 테스트 실패 (네트워크 문제일 수 있음)"
        fi
    fi
    
    log_success "복원 후 테스트 완료"
}

# 복원 요약 생성
generate_restore_summary() {
    log_info "복원 요약 생성 중..."
    
    local summary_file="$LOG_DIR/restore_summary_$DATE.txt"
    
    {
        echo "티켓 알림 시스템 복원 요약"
        echo "복원 시간: $(date)"
        echo "백업 파일: $BACKUP_FILE"
        echo "복원 타입: $BACKUP_TYPE"
        echo "========================================"
        echo
        
        echo "복원된 구성 요소:"
        [[ "$RESTORE_DATA" == true ]] && echo "  ✓ 애플리케이션 데이터"
        [[ "$RESTORE_LOGS" == true ]] && echo "  ✓ 로그 파일"
        [[ "$RESTORE_CONFIG" == true ]] && echo "  ✓ 시스템 설정"
        echo
        
        echo "복원 옵션:"
        [[ "$FORCE_RESTORE" == true ]] && echo "  - 강제 복원 모드"
        [[ "$SKIP_BACKUP" == true ]] && echo "  - 사전 백업 건너뜀"
        [[ "$DRY_RUN" == true ]] && echo "  - 시뮬레이션 모드"
        echo
        
        echo "시스템 상태:"
        if command -v supervisorctl >/dev/null 2>&1; then
            echo "  Supervisor: $(supervisorctl status ticket-alarm 2>/dev/null | awk '{print $2}' || echo 'N/A')"
        fi
        
        if [[ -d "$APP_DIR" ]]; then
            echo "  애플리케이션 디렉토리: 존재"
            echo "  설정 파일: $([ -f "$APP_DIR/config.json" ] && echo '존재' || echo '없음')"
        fi
        
        echo
        echo "복원 로그: $RESTORE_LOG"
        
    } > "$summary_file"
    
    log_success "복원 요약 생성 완료: $summary_file"
}

# 메인 복원 함수
main() {
    log_info "복원 프로세스 시작"
    
    # 로그 디렉토리 생성
    mkdir -p "$LOG_DIR"
    
    # 검증 전용 모드
    if [[ "$VERIFY_ONLY" == true ]]; then
        if [[ -z "$BACKUP_FILE" ]]; then
            select_backup_file
        fi
        
        if verify_backup_file "$BACKUP_FILE"; then
            log_success "백업 파일 검증 완료: $BACKUP_FILE"
            exit 0
        else
            log_error "백업 파일 검증 실패: $BACKUP_FILE"
            exit 1
        fi
    fi
    
    # 백업 파일 선택 및 검증
    if [[ -z "$BACKUP_FILE" ]]; then
        select_backup_file
    fi
    
    if ! verify_backup_file "$BACKUP_FILE"; then
        log_error "백업 파일 검증 실패, 복원을 중단합니다"
        exit 1
    fi
    
    # 사용자 확인
    confirm_action "시스템을 복원하시겠습니까? 현재 데이터가 덮어쓰여집니다."
    
    # 복원 프로세스
    local restore_success=true
    
    # 현재 상태 백업
    backup_current_state
    
    # 서비스 중지
    stop_services
    
    # 데이터 복원
    if ! restore_application_data; then
        restore_success=false
    fi
    
    if ! restore_logs; then
        restore_success=false
    fi
    
    if ! restore_system_config; then
        restore_success=false
    fi
    
    # 의존성 설치
    if [[ "$restore_success" == true ]]; then
        install_dependencies
        
        # 설정 검증
        if ! validate_config; then
            restore_success=false
        fi
    fi
    
    # 서비스 시작
    if [[ "$restore_success" == true ]]; then
        start_services
        
        # 복원 후 테스트
        post_restore_test
    fi
    
    # 요약 생성
    generate_restore_summary
    
    if [[ "$restore_success" == true ]]; then
        log_success "복원 프로세스 완료"
        
        # 성공 알림
        if [[ -f "$APP_DIR/config.json" && "$DRY_RUN" != true ]]; then
            local webhook_url=$(python3 -c "import json; config=json.load(open('$APP_DIR/config.json')); print(config.get('DISCORD_WEBHOOK_URL', ''))" 2>/dev/null)
            if [[ -n "$webhook_url" ]]; then
                local message="🔄 시스템 복원 완료\n백업 파일: $(basename $BACKUP_FILE)\n시간: $(date)\n상태: 성공"
                curl -s -X POST -H "Content-Type: application/json" \
                    -d "{\"content\":\"$message\"}" \
                    "$webhook_url" &>/dev/null
            fi
        fi
        
        exit 0
    else
        log_error "복원 프로세스 중 오류 발생"
        exit 1
    fi
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi