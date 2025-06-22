#!/bin/bash

# 티켓 알림 시스템 환경 설정 스크립트
# Ubuntu/Debian 기반 시스템용

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# 진행률 표시
show_progress() {
    local current=$1
    local total=$2
    local desc="$3"
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r${CYAN}[%3d%%]${NC} [" "$percent"
    printf "%*s" "$filled" | tr ' ' '█'
    printf "%*s" "$empty" | tr ' ' '░'
    printf "] %s" "$desc"
    
    if [ "$current" -eq "$total" ]; then
        echo
    fi
}

# 시스템 정보 확인
check_system() {
    log_step "시스템 정보 확인"
    
    # OS 확인
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        log_info "운영체제: $NAME $VERSION"
    else
        log_error "지원되지 않는 운영체제입니다"
        exit 1
    fi
    
    # 아키텍처 확인
    ARCH=$(uname -m)
    log_info "아키텍처: $ARCH"
    
    # 메모리 확인
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    log_info "메모리: ${MEMORY_GB}GB"
    
    if [ "$MEMORY_GB" -lt 1 ]; then
        log_warning "메모리가 부족할 수 있습니다 (권장: 2GB 이상)"
    fi
    
    # 디스크 공간 확인
    DISK_AVAILABLE=$(df / | awk 'NR==2 {print int($4/1024/1024)}')
    log_info "사용 가능한 디스크 공간: ${DISK_AVAILABLE}GB"
    
    if [ "$DISK_AVAILABLE" -lt 5 ]; then
        log_error "디스크 공간이 부족합니다 (최소 5GB 필요)"
        exit 1
    fi
}

# 루트 권한 확인
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "이 스크립트는 루트 권한이 필요합니다"
        log_info "다음 명령으로 실행하세요: sudo $0"
        exit 1
    fi
}

# 패키지 관리자 확인
check_package_manager() {
    if command -v apt-get >/dev/null 2>&1; then
        PKG_MANAGER="apt-get"
        PKG_UPDATE="apt-get update"
        PKG_INSTALL="apt-get install -y"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MANAGER="yum"
        PKG_UPDATE="yum update -y"
        PKG_INSTALL="yum install -y"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_MANAGER="dnf"
        PKG_UPDATE="dnf update -y"
        PKG_INSTALL="dnf install -y"
    else
        log_error "지원되는 패키지 관리자를 찾을 수 없습니다"
        exit 1
    fi
    
    log_info "패키지 관리자: $PKG_MANAGER"
}

# 시스템 패키지 업데이트
update_system() {
    log_step "시스템 패키지 업데이트"
    
    show_progress 1 3 "패키지 목록 업데이트"
    $PKG_UPDATE >/dev/null 2>&1
    
    show_progress 2 3 "시스템 패키지 업그레이드"
    if [ "$PKG_MANAGER" = "apt-get" ]; then
        apt-get upgrade -y >/dev/null 2>&1
    fi
    
    show_progress 3 3 "완료"
    log_success "시스템 업데이트 완료"
}

# 필수 패키지 설치
install_dependencies() {
    log_step "필수 패키지 설치"
    
    local packages=(
        "curl"
        "wget"
        "git"
        "unzip"
        "software-properties-common"
        "apt-transport-https"
        "ca-certificates"
        "gnupg"
        "lsb-release"
        "build-essential"
        "libssl-dev"
        "libffi-dev"
        "python3-dev"
        "python3-pip"
        "python3-venv"
        "supervisor"
        "nginx"
        "ufw"
        "fail2ban"
        "htop"
        "tree"
        "jq"
        "sqlite3"
    )
    
    local total=${#packages[@]}
    local current=0
    
    for package in "${packages[@]}"; do
        current=$((current + 1))
        show_progress $current $total "$package 설치 중"
        
        if ! dpkg -l | grep -q "^ii  $package "; then
            $PKG_INSTALL "$package" >/dev/null 2>&1 || {
                log_warning "$package 설치 실패, 계속 진행합니다"
            }
        fi
    done
    
    log_success "필수 패키지 설치 완료"
}

# Python 환경 설정
setup_python() {
    log_step "Python 환경 설정"
    
    # Python 버전 확인
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    log_info "Python 버전: $PYTHON_VERSION"
    
    # pip 업그레이드
    show_progress 1 3 "pip 업그레이드"
    python3 -m pip install --upgrade pip >/dev/null 2>&1
    
    # 가상환경 도구 설치
    show_progress 2 3 "가상환경 도구 설치"
    python3 -m pip install virtualenv >/dev/null 2>&1
    
    show_progress 3 3 "완료"
    log_success "Python 환경 설정 완료"
}

# Node.js 설치 (선택사항)
install_nodejs() {
    log_step "Node.js 설치 (선택사항)"
    
    read -p "Node.js를 설치하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_progress 1 4 "NodeSource 저장소 추가"
        curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - >/dev/null 2>&1
        
        show_progress 2 4 "Node.js 설치"
        $PKG_INSTALL nodejs >/dev/null 2>&1
        
        show_progress 3 4 "npm 업데이트"
        npm install -g npm@latest >/dev/null 2>&1
        
        show_progress 4 4 "완료"
        
        NODE_VERSION=$(node --version 2>/dev/null || echo "설치 실패")
        NPM_VERSION=$(npm --version 2>/dev/null || echo "설치 실패")
        
        log_success "Node.js 설치 완료"
        log_info "Node.js 버전: $NODE_VERSION"
        log_info "npm 버전: $NPM_VERSION"
    else
        log_info "Node.js 설치를 건너뜁니다"
    fi
}

# Docker 설치 (선택사항)
install_docker() {
    log_step "Docker 설치 (선택사항)"
    
    read -p "Docker를 설치하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_progress 1 6 "기존 Docker 제거"
        apt-get remove -y docker docker-engine docker.io containerd runc >/dev/null 2>&1 || true
        
        show_progress 2 6 "Docker GPG 키 추가"
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        show_progress 3 6 "Docker 저장소 추가"
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        show_progress 4 6 "패키지 목록 업데이트"
        apt-get update >/dev/null 2>&1
        
        show_progress 5 6 "Docker 설치"
        $PKG_INSTALL docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null 2>&1
        
        show_progress 6 6 "Docker 서비스 시작"
        systemctl enable docker >/dev/null 2>&1
        systemctl start docker >/dev/null 2>&1
        
        DOCKER_VERSION=$(docker --version 2>/dev/null || echo "설치 실패")
        log_success "Docker 설치 완료"
        log_info "Docker 버전: $DOCKER_VERSION"
        
        # 현재 사용자를 docker 그룹에 추가
        if [ -n "$SUDO_USER" ]; then
            usermod -aG docker "$SUDO_USER"
            log_info "사용자 $SUDO_USER를 docker 그룹에 추가했습니다"
            log_warning "Docker를 사용하려면 다시 로그인해야 합니다"
        fi
    else
        log_info "Docker 설치를 건너뜁니다"
    fi
}

# 방화벽 설정
setup_firewall() {
    log_step "방화벽 설정"
    
    show_progress 1 5 "UFW 활성화"
    ufw --force enable >/dev/null 2>&1
    
    show_progress 2 5 "기본 정책 설정"
    ufw default deny incoming >/dev/null 2>&1
    ufw default allow outgoing >/dev/null 2>&1
    
    show_progress 3 5 "SSH 포트 허용"
    ufw allow ssh >/dev/null 2>&1
    
    show_progress 4 5 "웹 포트 허용"
    ufw allow 80/tcp >/dev/null 2>&1
    ufw allow 443/tcp >/dev/null 2>&1
    ufw allow 8000/tcp >/dev/null 2>&1
    ufw allow 8001/tcp >/dev/null 2>&1
    
    show_progress 5 5 "완료"
    log_success "방화벽 설정 완료"
}

# Fail2Ban 설정
setup_fail2ban() {
    log_step "Fail2Ban 설정"
    
    # Fail2Ban 설정 파일 생성
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
ignoreip = 127.0.0.1/8 ::1

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
EOF
    
    systemctl enable fail2ban >/dev/null 2>&1
    systemctl restart fail2ban >/dev/null 2>&1
    
    log_success "Fail2Ban 설정 완료"
}

# 사용자 계정 생성
create_user() {
    log_step "애플리케이션 사용자 생성"
    
    local username="ticket-alarm"
    
    if ! id "$username" >/dev/null 2>&1; then
        show_progress 1 3 "사용자 생성"
        useradd -r -s /bin/bash -d /opt/ticket-alarm -m "$username"
        
        show_progress 2 3 "디렉토리 권한 설정"
        chown -R "$username:$username" "/opt/ticket-alarm"
        
        show_progress 3 3 "완료"
        log_success "사용자 '$username' 생성 완료"
    else
        log_info "사용자 '$username'이 이미 존재합니다"
    fi
}

# 로그 디렉토리 설정
setup_logging() {
    log_step "로그 시스템 설정"
    
    # 로그 디렉토리 생성
    mkdir -p /var/log/ticket-alarm
    chown ticket-alarm:ticket-alarm /var/log/ticket-alarm
    
    # 로그 로테이션 설정
    cat > /etc/logrotate.d/ticket-alarm << 'EOF'
/var/log/ticket-alarm/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 ticket-alarm ticket-alarm
    postrotate
        systemctl reload supervisor >/dev/null 2>&1 || true
    endscript
}
EOF
    
    log_success "로그 시스템 설정 완료"
}

# 시스템 최적화
optimize_system() {
    log_step "시스템 최적화"
    
    # 스왑 설정 최적화
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    
    # 파일 디스크립터 제한 증가
    cat >> /etc/security/limits.conf << 'EOF'
* soft nofile 65536
* hard nofile 65536
root soft nofile 65536
root hard nofile 65536
EOF
    
    # 네트워크 최적화
    cat >> /etc/sysctl.conf << 'EOF'
# 네트워크 최적화
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.core.netdev_max_backlog = 5000
EOF
    
    sysctl -p >/dev/null 2>&1
    
    log_success "시스템 최적화 완료"
}

# SSL 인증서 도구 설치
install_ssl_tools() {
    log_step "SSL 인증서 도구 설치"
    
    read -p "Let's Encrypt (Certbot)을 설치하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        show_progress 1 3 "Certbot 저장소 추가"
        add-apt-repository -y ppa:certbot/certbot >/dev/null 2>&1
        
        show_progress 2 3 "Certbot 설치"
        apt-get update >/dev/null 2>&1
        $PKG_INSTALL certbot python3-certbot-nginx >/dev/null 2>&1
        
        show_progress 3 3 "완료"
        log_success "Certbot 설치 완료"
        log_info "SSL 인증서 발급: sudo certbot --nginx -d your-domain.com"
    else
        log_info "Certbot 설치를 건너뜁니다"
    fi
}

# 모니터링 도구 설치
install_monitoring() {
    log_step "모니터링 도구 설치"
    
    read -p "추가 모니터링 도구를 설치하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        local tools=("iotop" "nethogs" "ncdu" "glances" "nmon")
        local total=${#tools[@]}
        local current=0
        
        for tool in "${tools[@]}"; do
            current=$((current + 1))
            show_progress $current $total "$tool 설치 중"
            $PKG_INSTALL "$tool" >/dev/null 2>&1 || true
        done
        
        log_success "모니터링 도구 설치 완료"
    else
        log_info "모니터링 도구 설치를 건너뜁니다"
    fi
}

# 설치 요약
show_summary() {
    log_step "설치 요약"
    
    echo
    echo "=== 티켓 알림 시스템 환경 설정 완료 ==="
    echo
    
    # 설치된 소프트웨어 버전 정보
    echo "📦 설치된 소프트웨어:"
    echo "  • Python: $(python3 --version 2>/dev/null || echo '설치 실패')"
    echo "  • pip: $(python3 -m pip --version 2>/dev/null | cut -d' ' -f2 || echo '설치 실패')"
    echo "  • Git: $(git --version 2>/dev/null || echo '설치 실패')"
    echo "  • Nginx: $(nginx -v 2>&1 | cut -d' ' -f3 || echo '설치 실패')"
    echo "  • Supervisor: $(supervisord --version 2>/dev/null || echo '설치 실패')"
    
    if command -v node >/dev/null 2>&1; then
        echo "  • Node.js: $(node --version)"
        echo "  • npm: $(npm --version)"
    fi
    
    if command -v docker >/dev/null 2>&1; then
        echo "  • Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
    fi
    
    echo
    echo "🔧 시스템 설정:"
    echo "  • 사용자: ticket-alarm"
    echo "  • 홈 디렉토리: /opt/ticket-alarm"
    echo "  • 로그 디렉토리: /var/log/ticket-alarm"
    echo "  • 방화벽: UFW 활성화"
    echo "  • 보안: Fail2Ban 설정"
    echo
    
    echo "🚀 다음 단계:"
    echo "  1. 애플리케이션 설치: ./install.sh"
    echo "  2. 설정 파일 편집: config.json"
    echo "  3. 서비스 시작: sudo supervisorctl start ticket-alarm:*"
    echo "  4. 웹 대시보드 접속: http://localhost:8001"
    echo
    
    echo "📚 유용한 명령어:"
    echo "  • 서비스 상태 확인: sudo supervisorctl status"
    echo "  • 로그 확인: tail -f /var/log/ticket-alarm/monitor.log"
    echo "  • 방화벽 상태: sudo ufw status"
    echo "  • 시스템 모니터링: htop 또는 glances"
    echo
    
    log_success "환경 설정이 완료되었습니다!"
}

# 메인 실행 함수
main() {
    echo "=== 티켓 알림 시스템 환경 설정 ==="
    echo "이 스크립트는 티켓 알림 시스템 실행에 필요한 환경을 설정합니다."
    echo
    
    # 사용자 확인
    read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "설치를 취소했습니다"
        exit 0
    fi
    
    # 시스템 검사
    check_root
    check_system
    check_package_manager
    
    # 환경 설정 실행
    update_system
    install_dependencies
    setup_python
    install_nodejs
    install_docker
    setup_firewall
    setup_fail2ban
    create_user
    setup_logging
    optimize_system
    install_ssl_tools
    install_monitoring
    
    # 요약 출력
    show_summary
}

# 스크립트 실행
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi