"""
티켓 오픈 모니터링 시스템
주기적으로 티켓 사이트를 크롤링하고 새로운 정보를 디스코드로 알림을 보냅니다.
"""
import time
import random
import argparse
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from discord_notifier import DiscordNotifier
from crawlers.interpark_crawler import get_interpark_notices
from crawlers.yes24_crawler import get_yes24_notices
from crawlers.melon_crawler import get_melon_notices
from crawlers.ticketlink_crawler import get_ticketlink_notices


def save_all_tickets(tickets: List[Dict[str, Any]], filename: str = "all_tickets.json"):
    """수집된 모든 티켓 정보를 JSON 파일로 저장합니다."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "last_updated": datetime.now().isoformat(),
                "count": len(tickets),
                "tickets": tickets
            }, f, ensure_ascii=False, indent=2)
        print(f"{len(tickets)}개의 티켓 정보를 {filename}에 저장했습니다.")
    except Exception as e:
        print(f"티켓 정보 저장 중 오류 발생: {e}")


def collect_all_tickets(sources: List[str] = None) -> List[Dict[str, Any]]:
    """
    모든 소스에서 티켓 정보를 수집합니다.
    
    Args:
        sources: 크롤링할 소스 목록 (None이면 모든 소스 크롤링)
        
    Returns:
        수집된 티켓 정보 리스트
    """
    all_tickets = []
    
    # 소스가 지정되지 않았으면 모든 소스 크롤링
    if sources is None:
        sources = ["interpark", "yes24", "melon", "ticketlink"]
    
    # 각 소스별로 크롤링
    for source in sources:
        try:
            if source.lower() == "interpark":
                print("\n인터파크 크롤링 시작...")
                tickets = get_interpark_notices()
                all_tickets.extend(tickets)
                print(f"인터파크 크롤링 완료: {len(tickets)}개 수집")
                
            elif source.lower() == "yes24":
                print("\nYES24 크롤링 시작...")
                tickets = get_yes24_notices()
                all_tickets.extend(tickets)
                print(f"YES24 크롤링 완료: {len(tickets)}개 수집")
                
            elif source.lower() == "melon":
                print("\n멜론티켓 크롤링 시작...")
                tickets = get_melon_notices()
                all_tickets.extend(tickets)
                print(f"멜론티켓 크롤링 완료: {len(tickets)}개 수집")
                
            elif source.lower() == "ticketlink":
                print("\n티켓링크 크롤링 시작...")
                tickets = get_ticketlink_notices()
                all_tickets.extend(tickets)
                print(f"티켓링크 크롤링 완료: {len(tickets)}개 수집")
        except Exception as e:
            print(f"{source} 크롤링 중 오류 발생: {e}")
    
    return all_tickets


def monitor_tickets(webhook_url: str, interval: int = 3600, sources: List[str] = None):
    """
    주기적으로 티켓 정보를 모니터링하고 디스코드로 알림을 보냅니다.
    
    Args:
        webhook_url: 디스코드 웹훅 URL
        interval: 모니터링 간격(초)
        sources: 크롤링할 소스 목록
    """
    notifier = DiscordNotifier(webhook_url)
    
    print(f"티켓 모니터링을 시작합니다. 간격: {interval}초")
    
    try:
        while True:
            start_time = time.time()
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 티켓 정보 수집 시작")
            
            # 티켓 정보 수집
            tickets = collect_all_tickets(sources)
            
            # 모든 티켓 정보 저장
            save_all_tickets(tickets)
            
            # 새로운 티켓 정보만 알림 전송
            if tickets:
                sent_count = notifier.send_batch_notifications(tickets)
                print(f"\n{sent_count}개의 새로운 티켓 정보를 디스코드로 전송했습니다.")
            else:
                print("\n전송할 티켓 정보가 없습니다.")
            
            # 다음 실행까지 대기
            elapsed = time.time() - start_time
            wait_time = max(interval - elapsed, 0)
            
            # 정확한 간격을 위해 조금의 랜덤 지연 추가 (봇 감지 방지)
            jitter = random.uniform(0, 60)  # 0~60초 랜덤 지연
            wait_time += jitter
            
            next_run = datetime.now().timestamp() + wait_time
            next_run_str = datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n다음 실행 시간: {next_run_str} (약 {wait_time/60:.1f}분 후)")
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        print("\n모니터링을 종료합니다.")
    except Exception as e:
        print(f"\n모니터링 중 오류 발생: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="티켓 오픈 모니터링 시스템")
    parser.add_argument("--webhook", "-w", type=str, help="디스코드 웹훅 URL")
    parser.add_argument("--interval", "-i", type=int, default=3600, help="모니터링 간격(초), 기본값: 3600초(1시간)")
    parser.add_argument("--sources", "-s", type=str, nargs="+", choices=["interpark", "yes24", "melon", "ticketlink"], 
                        help="크롤링할 소스 목록 (지정하지 않으면 모든 소스 크롤링)")
    parser.add_argument("--config", "-c", type=str, help="설정 파일 경로")
    
    args = parser.parse_args()
    
    # 설정 파일이 있으면 로드
    config = {}
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {e}")
    
    # 명령줄 인수가 우선, 없으면 설정 파일에서 로드
    webhook_url = args.webhook or config.get('webhook_url')
    interval = args.interval or config.get('interval', 3600)
    sources = args.sources or config.get('sources')
    
    if not webhook_url:
        webhook_url = input("디스코드 웹훅 URL을 입력하세요: ")
    
    # 모니터링 시작
    monitor_tickets(webhook_url, interval, sources)


if __name__ == "__main__":
    main()