"""
데이터베이스 기반 디스코드 알림 시스템
티켓 정보를 디스코드로 전송하고 알림 기록을 데이터베이스에 저장합니다.
"""

import requests
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseDiscordNotifier:
    """데이터베이스 기반 디스코드 알림 클래스"""
    
    def __init__(self, webhook_url: str, data_manager):
        """
        초기화
        
        Args:
            webhook_url: 디스코드 웹훅 URL
            data_manager: 데이터베이스 데이터 매니저 인스턴스
        """
        self.webhook_url = webhook_url
        self.data_manager = data_manager
        self.session = requests.Session()
        
        # 요청 헤더 설정
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TicketMonitor/2.0'
        })
    
    def send_notification(self, ticket: Dict[str, Any]) -> bool:
        """
        단일 티켓에 대한 알림 전송
        
        Args:
            ticket: 티켓 정보 딕셔너리
            
        Returns:
            전송 성공 여부
        """
        try:
            # 임베드 메시지 생성
            embed = self._create_embed(ticket)
            
            payload = {
                "embeds": [embed],
                "username": "티켓 오픈 알리미",
                "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/ticket_icon.png"
            }
            
            # 디스코드로 전송
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            
            success = response.status_code == 204
            
            if success:
                logger.info(f"알림 전송 성공: {ticket.get('title', 'Unknown')}")
                
                # 성공한 경우 데이터베이스에 기록
                if 'id' in ticket:
                    self.data_manager.record_sent_notification(
                        ticket_id=ticket['id'],
                        notification_type='discord',
                        success=True,
                        webhook_url=self.webhook_url
                    )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"알림 전송 실패: {ticket.get('title', 'Unknown')} - {error_msg}")
                
                # 실패한 경우도 기록
                if 'id' in ticket:
                    self.data_manager.record_sent_notification(
                        ticket_id=ticket['id'],
                        notification_type='discord',
                        success=False,
                        error_message=error_msg,
                        webhook_url=self.webhook_url
                    )
            
            return success
            
        except requests.exceptions.RequestException as e:
            error_msg = f"네트워크 오류: {str(e)}"
            logger.error(f"알림 전송 중 네트워크 오류: {ticket.get('title', 'Unknown')} - {error_msg}")
            
            # 네트워크 오류도 기록
            if 'id' in ticket:
                self.data_manager.record_sent_notification(
                    ticket_id=ticket['id'],
                    notification_type='discord',
                    success=False,
                    error_message=error_msg,
                    webhook_url=self.webhook_url
                )
            
            return False
            
        except Exception as e:
            error_msg = f"예상치 못한 오류: {str(e)}"
            logger.error(f"알림 전송 중 예상치 못한 오류: {ticket.get('title', 'Unknown')} - {error_msg}")
            
            if 'id' in ticket:
                self.data_manager.record_sent_notification(
                    ticket_id=ticket['id'],
                    notification_type='discord',
                    success=False,
                    error_message=error_msg,
                    webhook_url=self.webhook_url
                )
            
            return False
    
    def send_batch_notifications(self, tickets: List[Dict[str, Any]], 
                               delay_between_sends: float = 1.0) -> int:
        """
        여러 티켓에 대한 배치 알림 전송
        
        Args:
            tickets: 티켓 정보 리스트
            delay_between_sends: 전송 간 지연 시간 (초)
            
        Returns:
            성공적으로 전송된 알림 수
        """
        if not tickets:
            logger.info("전송할 티켓이 없습니다.")
            return 0
        
        logger.info(f"{len(tickets)}개의 티켓 알림을 전송합니다...")
        
        success_count = 0
        
        for i, ticket in enumerate(tickets, 1):
            logger.info(f"알림 전송 중... ({i}/{len(tickets)})")
            
            if self.send_notification(ticket):
                success_count += 1
            
            # 마지막 티켓이 아닌 경우 지연
            if i < len(tickets):
                time.sleep(delay_between_sends)
        
        logger.info(f"배치 알림 전송 완료: {success_count}/{len(tickets)} 성공")
        return success_count
    
    def _create_embed(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 정보로부터 디스코드 임베드 메시지 생성
        
        Args:
            ticket: 티켓 정보 딕셔너리
            
        Returns:
            디스코드 임베드 딕셔너리
        """
        title = ticket.get('title', '제목 없음')
        source = ticket.get('source', '').upper()
        open_date = ticket.get('open_date', '날짜 미정')
        link = ticket.get('link', '')
        place = ticket.get('place', '')
        genre = ticket.get('genre', '')
        price = ticket.get('price', '')
        
        # 소스별 색상 설정
        color_map = {
            'INTERPARK': 0xFF6B6B,    # 빨간색
            'YES24': 0x4ECDC4,        # 청록색
            'MELON': 0x45B7D1,        # 파란색
            'TICKETLINK': 0x96CEB4,   # 연두색
        }
        color = color_map.get(source, 0x95A5A6)  # 기본 회색
        
        # 임베드 기본 구조
        embed = {
            "title": f"🎫 {title}",
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"티켓 오픈 알리미 | {source}",
                "icon_url": "https://cdn.discordapp.com/attachments/123456789/123456789/ticket_icon.png"
            }
        }
        
        # URL 추가 (있는 경우)
        if link:
            embed["url"] = link
        
        # 필드 추가
        fields = []
        
        # 오픈 날짜
        fields.append({
            "name": "📅 오픈 일시",
            "value": open_date,
            "inline": True
        })
        
        # 장소 (있는 경우)
        if place:
            fields.append({
                "name": "📍 장소",
                "value": place,
                "inline": True
            })
        
        # 장르 (있는 경우)
        if genre:
            fields.append({
                "name": "🎭 장르",
                "value": genre,
                "inline": True
            })
        
        # 가격 (있는 경우)
        if price:
            fields.append({
                "name": "💰 가격",
                "value": price,
                "inline": True
            })
        
        # 티켓 링크
        if link:
            fields.append({
                "name": "🔗 티켓 예매",
                "value": f"[여기를 클릭하여 예매하기]({link})",
                "inline": False
            })
        
        embed["fields"] = fields
        
        # 설명 추가
        description_parts = []
        if genre:
            description_parts.append(f"**{genre}**")
        if place:
            description_parts.append(f"📍 {place}")
        
        if description_parts:
            embed["description"] = " | ".join(description_parts)
        
        return embed
    
    def send_summary_notification(self, summary: Dict[str, Any]) -> bool:
        """
        요약 정보 알림 전송 (예: 일일 요약, 주간 요약 등)
        
        Args:
            summary: 요약 정보 딕셔너리
            
        Returns:
            전송 성공 여부
        """
        try:
            embed = {
                "title": "📊 티켓 모니터링 요약",
                "color": 0x3498DB,
                "timestamp": datetime.now().isoformat(),
                "footer": {
                    "text": "티켓 오픈 알리미 | 요약 리포트"
                }
            }
            
            fields = []
            
            # 총 티켓 수
            if 'total_count' in summary:
                fields.append({
                    "name": "📋 총 티켓 수",
                    "value": str(summary['total_count']),
                    "inline": True
                })
            
            # 오늘 오픈
            if 'today_count' in summary:
                fields.append({
                    "name": "🔥 오늘 오픈",
                    "value": str(summary['today_count']),
                    "inline": True
                })
            
            # 내일 오픈
            if 'tomorrow_count' in summary:
                fields.append({
                    "name": "⏰ 내일 오픈",
                    "value": str(summary['tomorrow_count']),
                    "inline": True
                })
            
            # 소스별 분포
            if 'source_counts' in summary:
                source_text = "\n".join([
                    f"{source}: {count}개" 
                    for source, count in summary['source_counts'].items()
                ])
                fields.append({
                    "name": "🌐 소스별 분포",
                    "value": source_text or "없음",
                    "inline": True
                })
            
            # 장르별 분포
            if 'genre_counts' in summary:
                genre_text = "\n".join([
                    f"{genre}: {count}개" 
                    for genre, count in list(summary['genre_counts'].items())[:5]  # 상위 5개만
                ])
                fields.append({
                    "name": "🎭 장르별 분포 (상위 5개)",
                    "value": genre_text or "없음",
                    "inline": True
                })
            
            embed["fields"] = fields
            
            payload = {
                "embeds": [embed],
                "username": "티켓 오픈 알리미",
            }
            
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            
            success = response.status_code == 204
            
            if success:
                logger.info("요약 알림 전송 성공")
            else:
                logger.error(f"요약 알림 전송 실패: HTTP {response.status_code}")
            
            return success
            
        except Exception as e:
            logger.error(f"요약 알림 전송 중 오류: {e}")
            return False
    
    def test_webhook(self) -> bool:
        """
        웹훅 연결 테스트
        
        Returns:
            연결 성공 여부
        """
        try:
            test_embed = {
                "title": "🧪 테스트 메시지",
                "description": "티켓 오픈 알리미 웹훅 연결 테스트입니다.",
                "color": 0x00FF00,
                "timestamp": datetime.now().isoformat(),
                "footer": {
                    "text": "티켓 오픈 알리미 | 연결 테스트"
                }
            }
            
            payload = {
                "embeds": [test_embed],
                "username": "티켓 오픈 알리미",
            }
            
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            
            success = response.status_code == 204
            
            if success:
                logger.info("웹훅 테스트 성공")
            else:
                logger.error(f"웹훅 테스트 실패: HTTP {response.status_code}")
            
            return success
            
        except Exception as e:
            logger.error(f"웹훅 테스트 중 오류: {e}")
            return False
    
    def close(self):
        """세션 정리"""
        if self.session:
            self.session.close()