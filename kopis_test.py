import os
import json
import requests
from datetime import datetime, timedelta

def get_api_key():
    """config.json에서 KOPIS API 키를 읽어옵니다."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("KOPIS_API_KEY")
    except FileNotFoundError:
        print(f"Error: config.json 파일을 찾을 수 없습니다. 경로: {config_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: config.json 파일의 형식이 올바르지 않습니다.")
        return None

def get_performance_list(api_key):
    """KOPIS API를 사용하여 현재 날짜로부터 1개월간의 공연 목록을 조회합니다."""
    print("===== 공연 목록 조회 시작 =====")
    
    # API 엔드포인트 및 파라미터 설정
    url = "http://www.kopis.or.kr/openApi/restful/pblprfr"
    start_date = datetime.now().strftime('%Y%m%d')
    end_date = (datetime.now() + timedelta(days=30)).strftime('%Y%m%d')
    
    params = {
        'service': api_key,
        'stdate': start_date,
        'eddate': end_date,
        'cpage': '1',
        'rows': '10', # 테스트를 위해 10개만 조회
        'shcate': 'AAAA' # 장르: 연극
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        
        # XML 응답을 JSON으로 변환하는 것은 복잡하므로, 여기서는 텍스트로 출력합니다.
        # 실제 운영 코드에서는 xmltodict와 같은 라이브러리 사용을 권장합니다.
        print("공연 목록 조회 성공 (raw XML):")
        print(response.text[:500] + "...") # 너무 길어서 일부만 출력
        
        # 간단한 파싱으로 공연 ID 추출 (테스트 목적)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        performances = root.findall('.//db')
        
        if not performances:
            print("조회된 공연 목록이 없습니다.")
            return None
            
        print(f"\n총 {len(performances)}개의 공연 목록을 가져왔습니다.")
        for i, p in enumerate(performances[:3]): # 상위 3개만 출력
            title = p.find('prfnm').text
            mt20id = p.find('mt20id').text
            print(f"  [{i+1}] ID: {mt20id}, 제목: {title}")

        return performances

    except requests.exceptions.RequestException as e:
        print(f"공연 목록 조회 중 오류 발생: {e}")
        return None

def get_performance_detail(api_key, performance_id):
    """KOPIS API를 사용하여 특정 공연의 상세 정보를 조회합니다."""
    print(f"\n===== 공연 상세 정보 조회 시작 (ID: {performance_id}) =====")
    
    url = f"http://www.kopis.or.kr/openApi/restful/pblprfr/{performance_id}"
    params = {'service': api_key}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        print("공연 상세 정보 조회 성공 (raw XML):")
        print(response.text)
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        detail = root.find('.//db')
        
        if detail:
            title = detail.find('prfnm').text
            place = detail.find('fcltynm').text
            start_date = detail.find('prfpdfrom').text
            end_date = detail.find('prfpdto').text
            print("\n[상세 정보 요약]")
            print(f"  - 제목: {title}")
            print(f"  - 장소: {place}")
            print(f"  - 기간: {start_date} ~ {end_date}")
        
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"공연 상세 정보 조회 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    api_key = get_api_key()
    
    if not api_key:
        print("API 키를 찾을 수 없어 테스트를 종료합니다.")
    else:
        # 1. 공연 목록 조회 (REQ-002)
        performances = get_performance_list(api_key)
        
        if performances:
            # 2. 공연 상세 조회 (REQ-004)
            # 목록의 첫 번째 공연 ID를 사용하여 상세 정보 조회
            first_performance_id = performances[0].find('mt20id').text
            get_performance_detail(api_key, first_performance_id)
        else:
            print("조회된 공연이 없어 상세 정보 조회를 건너뜁니다.")