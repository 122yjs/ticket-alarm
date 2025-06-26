import os
import json
import requests
import xmltodict
from datetime import datetime, timedelta
from database_manager import DatabaseManager
from loguru import logger

# 로거 설정
logger.add("logs/sync_kopis.log", rotation="10 MB", level="DEBUG", format="{time} {level} {message}")

def get_api_key():
    """config.json에서 KOPIS API 키를 읽어옵니다."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("KOPIS_API_KEY")
    except FileNotFoundError:
        logger.error(f"설정 파일을 찾을 수 없습니다: {config_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"설정 파일의 형식이 올바르지 않습니다: {config_path}")
        return None

def get_performance_list(api_key, start_date, end_date, rows='100'):
    """KOPIS API를 사용하여 지정된 기간의 모든 공연 목록을 페이지네이션을 통해 조회합니다."""
    url = "http://www.kopis.or.kr/openApi/restful/pblprfr"
    all_performances = []
    cpage = 1
    
    while True:
        params = {
            'service': api_key,
            'stdate': start_date,
            'eddate': end_date,
            'cpage': str(cpage),
            'rows': rows,
        }
        try:
            logger.info(f"KOPIS API에서 {cpage} 페이지의 공연 목록을 가져옵니다...")
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = xmltodict.parse(response.content)
            
            # API 응답이 리스트가 아닌 경우를 대비
            page_data = data.get('dbs', {}).get('db')
            if not page_data:
                logger.info("더 이상 가져올 공연 정보가 없습니다. 조회를 중단합니다.")
                break

            # 공연 정보가 하나일 경우 dict로, 여러 개일 경우 list로 반환되므로 항상 list로 처리
            if isinstance(page_data, dict):
                page_data = [page_data]
            
            all_performances.extend(page_data)
            
            cpage += 1

        except requests.exceptions.RequestException as e:
            logger.error(f"KOPIS 공연 목록 API 호출 중 오류 발생 (페이지: {cpage}): {e}")
            break
        except Exception as e:
            logger.error(f"KOPIS 공연 목록 처리 중 예외 발생 (페이지: {cpage}): {e}")
            break
            
    return all_performances

def get_performance_detail(api_key, performance_id):
    """KOPIS API를 사용하여 특정 공연의 상세 정보를 조회합니다."""
    url = f"http://www.kopis.or.kr/openApi/restful/pblprfr/{performance_id}"
    params = {'service': api_key}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = xmltodict.parse(response.content)
        return data.get('dbs', {}).get('db', None)
    except requests.exceptions.RequestException as e:
        logger.error(f"KOPIS 공연 상세 API 호출 중 오류 발생 (ID: {performance_id}): {e}")
        return None
    except Exception as e:
        logger.error(f"KOPIS 공연 상세 정보 처리 중 오류 발생 (ID: {performance_id}): {e}")
        return None

def sync_performances():
    """KOPIS API의 공연 정보를 데이터베이스와 동기화합니다."""
    logger.info("KOPIS 데이터 동기화 작업을 시작합니다.")

    api_key = get_api_key()
    if not api_key:
        logger.error("KOPIS API 키가 없어 동기화 작업을 중단합니다.")
        return

    db_manager = DatabaseManager()

    # 1. API에서 공연 목록 가져오기 (향후 90일, 페이지네이션 자동 처리)
    start_date = datetime.now().strftime('%Y%m%d')
    end_date = (datetime.now() + timedelta(days=90)).strftime('%Y%m%d')
    
    api_performances = get_performance_list(api_key, start_date, end_date, rows='100')

    if not api_performances:
        logger.warning("KOPIS API에서 가져올 공연 정보가 없습니다.")
        return

    # 2. DB에 저장된 모든 공연의 kopis_id 조회
    db_kopis_ids = set(db_manager.get_all_kopis_ids())
    logger.info(f"DB에 저장된 공연 수: {len(db_kopis_ids)}개")
    
    insert_count = 0
    update_count = 0

    # 3. API 목록과 DB 목록 비교하여 동기화
    for perf in api_performances:
        logger.debug(f"Processing perf: {perf}")
        kopis_id = perf.get('mt20id')
        if not kopis_id:
            logger.warning(f"Skipping item due to missing 'mt20id': {perf}")
            continue

        if kopis_id not in db_kopis_ids:
            # INSERT: 신규 공연
            detail_info = get_performance_detail(api_key, kopis_id)
            logger.debug(f"Fetched detail_info for {kopis_id}: {detail_info}")
            if detail_info:
                performance_data = {
                    'kopis_id': detail_info.get('mt20id'),
                    'name': detail_info.get('prfnm'),
                    'start_date': detail_info.get('prfpdfrom'),
                    'end_date': detail_info.get('prfpdto'),
                    'facility_name': detail_info.get('fcltynm'),
                    'poster_url': detail_info.get('poster'),
                    'genre': detail_info.get('genrenm'),
                    'status': detail_info.get('prfstate'),
                    'cast': detail_info.get('prfcast'),
                    'crew': detail_info.get('prfcrew'),
                    'runtime': detail_info.get('prfruntime'),
                    'age_limit': detail_info.get('prfage'),
                    'price': detail_info.get('pcseguidance'),
                    'synopsis': detail_info.get('sty'),
                    'relates_url': detail_info.get('relateurl'),
                }
                # None 값을 가진 필드 제거
                performance_data = {k: v for k, v in performance_data.items() if v is not None}
                
                db_manager.insert_performance(performance_data)
                insert_count += 1
                logger.info(f"INSERT: 신규 공연 '{performance_data['name']}' (ID: {kopis_id}) 추가")
        else:
            # UPDATE: 기존 공연 정보 업데이트
            update_data = {
                'end_date': perf.get('prfpdto'),
                'status': perf.get('prfstate'),
            }
            # None 값을 가진 필드 제거
            update_data = {k: v for k, v in update_data.items() if v is not None}

            if update_data:
                db_manager.update_performance(kopis_id, update_data)
                update_count += 1
                logger.info(f"UPDATE: 기존 공연 '{perf.get('prfnm')}' (ID: {kopis_id}) 정보 업데이트")

    logger.info("KOPIS 데이터 동기화 작업 완료.")
    logger.info(f"총 {len(api_performances)}건 처리. 신규 추가: {insert_count}건, 정보 업데이트: {update_count}건")

if __name__ == "__main__":
    sync_performances()