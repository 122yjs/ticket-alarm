# 🚀 빠른 시작 가이드 - 티켓 오픈 알리미 DB 버전

## 🎯 현재 상황
✅ **모든 파일 준비 완료!**  
✅ **240개 기존 티켓 데이터 보유!**  
⚠️ **Python 설치 필요**

## ⚡ 5분 만에 시작하기

### 1️⃣ **Python 설치** (아직 안 되어 있다면)
```bash
# Windows에서 Python 설치
# https://python.org 에서 Python 3.8+ 다운로드 및 설치
```

### 2️⃣ **의존성 설치**
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3️⃣ **즉시 웹 대시보드 실행** ⭐
```bash
python web_app_db.py
```
🌐 **브라우저에서 http://localhost:8000 접속**  
→ **240개 티켓의 멋진 대시보드 확인!**

### 4️⃣ **기존 데이터 DB로 이전** (선택사항)
```bash
python migrate_to_db.py
```

### 5️⃣ **디스코드 알림 설정** (선택사항)
```bash
# data/config.json 파일 편집
{
  "DISCORD_WEBHOOK_URL": "실제_웹훅_URL_입력",
  "KEYWORDS": ["뮤지컬", "콘서트", "원하는_키워드"],
  "interval": 3600,
  "sources": ["interpark", "yes24", "melon", "ticketlink"]
}

# 웹훅 테스트
python run_db.py --test-webhook
```

## 🎪 주요 기능 체험

### 🔍 **검색 테스트**
```bash
python run_db.py --search "AKMU"      # AKMU 콘서트 검색
python run_db.py --search "뮤지컬"     # 뮤지컬 검색
python run_db.py --search "콘서트"     # 콘서트 검색
```

### 📊 **통계 확인**
```bash
python run_db.py --stats-only         # 현재 DB 통계
```

### 🕷️ **새 데이터 크롤링**
```bash
python run_db.py                      # 일회성 크롤링
python monitor_db.py                  # 지속적 모니터링
```

## 🌟 **예상 결과**

### 웹 대시보드에서 볼 수 있는 것들:
- 📈 **실시간 통계**: 총 240개 티켓
- 🎭 **장르별 분포**: 콘서트, 뮤지컬, 연극 등
- 🌐 **소스별 분포**: 인터파크, YES24, 멜론, 티켓링크
- 📅 **날짜별 오픈 일정**: 7월 오픈 예정 티켓들
- 🔍 **실시간 검색**: 키워드로 즉시 검색
- 📱 **모바일 지원**: 스마트폰에서도 완벽 동작

### 샘플 티켓 데이터:
```
🎵 2025 AKMU STANDING CONCERT ［악동들］
📅 07.02(수) 20:00
🏢 인터파크

🎭 뮤지컬 최고다 호기심딱지 시즌3
📅 07.03(목) 10:00  
🏢 인터파크
```

## 🎯 **1분 요약**

1. `python web_app_db.py` 실행
2. http://localhost:8000 접속
3. 240개 티켓 대시보드 확인
4. 끝! 🎉

**이미 모든 준비가 완료되어 있어서 Python만 설치하면 바로 사용 가능합니다!**