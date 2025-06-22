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

# 사용자 권한 설정 (실제 환경에서는 데이터베이스나 설정 파일에서 관리)
ADMIN_USERS = {"admin", "manager"}  # 관리자 권한을 가진 사용자 목록

# 자동 갱신 설정
AUTO_REFRESH_INTERVAL = 3600  # 1시간 (초 단위)



def refresh_ticket_data():
    """
    티켓 데이터를 새로고침합니다.
    """
    global ticket_cache, last_update_time
    
    try:
        # 데이터 관리 모듈을 사용하여 티켓 로드
        all_tickets = load_tickets()
        
        # 데이터 가공 (웹 표시용)
        processed_tickets = []
        for t in all_tickets:
            # D-day 계산
            d_day = ""
            open_date_str = t.get('open_date', '')
            if open_date_str and open_date_str != '미정':
                try:
                    # 날짜 형식 파싱 (예: '2024.07.25 14:00')
                    open_datetime = datetime.strptime(open_date_str.split(' ')[0], '%Y.%m.%d')
                    delta = open_datetime.date() - datetime.now().date()
                    if delta.days == 0:
                        d_day = "D-DAY"
                    elif delta.days > 0:
                        d_day = f"D-{delta.days}"
                except ValueError:
                    pass # 날짜 형식 안맞으면 무시

            processed_tickets.append({
                "image_url": t.get('image', 'https://via.placeholder.com/300x400.png?text=No+Image'), # 기본 이미지
                "title": t.get('title', '제목 없음'),
                "open_date_str": t.get('open_date', '미정'),
                "date": t.get('date', '날짜 정보 없음'),
                "place": t.get('place', '장소 정보 없음'),
                "genre": t.get('genre', '장르 미분류'),
                "platform": t.get('source', '플랫폼 정보 없음'),
                "d_day": d_day,
                "link": t.get('link', '#')
            })
        
        ticket_cache = processed_tickets
        last_update_time = datetime.now()
        logger.info(f"티켓 데이터 새로고침 및 가공 완료: {len(ticket_cache)}건")
        
    except Exception as e:
        logger.error(f"티켓 데이터 로드 및 가공 중 오류: {e}", exc_info=True)
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
    # 간단한 통계 정보 생성
    stats = {
        "total_count": len(ticket_cache)
    }
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tickets": ticket_cache[:50],  # 최대 50개만 표시
        "stats": stats
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