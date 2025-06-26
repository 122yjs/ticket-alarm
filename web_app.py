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
from data_manager import load_config
from filters import filter_tickets_by_keywords, filter_tickets_by_date_range
from database_manager import DatabaseManager

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
    app.state.db_manager = DatabaseManager()
    logger.info("데이터베이스 관리자 초기화")
    refresh_ticket_data() # 앱 시작 시 초기 데이터 로드
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

# 사용자 권한 설정 (실제 환경에서는 데이터베이스나 설정 파일에서 관리)
ADMIN_USERS = {"admin", "manager"}  # 관리자 권한을 가진 사용자 목록

# 자동 갱신 설정
AUTO_REFRESH_INTERVAL = 3600  # 1시간 (초 단위)

def get_source_from_relates(relates: Optional[Dict[str, Any]]) -> str:
    """
    relates 딕셔너리의 relateurl을 기반으로 예매처 이름을 반환합니다.
    """
    relates_url = relates if isinstance(relates, str) else ""
    if not relates_url:
        return "기타"
    if "ticket.interpark.com" in relates_url:
        return "인터파크"
    if "ticket.yes24.com" in relates_url:
        return "예스24"
    if "ticketlink.co.kr" in relates_url:
        return "티켓링크"
    if "ticket.melon.com" in relates_url:
        return "멜론티켓"
    return "기타"

def map_genre(genre: Optional[str]) -> str:
    """
    KOPIS 장르를 프론트엔드 필터 카테고리로 매핑합니다.
    """
    if not genre:
        return "기타"

    if '대중음악' in genre:
        return '콘서트'
    elif '서양음악(클래식)' in genre or '한국음악(국악)' in genre:
        return '클래식'
    elif '뮤지컬' in genre:
        return '뮤지컬'
    elif '연극' in genre:
        return '연극'
    else:
        return '기타'

def transform_performance_for_frontend(performance: Dict[str, Any]) -> Dict[str, Any]:
    """
    데이터베이스 공연 정보를 프론트엔드에서 사용하는 형식으로 변환합니다.
    """
    start_date = performance.get("start_date", "")
    end_date = performance.get("end_date", "")
    
    # KOPIS 날짜 형식(YYYY.MM.DD)을 JS new Date()가 인식할 수 있는 형식(YYYY-MM-DD HH:MM:SS)으로 변환
    try:
        open_date_obj = datetime.strptime(start_date, "%Y.%m.%d")
        open_date_formatted = open_date_obj.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        open_date_formatted = start_date # 파싱 실패 시 원본 값 사용

    # 데이터 가공 로직 적용
    source = get_source_from_relates(performance.get("relates_url"))
    genre = map_genre(performance.get("genre"))

    return {
        "id": performance.get("kopis_id"),
        "kopis_id": performance.get("kopis_id"),
        "title": performance.get("name"),
        "place": performance.get("facility_name"),
        "image_url": performance.get("poster_url"),
        "open_date": open_date_formatted,
        "source": source,
        "url": f"/detail/{performance.get('kopis_id')}",
        "perf_date": f"{start_date} ~ {end_date}",
        "genre": genre,
        "status": performance.get("status"),
    }

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
    
    # 장르별 카운트
    genre_counts = {}
    for ticket in tickets:
        genre = ticket.get('genre', '기타')
        genre_counts[genre] = genre_counts.get(genre, 0) + 1

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)
    
    today_count = 0
    tomorrow_count = 0
    this_week_count = 0
    
    for ticket in tickets:
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

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: Optional[str] = Query(None, description="사용자 ID")):
    """
    메인 페이지를 렌더링합니다. 데이터는 클라이언트 측에서 API를 통해 로드됩니다.
    """
    is_admin = user in ADMIN_USERS if user else False
    
    # 초기 페이지 로드 시에는 빈 데이터로 렌더링하고,
    # 클라이언트 스크립트가 /api/tickets를 호출하여 동적으로 데이터를 채웁니다.
    
    app_config = {
        "isAdmin": is_admin,
        "autoRefreshInterval": AUTO_REFRESH_INTERVAL,
        "lastUpdateIso": datetime.now().isoformat() # 초기 로드 시간
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "tickets": [], # 초기에는 비어있음
        "stats": get_ticket_stats([]), # 초기에는 비어있음
        "last_update": "로딩 중...",
        "total_tickets": 0,
        "is_admin": is_admin,
        "app_config_json": json.dumps(app_config)
    })

# /performance/{kopis_id} 엔드포인트는 현재 사용되지 않으므로 제거하거나 주석 처리합니다.
# 이 엔드포인트는 DB 중심 아키텍처에서 의미가 있습니다.

@app.get("/api/tickets")
async def get_tickets(request: Request):
    """
    데이터베이스에서 모든 공연 정보를 가져와 가공한 후 JSON으로 반환합니다.
    이 과정에서 예매처(source)와 장르(genre) 정보가 변환됩니다.
    """
    try:
        db_manager = request.app.state.db_manager
        raw_performances = db_manager.get_all_performances()
        
        # DB 데이터를 프론트엔드 형식으로 변환
        transformed_tickets = [transform_performance_for_frontend(p) for p in raw_performances]
        
        config = load_config()
        platform_colors = config.get("platform_colors", {})
        
        # 마지막 업데이트 시간은 현재 시간으로 설정 (실시간 조회이므로)
        last_update = datetime.now()

        return JSONResponse({
            "tickets": transformed_tickets,
            "stats": get_ticket_stats(transformed_tickets),
            "platform_colors": platform_colors,
            "last_update": last_update.isoformat()
        })
    except Exception as e:
        logger.error(f"/api/tickets 엔드포인트 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

@app.get("/api/stats")
async def get_stats(request: Request):
    """
    현재 DB의 데이터를 기반으로 티켓 통계 정보를 반환합니다.
    """
    try:
        db_manager = request.app.state.db_manager
        raw_performances = db_manager.get_all_performances()
        transformed_tickets = [transform_performance_for_frontend(p) for p in raw_performances]
        stats = get_ticket_stats(transformed_tickets)
        return JSONResponse(stats)
    except Exception as e:
        logger.error(f"/api/stats 엔드포인트 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")



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