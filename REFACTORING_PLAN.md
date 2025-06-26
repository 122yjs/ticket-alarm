# 수정된 리팩터링 계획: 데이터 동기화 강화 및 구조 불일치 해결

## 1. 문제 원인 진단 (확장)

기존 문제에 더해 데이터 동기화의 근본적인 한계를 추가로 진단했습니다.

*   **1.1. 데이터 구조 불일치 (기존 문제):** 백엔드 DB 필드(`name`, `start_date` 등)와 프론트엔드 기대 필드(`title`, `open_date`, `source` 등)가 다릅니다.
*   **1.2. 불충분한 데이터 동기화 (신규 발견):**
    *   **페이지네이션 부재:** `sync_kopis.py`에서 `cpage` (페이지 번호)가 '1'로 고정되어 있어, API 호출 당 최대 100건의 데이터만 가져옵니다.
    *   **제한된 조회 기간:** `sync_kopis.py`에서 향후 30일간의 데이터만 조회하여 전체 공연 정보를 충분히 확보하지 못합니다.

## 2. 해결 전략 (확장)

두 가지 문제를 해결하기 위해 아래와 같이 2단계 접근 방식을 사용합니다.

*   **1단계 (데이터 동기화 강화):** `sync_kopis.py`를 수정하여 KOPIS API로부터 **최대한 많은 공연 정보를 완전하게** 가져와 데이터베이스에 저장합니다.
*   **2단계 (백엔드 데이터 변환):** `web_app.py`에서 DB 데이터를 프론트엔드가 요구하는 구조로 변환하여 API를 통해 제공합니다.

## 3. 상세 리팩터링 계획

### **1단계: `sync_kopis.py` 수정 (데이터 동기화 강화)**

*   **목표:** 페이지네이션을 구현하고 조회 기간을 확장하여 KOPIS의 공연 정보를 빠짐없이 가져옵니다.
*   **수정 파일:** `sync_kopis.py`
*   **수정 로직:**
    1.  **조회 기간 확장:** `sync_performances` 함수에서 `timedelta(days=30)`을 `timedelta(days=90)` 등으로 늘려 더 넓은 기간의 데이터를 조회하도록 변경합니다.
    2.  **페이지네이션 구현:** `get_performance_list` 함수를 반복 호출하며 `cpage`를 1씩 증가시킵니다. 더 이상 결과가 없거나(빈 리스트 반환) 조회된 개수가 100개 미만일 때 반복을 중단합니다.

    ```python
    # sync_kopis.py의 sync_performances 함수 내 수정 제안 (의사코드)

    # 1. 조회 기간 확장 (예: 90일)
    start_date = datetime.now().strftime('%Y%m%d')
    end_date = (datetime.now() + timedelta(days=90)).strftime('%Y%m%d')
    
    all_api_performances = []
    current_page = 1
    
    # 2. 페이지네이션 루프 구현
    while True:
        logger.info(f"{current_page} 페이지의 공연 목록을 가져옵니다...")
        # get_performance_list 호출 시 cpage 파라미터 전달
        api_performances_page = get_performance_list(api_key, start_date, end_date, rows='100', cpage=str(current_page))
        
        if not api_performances_page:
            logger.info("더 이상 가져올 공연 정보가 없어 루프를 종료합니다.")
            break
        
        # 단일 항목이 dict로 오는 경우 list로 변환
        if isinstance(api_performances_page, dict):
            api_performances_page = [api_performances_page]
            
        all_api_performances.extend(api_performances_page)
        
        # 가져온 개수가 100개 미만이면 마지막 페이지이므로 종료
        if len(api_performances_page) < 100:
            logger.info("마지막 페이지입니다. 루프를 종료합니다.")
            break
            
        current_page += 1

    # 이후 로직은 all_api_performances 리스트를 사용하여 동일하게 진행
    # ...
    ```

### **2단계: `web_app.py` 수정 (API 응답 데이터 변환)**

*   **목표:** `/api/tickets` 엔드포인트가 프론트엔드가 기대하는 형식의 데이터를 반환하도록 수정합니다.
*   **수정 파일:** `web_app.py`
*   **수정 로직:**
    1.  `DatabaseManager.get_all_performances()`로 데이터를 조회합니다.
    2.  각 공연 데이터를 프론트엔드 요구사항에 맞게 변환하는 `transform_performance_for_frontend` 함수를 정의하고 적용합니다.
        *   `name` → `title`
        *   `facility_name` → `place`
        *   `poster_url` → `image_url`
        *   `start_date` → `open_date`
        *   `source` 필드 추가 (값: "KOPIS")

### **3단계: `static/script.js` 검토**

*   **목표:** 백엔드 API 응답 변경 후 프론트엔드 코드가 정상 동작하는지 확인합니다.
*   **예상 결과:** 1, 2단계 수정이 올바르게 적용되면, 프론트엔드 코드는 **수정 없이** 모든 기능(필터링, 정렬, 표시)이 정상적으로 동작할 것입니다.