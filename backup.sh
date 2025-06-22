#!/bin/bash

# 티켓 알림 시스템 백업 스크립트
# 데이터, 설정, 로그를 정기적으로 백업하고 관리합니다.

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
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" >> "$BACKUP_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1" >> "$BACKUP_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1" >> "$BACKUP_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >> "$BACKUP_LOG"
}

# 기본 설정
APP_DIR="/opt/ticket-alarm"
BACKUP_BASE_DIR="/opt/backups"
BACKUP_DIR="$BACKUP_BASE_DIR/ticket-alarm"
LOG_DIR="/var/log/ticket-alarm"
BACKUP_LOG="$LOG_DIR/backup.log"
DATE=$(date +%Y%m%d_%H%M%S)
DATE_ONLY=$(date +%Y%m%d)

# 백업 보존 기간 (일)
DAILY_RETENTION=7
WEEKLY_RETENTION=30
MONTHLY_RETENTION=365

# 압축 레벨 (1-9, 9가 최고 압축률)
COMPRESSION_LEVEL=6

# 백업 타입 설정
BACKUP_TYPE="daily"  # daily, weekly, monthly
FULL_BACKUP=false
INCREMENTAL_BACKUP=false
COMPRESSION=true
ENCRYPTION=false
REMOTE_BACKUP=false

# 명령행 인수 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            BACKUP_TYPE="$2"
            shift 2
            ;;
        --full)
            FULL_BACKUP=true
            shift
            ;;
        --incremental)
            INCREMENTAL_BACKUP=true
            shift
            ;;
        --no-compression)
            COMPRESSION=false
            shift
            ;;
        --encrypt)
            ENCRYPTION=true
            shift
            ;;
        --remote)
            REMOTE_BACKUP=true
            shift
            ;;
        -h|--help)
            echo "사용법: $0 [옵션]"
            echo "옵션:"
            echo "  --type TYPE        백업 타입 (daily, weekly, monthly)"
            echo "  --full             전체 백업 수행"
            echo "  --incremental      증분 백업 수행"
            echo "  --no-compression   압축 비활성화"
            echo "  --encrypt          백업 파일 암호화"
            echo "  --remote           원격 백업 수행"
            echo "  -h, --help         도움말 표시"
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

# 백업 디렉토리 생성
create_backup_directories() {
    log_info "백업 디렉토리 생성 중..."
    
    mkdir -p "$BACKUP_DIR/daily"
    mkdir -p "$BACKUP_DIR/weekly"
    mkdir -p "$BACKUP_DIR/monthly"
    mkdir -p "$BACKUP_DIR/incremental"
    mkdir -p "$LOG_DIR"
    
    # 권한 설정
    chmod 755 "$BACKUP_BASE_DIR"
    chmod 755 "$BACKUP_DIR"
    chmod 755 "$BACKUP_DIR"/*
    
    log_success "백업 디렉토리 생성 완료"
}

# 디스크 공간 확인
check_disk_space() {
    log_info "디스크 공간 확인 중..."
    
    local app_size=$(du -sm "$APP_DIR" 2>/dev/null | cut -f1 || echo "0")
    local log_size=$(du -sm "$LOG_DIR" 2>/dev/null | cut -f1 || echo "0")
    local total_size=$((app_size + log_size))
    
    # 압축을 고려한 예상 백업 크기 (약 30% 압축률 가정)
    local estimated_backup_size=$((total_size * 70 / 100))
    
    # 여유 공간 확인 (백업 크기의 2배 이상 필요)
    local required_space=$((estimated_backup_size * 2))
    local available_space=$(df "$BACKUP_DIR" | tail -1 | awk '{print $4}')
    local available_space_mb=$((available_space / 1024))
    
    log_info "예상 백업 크기: ${estimated_backup_size}MB"
    log_info "사용 가능한 공간: ${available_space_mb}MB"
    
    if [[ $available_space_mb -lt $required_space ]]; then
        log_error "디스크 공간이 부족합니다. 필요: ${required_space}MB, 사용가능: ${available_space_mb}MB"
        return 1
    fi
    
    log_success "디스크 공간 충분"
}

# 애플리케이션 데이터 백업
backup_application_data() {
    log_info "애플리케이션 데이터 백업 중..."
    
    local backup_file="$BACKUP_DIR/$BACKUP_TYPE/app_data_$DATE.tar"
    
    # 백업할 파일/디렉토리 목록
    local backup_items=(
        "config.json"
        "data/"
        "requirements.txt"
        "*.py"
        "crawlers/"
        "templates/"
        "static/"
    )
    
    # 제외할 파일/디렉토리 목록
    local exclude_items=(
        "--exclude=*.pyc"
        "--exclude=__pycache__"
        "--exclude=.git"
        "--exclude=venv"
        "--exclude=*.log"
        "--exclude=.pytest_cache"
    )
    
    cd "$APP_DIR"
    
    # tar 명령어 구성
    local tar_cmd="tar -cf \"$backup_file\""
    
    # 제외 항목 추가
    for exclude in "${exclude_items[@]}"; do
        tar_cmd="$tar_cmd $exclude"
    done
    
    # 백업 항목 추가
    for item in "${backup_items[@]}"; do
        if [[ -e "$item" ]]; then
            tar_cmd="$tar_cmd \"$item\""
        fi
    done
    
    # 백업 실행
    eval "$tar_cmd" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        local file_size=$(du -h "$backup_file" | cut -f1)
        log_success "애플리케이션 데이터 백업 완료: $backup_file ($file_size)"
        
        # 압축 (옵션)
        if [[ "$COMPRESSION" == true ]]; then
            compress_backup "$backup_file"
        fi
        
        return 0
    else
        log_error "애플리케이션 데이터 백업 실패"
        return 1
    fi
}

# 로그 파일 백업
backup_logs() {
    log_info "로그 파일 백업 중..."
    
    local backup_file="$BACKUP_DIR/$BACKUP_TYPE/logs_$DATE.tar"
    
    if [[ -d "$LOG_DIR" ]]; then
        tar -cf "$backup_file" -C "$(dirname $LOG_DIR)" "$(basename $LOG_DIR)" 2>/dev/null
        
        if [[ $? -eq 0 ]]; then
            local file_size=$(du -h "$backup_file" | cut -f1)
            log_success "로그 파일 백업 완료: $backup_file ($file_size)"
            
            # 압축 (옵션)
            if [[ "$COMPRESSION" == true ]]; then
                compress_backup "$backup_file"
            fi
            
            return 0
        else
            log_error "로그 파일 백업 실패"
            return 1
        fi
    else
        log_warning "로그 디렉토리가 존재하지 않습니다: $LOG_DIR"
        return 0
    fi
}

# 시스템 설정 백업
backup_system_config() {
    log_info "시스템 설정 백업 중..."
    
    local backup_file="$BACKUP_DIR/$BACKUP_TYPE/system_config_$DATE.tar"
    
    # 백업할 시스템 설정 파일들
    local config_files=(
        "/etc/supervisor/conf.d/ticket-alarm.conf"
        "/etc/nginx/sites-available/ticket-alarm"
        "/etc/logrotate.d/ticket-alarm"
    )
    
    local temp_dir="/tmp/system_config_$DATE"
    mkdir -p "$temp_dir"
    
    # 존재하는 설정 파일들을 임시 디렉토리에 복사
    local copied_files=0
    for config_file in "${config_files[@]}"; do
        if [[ -f "$config_file" ]]; then
            local dest_dir="$temp_dir$(dirname $config_file)"
            mkdir -p "$dest_dir"
            cp "$config_file" "$dest_dir/"
            copied_files=$((copied_files + 1))
        fi
    done
    
    if [[ $copied_files -gt 0 ]]; then
        tar -cf "$backup_file" -C "$temp_dir" . 2>/dev/null
        
        if [[ $? -eq 0 ]]; then
            local file_size=$(du -h "$backup_file" | cut -f1)
            log_success "시스템 설정 백업 완료: $backup_file ($file_size)"
            
            # 압축 (옵션)
            if [[ "$COMPRESSION" == true ]]; then
                compress_backup "$backup_file"
            fi
        else
            log_error "시스템 설정 백업 실패"
        fi
    else
        log_warning "백업할 시스템 설정 파일이 없습니다"
    fi
    
    # 임시 디렉토리 정리
    rm -rf "$temp_dir"
}

# 데이터베이스 백업 (향후 확장용)
backup_database() {
    log_info "데이터베이스 백업 건너뜀 (현재 파일 기반 시스템)"
    # 향후 PostgreSQL, MySQL 등 사용 시 구현
}

# 파일 압축
compress_backup() {
    local file_path="$1"
    
    if [[ ! -f "$file_path" ]]; then
        log_error "압축할 파일이 없습니다: $file_path"
        return 1
    fi
    
    log_info "파일 압축 중: $(basename $file_path)"
    
    # gzip 압축
    gzip -$COMPRESSION_LEVEL "$file_path"
    
    if [[ $? -eq 0 ]]; then
        local compressed_file="${file_path}.gz"
        local original_size=$(stat -c%s "$file_path" 2>/dev/null || echo "0")
        local compressed_size=$(stat -c%s "$compressed_file" 2>/dev/null || echo "0")
        
        if [[ $original_size -gt 0 ]]; then
            local compression_ratio=$((100 - (compressed_size * 100 / original_size)))
            log_success "압축 완료: $(basename $compressed_file) (압축률: ${compression_ratio}%)"
        else
            log_success "압축 완료: $(basename $compressed_file)"
        fi
    else
        log_error "압축 실패: $(basename $file_path)"
        return 1
    fi
}

# 백업 파일 암호화
encrypt_backup() {
    local file_path="$1"
    local password="$2"
    
    if [[ ! -f "$file_path" ]]; then
        log_error "암호화할 파일이 없습니다: $file_path"
        return 1
    fi
    
    if [[ -z "$password" ]]; then
        log_error "암호화 비밀번호가 제공되지 않았습니다"
        return 1
    fi
    
    log_info "파일 암호화 중: $(basename $file_path)"
    
    # OpenSSL을 사용한 AES-256 암호화
    openssl enc -aes-256-cbc -salt -in "$file_path" -out "${file_path}.enc" -pass pass:"$password"
    
    if [[ $? -eq 0 ]]; then
        rm "$file_path"  # 원본 파일 삭제
        log_success "암호화 완료: $(basename ${file_path}.enc)"
    else
        log_error "암호화 실패: $(basename $file_path)"
        return 1
    fi
}

# 증분 백업
perform_incremental_backup() {
    log_info "증분 백업 수행 중..."
    
    local last_backup_file="$BACKUP_DIR/incremental/last_backup_timestamp"
    local current_time=$(date +%s)
    
    # 마지막 백업 시간 확인
    local last_backup_time=0
    if [[ -f "$last_backup_file" ]]; then
        last_backup_time=$(cat "$last_backup_file")
    fi
    
    log_info "마지막 백업: $(date -d @$last_backup_time)"
    log_info "현재 시간: $(date -d @$current_time)"
    
    # 변경된 파일들 찾기
    local changed_files="$BACKUP_DIR/incremental/changed_files_$DATE.txt"
    
    cd "$APP_DIR"
    find . -type f -newer "$last_backup_file" 2>/dev/null > "$changed_files" || \
    find . -type f 2>/dev/null > "$changed_files"
    
    local file_count=$(wc -l < "$changed_files")
    
    if [[ $file_count -eq 0 ]]; then
        log_info "변경된 파일이 없습니다. 증분 백업을 건너뜁니다."
        rm "$changed_files"
        return 0
    fi
    
    log_info "변경된 파일 수: $file_count"
    
    # 증분 백업 파일 생성
    local backup_file="$BACKUP_DIR/incremental/incremental_$DATE.tar"
    
    tar -cf "$backup_file" -T "$changed_files" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        local file_size=$(du -h "$backup_file" | cut -f1)
        log_success "증분 백업 완료: $backup_file ($file_size)"
        
        # 압축
        if [[ "$COMPRESSION" == true ]]; then
            compress_backup "$backup_file"
        fi
        
        # 타임스탬프 업데이트
        echo "$current_time" > "$last_backup_file"
        
        # 변경된 파일 목록 보관
        mv "$changed_files" "$BACKUP_DIR/incremental/"
    else
        log_error "증분 백업 실패"
        rm "$changed_files"
        return 1
    fi
}

# 원격 백업
perform_remote_backup() {
    log_info "원격 백업 수행 중..."
    
    # 원격 백업 설정 (환경변수 또는 설정 파일에서 읽기)
    local remote_host="${BACKUP_REMOTE_HOST:-}"
    local remote_user="${BACKUP_REMOTE_USER:-}"
    local remote_path="${BACKUP_REMOTE_PATH:-}"
    
    if [[ -z "$remote_host" || -z "$remote_user" || -z "$remote_path" ]]; then
        log_warning "원격 백업 설정이 완전하지 않습니다. 건너뜁니다."
        return 0
    fi
    
    # rsync를 사용한 원격 동기화
    rsync -avz --delete "$BACKUP_DIR/" "$remote_user@$remote_host:$remote_path/"
    
    if [[ $? -eq 0 ]]; then
        log_success "원격 백업 완료: $remote_user@$remote_host:$remote_path"
    else
        log_error "원격 백업 실패"
        return 1
    fi
}

# 오래된 백업 파일 정리
cleanup_old_backups() {
    log_info "오래된 백업 파일 정리 중..."
    
    # 일일 백업 정리
    local deleted_count=0
    
    # 일일 백업 (7일 보관)
    find "$BACKUP_DIR/daily" -name "*.tar*" -mtime +$DAILY_RETENTION -type f | while read file; do
        rm "$file"
        log_info "삭제된 일일 백업: $(basename $file)"
        deleted_count=$((deleted_count + 1))
    done
    
    # 주간 백업 (30일 보관)
    find "$BACKUP_DIR/weekly" -name "*.tar*" -mtime +$WEEKLY_RETENTION -type f | while read file; do
        rm "$file"
        log_info "삭제된 주간 백업: $(basename $file)"
        deleted_count=$((deleted_count + 1))
    done
    
    # 월간 백업 (365일 보관)
    find "$BACKUP_DIR/monthly" -name "*.tar*" -mtime +$MONTHLY_RETENTION -type f | while read file; do
        rm "$file"
        log_info "삭제된 월간 백업: $(basename $file)"
        deleted_count=$((deleted_count + 1))
    done
    
    # 증분 백업 (30일 보관)
    find "$BACKUP_DIR/incremental" -name "*.tar*" -mtime +30 -type f | while read file; do
        rm "$file"
        log_info "삭제된 증분 백업: $(basename $file)"
        deleted_count=$((deleted_count + 1))
    done
    
    log_success "백업 정리 완료"
}

# 백업 검증
verify_backup() {
    local backup_file="$1"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "백업 파일이 존재하지 않습니다: $backup_file"
        return 1
    fi
    
    log_info "백업 파일 검증 중: $(basename $backup_file)"
    
    # tar 파일 무결성 검사
    if [[ "$backup_file" == *.tar.gz ]]; then
        gzip -t "$backup_file"
        if [[ $? -ne 0 ]]; then
            log_error "압축 파일 손상: $(basename $backup_file)"
            return 1
        fi
        
        # tar 내용 검사
        tar -tzf "$backup_file" > /dev/null
    elif [[ "$backup_file" == *.tar ]]; then
        tar -tf "$backup_file" > /dev/null
    fi
    
    if [[ $? -eq 0 ]]; then
        log_success "백업 파일 검증 성공: $(basename $backup_file)"
        return 0
    else
        log_error "백업 파일 검증 실패: $(basename $backup_file)"
        return 1
    fi
}

# 백업 통계 생성
generate_backup_stats() {
    log_info "백업 통계 생성 중..."
    
    local stats_file="$BACKUP_DIR/backup_stats_$DATE_ONLY.txt"
    
    {
        echo "티켓 알림 시스템 백업 통계"
        echo "생성 시간: $(date)"
        echo "백업 타입: $BACKUP_TYPE"
        echo "========================================"
        echo
        
        # 각 백업 타입별 통계
        for backup_type in daily weekly monthly incremental; do
            local type_dir="$BACKUP_DIR/$backup_type"
            if [[ -d "$type_dir" ]]; then
                local file_count=$(find "$type_dir" -name "*.tar*" -type f | wc -l)
                local total_size=$(du -sh "$type_dir" 2>/dev/null | cut -f1 || echo "0")
                
                echo "$backup_type 백업:"
                echo "  파일 수: $file_count"
                echo "  총 크기: $total_size"
                echo
            fi
        done
        
        # 전체 백업 디렉토리 크기
        local total_backup_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "0")
        echo "전체 백업 크기: $total_backup_size"
        
        # 디스크 사용량
        echo
        echo "디스크 사용량:"
        df -h "$BACKUP_DIR"
        
    } > "$stats_file"
    
    log_success "백업 통계 생성 완료: $stats_file"
}

# 메인 백업 함수
main() {
    log_info "백업 프로세스 시작 - 타입: $BACKUP_TYPE"
    
    # 사전 검사
    create_backup_directories
    
    if ! check_disk_space; then
        log_error "디스크 공간 부족으로 백업을 중단합니다"
        exit 1
    fi
    
    # 백업 수행
    local backup_success=true
    
    if [[ "$INCREMENTAL_BACKUP" == true ]]; then
        if ! perform_incremental_backup; then
            backup_success=false
        fi
    else
        # 전체 백업
        if ! backup_application_data; then
            backup_success=false
        fi
        
        if ! backup_logs; then
            backup_success=false
        fi
        
        if ! backup_system_config; then
            backup_success=false
        fi
        
        backup_database  # 현재는 건너뜀
    fi
    
    # 원격 백업 (옵션)
    if [[ "$REMOTE_BACKUP" == true ]]; then
        perform_remote_backup
    fi
    
    # 정리 작업
    cleanup_old_backups
    generate_backup_stats
    
    if [[ "$backup_success" == true ]]; then
        log_success "백업 프로세스 완료"
        
        # 성공 알림 (디스코드)
        if [[ -f "$APP_DIR/config.json" ]]; then
            local webhook_url=$(python3 -c "import json; config=json.load(open('$APP_DIR/config.json')); print(config.get('DISCORD_WEBHOOK_URL', ''))" 2>/dev/null)
            if [[ -n "$webhook_url" ]]; then
                local message="💾 백업 완료\n타입: $BACKUP_TYPE\n시간: $(date)\n상태: 성공"
                curl -s -X POST -H "Content-Type: application/json" \
                    -d "{\"content\":\"$message\"}" \
                    "$webhook_url" &>/dev/null
            fi
        fi
        
        exit 0
    else
        log_error "백업 프로세스 중 오류 발생"
        exit 1
    fi
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi