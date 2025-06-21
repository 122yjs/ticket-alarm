"""
티켓링크 크롤러 테스트 스크립트
"""
from crawlers.ticketlink_crawler import get_ticketlink_notices

def main():
    print("티켓링크 크롤러 테스트를 시작합니다.")
    tickets = get_ticketlink_notices()
    
    if tickets:
        print(f"\n--- 최종 결과 ({len(tickets)}건) ---")
        for i, ticket in enumerate(tickets):
            print(f"{i+1}. [{ticket['source']}] {ticket['open_date']} - {ticket['title']}")
            print(f"   링크: {ticket['link']}")
    else:
        print("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()