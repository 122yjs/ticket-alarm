#!/bin/bash

# 티켓 알림 시스템 설치 스크립트
# Ubuntu/Debian 기반 시스템에서 전체 시스템을 자동으로 설치합니다.

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
WEB_PORT=8000
GIT_REPO="https://github.com/yourusername/ticket-alarm.git"  # 실제 저장소로 변경
BRANCH="main"

# 설치 옵션
INSTALL_NGINX=true
INSTALL_SUPERVISOR=true
INSTALL_SSL=false
SKIP_DEPENDENCIES=false
DEVELOPMENT_MODE=false
FORCE_INSTALL=false

# 명령행 인수 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        --app-dir)
            APP_DIR="$2"
            shift 2
            ;;
        --port)
            WEB_PORT="$2"
            shift 2
            ;;
        --git-repo)
            GIT_REPO="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --no-nginx)
            INSTALL_NGINX=false
            shift
            ;;
        --no-supervisor)
            INSTALL_SUPERVISOR=false
            shift
            ;;
        --ssl)
            INSTALL_SSL=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPENDENCIES=true
            shift
            ;;
        --dev)
            DEVELOPMENT_MODE=true
            shift
            ;;
        --force)
            FORCE_INSTALL=true
            shift
            ;;
        -h|--help)
            echo "사용법: $0 [옵션]"
            echo "옵션:"
            echo "  --app-dir DIR      애플리케이션 설치 디렉토리 (기본: /opt/ticket-alarm)"
            echo "  --port PORT        웹 서버 포트 (기본: 8000)"
            echo "  --git-repo URL     Git 저장소 URL"
            echo "  --branch BRANCH    Git 브랜치 (기본: main)"
            echo "  --no-nginx         Nginx 설치 건너뛰기"
            echo "  --no-supervisor    Supervisor 설치 건너뛰기"
            echo "  --ssl              SSL 인증서 설치"
            echo "  --skip-deps        의존성 설치 건너뛰기"
            echo "  --dev              개발 모드 설치"
            echo "  --force            강제 설치 (기존 설치 덮어쓰기)"
            echo "  -h, --help         도움말 표시"
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

# 루트 권한 확인
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "이 스크립트는 루트 권한으로 실행해야 합니다"
        log_info "다음 명령어로 실행하세요: sudo $0"
        exit 1
    fi
}

# 시스템 정보 확인
check_system() {
    log_info "시스템 정보 확인 중..."
    
    # OS 확인
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        log_info "OS: $NAME $VERSION"
        
        # Ubuntu/Debian 계열인지 확인
        if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
            log_warning "이 스크립트는 Ubuntu/Debian 기반 시스템용입니다"
            log_warning "다른 배포판에서는 수동 설치가 필요할 수 있습니다"
        fi
    else
        log_warning "OS 정보를 확인할 수 없습니다"
    fi
    
    # 아키텍처 확인
    local arch=$(uname -m)
    log_info "아키텍처: $arch"
    
    # 메모리 확인
    local memory=$(free -h | awk '/^Mem:/ {print $2}')
    log_info "메모리: $memory"
    
    # 디스크 공간 확인
    local disk=$(df -h / | awk 'NR==2 {print $4}')
    log_info "사용 가능한 디스크 공간: $disk"
    
    # 최소 요구사항 확인
    local memory_mb=$(free -m | awk '/^Mem:/ {print $2}')
    if [[ $memory_mb -lt 1024 ]]; then
        log_warning "메모리가 1GB 미만입니다. 성능에 영향을 줄 수 있습니다."
    fi
    
    local disk_gb=$(df --output=avail / | tail -1 | awk '{print int($1/1024/1024)}')
    if [[ $disk_gb -lt 5 ]]; then
        log_error "디스크 공간이 5GB 미만입니다. 설치를 중단합니다."
        exit 1
    fi
}

# 기존 설치 확인
check_existing_installation() {
    if [[ -d "$APP_DIR" && "$FORCE_INSTALL" != true ]]; then
        log_warning "기존 설치가 발견되었습니다: $APP_DIR"
        read -p "기존 설치를 덮어쓰시겠습니까? (y/N): " -n 1 -r
        echo
        
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "설치를 취소했습니다"
            exit 0
        fi
        
        log_info "기존 설치를 백업하고 새로 설치합니다"
        
        # 기존 설치 백업
        local backup_name="${APP_NAME}_backup_$(date +%Y%m%d_%H%M%S)"
        mv "$APP_DIR" "/tmp/$backup_name"
        log_success "기존 설치를 /tmp/$backup_name 으로 백업했습니다"
    fi
}

# 시스템 패키지 업데이트
update_system() {
    log_info "시스템 패키지 업데이트 중..."
    
    apt-get update -qq
    apt-get upgrade -y -qq
    
    log_success "시스템 패키지 업데이트 완료"
}

# 기본 의존성 설치
install_dependencies() {
    if [[ "$SKIP_DEPENDENCIES" == true ]]; then
        log_info "의존성 설치를 건너뜁니다"
        return 0
    fi
    
    log_info "기본 의존성 설치 중..."
    
    # 필수 패키지 목록
    local packages=(
        "python3"
        "python3-pip"
        "python3-venv"
        "python3-dev"
        "git"
        "curl"
        "wget"
        "unzip"
        "build-essential"
        "libssl-dev"
        "libffi-dev"
        "libxml2-dev"
        "libxslt1-dev"
        "zlib1g-dev"
        "libjpeg-dev"
        "libpng-dev"
        "cron"
        "logrotate"
    )
    
    # Nginx 설치 (옵션)
    if [[ "$INSTALL_NGINX" == true ]]; then
        packages+=("nginx")
    fi
    
    # Supervisor 설치 (옵션)
    if [[ "$INSTALL_SUPERVISOR" == true ]]; then
        packages+=("supervisor")
    fi
    
    # SSL 관련 패키지 (옵션)
    if [[ "$INSTALL_SSL" == true ]]; then
        packages+=("certbot" "python3-certbot-nginx")
    fi
    
    # 패키지 설치
    apt-get install -y "${packages[@]}"
    
    log_success "기본 의존성 설치 완료"
}

# 사용자 및 디렉토리 생성
setup_directories() {
    log_info "디렉토리 및 사용자 설정 중..."
    
    # 시스템 사용자 확인/생성
    if ! id "$SYSTEM_USER" &>/dev/null; then
        useradd --system --shell /bin/false --home-dir "$APP_DIR" "$SYSTEM_USER"
        log_success "시스템 사용자 생성됨: $SYSTEM_USER"
    else
        log_info "시스템 사용자가 이미 존재합니다: $SYSTEM_USER"
    fi
    
    # 디렉토리 생성
    local directories=(
        "$APP_DIR"
        "$LOG_DIR"
        "$BACKUP_DIR"
        "$APP_DIR/data"
        "$APP_DIR/static"
        "$APP_DIR/templates"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        chown "$SYSTEM_USER:$SYSTEM_GROUP" "$dir"
        chmod 755 "$dir"
    done
    
    log_success "디렉토리 설정 완료"
}

# 애플리케이션 코드 다운로드
download_application() {
    log_info "애플리케이션 코드 다운로드 중..."
    
    cd "$(dirname $APP_DIR)"
    
    if [[ -n "$GIT_REPO" ]]; then
        # Git 저장소에서 클론
        git clone -b "$BRANCH" "$GIT_REPO" "$(basename $APP_DIR)"
        
        cd "$APP_DIR"
        
        # Git 정보 표시
        local commit_hash=$(git rev-parse HEAD)
        local commit_date=$(git show -s --format=%ci HEAD)
        
        log_info "Git 커밋: $commit_hash"
        log_info "커밋 날짜: $commit_date"
    else
        # 현재 디렉토리에서 파일 복사 (개발 모드)
        log_info "로컬 파일에서 복사 중..."
        
        local source_dir="$(pwd)"
        
        # Python 파일들 복사
        find "$source_dir" -name "*.py" -exec cp {} "$APP_DIR/" \;
        
        # 설정 파일들 복사
        [[ -f "$source_dir/requirements.txt" ]] && cp "$source_dir/requirements.txt" "$APP_DIR/"
        [[ -f "$source_dir/config.json.example" ]] && cp "$source_dir/config.json.example" "$APP_DIR/"
        [[ -f "$source_dir/production.env.example" ]] && cp "$source_dir/production.env.example" "$APP_DIR/"
        
        # 스크립트 파일들 복사
        find "$source_dir" -name "*.sh" -exec cp {} "$APP_DIR/" \;
        
        # 문서 파일들 복사
        find "$source_dir" -name "*.md" -exec cp {} "$APP_DIR/" \;
    fi
    
    # 권한 설정
    chown -R "$SYSTEM_USER:$SYSTEM_GROUP" "$APP_DIR"
    find "$APP_DIR" -type f -name "*.py" -exec chmod 644 {} \;
    find "$APP_DIR" -type f -name "*.sh" -exec chmod 755 {} \;
    
    log_success "애플리케이션 코드 다운로드 완료"
}

# Python 가상환경 설정
setup_python_environment() {
    log_info "Python 가상환경 설정 중..."
    
    cd "$APP_DIR"
    
    # 가상환경 생성
    sudo -u "$SYSTEM_USER" python3 -m venv venv
    
    # 가상환경 활성화 및 pip 업그레이드
    sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && pip install --upgrade pip"
    
    # requirements.txt가 있으면 의존성 설치
    if [[ -f "requirements.txt" ]]; then
        log_info "Python 의존성 설치 중..."
        sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && pip install -r requirements.txt"
        log_success "Python 의존성 설치 완료"
    else
        log_warning "requirements.txt 파일이 없습니다"
        
        # 기본 의존성 설치
        local basic_packages=("requests" "beautifulsoup4" "lxml" "flask" "gunicorn")
        
        for package in "${basic_packages[@]}"; do
            sudo -u "$SYSTEM_USER" bash -c "source venv/bin/activate && pip install $package"
        done
        
        log_info "기본 Python 패키지 설치 완료"
    fi
    
    log_success "Python 가상환경 설정 완료"
}

# 설정 파일 생성
setup_configuration() {
    log_info "설정 파일 생성 중..."
    
    cd "$APP_DIR"
    
    # config.json 생성
    if [[ ! -f "config.json" ]]; then
        if [[ -f "config.json.example" ]]; then
            cp "config.json.example" "config.json"
            log_info "config.json.example에서 config.json을 생성했습니다"
        else
            # 기본 설정 파일 생성
            cat > "config.json" << EOF
{
    "DISCORD_WEBHOOK_URL": "",
    "KEYWORDS": ["개발자", "프로그래머", "백엔드", "프론트엔드"],
    "PRIORITY_KEYWORDS": ["시니어", "리드", "테크리드"],
    "CHECK_INTERVAL": 300,
    "notification_delay": 2,
    "max_notifications_per_cycle": 10,
    "WEB_PORT": $WEB_PORT,
    "LOG_LEVEL": "INFO"
}
EOF
            log_info "기본 config.json을 생성했습니다"
        fi
        
        # 권한 설정 (민감한 정보 포함)
        chmod 600 "config.json"
        chown "$SYSTEM_USER:$SYSTEM_GROUP" "config.json"
    fi
    
    # .env 파일 생성
    if [[ ! -f ".env" && -f "production.env.example" ]]; then
        cp "production.env.example" ".env"
        
        # 기본값 설정
        sed -i "s|APP_DIR=.*|APP_DIR=$APP_DIR|" ".env"
        sed -i "s|LOG_DIR=.*|LOG_DIR=$LOG_DIR|" ".env"
        sed -i "s|BACKUP_DIR=.*|BACKUP_DIR=$BACKUP_DIR|" ".env"
        sed -i "s|WEB_PORT=.*|WEB_PORT=$WEB_PORT|" ".env"
        
        if [[ "$DEVELOPMENT_MODE" == true ]]; then
            sed -i "s|ENVIRONMENT=.*|ENVIRONMENT=development|" ".env"
            sed -i "s|DEBUG=.*|DEBUG=true|" ".env"
            sed -i "s|LOG_LEVEL=.*|LOG_LEVEL=DEBUG|" ".env"
        fi
        
        chmod 600 ".env"
        chown "$SYSTEM_USER:$SYSTEM_GROUP" ".env"
        
        log_info ".env 파일을 생성했습니다"
    fi
    
    log_success "설정 파일 생성 완료"
}

# Nginx 설정
setup_nginx() {
    if [[ "$INSTALL_NGINX" != true ]]; then
        log_info "Nginx 설정을 건너뜁니다"
        return 0
    fi
    
    log_info "Nginx 설정 중..."
    
    # Nginx 설정 파일 생성
    cat > "/etc/nginx/sites-available/$APP_NAME" << EOF
server {
    listen 80;
    server_name _;
    
    client_max_body_size 10M;
    
    # 정적 파일 서빙
    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 애플리케이션 프록시
    location / {
        proxy_pass http://127.0.0.1:$WEB_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 타임아웃 설정
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # 헬스 체크
    location /health {
        proxy_pass http://127.0.0.1:$WEB_PORT/health;
        access_log off;
    }
    
    # 로그 설정
    access_log $LOG_DIR/nginx_access.log;
    error_log $LOG_DIR/nginx_error.log;
}
EOF
    
    # 사이트 활성화
    ln -sf "/etc/nginx/sites-available/$APP_NAME" "/etc/nginx/sites-enabled/$APP_NAME"
    
    # 기본 사이트 비활성화
    rm -f "/etc/nginx/sites-enabled/default"
    
    # Nginx 설정 테스트
    nginx -t
    
    # Nginx 재시작
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx 설정 완료"
}

# Supervisor 설정
setup_supervisor() {
    if [[ "$INSTALL_SUPERVISOR" != true ]]; then
        log_info "Supervisor 설정을 건너뜁니다"
        return 0
    fi
    
    log_info "Supervisor 설정 중..."
    
    # Supervisor 설정 파일 생성
    cat > "/etc/supervisor/conf.d/$APP_NAME.conf" << EOF
[program:$APP_NAME]
command=$APP_DIR/venv/bin/python $APP_DIR/monitor.py
directory=$APP_DIR
user=$SYSTEM_USER
autostart=true
autorestart=true
startretries=3
redirect_stderr=true
stdout_logfile=$LOG_DIR/supervisor.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PATH="$APP_DIR/venv/bin"

[program:${APP_NAME}-web]
command=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:$WEB_PORT --workers 3 --timeout 30 app:app
directory=$APP_DIR
user=$SYSTEM_USER
autostart=true
autorestart=true
startretries=3
redirect_stderr=true
stdout_logfile=$LOG_DIR/web.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PATH="$APP_DIR/venv/bin"
EOF
    
    # Supervisor 설정 재로드
    supervisorctl reread
    supervisorctl update
    
    # 서비스 시작
    supervisorctl start "$APP_NAME:*"
    
    # Supervisor 자동 시작 설정
    systemctl enable supervisor
    
    log_success "Supervisor 설정 완료"
}

# 로그 로테이션 설정
setup_log_rotation() {
    log_info "로그 로테이션 설정 중..."
    
    # logrotate 설정 파일 생성
    cat > "/etc/logrotate.d/$APP_NAME" << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $SYSTEM_USER $SYSTEM_GROUP
    postrotate
        supervisorctl restart $APP_NAME:* > /dev/null 2>&1 || true
    endscript
}
EOF
    
    log_success "로그 로테이션 설정 완료"
}

# 크론탭 설정
setup_crontab() {
    log_info "크론탭 설정 중..."
    
    # 백업 크론 작업 추가
    local cron_file="/etc/cron.d/$APP_NAME"
    
    cat > "$cron_file" << EOF
# 티켓 알림 시스템 크론 작업

# 매일 새벽 2시 백업
0 2 * * * $SYSTEM_USER cd $APP_DIR && ./backup.sh --type daily

# 매주 일요일 새벽 3시 주간 백업
0 3 * * 0 $SYSTEM_USER cd $APP_DIR && ./backup.sh --type weekly

# 매월 1일 새벽 4시 월간 백업
0 4 1 * * $SYSTEM_USER cd $APP_DIR && ./backup.sh --type monthly

# 5분마다 헬스 체크
*/5 * * * * $SYSTEM_USER cd $APP_DIR && ./health_check.sh --quiet

# 매시간 로그 정리
0 * * * * $SYSTEM_USER find $LOG_DIR -name "*.log" -size +100M -exec truncate -s 50M {} \;
EOF
    
    chmod 644 "$cron_file"
    
    # cron 서비스 재시작
    systemctl restart cron
    
    log_success "크론탭 설정 완료"
}

# 방화벽 설정
setup_firewall() {
    log_info "방화벽 설정 중..."
    
    # UFW가 설치되어 있는지 확인
    if command -v ufw >/dev/null 2>&1; then
        # HTTP 포트 허용
        ufw allow 80/tcp
        
        # HTTPS 포트 허용 (SSL 사용 시)
        if [[ "$INSTALL_SSL" == true ]]; then
            ufw allow 443/tcp
        fi
        
        # SSH 포트 허용 (이미 허용되어 있을 수 있음)
        ufw allow ssh
        
        log_success "방화벽 설정 완료"
    else
        log_warning "UFW가 설치되어 있지 않습니다. 수동으로 방화벽을 설정하세요."
    fi
}

# SSL 인증서 설정
setup_ssl() {
    if [[ "$INSTALL_SSL" != true ]]; then
        log_info "SSL 설정을 건너뜁니다"
        return 0
    fi
    
    log_info "SSL 인증서 설정을 위해서는 도메인이 필요합니다"
    log_info "다음 명령어로 SSL 인증서를 설정하세요:"
    log_info "certbot --nginx -d yourdomain.com"
    
    # 자동 갱신 설정
    if ! crontab -l | grep -q "certbot renew"; then
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
        log_success "SSL 인증서 자동 갱신 설정 완료"
    fi
}

# 설치 후 테스트
post_install_test() {
    log_info "설치 후 테스트 수행 중..."
    
    # 서비스 상태 확인
    if [[ "$INSTALL_SUPERVISOR" == true ]]; then
        if supervisorctl status "$APP_NAME:*" | grep -q "RUNNING"; then
            log_success "Supervisor 서비스 실행 중"
        else
            log_error "Supervisor 서비스 실행 실패"
            return 1
        fi
    fi
    
    # Nginx 상태 확인
    if [[ "$INSTALL_NGINX" == true ]]; then
        if systemctl is-active --quiet nginx; then
            log_success "Nginx 서비스 실행 중"
        else
            log_error "Nginx 서비스 실행 실패"
            return 1
        fi
    fi
    
    # 웹 서버 응답 확인
    sleep 5  # 서비스 시작 대기
    
    if curl -s "http://localhost:$WEB_PORT/health" >/dev/null; then
        log_success "웹 서버 응답 정상"
    else
        log_warning "웹 서버 응답 확인 실패 (아직 시작 중일 수 있음)"
    fi
    
    # 로그 파일 확인
    if [[ -f "$LOG_DIR/supervisor.log" ]]; then
        log_success "로그 파일 생성 확인"
    else
        log_warning "로그 파일이 아직 생성되지 않았습니다"
    fi
    
    log_success "설치 후 테스트 완료"
}

# 설치 요약 출력
print_installation_summary() {
    log_success "=== 설치 완료 ==="
    echo
    log_info "애플리케이션 디렉토리: $APP_DIR"
    log_info "로그 디렉토리: $LOG_DIR"
    log_info "백업 디렉토리: $BACKUP_DIR"
    log_info "웹 포트: $WEB_PORT"
    echo
    
    if [[ "$INSTALL_NGINX" == true ]]; then
        log_info "웹 접속: http://your-server-ip/"
    else
        log_info "웹 접속: http://your-server-ip:$WEB_PORT/"
    fi
    
    echo
    log_info "다음 단계:"
    log_info "1. $APP_DIR/config.json 파일을 편집하여 디스코드 웹훅 URL을 설정하세요"
    log_info "2. 키워드를 원하는 대로 수정하세요"
    log_info "3. 서비스 상태 확인: supervisorctl status"
    log_info "4. 로그 확인: tail -f $LOG_DIR/supervisor.log"
    
    if [[ "$INSTALL_SSL" == true ]]; then
        echo
        log_info "SSL 인증서 설정:"
        log_info "certbot --nginx -d yourdomain.com"
    fi
    
    echo
    log_info "유용한 명령어:"
    log_info "- 서비스 재시작: supervisorctl restart $APP_NAME:*"
    log_info "- 백업 실행: cd $APP_DIR && ./backup.sh"
    log_info "- 헬스 체크: cd $APP_DIR && ./health_check.sh"
    log_info "- 로그 확인: tail -f $LOG_DIR/*.log"
}

# 메인 설치 함수
main() {
    log_info "티켓 알림 시스템 설치를 시작합니다"
    
    # 사전 검사
    check_root
    check_system
    check_existing_installation
    
    # 시스템 준비
    update_system
    install_dependencies
    
    # 애플리케이션 설치
    setup_directories
    download_application
    setup_python_environment
    setup_configuration
    
    # 서비스 설정
    setup_nginx
    setup_supervisor
    setup_log_rotation
    setup_crontab
    setup_firewall
    setup_ssl
    
    # 설치 후 작업
    post_install_test
    print_installation_summary
    
    log_success "설치가 완료되었습니다!"
}

# 스크립트 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi