# -*- coding: utf-8 -*-
"""
KOPIS API에서 공연 정보를 가져와 로컬 SQLite 데이터베이스에 동기화하는 스크립트.
"""
import time
from datetime import datetime, timedelta

# 내부 모듈 임포트
from kopis_test import get_api_key, get_performance_list, get_performance_detail
from database_manager import create_table, upsert_performance


def sync_data():
    """
    KOPIS API로부터 공연 데이터를 가져와 데이터베이스에 동기화합니다.
    """
    print("데이터베이스 테이블을 준비합니다...")
    create_table()

    try:
        api_key = get_api_key()
        print("KOPIS API 키를 성공적으로 불러왔습니다.")
    except (FileNotFoundError, KeyError) as e:
        print(f"오류: {e}")
        return

    # REQ-002: 오늘부터 60일 후까지의 공연 목록 조회
    today = datetime.now()
    start_date = today.strftime('%Y%m%d')
    end_date = (today + timedelta(days=60)).strftime('%Y%m%d')

    print(f"공연 목록을 조회합니다. (기간: {start_date} ~ {end_date})")
    # 테스트를 위해 초기에는 rows=20으로 제한
    performance_list = get_performance_list(api_key, start_date, end_date, rows=20)

    if not performance_list:
        print("조회된 공연 목록이 없습니다.")
        return

    print(f"총 {len(performance_list)}개의 공연 목록을 찾았습니다. 상세 정보 동기화를 시작합니다.")

    for performance_summary in performance_list:
        perf_id = performance_summary['mt20id']
        perf_name = performance_summary['prfnm']
        print(f"동기화 중: {perf_name} ({perf_id})")

        # 상세 정보 조회
        detail = get_performance_detail(api_key, perf_id)

        if detail:
            # REQ-005: API 응답을 DB 스키마에 맞게 매핑
            performance_data = {
                'kopis_id': detail.get('mt20id'),
                'name': detail.get('prfnm'),
                'start_date': detail.get('prfpdfrom'),
                'end_date': detail.get('prfpdto'),
                'facility_name': detail.get('fcltynm'),
                'poster_url': detail.get('poster'),
                'genre': detail.get('genrenm'),
                'status': detail.get('prfstate'),
                'cast': detail.get('prfcast'),
                'crew': detail.get('prfcrew'),
                'runtime': detail.get('prfruntime'),
                'age_limit': detail.get('prfage'),
                'price': detail.get('pcseguidance'),
                'synopsis': detail.get('sty')
            }
            
            # 데이터베이스에 저장 (Upsert)
            upsert_performance(performance_data)
        else:
            print(f"  -> 상세 정보 조회 실패: {perf_name}")
        
        # API 요청 간에 약간의 지연시간을 두어 서버 부하를 줄입니다.
        time.sleep(0.1)


if __name__ == "__main__":
    print("=" * 50)
    print("KOPIS 데이터 동기화 스크립트를 시작합니다.")
    print("=" * 50)

    start_time = time.time()
    sync_data()
    end_time = time.time()

    print("\n" + "=" * 50)
    print(f"동기화가 완료되었습니다. (총 소요 시간: {end_time - start_time:.2f}초)")
    print("=" * 50)