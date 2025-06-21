# 티켓 오픈 알리미

다양한 티켓 판매 사이트(인터파크, YES24, 멜론티켓, 티켓링크)에서 공연 티켓 오픈 정보를 수집하고 디스코드로 알림을 보내는 시스템입니다.

## 기능

- 다양한 티켓 판매 사이트에서 티켓 오픈 정보 수집
- 수집된 정보를 디스코드로 알림
- 주기적인 모니터링 및 새로운 정보 알림
- 이미 알림을 보낸 정보는 중복 알림 방지

## 설치 및 실행

### 필수 패키지 설치

```bash
pip install playwright requests beautifulsoup4
playwright install chromium
```

### 설정

1. `config.json.example` 파일을 `config.json`으로 복사하고 디스코드 웹훅 URL을 입력합니다.

```json
{
  "webhook_url": "여기에_디스코드_웹훅_URL을_입력하세요",
  "interval": 3600,
  "sources": ["interpark", "yes24", "melon", "ticketlink"]
}
```

### 실행

```bash
# 설정 파일을 사용하여 실행
python monitor.py --config config.json

# 또는 명령줄 인수로 실행
python monitor.py --webhook 웹훅URL --interval 3600 --sources interpark yes24 melon ticketlink
```

## 크롤러 테스트

각 크롤러를 개별적으로 테스트할 수 있습니다:

```bash
# 모든 크롤러 테스트
python test_crawlers.py

# 개별 크롤러 테스트
python test_melon_crawler.py
python test_ticketlink_crawler.py
```

## 주의사항

- 웹사이트 구조가 변경되면 크롤러가 작동하지 않을 수 있습니다.
- 너무 자주 크롤링하면 IP가 차단될 수 있으니 적절한 간격을 설정하세요.
- 수집한 정보는 개인 용도로만 사용하세요.

## 라이선스

개인 사용 목적으로만 사용하세요.