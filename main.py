from crawlers.interpark_crawler import get_interpark_notices
from crawlers.yes24_crawler import get_yes24_notices
from crawlers.melon_crawler import get_melon_notices
from crawlers.ticketlink_crawler import get_ticketlink_notices
import json
from datetime import datetime
import os

def run_all_crawlers():
    """모든 크롤러를 실행하고 결과를 합칩니다."""
    print("모든 티켓 사이트 크롤링을 시작합니다...")
    
    # 각 크롤러 실행
    interpark_tickets = get_interpark_notices()
    yes24_tickets = get_yes24_notices()
    melon_tickets = get_melon_notices()
    ticketlink_tickets = get_ticketlink_notices()
    
    # 모든 결과 합치기
    all_tickets = interpark_tickets + yes24_tickets + melon_tickets + ticketlink_tickets
    
    print(f"\n모든 크롤링 완료. 총 {len(all_tickets)}건의 티켓 정보를 수집했습니다.")
    return all_tickets

def save_tickets_to_json(tickets, filename=None):
    """티켓 정보를 JSON 파일로 저장합니다."""
    if filename is None:
        # 현재 날짜와 시간을 파일명에 포함
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tickets_{now}.json"
    
    # data 디렉토리가 없으면 생성
    os.makedirs("data", exist_ok=True)
    filepath = os.path.join("data", filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)
    
    print(f"티켓 정보가 '{filepath}' 파일에 저장되었습니다.")
    return filepath

def filter_tickets_by_date(tickets):
    """티켓을 날짜순으로 정렬합니다."""
    # 날짜 형식이 다양할 수 있으므로 원본 문자열 기준으로 정렬
    return sorted(tickets, key=lambda x: x["open_date"])

def filter_tickets_by_title(tickets):
    """티켓을 공연 제목순으로 정렬합니다."""
    return sorted(tickets, key=lambda x: x["title"])

def filter_tickets_by_source(tickets):
    """티켓을 소스(사이트)별로 정렬합니다."""
    return sorted(tickets, key=lambda x: x["source"])

def search_tickets_by_keyword(tickets, keyword):
    """키워드로 티켓을 검색합니다."""
    keyword = keyword.lower()
    return [ticket for ticket in tickets if keyword in ticket["title"].lower()]

def display_tickets(tickets):
    """티켓 정보를 콘솔에 출력합니다."""
    print(f"\n--- 티켓 정보 ({len(tickets)}건) ---")
    for i, ticket in enumerate(tickets, 1):
        print(f"{i}. [{ticket['source']}] {ticket['open_date']} - {ticket['title']}")
        print(f"   링크: {ticket['link']}")
        print("-" * 80)

if __name__ == "__main__":
    # 모든 크롤러 실행
    all_tickets = run_all_crawlers()
    
    if all_tickets:
        # 결과 저장
        save_tickets_to_json(all_tickets)
        
        # 날짜순으로 정렬하여 출력
        print("\n=== 날짜순 정렬 ===")
        date_sorted = filter_tickets_by_date(all_tickets)
        display_tickets(date_sorted)
        
        # 키워드 검색 예시
        keyword = "콘서트"  # 검색할 키워드 설정
        print(f"\n=== '{keyword}' 키워드 검색 결과 ===")
        search_results = search_tickets_by_keyword(all_tickets, keyword)
        display_tickets(search_results)
    else:
        print("수집된 티켓 정보가 없습니다.")