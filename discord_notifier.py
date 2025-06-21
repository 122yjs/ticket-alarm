"""
디스코드 알림 시스템
티켓 오픈 정보를 디스코드 웹훅을 통해 알림으로 전송합니다.
"""
import json
import requests
from datetime import datetime
import time
import os
from typing import List, Dict, Any, Optional

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        """
        디스코드 알림 시스템 초기화
        
        Args:
            webhook_url: 디스코드 웹훅 URL
        """
        self.webhook_url = webhook_url
        self.sent_notifications = self._load_sent_notifications()
    
    def _load_sent_notifications(self) -> Dict[str, Any]:
        """이전에 전송한 알림 기록을 로드합니다."""
        if os.path.exists('sent_notifications.json'):
            try:
                with open('sent_notifications.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"알림 기록 로드 중 오류 발생: {e}")
                return {}
        return {}
    
    def _save_sent_notifications(self):
        """전송한 알림 기록을 저장합니다."""
        try:
            with open('sent_notifications.json', 'w', encoding='utf-8') as f:
                json.dump(self.sent_notifications, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"알림 기록 저장 중 오류 발생: {e}")
    
    def is_new_ticket(self, ticket: Dict[str, Any]) -> bool:
        """
        새로운 티켓인지 확인합니다.
        
        Args:
            ticket: 티켓 정보
            
        Returns:
            새로운 티켓이면 True, 아니면 False
        """
        ticket_id = f"{ticket['source']}_{ticket['title']}_{ticket['open_date']}"
        return ticket_id not in self.sent_notifications
    
    def mark_as_sent(self, ticket: Dict[str, Any]):
        """
        티켓을 전송 완료로 표시합니다.
        
        Args:
            ticket: 티켓 정보
        """
        ticket_id = f"{ticket['source']}_{ticket['title']}_{ticket['open_date']}"
        self.sent_notifications[ticket_id] = {
            'sent_at': datetime.now().isoformat(),
            'ticket_info': ticket
        }
        self._save_sent_notifications()
    
    def create_embed(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        디스코드 임베드 메시지를 생성합니다.
        
        Args:
            ticket: 티켓 정보
            
        Returns:
            디스코드 임베드 메시지
        """
        # 소스별 색상 설정
        color_map = {
            "인터파크": 0x00AAFF,  # 파란색
            "YES24": 0x00FF00,    # 녹색
            "멜론티켓": 0x44CF00,  # 연두색
            "티켓링크": 0xFF5500   # 주황색
        }
        
        color = color_map.get(ticket['source'], 0x808080)  # 기본값은 회색
        
        return {
            "title": ticket['title'],
            "description": f"**오픈 일시:** {ticket['open_date']}",
            "url": ticket['link'],
            "color": color,
            "footer": {
                "text": f"출처: {ticket['source']} | 알림 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
    
    def send_notification(self, ticket: Dict[str, Any]) -> bool:
        """
        디스코드로 알림을 전송합니다.
        
        Args:
            ticket: 티켓 정보
            
        Returns:
            전송 성공 여부
        """
        if not self.is_new_ticket(ticket):
            print(f"이미 전송된 티켓입니다: {ticket['title']}")
            return False
        
        embed = self.create_embed(ticket)
        
        payload = {
            "content": f"🎫 **새로운 티켓 오픈 정보** 🎫",
            "embeds": [embed]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload
            )
            response.raise_for_status()
            
            # 전송 성공 시 기록
            self.mark_as_sent(ticket)
            print(f"알림 전송 성공: {ticket['title']}")
            return True
            
        except Exception as e:
            print(f"알림 전송 중 오류 발생: {e}")
            return False
    
    def send_batch_notifications(self, tickets: List[Dict[str, Any]], delay: float = 1.0) -> int:
        """
        여러 티켓 정보를 배치로 전송합니다.
        
        Args:
            tickets: 티켓 정보 리스트
            delay: 각 알림 사이의 지연 시간(초)
            
        Returns:
            성공적으로 전송된 알림 수
        """
        sent_count = 0
        
        for ticket in tickets:
            if self.send_notification(ticket):
                sent_count += 1
                # 디스코드 API 속도 제한 방지를 위한 지연
                time.sleep(delay)
        
        return sent_count


def main():
    # 테스트용 코드
    from crawlers.interpark_crawler import get_interpark_notices
    from crawlers.yes24_crawler import get_yes24_notices
    from crawlers.melon_crawler import get_melon_notices
    from crawlers.ticketlink_crawler import get_ticketlink_notices
    
    # 디스코드 웹훅 URL 설정
    webhook_url = "여기에_디스코드_웹훅_URL을_입력하세요"
    
    # 알림 시스템 초기화
    notifier = DiscordNotifier(webhook_url)
    
    # 모든 크롤러에서 데이터 수집
    all_tickets = []
    
    print("인터파크 크롤링 시작...")
    interpark_tickets = get_interpark_notices()
    all_tickets.extend(interpark_tickets)
    
    print("YES24 크롤링 시작...")
    yes24_tickets = get_yes24_notices()
    all_tickets.extend(yes24_tickets)
    
    print("멜론티켓 크롤링 시작...")
    melon_tickets = get_melon_notices()
    all_tickets.extend(melon_tickets)
    
    print("티켓링크 크롤링 시작...")
    ticketlink_tickets = get_ticketlink_notices()
    all_tickets.extend(ticketlink_tickets)
    
    # 수집된 티켓 정보 출력
    print(f"\n총 {len(all_tickets)}개의 티켓 정보를 수집했습니다.")
    
    # 알림 전송
    if all_tickets:
        sent_count = notifier.send_batch_notifications(all_tickets)
        print(f"\n{sent_count}개의 새로운 티켓 정보를 디스코드로 전송했습니다.")
    else:
        print("\n전송할 티켓 정보가 없습니다.")


if __name__ == "__main__":
    main()