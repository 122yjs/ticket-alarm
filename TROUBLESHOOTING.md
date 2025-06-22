# 티켓 알림 시스템 트러블슈팅 가이드

## 목차
1. [크롤링 관련 문제](#크롤링-관련-문제)
2. [디스코드 알림 문제](#디스코드-알림-문제)
3. [시스템 성능 문제](#시스템-성능-문제)
4. [네트워크 관련 문제](#네트워크-관련-문제)
5. [설정 및 구성 문제](#설정-및-구성-문제)
6. [로그 분석 방법](#로그-분석-방법)
7. [응급 복구 절차](#응급-복구-절차)

---

## 크롤링 관련 문제

### 1. 특정 사이트 크롤링 실패

#### 증상
- 특정 티켓 사이트에서 데이터를 가져오지 못함
- "크롤링 실패" 로그 메시지 반복
- 해당 사이트의 티켓 정보가 업데이트되지 않음

#### 원인 분석
```bash
# 1. 개별 크롤러 테스트
python test_crawlers.py

# 2. 네트워크 연결 확인
curl -I https://ticket.interpark.com
curl -I https://www.yes24.com
curl -I https://ticket.melon.com
curl -I https://www.ticketlink.co.kr

# 3. 로그에서 에러 패턴 확인
grep -A 5 -B 5 "크롤링 실패" /var/log/ticket-alarm/monitor.out.log
```

#### 해결 방법

**A. User-Agent 업데이트**
```python
# crawlers/base_crawler.py 수정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
```

**B. 요청 간격 조정**
```python
# crawlers/interpark_crawler.py 예시
import time

def crawl_tickets(self):
    # 요청 간격을 늘려서 차단 방지
    time.sleep(2)  # 2초 대기
    response = requests.get(url, headers=self.headers)
```

**C. 프록시 사용 (필요시)**
```python
# config.json에 프록시 설정 추가
{
    "proxy": {
        "http": "http://proxy-server:port",
        "https": "https://proxy-server:port"
    }
}
```

### 2. 크롤링 속도 저하

#### 증상
- 크롤링 완료 시간이 평소보다 오래 걸림
- 타임아웃 에러 발생

#### 해결 방법
```python
# crawlers/base_crawler.py에서 타임아웃 설정 조정
response = requests.get(url, headers=headers, timeout=30)  # 30초로 증가

# 동시 요청 수 제한
import asyncio
semaphore = asyncio.Semaphore(3)  # 최대 3개 동시 요청
```

### 3. 데이터 파싱 오류

#### 증상
- 티켓 정보가 부분적으로만 수집됨
- 가격이나 날짜 정보가 누락됨

#### 해결 방법
```bash
# 1. 사이트 구조 변경 확인
# 브라우저 개발자 도구로 HTML 구조 분석

# 2. 셀렉터 업데이트
# 해당 크롤러 파일에서 CSS 셀렉터 수정
```

---

## 디스코드 알림 문제

### 1. 알림이 전송되지 않음

#### 증상
- 새로운 티켓이 발견되었지만 디스코드 알림이 오지 않음
- "알림 전송 실패" 로그 메시지

#### 진단 방법
```bash
# 1. 웹훅 URL 테스트
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"테스트 메시지"}' \
  "YOUR_WEBHOOK_URL"

# 2. 설정 파일 확인
cat config.json | grep DISCORD_WEBHOOK_URL

# 3. 네트워크 연결 확인
ping discord.com
nslookup discord.com
```

#### 해결 방법

**A. 웹훅 URL 재설정**
1. 디스코드에서 새 웹훅 생성
2. `config.json`에서 URL 업데이트
3. 시스템 재시작

**B. 방화벽 설정 확인**
```bash
# 아웃바운드 HTTPS 트래픽 허용 확인
sudo ufw status
sudo ufw allow out 443
```

### 2. 중복 알림 발생

#### 증상
- 같은 티켓에 대해 여러 번 알림이 전송됨

#### 해결 방법
```bash
# 1. 알림 히스토리 파일 확인
cat data/notification_history.json

# 2. 파일이 손상된 경우 재생성
rm data/notification_history.json
# 시스템이 자동으로 새 파일 생성

# 3. 해시 충돌 확인
grep "해시 충돌" /var/log/ticket-alarm/monitor.out.log
```

### 3. 알림 형식 문제

#### 증상
- 임베드 메시지가 제대로 표시되지 않음
- 이미지나 링크가 깨짐

#### 해결 방법
```python
# discord_notifier.py에서 임베드 검증
def validate_embed(embed_data):
    required_fields = ['title', 'description', 'url']
    for field in required_fields:
        if field not in embed_data or not embed_data[field]:
            return False
    return True
```

---

## 시스템 성능 문제

### 1. 메모리 부족

#### 증상
- 시스템이 느려짐
- 프로세스가 갑자기 종료됨
- "Out of Memory" 에러

#### 진단
```bash
# 메모리 사용량 확인
free -h
ps aux --sort=-%mem | head -10

# 스왑 사용량 확인
swapon --show
```

#### 해결 방법

**A. 임시 스왑 파일 생성**
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**B. 메모리 사용량 최적화**
```python
# monitor.py에서 메모리 정리
import gc

def cleanup_memory():
    gc.collect()  # 가비지 컬렉션 강제 실행
    
# 주기적으로 호출
if cycle_count % 10 == 0:  # 10사이클마다
    cleanup_memory()
```

### 2. CPU 사용률 과다

#### 증상
- CPU 사용률이 지속적으로 높음
- 시스템 응답 속도 저하

#### 해결 방법
```bash
# 1. 프로세스별 CPU 사용률 확인
top -p $(pgrep -d',' python)

# 2. 크롤링 간격 조정
# config.json에서 interval 값 증가
{
    "interval": 7200  # 2시간으로 증가
}

# 3. 동시 실행 프로세스 수 제한
# supervisor 설정에서 numprocs 조정
```

### 3. 디스크 공간 부족

#### 증상
- "No space left on device" 에러
- 로그 파일 생성 실패

#### 해결 방법
```bash
# 1. 디스크 사용량 확인
df -h
du -sh /opt/ticket-alarm/*

# 2. 오래된 로그 파일 정리
find /var/log/ticket-alarm -name "*.log" -mtime +7 -delete
find /opt/ticket-alarm/data -name "*.json" -mtime +30 -delete

# 3. 로그 로테이션 강제 실행
sudo logrotate -f /etc/logrotate.d/ticket-alarm
```

---

## 네트워크 관련 문제

### 1. 연결 타임아웃

#### 증상
- "Connection timeout" 에러
- 간헐적인 크롤링 실패

#### 해결 방법
```python
# requests 설정 최적화
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
```

### 2. DNS 해결 실패

#### 증상
- "Name resolution failed" 에러
- 특정 도메인에 접근 불가

#### 해결 방법
```bash
# 1. DNS 서버 확인
cat /etc/resolv.conf

# 2. DNS 서버 변경 (Google DNS)
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf

# 3. DNS 캐시 플러시
sudo systemctl restart systemd-resolved
```

### 3. 방화벽 차단

#### 증상
- 특정 포트로의 연결 실패
- "Connection refused" 에러

#### 해결 방법
```bash
# 1. 방화벽 상태 확인
sudo ufw status verbose

# 2. 필요한 포트 열기
sudo ufw allow out 80
sudo ufw allow out 443

# 3. 특정 도메인 허용
sudo ufw allow out to discord.com
```

---

## 설정 및 구성 문제

### 1. 설정 파일 오류

#### 증상
- "JSON decode error" 메시지
- 시스템 시작 실패

#### 해결 방법
```bash
# 1. JSON 문법 검증
python -m json.tool config.json

# 2. 백업에서 복원
cp config.json.example config.json
# 설정 다시 입력

# 3. 설정 파일 권한 확인
ls -la config.json
chmod 644 config.json
```

### 2. 환경 변수 문제

#### 증상
- 모듈 import 실패
- 경로 관련 에러

#### 해결 방법
```bash
# 1. PYTHONPATH 설정
export PYTHONPATH="/opt/ticket-alarm:$PYTHONPATH"

# 2. 가상환경 활성화 확인
which python
python --version

# 3. 의존성 재설치
pip install -r requirements.txt --force-reinstall
```

### 3. 권한 문제

#### 증상
- "Permission denied" 에러
- 파일 생성/수정 실패

#### 해결 방법
```bash
# 1. 파일 권한 확인
ls -la /opt/ticket-alarm/

# 2. 소유권 변경
sudo chown -R ubuntu:ubuntu /opt/ticket-alarm/

# 3. 디렉토리 권한 설정
chmod 755 /opt/ticket-alarm/
chmod 644 /opt/ticket-alarm/*.py
chmod 755 /opt/ticket-alarm/data/
```

---

## 로그 분석 방법

### 1. 로그 파일 위치
```bash
# 시스템 로그
/var/log/ticket-alarm/monitor.out.log    # 모니터링 출력
/var/log/ticket-alarm/monitor.err.log    # 모니터링 에러
/var/log/ticket-alarm/webapp.out.log     # 웹앱 출력
/var/log/ticket-alarm/webapp.err.log     # 웹앱 에러

# 백업 및 유지보수 로그
/var/log/ticket-alarm/backup.log         # 백업 로그
/var/log/ticket-alarm/security.log       # 보안 점검 로그
/var/log/ticket-alarm/update.log         # 업데이트 로그
```

### 2. 유용한 로그 분석 명령어

```bash
# 최근 에러 확인
tail -f /var/log/ticket-alarm/monitor.err.log

# 특정 키워드 검색
grep -i "error\|fail\|exception" /var/log/ticket-alarm/*.log

# 시간대별 로그 필터링
grep "$(date '+%Y-%m-%d %H')" /var/log/ticket-alarm/monitor.out.log

# 크롤링 성공률 계산
grep -c "크롤링 완료" /var/log/ticket-alarm/monitor.out.log
grep -c "크롤링 실패" /var/log/ticket-alarm/monitor.out.log

# 알림 전송 통계
grep "알림 전송" /var/log/ticket-alarm/monitor.out.log | tail -20

# 메모리 사용량 추적
grep "메모리 사용량" /var/log/ticket-alarm/monitor.out.log
```

### 3. 로그 레벨별 분석

```bash
# ERROR 레벨 로그만 확인
grep "\[ERROR\]" /var/log/ticket-alarm/*.log

# WARNING 레벨 로그 확인
grep "\[WARNING\]" /var/log/ticket-alarm/*.log

# INFO 레벨에서 중요 정보 추출
grep "\[INFO\].*완료\|시작\|성공" /var/log/ticket-alarm/*.log
```

---

## 응급 복구 절차

### 1. 시스템 전체 재시작

```bash
# 1단계: 모든 프로세스 중지
sudo supervisorctl stop ticket-alarm:*

# 2단계: 백업 생성
/opt/ticket-alarm/backup.sh

# 3단계: 시스템 재시작
sudo supervisorctl start ticket-alarm:*

# 4단계: 상태 확인
sudo supervisorctl status
tail -f /var/log/ticket-alarm/monitor.out.log
```

### 2. 데이터 복구

```bash
# 1. 최신 백업 확인
ls -la /opt/backups/ticket-alarm/ | tail -5

# 2. 데이터 복원
cd /opt/ticket-alarm
tar -xzf /opt/backups/ticket-alarm/data_YYYYMMDD_HHMMSS.tar.gz

# 3. 권한 복원
chown -R ubuntu:ubuntu data/
chmod 755 data/
```

### 3. 설정 롤백

```bash
# 1. 이전 설정으로 복원
cp /opt/backups/ticket-alarm/config_YYYYMMDD_HHMMSS.json config.json

# 2. 설정 검증
python -c "import json; json.load(open('config.json'))"

# 3. 시스템 재시작
sudo supervisorctl restart ticket-alarm:*
```

### 4. 긴급 연락 절차

1. **시스템 관리자에게 연락**
   - 이메일: [관리자 이메일]
   - 전화: [긴급 연락처]

2. **상황 보고 템플릿**
   ```
   제목: [긴급] 티켓 알림 시스템 장애
   
   발생 시간: YYYY-MM-DD HH:MM:SS
   증상: [구체적인 증상 설명]
   에러 메시지: [에러 로그 첨부]
   시도한 해결책: [수행한 조치 내용]
   현재 상태: [시스템 현재 상태]
   ```

3. **임시 대안**
   - 수동 티켓 확인 및 알림
   - 백업 시스템 가동 (있는 경우)
   - 사용자 공지사항 발송

---

## 예방 조치

### 1. 정기 점검 체크리스트

**일일 점검**
- [ ] 시스템 상태 확인 (`supervisorctl status`)
- [ ] 에러 로그 확인
- [ ] 디스크 사용량 확인
- [ ] 최근 알림 전송 확인

**주간 점검**
- [ ] 크롤링 성공률 분석
- [ ] 메모리 사용량 추세 확인
- [ ] 백업 파일 상태 확인
- [ ] 보안 로그 검토

**월간 점검**
- [ ] 시스템 업데이트
- [ ] 의존성 패키지 업데이트
- [ ] 성능 최적화
- [ ] 문서 업데이트

### 2. 모니터링 알림 설정

```bash
# 시스템 모니터링 스크립트
#!/bin/bash
# /opt/ticket-alarm/health_check.sh

# CPU 사용률 확인
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo "HIGH CPU USAGE: $CPU_USAGE%" | mail -s "System Alert" admin@example.com
fi

# 메모리 사용률 확인
MEM_USAGE=$(free | grep Mem | awk '{printf "%.2f", $3/$2 * 100.0}')
if (( $(echo "$MEM_USAGE > 85" | bc -l) )); then
    echo "HIGH MEMORY USAGE: $MEM_USAGE%" | mail -s "System Alert" admin@example.com
fi

# 디스크 사용률 확인
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
if [ $DISK_USAGE -gt 85 ]; then
    echo "HIGH DISK USAGE: $DISK_USAGE%" | mail -s "System Alert" admin@example.com
fi
```

---

**문서 업데이트**: 2024년 1월
**버전**: 1.0
**작성자**: 시스템 관리팀