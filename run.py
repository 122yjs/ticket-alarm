# -*- coding: utf-8 -*-
"""
티켓 정보 수집, 필터링, 저장 및 알림을 위한 통합 실행 스크립트.

이 스크립트는 다음 작업을 수행합니다:
1. 설정된 모든 웹사이트에서 티켓 공지 정보를 크롤링합니다.
2. 수집된 모든 티켓 정보를 단일 리스트로 통합합니다.
3. 티켓 정보를 날짜, 제목 등 다양한 기준으로 정렬하고 키워드로 검색합니다.
4. 최종 결과를 JSON 파일 형태로 'data' 폴더에 저장합니다.
5. 콘솔에 처리 결과를 출력합니다.
"""

import json
from datetime import datetime
import os
import re
import logging

# 크롤러 함수 임포트
from crawlers.interpark_crawler import get_interpark_notices
from crawlers.yes24_crawler import get_yes24_notices
from crawlers.melon_crawler import get_melon_notices
from crawlers.ticketlink_crawler import get_ticketlink_notices

# --- 데이터 폴더 관리 ---
DATA_DIR = "data"
ALL_TICKETS_FILE = os.path.join(DATA_DIR, "all_tickets.json")
SENT_NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "sent_notifications.json")

def ensure_data_directory():
    """
    데이터 저장을 위한 'data' 폴더가 있는지 확인하고, 없으면 생성합니다.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.info(f"'{DATA_DIR}' 폴더를 확인하고 준비했습니다.")

# --- 티켓 수집 ---
def collect_all_tickets():
    """
    모든 티켓 사이트 크롤러를 실행하고 결과를 하나로 합칩니다.
    """
    logging.info("모든 티켓 사이트의 정보 수집을 시작합니다...")
    
    # 각 크롤러를 병렬로 실행하면 더 효율적일 수 있으나, 우선 순차적으로 실행합니다.
    interpark_tickets = get_interpark_notices()
    yes24_tickets = get_yes24_notices()
    melon_tickets = get_melon_notices()
    ticketlink_tickets = get_ticketlink_notices()
    
    # 모든 결과를 하나의 리스트로 통합합니다.
    all_tickets = interpark_tickets + yes24_tickets + melon_tickets + ticketlink_tickets
    
    logging.info(f"크롤링 완료! 총 {len(all_tickets)}건의 티켓 정보를 수집했습니다.")
    return all_tickets

# --- 데이터 정제 및 필터링 ---
def parse_date(date_str):
    """
    다양한 형식의 날짜 문자열을 파싱하여 datetime 객체로 변환합니다.
    정확한 시간 정보가 없으면 기본값으로 자정을 사용합니다.
    """
    try:
        # 일반적인 날짜 형식에 대한 정규 표현식 패턴
        patterns = [
            # YYYY.MM.DD HH:MM
            (r'(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})[\s]+(\d{1,2}):(\d{1,2})', 5),
            # YYYY.MM.DD
            (r'(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})', 3),
            # MM.DD HH:MM
            (r'(\d{1,2})[\.\-/](\d{1,2})[\s]+(\d{1,2}):(\d{1,2})', 4),
            # MM월 DD일 HH시 MM분
            (r'(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시\s*(\d{1,2})분', 4),
        ]
        
        for pattern, group_count in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                now = datetime.now()
                if group_count == 5:  # YYYY.MM.DD HH:MM
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]), int(groups[4]))
                elif group_count == 3:  # YYYY.MM.DD
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                elif group_count == 4:  # MM.DD HH:MM or MM월 DD일 HH시 MM분
                    return datetime(now.year, int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]))
        
        # 알려진 패턴과 일치하지 않을 경우, 파싱 실패를 알립니다.
        logging.warning(f"날짜 형식을 파싱할 수 없습니다: '{date_str}'")
        return datetime.max # 정렬 시 맨 뒤로 가도록 설정
    except Exception as e:
        logging.error(f"날짜 파싱 중 예외 발생 - {e}, 입력: '{date_str}'")
        return datetime.max

def sort_by_date(tickets):
    """
    티켓 정보를 오픈 날짜순으로 정렬합니다.
    """
    logging.info("티켓을 날짜순으로 정렬합니다.")
    return sorted(tickets, key=lambda x: parse_date(x.get('open_date', '')))

def sort_by_title(tickets):
    """
    티켓 정보를 공연 제목의 가나다순으로 정렬합니다.
    """
    logging.info("티켓을 제목순으로 정렬합니다.")
    return sorted(tickets, key=lambda x: x.get('title', '').strip())

def search_tickets_by_keyword(tickets, keyword):
    """
    지정된 키워드가 제목에 포함된 티켓을 검색합니다. (대소문자 무시)
    """
    if not keyword:
        return tickets
    
    keyword = keyword.lower()
    logging.info(f"'{keyword}' 키워드로 티켓을 검색합니다.")
    return [ticket for ticket in tickets if keyword in ticket.get('title', '').lower()]

# --- 결과 출력 및 저장 ---
def display_tickets(tickets, title="티켓 정보"):
    """
    수집된 티켓 정보를 보기 좋은 형태로 콘솔에 출력합니다.
    """
    logging.info(f"--- {title} ({len(tickets)}건) ---")
    if not tickets:
        logging.info("표시할 티켓 정보가 없습니다.")
        return
        
    for i, ticket in enumerate(tickets, 1):
        logging.info(f"{i:2d}. [{ticket.get('source', 'N/A')}] {ticket.get('open_date', '날짜 미정')} - {ticket.get('title', '제목 없음')}")
        logging.info(f"    └ 링크: {ticket.get('link', '링크 없음')}")
    logging.info("-" * 80)

def save_tickets_to_json(tickets, filename):
    """
    티켓 정보를 지정된 파일 이름으로 JSON 형식으로 저장합니다.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tickets, f, ensure_ascii=False, indent=2)
        logging.info(f"티켓 정보가 '{filename}' 파일에 성공적으로 저장되었습니다.")
    except IOError as e:
        logging.error(f"'{filename}' 파일에 쓰는 중 에러가 발생했습니다 - {e}")

# --- 메인 실행 로직 ---
def main():
    """
    메인 실행 함수
    """
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')

    logging.info("="*80)
    logging.info("티켓 알람 시스템을 시작합니다.")
    logging.info("="*80)

    # 1. 데이터 폴더 확인 및 생성
    ensure_data_directory()

    # 2. 모든 티켓 정보 수집
    all_tickets = collect_all_tickets()

    if not all_tickets:
        logging.info("수집된 티켓 정보가 없습니다. 시스템을 종료합니다.")
        return

    # 3. 날짜순으로 정렬
    date_sorted_tickets = sort_by_date(all_tickets)
    
    # 4. 키워드 검색 (예: '콘서트')
    keyword_to_search = "콘서트"
    search_results = search_tickets_by_keyword(date_sorted_tickets, keyword_to_search)

    # 5. 결과 출력
    display_tickets(date_sorted_tickets, "전체 티켓 목록 (날짜순 정렬)")
    display_tickets(search_results, f"'{keyword_to_search}' 키워드 검색 결과")

    # 6. 파일로 저장
    save_tickets_to_json(all_tickets, ALL_TICKETS_FILE)
    
    # sent_notifications.json 파일은 알림 발송 시 생성/사용되므로, 여기서는 빈 파일을 생성해 둘 수 있습니다.
    if not os.path.exists(SENT_NOTIFICATIONS_FILE):
        save_tickets_to_json([], SENT_NOTIFICATIONS_FILE)

    logging.info("모든 작업이 완료되었습니다. 시스템을 종료합니다.")
    logging.info("="*80)


if __name__ == "__main__":
    main()