"""
데이터베이스 관리 모듈
SQLite를 사용하여 티켓 정보와 알림 기록을 관리합니다.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

class TicketDatabase:
    """티켓 정보 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "data/tickets.db"):
        """
        데이터베이스 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._local = threading.local()
        
        # data 디렉토리 생성
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 데이터베이스 초기화
        self._init_database()
        
    def _get_connection(self) -> sqlite3.Connection:
        """스레드별 데이터베이스 연결 반환"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            # WAL 모드 활성화 (동시 읽기/쓰기 성능 향상)
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA cache_size=10000")
            
        return self._local.connection
    
    @contextmanager
    def get_cursor(self):
        """커서 컨텍스트 매니저"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"데이터베이스 오류: {e}")
            raise
        finally:
            cursor.close()
    
    def _init_database(self):
        """데이터베이스 테이블 초기화"""
        with self.get_cursor() as cursor:
            # 티켓 정보 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    open_date TEXT,
                    open_datetime DATETIME,
                    source TEXT NOT NULL,
                    link TEXT,
                    place TEXT,
                    genre TEXT,
                    price TEXT,
                    description TEXT,
                    image_url TEXT,
                    status TEXT DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    raw_data TEXT,  -- 원본 JSON 데이터 저장
                    UNIQUE(title, source, open_date)  -- 중복 방지
                )
            """)
            
            # 알림 기록 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    notification_type TEXT DEFAULT 'discord',
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    webhook_url TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES tickets (id)
                )
            """)
            
            # 설정 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 인덱스 생성
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_source ON tickets(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_open_datetime ON tickets(open_datetime)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_ticket_id ON notifications(ticket_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON notifications(sent_at)")
            
        logger.info("데이터베이스 초기화 완료")
    
    def _parse_open_datetime(self, open_date_str: str) -> Optional[datetime]:
        """오픈 날짜 문자열을 datetime 객체로 변환"""
        if not open_date_str:
            return None
            
        # 다양한 날짜 형식 지원
        date_formats = [
            '%Y.%m.%d %H:%M',
            '%Y-%m-%d %H:%M',
            '%Y.%m.%d',
            '%Y-%m-%d',
            '%m.%d %H:%M',
            '%m/%d %H:%M',
            '%m.%d',
            '%m/%d'
        ]
        
        for fmt in date_formats:
            try:
                if '%Y' not in fmt:
                    # 연도가 없는 경우 현재 연도 추가
                    current_year = datetime.now().year
                    date_str_with_year = f"{current_year}.{open_date_str.replace('/', '.')}"
                    if '%H:%M' in fmt:
                        return datetime.strptime(date_str_with_year, f"{current_year}.{fmt}")
                    else:
                        return datetime.strptime(date_str_with_year, f"{current_year}.{fmt}")
                else:
                    return datetime.strptime(open_date_str, fmt)
            except ValueError:
                continue
                
        logger.warning(f"날짜 파싱 실패: {open_date_str}")
        return None
    
    def _classify_genre(self, title: str) -> str:
        """제목을 기반으로 장르 분류"""
        title_lower = title.lower()
        
        if any(keyword in title_lower for keyword in ['콘서트', 'concert', '공연']):
            return '콘서트'
        elif any(keyword in title_lower for keyword in ['뮤지컬', 'musical']):
            return '뮤지컬'
        elif any(keyword in title_lower for keyword in ['연극', 'play']):
            return '연극'
        elif any(keyword in title_lower for keyword in ['클래식', 'classic', '오케스트라', 'orchestra']):
            return '클래식'
        elif any(keyword in title_lower for keyword in ['스포츠', 'sport', '축구', '야구', '농구']):
            return '스포츠'
        elif any(keyword in title_lower for keyword in ['전시', 'exhibition', '박물관', '미술관']):
            return '전시'
        else:
            return '기타'
    
    def insert_tickets(self, tickets: List[Dict[str, Any]]) -> int:
        """
        티켓 정보를 데이터베이스에 삽입
        
        Args:
            tickets: 티켓 정보 리스트
            
        Returns:
            삽입된 티켓 수
        """
        if not tickets:
            return 0
            
        inserted_count = 0
        
        with self.get_cursor() as cursor:
            for ticket in tickets:
                try:
                    # 날짜 파싱
                    open_datetime = self._parse_open_datetime(ticket.get('open_date', ''))
                    
                    # 장르 분류
                    genre = self._classify_genre(ticket.get('title', ''))
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO tickets 
                        (title, open_date, open_datetime, source, link, place, genre, 
                         price, description, image_url, raw_data, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        ticket.get('title', ''),
                        ticket.get('open_date', ''),
                        open_datetime,
                        ticket.get('source', ''),
                        ticket.get('link', ''),
                        ticket.get('place', ''),
                        genre,
                        ticket.get('price', ''),
                        ticket.get('description', ''),
                        ticket.get('image_url', ''),
                        json.dumps(ticket, ensure_ascii=False)
                    ))
                    
                    if cursor.rowcount > 0:
                        inserted_count += 1
                        
                except Exception as e:
                    logger.error(f"티켓 삽입 실패: {ticket.get('title', 'Unknown')} - {e}")
                    
        logger.info(f"{inserted_count}개의 새로운 티켓이 데이터베이스에 추가되었습니다.")
        return inserted_count
    
    def get_tickets(self, 
                   limit: int = 100, 
                   offset: int = 0,
                   source: Optional[str] = None,
                   genre: Optional[str] = None,
                   search: Optional[str] = None,
                   date_from: Optional[date] = None,
                   date_to: Optional[date] = None,
                   order_by: str = 'open_datetime',
                   order_desc: bool = True) -> List[Dict[str, Any]]:
        """
        티켓 정보 조회
        
        Args:
            limit: 조회할 최대 개수
            offset: 시작 위치
            source: 소스 필터
            genre: 장르 필터
            search: 검색어 (제목, 장소에서 검색)
            date_from: 시작 날짜
            date_to: 종료 날짜
            order_by: 정렬 기준
            order_desc: 내림차순 여부
            
        Returns:
            티켓 정보 리스트
        """
        with self.get_cursor() as cursor:
            # 기본 쿼리
            query = """
                SELECT id, title, open_date, open_datetime, source, link, place, 
                       genre, price, description, image_url, status, created_at, updated_at
                FROM tickets 
                WHERE status = 'active'
            """
            params = []
            
            # 필터 조건 추가
            if source:
                query += " AND source = ?"
                params.append(source)
                
            if genre:
                query += " AND genre = ?"
                params.append(genre)
                
            if search:
                query += " AND (title LIKE ? OR place LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
                
            if date_from:
                query += " AND date(open_datetime) >= ?"
                params.append(date_from.isoformat())
                
            if date_to:
                query += " AND date(open_datetime) <= ?"
                params.append(date_to.isoformat())
            
            # 정렬
            valid_order_columns = ['open_datetime', 'created_at', 'title', 'source']
            if order_by not in valid_order_columns:
                order_by = 'open_datetime'
                
            order_direction = 'DESC' if order_desc else 'ASC'
            query += f" ORDER BY {order_by} {order_direction}"
            
            # LIMIT과 OFFSET
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            logger.info(f"Executing query: {query} with params: {params}") # SQL 쿼리 로깅
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 딕셔너리로 변환
            tickets = []
            for row in rows:
                ticket = dict(row)
                # datetime을 문자열로 변환
                if ticket['open_datetime']:
                    ticket['open_datetime'] = ticket['open_datetime']
                if ticket['created_at']:
                    ticket['created_at'] = ticket['created_at']
                if ticket['updated_at']:
                    ticket['updated_at'] = ticket['updated_at']
                tickets.append(ticket)
                
            return tickets
    
    def get_ticket_count(self,
                        source: Optional[str] = None,
                        genre: Optional[str] = None,
                        search: Optional[str] = None,
                        date_from: Optional[date] = None,
                        date_to: Optional[date] = None) -> int:
        """티켓 총 개수 조회"""
        with self.get_cursor() as cursor:
            query = "SELECT COUNT(*) FROM tickets WHERE status = 'active'"
            params = []
            
            # 필터 조건 추가 (get_tickets와 동일)
            if source:
                query += " AND source = ?"
                params.append(source)
                
            if genre:
                query += " AND genre = ?"
                params.append(genre)
                
            if search:
                query += " AND (title LIKE ? OR place LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
                
            if date_from:
                query += " AND date(open_datetime) >= ?"
                params.append(date_from.isoformat())
                
            if date_to:
                query += " AND date(open_datetime) <= ?"
                params.append(date_to.isoformat())
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    def get_statistics(self) -> Dict[str, Any]:
        """티켓 통계 정보 조회"""
        with self.get_cursor() as cursor:
            stats = {}
            
            # 전체 티켓 수
            cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'active'")
            stats['total_count'] = cursor.fetchone()[0]
            
            # 소스별 통계
            cursor.execute("""
                SELECT source, COUNT(*) as count 
                FROM tickets 
                WHERE status = 'active' 
                GROUP BY source 
                ORDER BY count DESC
            """)
            stats['source_counts'] = dict(cursor.fetchall())
            
            # 장르별 통계
            cursor.execute("""
                SELECT genre, COUNT(*) as count 
                FROM tickets 
                WHERE status = 'active' 
                GROUP BY genre 
                ORDER BY count DESC
            """)
            stats['genre_counts'] = dict(cursor.fetchall())
            
            # 날짜별 통계 (오늘, 내일, 이번 주)
            kst_now = datetime.utcnow() + timedelta(hours=9)
            today = kst_now.date()
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN date(open_datetime) = ? THEN 1 ELSE 0 END) as today_count,
                    SUM(CASE WHEN date(open_datetime) = date(?, '+1 day') THEN 1 ELSE 0 END) as tomorrow_count,
                    SUM(CASE WHEN date(open_datetime) BETWEEN ? AND date(?, '+7 days') THEN 1 ELSE 0 END) as week_count
                FROM tickets
                WHERE status = 'active' AND open_datetime IS NOT NULL
            """, (today.isoformat(), today.isoformat(), today.isoformat(), today.isoformat()))
            
            result = cursor.fetchone()
            stats['today_count'] = result[0] or 0
            stats['tomorrow_count'] = result[1] or 0
            stats['week_count'] = result[2] or 0
            
            return stats
    
    def record_notification(self, ticket_id: int, notification_type: str = 'discord', 
                          success: bool = True, error_message: str = None,
                          webhook_url: str = None) -> int:
        """알림 기록 저장"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO notifications 
                (ticket_id, notification_type, success, error_message, webhook_url)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, notification_type, success, error_message, webhook_url))
            
            return cursor.lastrowid
    
    def get_unsent_tickets(self, notification_type: str = 'discord') -> List[Dict[str, Any]]:
        """아직 알림을 보내지 않은 티켓 조회"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT t.id, t.title, t.open_date, t.open_datetime, t.source, 
                       t.link, t.place, t.genre, t.price, t.description, t.image_url
                FROM tickets t
                LEFT JOIN notifications n ON t.id = n.ticket_id 
                    AND n.notification_type = ? AND n.success = 1
                WHERE t.status = 'active' AND n.id IS NULL
                ORDER BY t.created_at DESC
            """, (notification_type,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def save_setting(self, key: str, value: Any):
        """설정 저장"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(value, ensure_ascii=False)))
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """설정 조회"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return default
    
    def close(self):
        """데이터베이스 연결 종료"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


# 전역 데이터베이스 인스턴스
_db_instance = None

def get_database() -> TicketDatabase:
    """데이터베이스 인스턴스 반환 (싱글톤)"""
    global _db_instance
    if _db_instance is None:
        _db_instance = TicketDatabase()
    return _db_instance