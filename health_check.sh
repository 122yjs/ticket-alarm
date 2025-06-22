#!/bin/bash

# 티켓 알림 시스템 헬스 체크 스크립트
# 시스템 상태를 종합적으로 점검하고 문제 발생 시 알림을 발송합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 설정
APP_DIR="/opt/ticket-alarm"
LOG_DIR="/var/log/ticket-alarm"
DATA_DIR="$APP_DIR/data"
CONFIG_FILE="$APP_DIR/config.json"
HEALTH_LOG="$LOG_DIR/health_check.log"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85
ALERT_THRESHOLD_DISK=85
MAX_LOG_SIZE_MB=100

# 로깅 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" >> "$HEALTH_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1" >> "$HEALTH_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1" >> "$HEALTH_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >> "$HEALTH_LOG"
}

# 헬스 체크 결과 저장
HEALTH_STATUS="OK"
HEALTH_ISSUES=()
HEALTH_WARNINGS=()

# 이슈 추가 함수
add_issue() {
    HEALTH_STATUS="CRITICAL"
    HEALTH_ISSUES+=("$1")
    log_error "$1"
}

add_warning() {
    if [[ "$HEALTH_STATUS" != "CRITICAL" ]]; then
        HEALTH_STATUS="WARNING"
    fi
    HEALTH_WARNINGS+=("$1")
    log_warning "$1"
}

# 시스템 리소스 체크
check_system_resources() {
    log_info "시스템 리소스 체크 시작"
    
    # CPU 사용률 체크
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 | cut -d',' -f1)
    cpu_usage=${cpu_usage%.*}  # 소수점 제거
    
    if [[ $cpu_usage -gt $ALERT_THRESHOLD_CPU ]]; then
        add_issue "CPU 사용률이 높습니다: ${cpu_usage}% (임계값: ${ALERT_THRESHOLD_CPU}%)"
    else
        log_success "CPU 사용률 정상: ${cpu_usage}%"
    fi
    
    # 메모리 사용률 체크
    local mem_info=$(free | grep Mem)
    local mem_total=$(echo $mem_info | awk '{print $2}')
    local mem_used=$(echo $mem_info | awk '{print $3}')
    local mem_usage=$((mem_used * 100 / mem_total))
    
    if [[ $mem_usage -gt $ALERT_THRESHOLD_MEMORY ]]; then
        add_issue "메모리 사용률이 높습니다: ${mem_usage}% (임계값: ${ALERT_THRESHOLD_MEMORY}%)"
    else
        log_success "메모리 사용률 정상: ${mem_usage}%"
    fi
    
    # 디스크 사용률 체크
    local disk_usage=$(df "$APP_DIR" | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    
    if [[ $disk_usage -gt $ALERT_THRESHOLD_DISK ]]; then
        add_issue "디스크 사용률이 높습니다: ${disk_usage}% (임계값: ${ALERT_THRESHOLD_DISK}%)"
    else
        log_success "디스크 사용률 정상: ${disk_usage}%"
    fi
    
    # 스왑 사용률 체크
    local swap_info=$(free | grep Swap)
    if [[ -n "$swap_info" ]]; then
        local swap_total=$(echo $swap_info | awk '{print $2}')
        local swap_used=$(echo $swap_info | awk '{print $3}')
        
        if [[ $swap_total -gt 0 ]]; then
            local swap_usage=$((swap_used * 100 / swap_total))
            if [[ $swap_usage -gt 50 ]]; then
                add_warning "스왑 사용률이 높습니다: ${swap_usage}%"
            else
                log_success "스왑 사용률 정상: ${swap_usage}%"
            fi
        fi
    fi
}

# 프로세스 상태 체크
check_processes() {
    log_info "프로세스 상태 체크 시작"
    
    # Supervisor 상태 확인
    if ! command -v supervisorctl &> /dev/null; then
        add_issue "supervisorctl 명령어를 찾을 수 없습니다"
        return
    fi
    
    local supervisor_status=$(sudo supervisorctl status ticket-alarm:* 2>/dev/null || echo "ERROR")
    
    if [[ "$supervisor_status" == "ERROR" ]]; then
        add_issue "Supervisor 상태를 확인할 수 없습니다"
        return
    fi
    
    # 각 프로세스 상태 확인
    local running_count=0
    local total_count=0
    
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            total_count=$((total_count + 1))
            if echo "$line" | grep -q "RUNNING"; then
                running_count=$((running_count + 1))
                local process_name=$(echo "$line" | awk '{print $1}')
                log_success "프로세스 실행 중: $process_name"
            else
                local process_name=$(echo "$line" | awk '{print $1}')
                local process_status=$(echo "$line" | awk '{print $2}')
                add_issue "프로세스 상태 이상: $process_name ($process_status)"
            fi
        fi
    done <<< "$supervisor_status"
    
    if [[ $running_count -eq $total_count ]] && [[ $total_count -gt 0 ]]; then
        log_success "모든 프로세스가 정상 실행 중입니다 ($running_count/$total_count)"
    elif [[ $total_count -eq 0 ]]; then
        add_issue "등록된 프로세스가 없습니다"
    else
        add_issue "일부 프로세스가 실행되지 않고 있습니다 ($running_count/$total_count)"
    fi
}

# 네트워크 연결 체크
check_network() {
    log_info "네트워크 연결 체크 시작"
    
    # 인터넷 연결 확인
    if ping -c 1 8.8.8.8 &> /dev/null; then
        log_success "인터넷 연결 정상"
    else
        add_issue "인터넷 연결 실패"
    fi
    
    # DNS 해결 확인
    if nslookup google.com &> /dev/null; then
        log_success "DNS 해결 정상"
    else
        add_issue "DNS 해결 실패"
    fi
    
    # 디스코드 연결 확인
    if curl -s --connect-timeout 10 https://discord.com &> /dev/null; then
        log_success "디스코드 연결 정상"
    else
        add_warning "디스코드 연결 실패 또는 느림"
    fi
    
    # 티켓 사이트 연결 확인
    local ticket_sites=("https://ticket.interpark.com" "https://www.yes24.com" "https://ticket.melon.com" "https://www.ticketlink.co.kr")
    local failed_sites=()
    
    for site in "${ticket_sites[@]}"; do
        if curl -s --connect-timeout 10 "$site" &> /dev/null; then
            log_success "사이트 연결 정상: $site"
        else
            failed_sites+=("$site")
            add_warning "사이트 연결 실패: $site"
        fi
    done
    
    if [[ ${#failed_sites[@]} -gt 2 ]]; then
        add_issue "다수의 티켓 사이트 연결 실패 (${#failed_sites[@]}개)"
    fi
}

# 웹 서비스 체크
check_web_service() {
    log_info "웹 서비스 체크 시작"
    
    # 포트 8000 확인
    if netstat -tuln | grep -q ":8000 "; then
        log_success "웹 서비스 포트 8000 리스닝 중"
        
        # HTTP 응답 확인
        local response_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 || echo "000")
        
        if [[ "$response_code" == "200" ]]; then
            log_success "웹 서비스 HTTP 응답 정상 (200)"
        else
            add_warning "웹 서비스 HTTP 응답 이상: $response_code"
        fi
    else
        add_issue "웹 서비스 포트 8000이 리스닝되지 않음"
    fi
    
    # Nginx 상태 확인
    if systemctl is-active nginx &> /dev/null; then
        log_success "Nginx 서비스 실행 중"
    else
        add_warning "Nginx 서비스가 실행되지 않음"
    fi
}

# 파일 시스템 체크
check_filesystem() {
    log_info "파일 시스템 체크 시작"
    
    # 필수 디렉토리 확인
    local required_dirs=("$APP_DIR" "$LOG_DIR" "$DATA_DIR")
    
    for dir in "${required_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            log_success "디렉토리 존재: $dir"
            
            # 쓰기 권한 확인
            if [[ -w "$dir" ]]; then
                log_success "디렉토리 쓰기 권한 정상: $dir"
            else
                add_warning "디렉토리 쓰기 권한 없음: $dir"
            fi
        else
            add_issue "필수 디렉토리 없음: $dir"
        fi
    done
    
    # 설정 파일 확인
    if [[ -f "$CONFIG_FILE" ]]; then
        log_success "설정 파일 존재: $CONFIG_FILE"
        
        # JSON 문법 확인
        if python3 -m json.tool "$CONFIG_FILE" &> /dev/null; then
            log_success "설정 파일 JSON 문법 정상"
        else
            add_issue "설정 파일 JSON 문법 오류"
        fi
    else
        add_issue "설정 파일 없음: $CONFIG_FILE"
    fi
    
    # 로그 파일 크기 확인
    local large_logs=()
    
    for log_file in "$LOG_DIR"/*.log; do
        if [[ -f "$log_file" ]]; then
            local file_size_mb=$(du -m "$log_file" | cut -f1)
            if [[ $file_size_mb -gt $MAX_LOG_SIZE_MB ]]; then
                large_logs+=("$log_file ($file_size_mb MB)")
                add_warning "로그 파일이 큽니다: $log_file ($file_size_mb MB)"
            fi
        fi
    done
    
    if [[ ${#large_logs[@]} -eq 0 ]]; then
        log_success "모든 로그 파일 크기 정상"
    fi
}

# 로그 분석
check_logs() {
    log_info "로그 분석 시작"
    
    local monitor_log="$LOG_DIR/monitor.out.log"
    local error_log="$LOG_DIR/monitor.err.log"
    
    # 최근 에러 확인 (지난 1시간)
    local recent_errors=0
    local recent_warnings=0
    
    if [[ -f "$error_log" ]]; then
        recent_errors=$(grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')\|$(date '+%Y-%m-%d %H')" "$error_log" 2>/dev/null | wc -l)
    fi
    
    if [[ -f "$monitor_log" ]]; then
        recent_warnings=$(grep -i "warning\|warn" "$monitor_log" | grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')\|$(date '+%Y-%m-%d %H')" 2>/dev/null | wc -l)
    fi
    
    if [[ $recent_errors -gt 10 ]]; then
        add_issue "최근 1시간 동안 에러가 많이 발생했습니다: ${recent_errors}개"
    elif [[ $recent_errors -gt 0 ]]; then
        add_warning "최근 1시간 동안 에러 발생: ${recent_errors}개"
    else
        log_success "최근 1시간 동안 에러 없음"
    fi
    
    if [[ $recent_warnings -gt 20 ]]; then
        add_warning "최근 1시간 동안 경고가 많이 발생했습니다: ${recent_warnings}개"
    fi
    
    # 크롤링 성공률 확인 (지난 24시간)
    if [[ -f "$monitor_log" ]]; then
        local crawl_success=$(grep "크롤링 완료" "$monitor_log" | grep "$(date -d '1 day ago' '+%Y-%m-%d')\|$(date '+%Y-%m-%d')" 2>/dev/null | wc -l)
        local crawl_failure=$(grep "크롤링 실패" "$monitor_log" | grep "$(date -d '1 day ago' '+%Y-%m-%d')\|$(date '+%Y-%m-%d')" 2>/dev/null | wc -l)
        
        if [[ $((crawl_success + crawl_failure)) -gt 0 ]]; then
            local success_rate=$((crawl_success * 100 / (crawl_success + crawl_failure)))
            
            if [[ $success_rate -lt 70 ]]; then
                add_issue "크롤링 성공률이 낮습니다: ${success_rate}% (성공: $crawl_success, 실패: $crawl_failure)"
            elif [[ $success_rate -lt 90 ]]; then
                add_warning "크롤링 성공률이 다소 낮습니다: ${success_rate}% (성공: $crawl_success, 실패: $crawl_failure)"
            else
                log_success "크롤링 성공률 양호: ${success_rate}% (성공: $crawl_success, 실패: $crawl_failure)"
            fi
        else
            add_warning "최근 24시간 동안 크롤링 기록이 없습니다"
        fi
    fi
}

# 디스코드 웹훅 테스트
check_discord_webhook() {
    log_info "디스코드 웹훅 테스트 시작"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        add_warning "설정 파일이 없어 웹훅 테스트를 건너뜁니다"
        return
    fi
    
    local webhook_url=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config.get('DISCORD_WEBHOOK_URL', ''))" 2>/dev/null)
    
    if [[ -z "$webhook_url" ]]; then
        add_warning "디스코드 웹훅 URL이 설정되지 않았습니다"
        return
    fi
    
    # 테스트 메시지 전송
    local test_message="🔍 헬스 체크 테스트 메시지 - $(date)"
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"$test_message\"}" \
        "$webhook_url" 2>/dev/null || echo "000")
    
    if [[ "$response_code" == "204" ]]; then
        log_success "디스코드 웹훅 테스트 성공"
    else
        add_issue "디스코드 웹훅 테스트 실패 (응답 코드: $response_code)"
    fi
}

# 알림 발송
send_alert() {
    local alert_level="$1"
    local message="$2"
    
    # 로그에 기록
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ALERT-$alert_level] $message" >> "$HEALTH_LOG"
    
    # 디스코드 알림 (설정된 경우)
    if [[ -f "$CONFIG_FILE" ]]; then
        local webhook_url=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config.get('DISCORD_WEBHOOK_URL', ''))" 2>/dev/null)
        
        if [[ -n "$webhook_url" ]]; then
            local emoji
            case $alert_level in
                "CRITICAL") emoji="🚨" ;;
                "WARNING") emoji="⚠️" ;;
                *) emoji="ℹ️" ;;
            esac
            
            local discord_message="$emoji **[$alert_level] 티켓 알림 시스템**\n$message\n\n시간: $(date)"
            
            curl -s -X POST -H "Content-Type: application/json" \
                -d "{\"content\":\"$discord_message\"}" \
                "$webhook_url" &>/dev/null
        fi
    fi
    
    # 이메일 알림 (설정된 경우)
    if command -v mail &> /dev/null; then
        echo "$message" | mail -s "[$alert_level] 티켓 알림 시스템 헬스 체크" admin@example.com 2>/dev/null || true
    fi
}

# 결과 요약 출력
print_summary() {
    echo
    echo "==========================================="
    echo "         헬스 체크 결과 요약"
    echo "==========================================="
    echo "시간: $(date)"
    echo "전체 상태: $HEALTH_STATUS"
    echo
    
    if [[ ${#HEALTH_ISSUES[@]} -gt 0 ]]; then
        echo "🚨 심각한 문제 (${#HEALTH_ISSUES[@]}개):"
        for issue in "${HEALTH_ISSUES[@]}"; do
            echo "  - $issue"
        done
        echo
    fi
    
    if [[ ${#HEALTH_WARNINGS[@]} -gt 0 ]]; then
        echo "⚠️ 경고 사항 (${#HEALTH_WARNINGS[@]}개):"
        for warning in "${HEALTH_WARNINGS[@]}"; do
            echo "  - $warning"
        done
        echo
    fi
    
    if [[ "$HEALTH_STATUS" == "OK" ]]; then
        echo "✅ 모든 시스템이 정상 작동 중입니다."
    fi
    
    echo "==========================================="
}

# 메인 함수
main() {
    # 로그 디렉토리 생성
    mkdir -p "$LOG_DIR"
    
    log_info "티켓 알림 시스템 헬스 체크 시작"
    
    # 각 체크 수행
    check_system_resources
    check_processes
    check_network
    check_web_service
    check_filesystem
    check_logs
    check_discord_webhook
    
    # 결과 요약
    print_summary
    
    # 알림 발송
    if [[ "$HEALTH_STATUS" == "CRITICAL" ]]; then
        local issues_text=$(printf "%s\n" "${HEALTH_ISSUES[@]}")
        send_alert "CRITICAL" "시스템에 심각한 문제가 발생했습니다:\n$issues_text"
    elif [[ "$HEALTH_STATUS" == "WARNING" ]]; then
        local warnings_text=$(printf "%s\n" "${HEALTH_WARNINGS[@]}")
        send_alert "WARNING" "시스템에 경고 사항이 있습니다:\n$warnings_text"
    fi
    
    log_info "헬스 체크 완료 - 상태: $HEALTH_STATUS"
    
    # 종료 코드 설정
    case $HEALTH_STATUS in
        "OK") exit 0 ;;
        "WARNING") exit 1 ;;
        "CRITICAL") exit 2 ;;
    esac
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi