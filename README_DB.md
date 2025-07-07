# 🎫 티켓 오픈 알리미 (데이터베이스 버전)

다양한 티켓 판매 사이트(인터파크, YES24, 멜론티켓, 티켓링크)에서 공연 티켓 오픈 정보를 수집하고 **SQLite 데이터베이스에 저장**하여 디스코드로 알림을 보내는 시스템입니다.

## 🆕 새로운 기능 (DB 버전)

- **📊 데이터베이스 저장**: SQLite를 사용한 효율적인 데이터 관리
- **🔍 고급 검색**: 키워드, 날짜, 장르별 필터링
- **📈 통계 대시보드**: 실시간 통계 및 분석
- **🚀 성능 향상**: 중복 제거 및 빠른 조회
- **🌐 웹 인터페이스**: 모던한 웹 UI로 데이터 시각화
- **📱 반응형 디자인**: 모바일/데스크톱 지원

## 🏗️ 시스템 구조

```
📁 프로젝트 루트/
├── 🗄️ 데이터베이스 관련
│   ├── database.py              # 데이터베이스 스키마 및 관리
│   ├── db_data_manager.py       # DB 기반 데이터 매니저
│   ├── migrate_to_db.py         # JSON → DB 마이그레이션
│   └── data/tickets.db          # SQLite 데이터베이스 파일
├── 🕷️ 크롤링 시스템
│   ├── crawlers/                # 각 사이트별 크롤러
│   ├── monitor_db.py            # DB 기반 모니터링
│   └── run_db.py               # DB 기반 실행 스크립트
├── 🔔 알림 시스템
│   └── discord_notifier_db.py   # DB 기반 디스코드 알림
├── 🌐 웹 인터페이스
│   ├── web_app_db.py           # DB 기반 웹 앱
│   ├── static/                 # CSS, JS 파일
│   └── templates/              # HTML 템플릿
└── 📋 기존 파일들 (호환성 유지)
```

## 🚀 설치 및 설정

### 1. 필수 패키지 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 설정 파일 준비

기존 JSON 설정 파일이 있다면 그대로 사용하거나, 새로 생성:

```bash
# config.json.example을 data/config.json으로 복사
cp config.json.example data/config.json
```

`data/config.json` 파일 편집:
```json
{
  "DISCORD_WEBHOOK_URL": "여기에_자신의_디스코드_웹훅_URL을_붙여넣으세요",
  "KEYWORDS": ["뮤지컬", "콘서트", "임영웅", "아이유"],
  "interval": 3600,
  "sources": ["interpark", "yes24", "melon", "ticketlink"]
}
```

### 3. 데이터베이스 초기화

#### 기존 JSON 데이터가 있는 경우 (마이그레이션)
```bash
python migrate_to_db.py
```

#### 새로 시작하는 경우
데이터베이스는 첫 실행 시 자동으로 생성됩니다.

## 📖 사용법

### 🎯 기본 사용법

#### 1. 일회성 크롤링 및 데이터 확인
```bash
python run_db.py
```

#### 2. 지속적인 모니터링
```bash
python monitor_db.py
```

#### 3. 웹 인터페이스 실행
```bash
python web_app_db.py
# 브라우저에서 http://localhost:8000 접속
```

### 🔧 고급 사용법

#### 통계만 확인
```bash
python run_db.py --stats-only
```

#### 키워드 검색
```bash
python run_db.py --search "뮤지컬"
python run_db.py --search "임영웅"
```

#### 디스코드 웹훅 테스트
```bash
python run_db.py --test-webhook
```

#### 크롤링만 실행 (통계 표시 안함)
```bash
python run_db.py --crawl-only
```

#### 최근 티켓 더 많이 보기
```bash
python run_db.py --recent 20
```

## 🌐 웹 인터페이스 기능

### 📊 대시보드
- 실시간 티켓 통계
- 소스별/장르별 분포
- 오늘/내일/이번주 오픈 티켓 현황

### 🔍 검색 및 필터링
- **키워드 검색**: 제목, 장소에서 검색
- **소스 필터**: 특정 티켓 사이트만 보기
- **장르 필터**: 뮤지컬, 콘서트 등 장르별 필터
- **날짜 필터**: 특정 기간 내 오픈 티켓만 보기

### 📱 반응형 디자인
- 모바일/태블릿/데스크톱 최적화
- 터치 친화적 인터페이스

## 🗄️ 데이터베이스 스키마

### tickets 테이블
```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    open_date TEXT,
    open_datetime DATETIME,
    source TEXT NOT NULL,
    link TEXT,
    place TEXT,
    genre TEXT,
    price TEXT,
    description TEXT,
    image_url TEXT,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_data TEXT
);
```

### notifications 테이블
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    notification_type TEXT DEFAULT 'discord',
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    webhook_url TEXT
);
```

### settings 테이블
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🔄 기존 시스템과의 호환성

기존 JSON 기반 시스템과 DB 기반 시스템을 모두 사용할 수 있습니다:

### JSON 기반 (기존)
```bash
python monitor.py      # 기존 모니터링
python run.py         # 기존 일회성 실행
python web_app.py     # 기존 웹 앱
```

### DB 기반 (새로운)
```bash
python monitor_db.py   # DB 기반 모니터링
python run_db.py      # DB 기반 실행
python web_app_db.py  # DB 기반 웹 앱
```

## 🧪 테스트

### 개별 크롤러 테스트
```bash
python test_crawlers.py
python test_melon_crawler.py
python test_ticketlink_crawler.py
```

### 시스템 전체 테스트
```bash
# 1. 크롤링 테스트
python run_db.py --crawl-only

# 2. 웹훅 테스트
python run_db.py --test-webhook

# 3. 웹 인터페이스 테스트
python web_app_db.py
```

## 📈 성능 최적화

### 데이터베이스 최적화
- **인덱스**: 자주 조회되는 컬럼에 인덱스 생성
- **WAL 모드**: 동시 읽기/쓰기 성능 향상
- **연결 풀링**: 스레드별 연결 관리

### 크롤링 최적화
- **병렬 처리**: 여러 사이트 동시 크롤링
- **재시도 로직**: 지수 백오프로 안정성 확보
- **중복 제거**: 데이터베이스 레벨에서 중복 방지

## 🚨 주의사항

- **데이터베이스 백업**: 정기적으로 `data/tickets.db` 파일 백업
- **디스크 공간**: 시간이 지나면서 데이터베이스 크기 증가
- **동시 실행**: 모니터링과 웹앱은 동시 실행 가능하지만, 여러 모니터링 프로세스는 피하세요
- **웹사이트 변경**: 사이트 구조 변경 시 크롤러 업데이트 필요

## 🔧 문제 해결

### 데이터베이스 관련
```bash
# 데이터베이스 상태 확인
python run_db.py --stats-only

# 마이그레이션 재실행
python migrate_to_db.py
```

### 웹훅 관련
```bash
# 웹훅 연결 테스트
python run_db.py --test-webhook
```

### 크롤링 관련
```bash
# 개별 크롤러 테스트
python test_crawlers.py
```

## 📊 모니터링 및 로그

### 로그 파일 위치
- 콘솔 출력으로 모든 로그 확인 가능
- 필요시 파일 로깅 설정 가능

### 주요 메트릭
- 수집된 티켓 수
- 새로운 티켓 수
- 알림 전송 성공률
- 크롤링 소요 시간

## 🎯 향후 계획

- [ ] PostgreSQL/MySQL 지원
- [ ] 더 많은 티켓 사이트 추가
- [ ] 모바일 앱 개발
- [ ] AI 기반 추천 시스템
- [ ] 가격 변동 알림
- [ ] 캘린더 연동

## 📄 라이선스

개인 사용 목적으로만 사용하세요.

---

## 🆘 도움이 필요하신가요?

1. **설정 문제**: `config.json` 파일 확인
2. **크롤링 문제**: `python test_crawlers.py` 실행
3. **웹훅 문제**: `python run_db.py --test-webhook` 실행
4. **데이터베이스 문제**: `python run_db.py --stats-only` 실행

더 자세한 도움이 필요하시면 이슈를 등록해 주세요! 🙏