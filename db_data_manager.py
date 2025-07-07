"""
데이터베이스 기반 데이터 매니저
기존 JSON 파일 기반 data_manager.py를 대체하는 DB 버전
"""

import logging
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from database import get_database

logger = logging.getLogger(__name__)

class DatabaseDataManager:
    """데이터베이스 기반 데이터 관리 클래스"""
    
    def __init__(self):
        self.db = get_database()
    
    def save_tickets(self, tickets: List[Dict[str, Any]]) -> int:
        """
        티켓 정보를 데이터베이스에 저장
        
        Args:
            tickets: 티켓 정보 리스트
            
        Returns:
            저장된 새로운 티켓 수
        """
        if not tickets:
            logger.info("저장할 티켓이 없습니다.")
            return 0
        
        # 데이터 정제
        cleaned_tickets = []
        for ticket in tickets:
            if self._validate_ticket(ticket):
                cleaned_tickets.append(self._clean_ticket_data(ticket))
            else:
                logger.warning(f"유효하지 않은 티켓 데이터: {ticket}")
        
        # 데이터베이스에 저장
        inserted_count = self.db.insert_tickets(cleaned_tickets)
        logger.info(f"총 {len(tickets)}개 중 {inserted_count}개의 새로운 티켓을 저장했습니다.")
        
        return inserted_count
    
    def load_tickets(self, 
                    limit: int = 100,
                    offset: int = 0,
                    filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        데이터베이스에서 티켓 정보 로드
        
        Args:
            limit: 조회할 최대 개수
            offset: 시작 위치
            filters: 필터 조건 딕셔너리
            
        Returns:
            티켓 정보 리스트
        """
        if filters is None:
            filters = {}
        
        tickets = self.db.get_tickets(
            limit=limit,
            offset=offset,
            source=filters.get('source'),
            genre=filters.get('genre'),
            search=filters.get('search'),
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to'),
            order_by=filters.get('order_by', 'open_datetime'),
            order_desc=filters.get('order_desc', True)
        )
        
        return tickets
    
    def get_ticket_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """필터 조건에 맞는 티켓 총 개수 반환"""
        if filters is None:
            filters = {}
            
        return self.db.get_ticket_count(
            source=filters.get('source'),
            genre=filters.get('genre'),
            search=filters.get('search'),
            date_from=filters.get('date_from'),
            date_to=filters.get('date_to')
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """티켓 통계 정보 반환"""
        return self.db.get_statistics()
    
    def filter_tickets_by_keywords(self, tickets: List[Dict[str, Any]], 
                                 keywords: List[str]) -> List[Dict[str, Any]]:
        """
        키워드로 티켓 필터링 (기존 호환성 유지)
        
        Args:
            tickets: 티켓 리스트
            keywords: 키워드 리스트
            
        Returns:
            필터링된 티켓 리스트
        """
        if not keywords:
            return tickets
        
        filtered_tickets = []
        keywords_lower = [keyword.lower() for keyword in keywords]
        
        for ticket in tickets:
            title = ticket.get('title', '').lower()
            place = ticket.get('place', '').lower()
            description = ticket.get('description', '').lower()
            
            search_text = f"{title} {place} {description}"
            
            if any(keyword in search_text for keyword in keywords_lower):
                filtered_tickets.append(ticket)
        
        return filtered_tickets
    
    def get_unsent_notifications(self, keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        아직 알림을 보내지 않은 티켓 조회
        
        Args:
            keywords: 필터링할 키워드 리스트
            
        Returns:
            알림을 보내지 않은 티켓 리스트
        """
        unsent_tickets = self.db.get_unsent_tickets()
        
        if keywords:
            unsent_tickets = self.filter_tickets_by_keywords(unsent_tickets, keywords)
        
        return unsent_tickets
    
    def record_sent_notification(self, ticket_id: int, 
                               notification_type: str = 'discord',
                               success: bool = True,
                               error_message: str = None,
                               webhook_url: str = None) -> int:
        """
        알림 전송 기록 저장
        
        Args:
            ticket_id: 티켓 ID
            notification_type: 알림 타입
            success: 성공 여부
            error_message: 에러 메시지
            webhook_url: 웹훅 URL
            
        Returns:
            알림 기록 ID
        """
        return self.db.record_notification(
            ticket_id=ticket_id,
            notification_type=notification_type,
            success=success,
            error_message=error_message,
            webhook_url=webhook_url
        )
    
    def save_config(self, config: Dict[str, Any]):
        """설정 저장"""
        for key, value in config.items():
            self.db.save_setting(key, value)
        logger.info("설정이 데이터베이스에 저장되었습니다.")
    
    def load_config(self) -> Dict[str, Any]:
        """
        설정 로드 (DB 우선, 없으면 파일에서 로드)
        
        Returns:
            설정 딕셔너리
        """
        # 먼저 데이터베이스에서 설정 확인
        config = {}
        
        # 주요 설정 키들
        config_keys = [
            'DISCORD_WEBHOOK_URL',
            'KEYWORDS', 
            'interval',
            'sources'
        ]
        
        db_config_exists = False
        for key in config_keys:
            value = self.db.get_setting(key)
            if value is not None:
                config[key] = value
                db_config_exists = True
        
        # DB에 설정이 없으면 파일에서 로드
        if not db_config_exists:
            config = self._load_config_from_file()
            if config:
                # 파일에서 로드한 설정을 DB에 저장
                self.save_config(config)
        
        return config
    
    def _load_config_from_file(self) -> Dict[str, Any]:
        """파일에서 설정 로드 (기존 방식)"""
        config_path = os.path.join('data', 'config.json')
        
        if not os.path.exists(config_path):
            logger.error(f"설정 파일({config_path})을 찾을 수 없습니다.")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info("파일에서 설정을 로드했습니다.")
            return config
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    def _validate_ticket(self, ticket: Dict[str, Any]) -> bool:
        """티켓 데이터 유효성 검사"""
        required_fields = ['title', 'source']
        
        for field in required_fields:
            if not ticket.get(field):
                return False
        
        return True
    
    def _clean_ticket_data(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """티켓 데이터 정제"""
        cleaned = ticket.copy()
        
        # 문자열 필드 정리
        string_fields = ['title', 'place', 'description', 'price']
        for field in string_fields:
            if field in cleaned and cleaned[field]:
                cleaned[field] = str(cleaned[field]).strip()
        
        # URL 정리
        if 'link' in cleaned and cleaned['link']:
            link = str(cleaned['link']).strip()
            if not link.startswith(('http://', 'https://')):
                if link.startswith('//'):
                    link = 'https:' + link
                elif link.startswith('/'):
                    # 상대 경로인 경우 소스에 따라 도메인 추가
                    source = cleaned.get('source', '').lower()
                    if source == 'interpark':
                        link = 'https://tickets.interpark.com' + link
                    elif source == 'yes24':
                        link = 'https://ticket.yes24.com' + link
                    elif source == 'melon':
                        link = 'https://ticket.melon.com' + link
                    elif source == 'ticketlink':
                        link = 'https://www.ticketlink.co.kr' + link
            cleaned['link'] = link
        
        return cleaned

# 전역 데이터 매니저 인스턴스
_data_manager = None

def get_data_manager() -> DatabaseDataManager:
    """데이터 매니저 인스턴스 반환 (싱글톤)"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DatabaseDataManager()
    return _data_manager

# 기존 함수들과의 호환성을 위한 래퍼 함수들
def save_tickets(tickets: List[Dict[str, Any]]) -> int:
    """기존 호환성을 위한 래퍼 함수"""
    return get_data_manager().save_tickets(tickets)

def load_tickets(limit: int = 100, offset: int = 0, 
                filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """기존 호환성을 위한 래퍼 함수"""
    return get_data_manager().load_tickets(limit, offset, filters)

def load_config() -> Dict[str, Any]:
    """기존 호환성을 위한 래퍼 함수"""
    return get_data_manager().load_config()

def get_statistics() -> Dict[str, Any]:
    """기존 호환성을 위한 래퍼 함수"""
    return get_data_manager().get_statistics()