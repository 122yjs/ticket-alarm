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
import re
from contextlib import asynccontextmanager
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

# FastAPI 앱 초기화 및 lifespan 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작 시 데이터 로드 및 정리 작업을 수행하는 lifespan 이벤트 핸들러
    """
    logger.info("티켓 오픈 모니터 웹 애플리케이션 시작")
    refresh_ticket_data()
    yield
    logger.info("애플리케이션 종료")

app = FastAPI(
    title="티켓 오픈 모니터",
    description="실시간 공연 티켓 오픈 알림 시스템",
    version="1.0.0",
    lifespan=lifespan
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

# 사용자 권한 설정 (실제 환경에서는 데이터베이스나 설정 파일에서 관리)
ADMIN_USERS = {"admin", "manager"}  # 관리자 권한을 가진 사용자 목록

# 자동 갱신 설정
AUTO_REFRESH_INTERVAL = 3600  # 1시간 (초 단위)

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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: Optional[str] = Query(None, description="사용자 ID")):
    """
    메인 페이지를 렌더링합니다.
    """
    all_tickets = load_tickets()
    stats = get_ticket_stats(all_tickets)
    
    # 사용자 권한 확인
    is_admin = user in ADMIN_USERS if user else False
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tickets": all_tickets[:50],  # 최대 50개만 표시
        "stats": stats,
        "last_update": last_update_time.strftime("%Y. %m. %d. %p %I:%M") if last_update_time else "업데이트 없음",
        "last_update_iso": last_update_time.isoformat() if last_update_time else None,
        "total_tickets": len(all_tickets),
        "is_admin": is_admin,
        "auto_refresh_interval": AUTO_REFRESH_INTERVAL * 1000  # JavaScript용 밀리초 단위
    })

@app.get("/api/tickets")
async def get_tickets(
    platform: Optional[str] = Query(None, description="플랫폼 필터"),
    genre: Optional[str] = Query(None, description="장르 필터"),
    date_filter: Optional[str] = Query(None, description="날짜 필터 (today, tomorrow, week)"),
    sort: Optional[str] = Query("open_date_asc", description="정렬 순서"),
    search: Optional[str] = Query(None, description="검색어"),
    limit: int = Query(50, description="최대 결과 수")
):
    """
    필터링된 티켓 목록을 JSON으로 반환합니다.
    """
    all_tickets = load_tickets()
    filtered_tickets = all_tickets.copy()
    
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
    if date_filter and date_filter != "all":
        today = datetime.now().date()
        date_filtered_tickets = []
        for t in filtered_tickets:
            parsed_date = _parse_ticket_date_improved(t.get('open_date', ''))
            if not parsed_date:
                continue

            if date_filter == "today" and parsed_date == today:
                date_filtered_tickets.append(t)
            elif date_filter == "tomorrow" and parsed_date == today + timedelta(days=1):
                date_filtered_tickets.append(t)
            elif date_filter == "week" and today <= parsed_date <= today + timedelta(days=6):
                date_filtered_tickets.append(t)
        filtered_tickets = date_filtered_tickets

    # 검색어 필터
    if search:
        search_lower = search.lower()
        filtered_tickets = [
            t for t in filtered_tickets
            if search_lower in t.get('title', '').lower() or
               search_lower in t.get('place', '').lower()
        ]
    
    # 정렬
    if sort == "open_date_desc":
        filtered_tickets.sort(key=lambda t: _parse_ticket_date_improved(t.get('open_date', '')) or datetime.min.date(), reverse=True)
    elif sort == "title_asc":
        filtered_tickets.sort(key=lambda t: t.get('title', ''))
    else: # 기본 정렬: open_date_asc
        filtered_tickets.sort(key=lambda t: _parse_ticket_date_improved(t.get('open_date', '')) or datetime.max.date())

    # 결과 제한
    total_count = len(filtered_tickets)
    limited_tickets = filtered_tickets[:limit]

    config = load_config()
    platform_colors = config.get("platform_colors", {})

    return JSONResponse({
        "tickets": limited_tickets,
        "total": total_count,
        "stats": get_ticket_stats(ticket_cache),  # 전체 데이터 기준 통계
        "platform_colors": platform_colors,
        "last_update": last_update_time.isoformat() if last_update_time else None
    })

@app.post("/api/refresh")
async def refresh_data(user: Optional[str] = Query(None, description="사용자 ID")):
    """
    티켓 데이터를 수동으로 새로고침합니다. (관리자 전용)
    """
    # 관리자 권한 확인
    if not user or user not in ADMIN_USERS:
        raise HTTPException(
            status_code=403, 
            detail="관리자 권한이 필요합니다. 수동 새로고침은 관리자만 사용할 수 있습니다."
        )
    
    refresh_ticket_data()
    logger.info(f"관리자 {user}가 수동으로 데이터를 새로고침했습니다.")
    
    return JSONResponse({
        "status": "success",
        "message": "데이터가 새로고침되었습니다.",
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "last_update_formatted": last_update_time.strftime("%Y. %m. %d. %p %I:%M") if last_update_time else "업데이트 없음",
        "total_tickets": len(ticket_cache)
    })

@app.get("/api/stats")
async def get_stats():
    """
    티켓 통계 정보를 반환합니다.
    """
    stats = get_ticket_stats(ticket_cache)
    return JSONResponse(stats)

@app.get("/api/update-info")
async def get_update_info():
    """
    데이터 업데이트 정보를 반환합니다.
    """
    return JSONResponse({
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "last_update_formatted": last_update_time.strftime("%Y. %m. %d. %p %I:%M") if last_update_time else "업데이트 없음",
        "total_tickets": len(ticket_cache),
        "auto_refresh_interval": AUTO_REFRESH_INTERVAL,
        "next_auto_refresh": (last_update_time + timedelta(seconds=AUTO_REFRESH_INTERVAL)).isoformat() if last_update_time else None
    })



def _parse_ticket_date_improved(date_str: str) -> Optional[datetime.date]:
    """
    정규표현식을 사용하여 다양한 형식의 날짜 문자열을 파싱합니다.
    지원 형식:
    - 'YYYY-MM-DD(요일) HH:MM' (예: '2025-06-24(화) 18:00')
    - 'MM.DD(요일) HH:MM' (예: '06.25(수) 13:00')
    - '[오픈]YY.MM.DD(요일)' (예: '[오픈]25.06.26(목)')
    - 'YYYY.MM.DD' 또는 'YYYY-MM-DD'
    - '오픈일정 보기 >'와 같은 문자열은 None을 반환합니다.

    Args:
        date_str: 날짜 문자열

    Returns:
        파싱된 date 객체 또는 실패 시 None
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if date_str in ['미정', '오픈일정 보기 >']:
        return None

    now = datetime.now()

    # 형식 1: 'YYYY-MM-DD(요일) HH:MM' 또는 'YYYY.MM.DD(요일) HH:MM'
    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})\(.\)\s*(\d{2}):(\d{2})', date_str)
    if match:
        try:
            year, month, day, hour, minute = map(int, match.groups())
            return datetime(year, month, day, hour, minute).date()
        except ValueError:
            pass

    # 형식 2: 'MM.DD(요일) HH:MM' (예: '06.25(수) 13:00')
    match = re.search(r'(\d{2})\.(\d{2})\(.\)\s*(\d{2}):(\d{2})', date_str)
    if match:
        try:
            month, day, hour, minute = map(int, match.groups())
            # 올해 날짜로 가정
            parsed_date = datetime(now.year, month, day, hour, minute)
            # 파싱된 날짜가 이미 지났다면 내년으로 간주
            if parsed_date < now:
                parsed_date = parsed_date.replace(year=now.year + 1)
            return parsed_date.date()
        except ValueError:
            pass # 다음 형식으로 넘어감

    # 형식 3: '[오픈]YY.MM.DD(요일)' (예: '[오픈]25.06.26(목)')
    match = re.search(r'\[오픈\]\s*(\d{2})\.(\d{2})\.(\d{2})', date_str)
    if match:
        try:
            year, month, day = map(int, match.groups())
            return datetime(2000 + year, month, day).date()
        except ValueError:
            pass

    # 형식 4: 'YYYY.MM.DD' 또는 'YYYY-MM-DD' (시간 정보가 없을 때)
    try:
        # 요일 정보 및 기타 텍스트 제거
        clean_date_str = re.sub(r'\s*\(.+\)', '', date_str).strip().rstrip('.')
        clean_date_str = clean_date_str.replace('-', '.') # 구분자 통일
        return datetime.strptime(clean_date_str, '%Y.%m.%d').date()
    except ValueError:
        pass

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