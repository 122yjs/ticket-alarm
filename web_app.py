#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 오픈 모니터 웹 인터페이스

실시간으로 수집된 티켓 정보를 시각적으로 표시하는 웹 애플리케이션입니다.
참조 사이트 스타일을 기반으로 한 모던한 UI를 제공합니다.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# 로컬 모듈 임포트
from data_manager import load_tickets, load_config
from filters import filter_tickets_by_keywords, filter_tickets_by_date_range

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="티켓 오픈 모니터",
    description="실시간 공연 티켓 오픈 알림 시스템",
    version="1.0.0"
)

# 정적 파일 및 템플릿 설정
static_dir = Path("static")
template_dir = Path("templates")

# 디렉토리 생성
static_dir.mkdir(exist_ok=True)
template_dir.mkdir(exist_ok=True)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# 템플릿 엔진 설정
templates = Jinja2Templates(directory="templates")

# 전역 변수
last_update_time = None
ticket_cache = []

def get_ticket_stats(tickets: List[Dict]) -> Dict[str, Any]:
    """
    티켓 통계 정보를 계산합니다.
    
    Args:
        tickets: 티켓 목록
        
    Returns:
        통계 정보 딕셔너리
    """
    if not tickets:
        return {
            "total_count": 0,
            "platform_counts": {},
            "genre_counts": {},
            "today_count": 0,
            "tomorrow_count": 0,
            "this_week_count": 0
        }
    
    # 플랫폼별 카운트
    platform_counts = {}
    for ticket in tickets:
        platform = ticket.get('source', '알 수 없음')
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
    
    # 장르별 카운트 (제목에서 추출)
    genre_counts = {
        "콘서트": 0,
        "뮤지컬": 0,
        "연극": 0,
        "클래식": 0,
        "기타": 0
    }
    
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)
    
    today_count = 0
    tomorrow_count = 0
    this_week_count = 0
    
    for ticket in tickets:
        title = ticket.get('title', '').lower()
        
        # 장르 분류
        if any(keyword in title for keyword in ['콘서트', 'concert', '공연']):
            genre_counts["콘서트"] += 1
        elif any(keyword in title for keyword in ['뮤지컬', 'musical']):
            genre_counts["뮤지컬"] += 1
        elif any(keyword in title for keyword in ['연극', 'play']):
            genre_counts["연극"] += 1
        elif any(keyword in title for keyword in ['클래식', 'classic', '오케스트라']):
            genre_counts["클래식"] += 1
        else:
            genre_counts["기타"] += 1
        
        # 날짜별 카운트
        open_date_str = ticket.get('open_date', '')
        if open_date_str and open_date_str != '미정':
            parsed_date = _parse_ticket_date_improved(open_date_str)
            if parsed_date:
                if parsed_date == today:
                    today_count += 1
                elif parsed_date == tomorrow:
                    tomorrow_count += 1
                elif today <= parsed_date <= week_end:
                    this_week_count += 1
    
    return {
        "total_count": len(tickets),
        "platform_counts": platform_counts,
        "genre_counts": genre_counts,
        "today_count": today_count,
        "tomorrow_count": tomorrow_count,
        "this_week_count": this_week_count
    }

def refresh_ticket_data():
    """
    티켓 데이터를 새로고침합니다.
    """
    global ticket_cache, last_update_time
    
    try:
        ticket_cache = load_tickets()
        last_update_time = datetime.now()
        logger.info(f"티켓 데이터 새로고침 완료: {len(ticket_cache)}건")
    except Exception as e:
        logger.error(f"티켓 데이터 로드 중 오류: {e}")
        ticket_cache = []

@app.on_event("startup")
async def startup_event():
    """
    애플리케이션 시작 시 초기화 작업을 수행합니다.
    """
    logger.info("티켓 오픈 모니터 웹 애플리케이션 시작")
    refresh_ticket_data()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    메인 페이지를 렌더링합니다.
    """
    stats = get_ticket_stats(ticket_cache)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tickets": ticket_cache[:50],  # 최대 50개만 표시
        "stats": stats,
        "last_update": last_update_time.strftime("%Y. %m. %d. %p %I:%M") if last_update_time else "업데이트 없음",
        "total_tickets": len(ticket_cache)
    })

@app.get("/api/tickets")
async def get_tickets(
    platform: Optional[str] = Query(None, description="플랫폼 필터"),
    genre: Optional[str] = Query(None, description="장르 필터"),
    date_filter: Optional[str] = Query(None, description="날짜 필터 (today, tomorrow, week)"),
    search: Optional[str] = Query(None, description="검색어"),
    limit: int = Query(50, description="최대 결과 수")
):
    """
    필터링된 티켓 목록을 JSON으로 반환합니다.
    """
    filtered_tickets = ticket_cache.copy()
    
    # 플랫폼 필터
    if platform and platform != "전체":
        filtered_tickets = [t for t in filtered_tickets if t.get('source') == platform]
    
    # 장르 필터
    if genre and genre != "전체":
        genre_keywords = {
            "콘서트": ['콘서트', 'concert', '공연'],
            "뮤지컬": ['뮤지컬', 'musical'],
            "연극": ['연극', 'play'],
            "클래식": ['클래식', 'classic', '오케스트라']
        }
        
        if genre in genre_keywords:
            keywords = genre_keywords[genre]
            filtered_tickets = [
                t for t in filtered_tickets 
                if any(keyword in t.get('title', '').lower() for keyword in keywords)
            ]
    
    # 날짜 필터
    if date_filter:
        today = datetime.now().date()
        
        if date_filter == "today":
            target_date = today
        elif date_filter == "tomorrow":
            target_date = today + timedelta(days=1)
        elif date_filter == "week":
            # 이번 주 필터링은 별도 로직 필요
            week_end = today + timedelta(days=7)
            filtered_tickets = [
                t for t in filtered_tickets
                if _parse_ticket_date(t.get('open_date', '')) and
                   today <= _parse_ticket_date(t.get('open_date', '')) <= week_end
            ]
        else:
            target_date = None
        
        if date_filter in ["today", "tomorrow"] and target_date:
            filtered_tickets = [
                t for t in filtered_tickets
                if _parse_ticket_date(t.get('open_date', '')) == target_date
            ]
    
    # 검색어 필터
    if search:
        search_lower = search.lower()
        filtered_tickets = [
            t for t in filtered_tickets
            if search_lower in t.get('title', '').lower() or
               search_lower in t.get('place', '').lower()
        ]
    
    # 결과 제한
    filtered_tickets = filtered_tickets[:limit]
    
    return JSONResponse({
        "tickets": filtered_tickets,
        "total": len(filtered_tickets),
        "stats": get_ticket_stats(filtered_tickets)
    })

@app.get("/api/refresh")
async def refresh_data():
    """
    티켓 데이터를 수동으로 새로고침합니다.
    """
    refresh_ticket_data()
    return JSONResponse({
        "status": "success",
        "message": "데이터가 새로고침되었습니다.",
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "total_tickets": len(ticket_cache)
    })

@app.get("/api/stats")
async def get_stats():
    """
    티켓 통계 정보를 반환합니다.
    """
    stats = get_ticket_stats(ticket_cache)
    return JSONResponse(stats)

def _parse_ticket_date(date_str: str) -> Optional[datetime.date]:
    """
    티켓 날짜 문자열을 파싱합니다.
    
    Args:
        date_str: 날짜 문자열
        
    Returns:
        파싱된 날짜 객체 또는 None
    """
    if not date_str:
        return None
    
    for date_format in ['%Y.%m.%d', '%Y-%m-%d', '%m/%d', '%m.%d']:
        try:
            if date_format in ['%m/%d', '%m.%d']:
                # 월/일 형식인 경우 현재 연도 추가
                date_str_with_year = f"{datetime.now().year}.{date_str.replace('/', '.').replace('.', '.')}"
                return datetime.strptime(date_str_with_year, '%Y.%m.%d').date()
            else:
                return datetime.strptime(date_str, date_format).date()
        except ValueError:
            continue
    
    return None

def _parse_ticket_date_improved(date_str: str) -> Optional[datetime.date]:
    """
    개선된 티켓 날짜 문자열 파싱 함수.
    더 다양한 형식을 지원하고 로깅을 추가합니다.
    
    Args:
        date_str: 날짜 문자열
        
    Returns:
        파싱된 날짜 객체 또는 None
    """
    if not date_str or date_str.strip() == '' or date_str == '미정':
        return None
    
    # 공백 제거 및 정규화
    date_str = date_str.strip()
    
    # 다양한 날짜 형식 시도
    date_formats = [
        '%Y.%m.%d',    # 2024.01.15
        '%Y-%m-%d',    # 2024-01-15
        '%Y/%m/%d',    # 2024/01/15
        '%m.%d',       # 01.15
        '%m/%d',       # 01/15
        '%m-%d',       # 01-15
        '%Y.%m.%d.',   # 2024.01.15. (끝에 점)
        '%Y.%m.%d (%a)', # 2024.01.15 (월)
    ]
    
    current_year = datetime.now().year
    
    for date_format in date_formats:
        try:
            if date_format in ['%m.%d', '%m/%d', '%m-%d']:
                # 월/일 형식인 경우 현재 연도 추가
                normalized_date = date_str.replace('/', '.').replace('-', '.')
                date_str_with_year = f"{current_year}.{normalized_date}"
                parsed_date = datetime.strptime(date_str_with_year, '%Y.%m.%d').date()
            else:
                # 괄호 안의 요일 정보 제거
                clean_date_str = date_str.split('(')[0].strip().rstrip('.')
                parsed_date = datetime.strptime(clean_date_str, date_format.split('(')[0].strip().rstrip('.'))
                if isinstance(parsed_date, datetime):
                    parsed_date = parsed_date.date()
            
            # 과거 날짜인 경우 다음 해로 가정 (월/일 형식의 경우)
            if date_format in ['%m.%d', '%m/%d', '%m-%d'] and parsed_date < datetime.now().date():
                date_str_with_year = f"{current_year + 1}.{normalized_date}"
                parsed_date = datetime.strptime(date_str_with_year, '%Y.%m.%d').date()
            
            return parsed_date
            
        except ValueError:
            continue
    
    # 모든 형식 실패 시 로깅
    logger.warning(f"날짜 파싱 실패: '{date_str}'")
    return None

if __name__ == "__main__":
    # 개발 서버 실행
    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )