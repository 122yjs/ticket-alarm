"""
티켓 크롤러 기능 검증 스크립트
각 크롤러를 개별적으로 테스트하고 결과를 확인합니다.
"""
import time
from crawlers.interpark_crawler import get_interpark_notices
from crawlers.yes24_crawler import get_yes24_notices
from crawlers.melon_crawler import get_melon_notices
from crawlers.ticketlink_crawler import get_ticketlink_notices

def test_crawler(crawler_func, name):
    print(f"\n{'='*50}")
    print(f"{name} 크롤러 테스트 시작")
    print(f"{'='*50}")
    
    start_time = time.time()
    results = crawler_func()
    end_time = time.time()
    
    print(f"\n{name} 크롤러 테스트 결과:")
    print(f"- 실행 시간: {end_time - start_time:.2f}초")
    print(f"- 수집된 항목 수: {len(results)}")
    
    if results:
        print("\n수집된 데이터 샘플 (최대 5개):")
        for i, item in enumerate(results[:5]):
            print(f"\n[{i+1}] {item['title']}")
            print(f"  - 오픈 날짜: {item['open_date']}")
            print(f"  - 링크: {item['link']}")
            print(f"  - 출처: {item['source']}")
    else:
        print("\n수집된 데이터가 없습니다.")
    
    return results

def main():
    print("티켓 크롤러 기능 검증을 시작합니다.")
    
    # 각 크롤러 테스트
    crawlers = [
        (get_interpark_notices, "인터파크"),
        (get_yes24_notices, "YES24"),
        (get_melon_notices, "멜론티켓"),
        (get_ticketlink_notices, "티켓링크")
    ]
    
    all_results = []
    
    for crawler_func, name in crawlers:
        try:
            results = test_crawler(crawler_func, name)
            all_results.extend(results)
        except Exception as e:
            print(f"\n[오류] {name} 크롤러 테스트 중 예외 발생: {e}")
    
    print(f"\n{'='*50}")
    print(f"모든 크롤러 테스트 완료")
    print(f"총 수집된 항목 수: {len(all_results)}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()