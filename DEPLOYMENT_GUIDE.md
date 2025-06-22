# 티켓 알림 시스템 배포 및 운영 가이드

## 목차
1. [시스템 요구사항](#시스템-요구사항)
2. [로컬 환경 설정](#로컬-환경-설정)
3. [서버 배포](#서버-배포)
4. [운영 및 모니터링](#운영-및-모니터링)
5. [문제 해결](#문제-해결)
6. [유지보수](#유지보수)

---

## 시스템 요구사항

### 최소 요구사항
- **운영체제**: Windows 10/11, Ubuntu 18.04+, CentOS 7+
- **Python**: 3.8 이상
- **메모리**: 최소 2GB RAM
- **저장공간**: 최소 1GB 여유 공간
- **네트워크**: 안정적인 인터넷 연결

### 권장 요구사항
- **운영체제**: Ubuntu 20.04 LTS (서버 환경)
- **Python**: 3.9 이상
- **메모리**: 4GB RAM 이상
- **저장공간**: 5GB 이상 여유 공간
- **네트워크**: 고속 인터넷 연결

---

## 로컬 환경 설정

### 1. 프로젝트 클론 및 설정

```bash
# 프로젝트 클론
git clone <repository-url>
cd ticket-alarm

# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 설정 파일 구성

```bash
# 설정 파일 복사
cp config.json.example config.json
```

`config.json` 파일을 편집하여 다음 항목들을 설정:

```json
{
  "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL",
  "KEYWORDS": ["원하는", "키워드", "목록"],
  "PRIORITY_KEYWORDS": ["우선순위", "키워드"],
  "interval": 3600,
  "notification_delay": 1.0,
  "max_notifications_per_cycle": 10,
  "sources": ["interpark", "yes24", "melon", "ticketlink"]
}
```

### 3. 디스코드 웹훅 설정

1. 디스코드 서버에서 채널 설정 → 연동 → 웹훅 생성
2. 웹훅 URL을 복사하여 `config.json`의 `DISCORD_WEBHOOK_URL`에 입력
3. 웹훅 이름과 아바타 설정 (선택사항)

### 4. 로컬 테스트

```bash
# 크롤러 테스트
python test_crawlers.py

# 웹 인터페이스 테스트
python web_app.py
# 브라우저에서 http://localhost:8000 접속

# 모니터링 시스템 테스트 (단축 실행)
python monitor.py
```

---

## 서버 배포

### 1. 클라우드 서버 선택

#### AWS EC2 (권장)
- **인스턴스 타입**: t3.small 이상
- **운영체제**: Ubuntu 20.04 LTS
- **보안 그룹**: HTTP(80), HTTPS(443), SSH(22) 포트 오픈

#### Google Cloud Platform
- **머신 타입**: e2-small 이상
- **운영체제**: Ubuntu 20.04 LTS

#### 기타 VPS 서비스
- Vultr, DigitalOcean, Linode 등

### 2. 서버 초기 설정

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor

# 방화벽 설정
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### 3. 애플리케이션 배포

```bash
# 애플리케이션 디렉토리 생성
sudo mkdir -p /opt/ticket-alarm
sudo chown $USER:$USER /opt/ticket-alarm

# 프로젝트 클론
cd /opt/ticket-alarm
git clone <repository-url> .

# 가상환경 설정
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 설정 파일 구성
cp config.json.example config.json
# config.json 편집
nano config.json

# 데이터 디렉토리 생성
mkdir -p data
chmod 755 data
```

### 4. Nginx 설정 (웹 인터페이스용)

```bash
# Nginx 설정 파일 생성
sudo nano /etc/nginx/sites-available/ticket-alarm
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 도메인 또는 IP 주소

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 정적 파일 직접 서빙
    location /static/ {
        alias /opt/ticket-alarm/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# 사이트 활성화
sudo ln -s /etc/nginx/sites-available/ticket-alarm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. Supervisor 설정 (프로세스 관리)

```bash
# Supervisor 설정 파일 생성
sudo nano /etc/supervisor/conf.d/ticket-alarm.conf
```

```ini
[group:ticket-alarm]
programs=ticket-monitor,ticket-webapp

[program:ticket-monitor]
command=/opt/ticket-alarm/venv/bin/python monitor.py
directory=/opt/ticket-alarm
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/ticket-alarm/monitor.err.log
stdout_logfile=/var/log/ticket-alarm/monitor.out.log
environment=PYTHONPATH="/opt/ticket-alarm"

[program:ticket-webapp]
command=/opt/ticket-alarm/venv/bin/python web_app.py
directory=/opt/ticket-alarm
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/var/log/ticket-alarm/webapp.err.log
stdout_logfile=/var/log/ticket-alarm/webapp.out.log
environment=PYTHONPATH="/opt/ticket-alarm"
```

```bash
# 로그 디렉토리 생성
sudo mkdir -p /var/log/ticket-alarm
sudo chown ubuntu:ubuntu /var/log/ticket-alarm

# Supervisor 재시작
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start ticket-alarm:*
```

### 6. SSL 인증서 설정 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d your-domain.com

# 자동 갱신 설정
sudo crontab -e
# 다음 라인 추가:
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 운영 및 모니터링

### 1. 시스템 상태 확인

```bash
# 프로세스 상태 확인
sudo supervisorctl status

# 로그 확인
sudo supervisorctl tail -f ticket-monitor
sudo supervisorctl tail -f ticket-webapp

# 시스템 리소스 확인
htop
df -h
free -h
```

### 2. 로그 관리

```bash
# 로그 로테이션 설정
sudo nano /etc/logrotate.d/ticket-alarm
```

```
/var/log/ticket-alarm/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
    postrotate
        supervisorctl restart ticket-alarm:*
    endscript
}
```

### 3. 백업 설정

```bash
# 백업 스크립트 생성
nano /opt/ticket-alarm/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/ticket-alarm"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 데이터 백업
tar -czf $BACKUP_DIR/data_$DATE.tar.gz -C /opt/ticket-alarm data/

# 설정 파일 백업
cp /opt/ticket-alarm/config.json $BACKUP_DIR/config_$DATE.json

# 30일 이상 된 백업 파일 삭제
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.json" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
# 실행 권한 부여
chmod +x /opt/ticket-alarm/backup.sh

# 크론탭에 일일 백업 추가
crontab -e
# 다음 라인 추가:
0 2 * * * /opt/ticket-alarm/backup.sh >> /var/log/ticket-alarm/backup.log 2>&1
```

### 4. 모니터링 대시보드

웹 인터페이스를 통해 다음 정보를 모니터링할 수 있습니다:
- 수집된 티켓 현황
- 크롤러별 성공률
- 알림 전송 통계
- 시스템 상태

---

## 문제 해결

### 1. 일반적인 문제들

#### 크롤링 실패
**증상**: 특정 사이트에서 데이터를 가져오지 못함
**해결책**:
```bash
# 개별 크롤러 테스트
python test_crawlers.py

# 네트워크 연결 확인
curl -I https://ticket.interpark.com

# User-Agent 업데이트 필요 시 crawlers/ 디렉토리의 해당 파일 수정
```

#### 디스코드 알림 실패
**증상**: 알림이 전송되지 않음
**해결책**:
```bash
# 웹훅 URL 확인
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"테스트 메시지"}' \
  YOUR_WEBHOOK_URL

# 설정 파일 확인
cat config.json | grep DISCORD_WEBHOOK_URL
```

#### 메모리 부족
**증상**: 시스템이 느려지거나 프로세스가 종료됨
**해결책**:
```bash
# 메모리 사용량 확인
free -h
ps aux --sort=-%mem | head

# 스왑 파일 생성 (임시 해결책)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 2. 로그 분석

```bash
# 에러 로그 검색
grep -i error /var/log/ticket-alarm/*.log

# 최근 1시간 로그
find /var/log/ticket-alarm -name "*.log" -exec grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" {} \;

# 크롤링 성공률 확인
grep "알림 전송 성공" /var/log/ticket-alarm/monitor.out.log | wc -l
```

### 3. 성능 최적화

```bash
# 데이터베이스 정리 (30일 이상 된 데이터)
find /opt/ticket-alarm/data -name "*.json" -mtime +30 -delete

# 로그 파일 압축
gzip /var/log/ticket-alarm/*.log.1

# 프로세스 재시작
sudo supervisorctl restart ticket-alarm:*
```

---

## 유지보수

### 1. 정기 업데이트

```bash
# 월간 시스템 업데이트 (매월 첫째 주 일요일)
#!/bin/bash
# /opt/ticket-alarm/monthly_update.sh

echo "Starting monthly update: $(date)"

# 백업 생성
/opt/ticket-alarm/backup.sh

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python 패키지 업데이트
source /opt/ticket-alarm/venv/bin/activate
pip list --outdated
# 필요시 수동으로 업데이트

# 프로세스 재시작
sudo supervisorctl restart ticket-alarm:*

echo "Monthly update completed: $(date)"
```

### 2. 보안 점검

```bash
# 주간 보안 점검 (매주 일요일)
#!/bin/bash
# /opt/ticket-alarm/security_check.sh

# 실패한 로그인 시도 확인
sudo grep "Failed password" /var/log/auth.log | tail -20

# 열린 포트 확인
sudo netstat -tulpn | grep LISTEN

# 방화벽 상태 확인
sudo ufw status

# 디스크 사용량 확인
df -h | grep -E "(8[0-9]|9[0-9])%"

echo "Security check completed: $(date)"
```

### 3. 성능 모니터링

```bash
# 일일 성능 리포트
#!/bin/bash
# /opt/ticket-alarm/daily_report.sh

DATE=$(date +%Y-%m-%d)
REPORT_FILE="/var/log/ticket-alarm/daily_report_$DATE.txt"

echo "Daily Performance Report - $DATE" > $REPORT_FILE
echo "=========================================" >> $REPORT_FILE

# 시스템 리소스
echo "System Resources:" >> $REPORT_FILE
free -h >> $REPORT_FILE
df -h >> $REPORT_FILE

# 프로세스 상태
echo "\nProcess Status:" >> $REPORT_FILE
sudo supervisorctl status >> $REPORT_FILE

# 크롤링 통계
echo "\nCrawling Statistics:" >> $REPORT_FILE
grep "알림 전송 완료" /var/log/ticket-alarm/monitor.out.log | tail -10 >> $REPORT_FILE

echo "Daily report generated: $REPORT_FILE"
```

### 4. 크론탭 설정 요약

```bash
# 전체 크론탭 설정
crontab -e
```

```cron
# 일일 백업 (새벽 2시)
0 2 * * * /opt/ticket-alarm/backup.sh >> /var/log/ticket-alarm/backup.log 2>&1

# 주간 보안 점검 (일요일 오전 6시)
0 6 * * 0 /opt/ticket-alarm/security_check.sh >> /var/log/ticket-alarm/security.log 2>&1

# 월간 업데이트 (매월 첫째 주 일요일 오전 4시)
0 4 1-7 * 0 /opt/ticket-alarm/monthly_update.sh >> /var/log/ticket-alarm/update.log 2>&1

# 일일 성능 리포트 (매일 오후 11시)
0 23 * * * /opt/ticket-alarm/daily_report.sh

# SSL 인증서 자동 갱신 (매일 정오)
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 연락처 및 지원

### 기술 지원
- 시스템 관련 문의: [관리자 이메일]
- 긴급 상황: [긴급 연락처]

### 유용한 링크
- 프로젝트 저장소: [GitHub URL]
- 문서: [문서 URL]
- 이슈 트래커: [이슈 URL]

---

**마지막 업데이트**: 2024년 1월
**문서 버전**: 1.0