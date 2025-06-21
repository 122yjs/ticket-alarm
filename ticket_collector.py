"""
티켓 정보 수집 및 필터링 시스템

모든 크롤러를 실행하여 티켓 정보를 수집하고,
시간순/공연순/아티스트별로 필터링하는 기능을 제공합니다.
"""
import datetime
import re
from crawlers.interpark_crawler import get_interpark_notices
from crawlers.yes24_crawler import get_yes24_notices
from crawlers.melon_crawler import get_melon_notices
from crawlers.ticketlink_crawler import get_ticketlink_notices

def collect_all_tickets():
    """모든 사이트에서 티켓 정보를 수집합니다."""
    print("모든 사이트에서 티켓 정보 수집을 시작합니다...")
    
    # 각 크롤러 실행
    interpark_tickets = get_interpark_notices()
    yes24_tickets = get_yes24_notices()
    melon_tickets = get_melon_notices()
    ticketlink_tickets = get_ticketlink_notices()
    
    # 모든 티켓 정보 합치기
    all_tickets = []
    all_tickets.extend(interpark_tickets)
    all_tickets.extend(yes24_tickets)
    all_tickets.extend(melon_tickets)
    all_tickets.extend(ticketlink_tickets)
    
    print(f"총 {len(all_tickets)}개의 티켓 정보가 수집되었습니다.")
    return all_tickets

def parse_date(date_str):
    """날짜 문자열을 파싱하여 datetime 객체로 변환합니다."""
    try:
        # 다양한 날짜 형식 처리
        patterns = [
            # YYYY.MM.DD HH:MM
            r'(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})[\s](\d{1,2}):(\d{1,2})',
            # YYYY.MM.DD
            r'(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})',
            # MM.DD HH:MM
            r'(\d{1,2})[\.\-/](\d{1,2})[\s](\d{1,2}):(\d{1,2})',
            # MM월 DD일 HH시 MM분
            r'(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시\s*(\d{1,2})분',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 5:  # YYYY.MM.DD HH:MM
                    return datetime.datetime(int(groups[0]), int(groups[1]), int(groups[2]), 
                                            int(groups[3]), int(groups[4]))
                elif len(groups) == 3:  # YYYY.MM.DD
                    return datetime.datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                elif len(groups) == 4:  # MM.DD HH:MM or MM월 DD일 HH시 MM분
                    current_year = datetime.datetime.now().year
                    return datetime.datetime(current_year, int(groups[0]), int(groups[1]), 
                                            int(groups[2]), int(groups[3]))
        
        # 패턴이 일치하지 않으면 현재 시간 반환
        print(f"날짜 형식을 파싱할 수 없습니다: {date_str}")
        return datetime.datetime.now()
    except Exception as e:
        print(f"날짜 파싱 중 오류 발생: {e}, 날짜: {date_str}")
        return datetime.datetime.now()

def sort_by_date(tickets):
    """티켓 정보를 날짜순으로 정렬합니다."""
    # 날짜 파싱 및 정렬
    try:
        return sorted(tickets, key=lambda x: parse_date(x['open_date']))
    except Exception as e:
        print(f"날짜순 정렬 중 오류 발생: {e}")
        return tickets

def sort_by_title(tickets):
    """티켓 정보를 공연 제목순으로 정렬합니다."""
    return sorted(tickets, key=lambda x: x['title'])

def filter_by_artist(tickets, artist_name):
    """특정 아티스트의 공연만 필터링합니다."""
    return [ticket for ticket in tickets if artist_name.lower() in ticket['title'].lower()]

def display_tickets(tickets, limit=None):
    """티켓 정보를 화면에 출력합니다."""
    if limit:
        tickets = tickets[:limit]
    
    print(f"\n{'='*80}")
    print(f"티켓 정보 ({len(tickets)}건)")
    print(f"{'='*80}")
    
    for i, ticket in enumerate(tickets):
        print(f"\n[{i+1}] {ticket['title']}")
        print(f"  - 오픈 날짜: {ticket['open_date']}")
        print(f"  - 출처: {ticket['source']}")
        print(f"  - 링크: {ticket['link']}")
    
    print(f"\n{'='*80}")

def save_to_file(tickets, filename="ticket_data.txt"):
    """티켓 정보를 파일로 저장합니다."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"티켓 정보 ({len(tickets)}건)\n")
            f.write(f"{'='*80}\n\n")
            
            for i, ticket in enumerate(tickets):
                f.write(f"[{i+1}] {ticket['title']}\n")
                f.write(f"  - 오픈 날짜: {ticket['open_date']}\n")
                f.write(f"  - 출처: {ticket['source']}\n")
                f.write(f"  - 링크: {ticket['link']}\n\n")
        
        print(f"티켓 정보가 {filename} 파일에 저장되었습니다.")
    except Exception as e:
        print(f"파일 저장 중 오류 발생: {e}")

def main():
    print("티켓 정보 수집 및 필터링 시스템을 시작합니다.")
    
    # 모든 티켓 정보 수집
    all_tickets = collect_all_tickets()
    
    if not all_tickets:
        print("수집된 티켓 정보가 없습니다.")
        return
    
    # 기본적으로 날짜순 정렬
    sorted_tickets = sort_by_date(all_tickets)
    
    # 결과 출력 및 저장
    display_tickets(sorted_tickets)
    save_to_file(sorted_tickets)
    
    # 필터링 예시
    print("\n제목순으로 정렬된 결과:")
    title_sorted = sort_by_title(all_tickets)
    display_tickets(title_sorted, limit=5)  # 처음 5개만 출력
    
    # 아티스트 필터링 예시
    artist_name = "콘서트"  # 예시 아티스트 이름
    print(f"\n'{artist_name}' 관련 공연:")
    artist_filtered = filter_by_artist(all_tickets, artist_name)
    display_tickets(artist_filtered)

if __name__ == "__main__":
    main()