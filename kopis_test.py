import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def get_api_key():
    """
    config.json 파일에서 KOPIS_API_KEY를 읽어옵니다.

    Returns:
        str: KOPIS API 키
    Raises:
        FileNotFoundError: config.json 파일이 없을 경우
        KeyError: KOPIS_API_KEY가 파일에 없을 경우
    """
    config_path = 'config.json'
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"'{config_path}' 파일을 찾을 수 없습니다. 'config.json.example'을 복사하여 생성하고 API 키를 입력해주세요.")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    api_key = config.get('KOPIS_API_KEY')
    if not api_key:
        raise KeyError("'KOPIS_API_KEY'를 config.json 파일에서 찾을 수 없습니다.")

    return api_key

def get_performance_list(api_key, start_date, end_date, page=1, rows=10):
    """
    KOPIS 공연 목록 조회 API를 호출합니다. (REQ-002)

    Args:
        api_key (str): KOPIS API 서비스 키
        start_date (str): 조회 시작일 (YYYYMMDD)
        end_date (str): 조회 종료일 (YYYYMMDD)
        page (int, optional): 페이지 번호. Defaults to 1.
        rows (int, optional): 페이지 당 목록 수. Defaults to 10.

    Returns:
        list: 공연 목록 (dict 리스트)
    """
    url = "http://www.kopis.or.kr/openApi/restful/pblprfr"
    params = {
        'service': api_key,
        'stdate': start_date,
        'eddate': end_date,
        'cpage': str(page),
        'rows': str(rows)
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # 200이 아닌 경우 HTTPError 발생

        root = ET.fromstring(response.content)
        performance_list = []
        for item in root.findall('.//db'):
            performance = {
                'mt20id': item.find('mt20id').text,
                'prfnm': item.find('prfnm').text,
                'prfpdfrom': item.find('prfpdfrom').text,
                'prfpdto': item.find('prfpdto').text,
                'fcltynm': item.find('fcltynm').text,
                'poster': item.find('poster').text,
                'genrenm': item.find('genrenm').text,
                'prfstate': item.find('prfstate').text,
                'openrun': item.find('openrun').text,
            }
            performance_list.append(performance)
        return performance_list

    except requests.exceptions.RequestException as e:
        print(f"API 요청 실패: {e}")
        if response:
            print("--- 응답 내용 (XML) ---")
            print(response.text)
        return None

def get_performance_detail(api_key, performance_id):
    """
    KOPIS 공연 상세 조회 API를 호출합니다. (REQ-004)

    Args:
        api_key (str): KOPIS API 서비스 키
        performance_id (str): 공연 ID (mt20id)

    Returns:
        dict: 공연 상세 정보
    """
    url = f"http://www.kopis.or.kr/openApi/restful/pblprfr/{performance_id}"
    params = {'service': api_key}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        detail_item = root.find('.//db')
        if detail_item:
            performance_detail = {
                'mt20id': detail_item.find('mt20id').text,
                'prfnm': detail_item.find('prfnm').text,
                'prfpdfrom': detail_item.find('prfpdfrom').text,
                'prfpdto': detail_item.find('prfpdto').text,
                'fcltynm': detail_item.find('fcltynm').text,
                'prfcast': detail_item.find('prfcast').text,
                'prfcrew': detail_item.find('prfcrew').text,
                'prfruntime': detail_item.find('prfruntime').text,
                'prfage': detail_item.find('prfage').text,
                'entrpsnm': detail_item.find('entrpsnm').text,
                'pcseguidance': detail_item.find('pcseguidance').text,
                'poster': detail_item.find('poster').text,
                'sty': detail_item.find('sty').text,
                'genrenm': detail_item.find('genrenm').text,
                'prfstate': detail_item.find('prfstate').text,
                'openrun': detail_item.find('openrun').text,
                'styurls': [url.text for url in detail_item.findall('.//styurl')],
                'mt10id': detail_item.find('mt10id').text,
                'dtguidance': detail_item.find('dtguidance').text,
            }
            return performance_detail
        return None

    except requests.exceptions.RequestException as e:
        print(f"API 요청 실패: {e}")
        if response:
            print("--- 응답 내용 (XML) ---")
            print(response.text)
        return None


if __name__ == "__main__":
    try:
        API_KEY = get_api_key()

        # 1. 공연 목록 조회 테스트
        print("--- 공연 목록 조회 테스트 ---")
        today = datetime.now()
        start_date = today.strftime('%Y%m%d')
        end_date = (today + timedelta(days=30)).strftime('%Y%m%d')

        print(f"조회 기간: {start_date} ~ {end_date}")
        performances = get_performance_list(API_KEY, start_date, end_date, page=1, rows=5)

        if performances:
            print(f"총 {len(performances)}개의 공연 정보를 가져왔습니다.")
            for i, p in enumerate(performances):
                print(f"  [{i+1}] {p['prfnm']} ({p['mt20id']})")

            # 2. 공연 상세 조회 테스트 (첫 번째 공연)
            if performances:
                first_perf_id = performances[0]['mt20id']
                print(f"\n--- '{performances[0]['prfnm']}' 상세 정보 조회 테스트 ---")
                detail = get_performance_detail(API_KEY, first_perf_id)

                if detail:
                    print(json.dumps(detail, indent=2, ensure_ascii=False))

    except (FileNotFoundError, KeyError) as e:
        print(f"오류: {e}")