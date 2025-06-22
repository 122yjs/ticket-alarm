"""  
디스코드 알림 시스템
티켓 오픈 정보를 디스코드 웹훅을 통해 알림으로 전송합니다.
개선된 기능:
- 향상된 메시지 가독성
- 강화된 중복 알림 방지
- 사용자 맞춤형 키워드 필터링
- 우선순위 기반 알림
"""
import json
import requests
from datetime import datetime, timedelta
import time
import os
import logging
import re
import hashlib
from typing import List, Dict, Any, Optional, Set

class DiscordNotifier:
    def __init__(self, webhook_url: str, keywords: Optional[List[str]] = None, priority_keywords: Optional[List[str]] = None):
        """
        디스코드 알림 시스템 초기화
        
        Args:
            webhook_url: 디스코드 웹훅 URL
            keywords: 일반 키워드 목록 (선택사항)
            priority_keywords: 우선순위 키워드 목록 (선택사항)
        """
        self.webhook_url = webhook_url
        self.keywords = keywords or []
        self.priority_keywords = priority_keywords or []
        self.sent_notifications = self._load_sent_notifications()
        self.notification_history = self._load_notification_history()
        
        # 중복 방지를 위한 해시 저장소
        self.ticket_hashes: Set[str] = set()
        self._load_ticket_hashes()
    
    def _load_sent_notifications(self) -> Dict[str, Any]:
        """이전에 전송한 알림 기록을 로드합니다."""
        notifications_file = os.path.join('data', 'sent_notifications.json')
        if os.path.exists(notifications_file):
            try:
                with open(notifications_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 30일 이상 된 기록은 정리
                    self._cleanup_old_notifications(data)
                    return data
            except Exception as e:
                logging.error(f"알림 기록 로드 중 오류 발생: {e}")
                return {}
        return {}
    
    def _load_notification_history(self) -> Dict[str, Any]:
        """알림 전송 이력을 로드합니다."""
        history_file = os.path.join('data', 'notification_history.json')
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"알림 이력 로드 중 오류 발생: {e}")
                return {'daily_counts': {}, 'total_sent': 0}
        return {'daily_counts': {}, 'total_sent': 0}
    
    def _load_ticket_hashes(self):
        """티켓 해시 정보를 로드합니다."""
        for ticket_id in self.sent_notifications.keys():
            self.ticket_hashes.add(ticket_id)
    
    def _cleanup_old_notifications(self, notifications: Dict[str, Any]):
        """30일 이상 된 알림 기록을 정리합니다."""
        cutoff_date = datetime.now() - timedelta(days=30)
        to_remove = []
        
        for ticket_id, data in notifications.items():
            try:
                sent_at = datetime.fromisoformat(data.get('sent_at', ''))
                if sent_at < cutoff_date:
                    to_remove.append(ticket_id)
            except (ValueError, TypeError):
                # 잘못된 날짜 형식인 경우 제거
                to_remove.append(ticket_id)
        
        for ticket_id in to_remove:
            del notifications[ticket_id]
            self.ticket_hashes.discard(ticket_id)
        
        if to_remove:
            logging.info(f"{len(to_remove)}개의 오래된 알림 기록을 정리했습니다.")
    
    def _save_sent_notifications(self):
        """전송한 알림 기록을 저장합니다."""
        try:
            # data 디렉토리가 없으면 생성
            if not os.path.exists('data'):
                os.makedirs('data')
            
            notifications_file = os.path.join('data', 'sent_notifications.json')
            with open(notifications_file, 'w', encoding='utf-8') as f:
                json.dump(self.sent_notifications, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"알림 기록 저장 중 오류 발생: {e}")
    
    def _save_notification_history(self):
        """알림 전송 이력을 저장합니다."""
        try:
            if not os.path.exists('data'):
                os.makedirs('data')
            
            history_file = os.path.join('data', 'notification_history.json')
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.notification_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"알림 이력 저장 중 오류 발생: {e}")
    
    def _generate_ticket_hash(self, ticket: Dict[str, Any]) -> str:
        """티켓 정보로부터 고유 해시를 생성합니다."""
        # 제목, 출처, 오픈 날짜, 링크를 조합하여 해시 생성
        content = f"{ticket.get('source', '')}_{ticket.get('title', '')}_{ticket.get('open_date', '')}_{ticket.get('link', '')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def is_new_ticket(self, ticket: Dict[str, Any]) -> bool:
        """
        새로운 티켓인지 확인합니다.
        향상된 중복 검사 로직을 사용합니다.
        
        Args:
            ticket: 티켓 정보
            
        Returns:
            새로운 티켓이면 True, 아니면 False
        """
        # 기존 방식과 새로운 해시 방식 모두 확인
        legacy_id = f"{ticket.get('source', '')}_{ticket.get('title', '')}_{ticket.get('open_date', '')}"
        ticket_hash = self._generate_ticket_hash(ticket)
        
        # 둘 중 하나라도 이미 존재하면 중복으로 판단
        return legacy_id not in self.sent_notifications and ticket_hash not in self.ticket_hashes
    
    def mark_as_sent(self, ticket: Dict[str, Any]):
        """
        티켓을 전송 완료로 표시합니다.
        
        Args:
            ticket: 티켓 정보
        """
        ticket_id = f"{ticket.get('source', '')}_{ticket.get('title', '')}_{ticket.get('open_date', '')}"
        ticket_hash = self._generate_ticket_hash(ticket)
        
        # 기존 방식과 새로운 해시 방식 모두 저장
        self.sent_notifications[ticket_id] = {
            'sent_at': datetime.now().isoformat(),
            'ticket_hash': ticket_hash,
            'ticket_info': ticket
        }
        self.ticket_hashes.add(ticket_hash)
        
        # 일일 통계 업데이트
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.notification_history['daily_counts']:
            self.notification_history['daily_counts'][today] = 0
        self.notification_history['daily_counts'][today] += 1
        self.notification_history['total_sent'] = self.notification_history.get('total_sent', 0) + 1
        
        self._save_sent_notifications()
        self._save_notification_history()
    
    def _check_priority(self, ticket: Dict[str, Any]) -> bool:
        """티켓이 우선순위 키워드를 포함하는지 확인합니다."""
        if not self.priority_keywords:
            return False
        
        title = ticket.get('title', '').lower()
        return any(keyword.lower() in title for keyword in self.priority_keywords)
    
    def _format_open_date(self, open_date: str) -> str:
        """오픈 날짜를 보기 좋게 포맷팅합니다."""
        if not open_date:
            return "날짜 미정"
        
        # 다양한 날짜 형식을 표준화
        try:
            # 기본적인 정리
            formatted_date = open_date.strip()
            
            # "오픈" 문자 제거
            formatted_date = re.sub(r'오픈\s*', '', formatted_date)
            
            # 연도가 없는 경우 현재 연도 추가
            if not re.search(r'\d{4}', formatted_date):
                current_year = datetime.now().year
                formatted_date = f"{current_year}년 {formatted_date}"
            
            return formatted_date
        except Exception:
            return open_date
    
    def _get_ticket_emoji(self, ticket: Dict[str, Any]) -> str:
        """티켓 유형에 따른 이모지를 반환합니다."""
        title = ticket.get('title', '').lower()
        
        if any(keyword in title for keyword in ['콘서트', '공연', '라이브']):
            return "🎵"
        elif any(keyword in title for keyword in ['뮤지컬', '연극', '오페라']):
            return "🎭"
        elif any(keyword in title for keyword in ['스포츠', '야구', '축구', '농구']):
            return "⚽"
        elif any(keyword in title for keyword in ['전시', '박람회', '페스티벌']):
            return "🎨"
        else:
            return "🎫"
    
    def create_embed(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        디스코드 임베드 메시지를 생성합니다.
        향상된 가독성과 정보 표시를 제공합니다.
        
        Args:
            ticket: 티켓 정보
            
        Returns:
            디스코드 임베드 메시지
        """
        # 소스별 색상 설정 (우선순위 티켓은 더 밝은 색상)
        is_priority = self._check_priority(ticket)
        
        color_map = {
            "인터파크": 0x0099FF if is_priority else 0x0066CC,  # 파란색
            "YES24": 0x00FF66 if is_priority else 0x00CC44,    # 녹색
            "멜론티켓": 0x66FF00 if is_priority else 0x44CC00,  # 연두색
            "티켓링크": 0xFF6600 if is_priority else 0xCC4400   # 주황색
        }
        
        source = ticket.get('source', '알 수 없음')
        color = color_map.get(source, 0xFF0000 if is_priority else 0x808080)
        
        # 티켓 제목에 이모지 추가
        emoji = self._get_ticket_emoji(ticket)
        title = f"{emoji} {ticket.get('title', '제목 없음')}"
        
        # 우선순위 티켓 표시
        if is_priority:
            title = f"⭐ {title}"
        
        # 설명 필드 구성
        formatted_date = self._format_open_date(ticket.get('open_date', ''))
        description_parts = [f"**📅 오픈 일시:** {formatted_date}"]
        
        # 추가 정보가 있다면 포함
        if ticket.get('venue'):
            description_parts.append(f"**📍 장소:** {ticket['venue']}")
        
        if ticket.get('price'):
            description_parts.append(f"**💰 가격:** {ticket['price']}")
        
        description = "\n".join(description_parts)
        
        # 푸터 텍스트 개선
        footer_text = f"출처: {source} | 알림: {datetime.now().strftime('%m/%d %H:%M')}"
        if is_priority:
            footer_text += " | ⭐ 우선순위 알림"
        
        embed = {
            "title": title,
            "description": description,
            "url": ticket.get('link', ''),
            "color": color,
            "footer": {
                "text": footer_text
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 썸네일 추가 (소스별)
        thumbnail_map = {
            "인터파크": "https://i.imgur.com/interpark_icon.png",  # 실제 아이콘 URL로 교체 필요
            "YES24": "https://i.imgur.com/yes24_icon.png",
            "멜론티켓": "https://i.imgur.com/melon_icon.png",
            "티켓링크": "https://i.imgur.com/ticketlink_icon.png"
        }
        
        if source in thumbnail_map:
            embed["thumbnail"] = {"url": thumbnail_map[source]}
        
        return embed
    
    def _create_notification_content(self, ticket: Dict[str, Any]) -> str:
        """알림 메시지의 컨텐츠를 생성합니다."""
        is_priority = self._check_priority(ticket)
        
        if is_priority:
            return "🚨 **우선순위 티켓 오픈 알림** 🚨"
        else:
            return "🎫 **새로운 티켓 오픈 정보** 🎫"
    
    def _should_send_notification(self, ticket: Dict[str, Any]) -> bool:
        """알림을 전송해야 하는지 확인합니다."""
        # 새로운 티켓인지 확인
        if not self.is_new_ticket(ticket):
            return False
        
        # 키워드 필터링 (키워드가 설정된 경우)
        if self.keywords:
            title = ticket.get('title', '').lower()
            if not any(keyword.lower() in title for keyword in self.keywords):
                logging.info(f"키워드 필터링으로 제외된 티켓: {ticket.get('title', '')}")
                return False
        
        return True
    
    def send_notification(self, ticket: Dict[str, Any]) -> bool:
        """
        디스코드로 알림을 전송합니다.
        향상된 필터링과 우선순위 처리를 포함합니다.
        
        Args:
            ticket: 티켓 정보
            
        Returns:
            전송 성공 여부
        """
        if not self._should_send_notification(ticket):
            return False
        
        embed = self.create_embed(ticket)
        content = self._create_notification_content(ticket)
        
        payload = {
            "content": content,
            "embeds": [embed]
        }
        
        # 우선순위 티켓의 경우 @everyone 멘션 추가 (선택사항)
        is_priority = self._check_priority(ticket)
        if is_priority:
            payload["content"] = f"@here {content}"  # @everyone 대신 @here 사용 (온라인 사용자만)
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10  # 타임아웃 설정
            )
            response.raise_for_status()
            
            # 전송 성공 시 기록
            self.mark_as_sent(ticket)
            
            priority_text = " (우선순위)" if is_priority else ""
            logging.info(f"알림 전송 성공{priority_text}: {ticket.get('title', '')}")
            return True
            
        except requests.exceptions.Timeout:
            logging.error(f"알림 전송 타임아웃: {ticket.get('title', '')}")
            return False
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit
                logging.warning(f"디스코드 API 속도 제한 도달. 잠시 대기 후 재시도합니다.")
                time.sleep(5)
                return self.send_notification(ticket)  # 재시도
            else:
                logging.error(f"HTTP 오류 발생: {e.response.status_code} - {e}")
                return False
        except Exception as e:
            logging.error(f"알림 전송 중 오류 발생: {e}")
            return False
    
    def send_batch_notifications(self, tickets: List[Dict[str, Any]], delay: float = 1.0, max_per_batch: int = 10) -> Dict[str, int]:
        """
        여러 티켓 정보를 배치로 전송합니다.
        우선순위 티켓을 먼저 처리하고, 배치 크기를 제한합니다.
        
        Args:
            tickets: 티켓 정보 리스트
            delay: 각 알림 사이의 지연 시간(초)
            max_per_batch: 한 번에 처리할 최대 티켓 수
            
        Returns:
            전송 결과 통계 (성공, 실패, 스킵 수)
        """
        if not tickets:
            return {'sent': 0, 'failed': 0, 'skipped': 0}
        
        # 우선순위 티켓과 일반 티켓 분리
        priority_tickets = []
        normal_tickets = []
        
        for ticket in tickets:
            if self._check_priority(ticket):
                priority_tickets.append(ticket)
            else:
                normal_tickets.append(ticket)
        
        # 우선순위 티켓을 먼저 정렬 (날짜순)
        priority_tickets.sort(key=lambda x: x.get('open_date', ''))
        normal_tickets.sort(key=lambda x: x.get('open_date', ''))
        
        # 전체 티켓 목록 (우선순위 먼저)
        sorted_tickets = priority_tickets + normal_tickets
        
        # 배치 크기 제한
        if len(sorted_tickets) > max_per_batch:
            logging.warning(f"티켓 수({len(sorted_tickets)})가 배치 제한({max_per_batch})을 초과합니다. 처음 {max_per_batch}개만 처리합니다.")
            sorted_tickets = sorted_tickets[:max_per_batch]
        
        sent_count = 0
        failed_count = 0
        skipped_count = 0
        
        logging.info(f"배치 알림 전송 시작: 총 {len(sorted_tickets)}개 (우선순위: {len(priority_tickets)}개, 일반: {len(normal_tickets)}개)")
        
        for i, ticket in enumerate(sorted_tickets, 1):
            try:
                if self.send_notification(ticket):
                    sent_count += 1
                else:
                    skipped_count += 1
                
                # 마지막 티켓이 아닌 경우에만 지연
                if i < len(sorted_tickets):
                    # 우선순위 티켓 간에는 더 짧은 지연
                    current_delay = delay * 0.5 if ticket in priority_tickets else delay
                    time.sleep(current_delay)
                    
            except Exception as e:
                logging.error(f"배치 전송 중 오류 발생: {e}")
                failed_count += 1
        
        result = {
            'sent': sent_count,
            'failed': failed_count,
            'skipped': skipped_count
        }
        
        logging.info(f"배치 알림 전송 완료: 성공 {sent_count}개, 실패 {failed_count}개, 스킵 {skipped_count}개")
        return result
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """알림 전송 통계를 반환합니다."""
        today = datetime.now().strftime('%Y-%m-%d')
        today_count = self.notification_history['daily_counts'].get(today, 0)
        total_count = self.notification_history.get('total_sent', 0)
        
        # 최근 7일 통계
        recent_days = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            count = self.notification_history['daily_counts'].get(date, 0)
            recent_days.append({'date': date, 'count': count})
        
        return {
            'today_count': today_count,
            'total_count': total_count,
            'recent_days': recent_days,
            'active_tickets': len(self.sent_notifications)
        }


def main():
    # 테스트용 코드
    from crawlers.interpark_crawler import get_interpark_notices
    from crawlers.yes24_crawler import get_yes24_notices
    from crawlers.melon_crawler import get_melon_notices
    from crawlers.ticketlink_crawler import get_ticketlink_notices
    
    # 디스코드 웹훅 URL 설정
    webhook_url = "https://discord.com/api/webhooks/abcde"
    
    # 알림 시스템 초기화
    notifier = DiscordNotifier(webhook_url)
    
    # 모든 크롤러에서 데이터 수집
    all_tickets = []
    
    logging.info("인터파크 크롤링 시작...")
    interpark_tickets = get_interpark_notices()
    all_tickets.extend(interpark_tickets)
    
    logging.info("YES24 크롤링 시작...")
    yes24_tickets = get_yes24_notices()
    all_tickets.extend(yes24_tickets)
    
    logging.info("멜론티켓 크롤링 시작...")
    melon_tickets = get_melon_notices()
    all_tickets.extend(melon_tickets)
    
    logging.info("티켓링크 크롤링 시작...")
    ticketlink_tickets = get_ticketlink_notices()
    all_tickets.extend(ticketlink_tickets)
    
    # 수집된 티켓 정보 출력
    logging.info(f"총 {len(all_tickets)}개의 티켓 정보를 수집했습니다.")
    
    # 알림 전송
    if all_tickets:
        sent_count = notifier.send_batch_notifications(all_tickets)
        logging.info(f"{sent_count}개의 새로운 티켓 정보를 디스코드로 전송했습니다.")
    else:
        logging.info("전송할 티켓 정보가 없습니다.")


if __name__ == "__main__":
    # 로깅 설정 (테스트용)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    main()