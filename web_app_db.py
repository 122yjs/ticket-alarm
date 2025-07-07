#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 기반 티켓 오픈 모니터 웹 인터페이스

SQLite 데이터베이스를 사용하여 실시간으로 수집된 티켓 정보를 시각적으로 표시하는 웹 애플리케이션입니다.
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# 로컬 모듈 임포트
from db_data_manager import get_data_manager
from database import get_database

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="티켓 오픈 모니터 (DB 버전)",
    description="데이터베이스 기반 실시간 공연 티켓 오픈 알림 시스템",
    version="2.0.0"
)

# 정적 파일 및 템플릿 설정
static_dir = Path("static")
template_dir = Path("templates")

# 디렉토리 생성
static_dir.mkdir(exist_ok=True)
template_dir.mkdir(exist_ok=True)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 전역 변수
data_manager = get_data_manager()
db = get_database()

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 초기화"""
    logger.info("웹 애플리케이션이 시작되었습니다.")
    
    # 데이터베이스 연결 확인
    try:
        stats = data_manager.get_statistics()
        logger.info(f"데이터베이스 연결 성공 - 총 티켓 수: {stats['total_count']}")
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 정리"""
    logger.info("웹 애플리케이션이 종료됩니다.")
    db.close()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """메인 페이지"""
    try:
        # 기본 통계 정보
        stats = data_manager.get_statistics()
        
        # 최근 티켓 몇 개
        recent_tickets = data_manager.load_tickets(limit=10, filters={'order_by': 'created_at'})
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "stats": stats,
            "recent_tickets": recent_tickets,
            "page_title": "티켓 오픈 모니터",
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logger.error(f"메인 페이지 로드 오류: {e}")
        raise HTTPException(status_code=500, detail="페이지 로드 중 오류가 발생했습니다.")

@app.get("/api/tickets")
async def get_tickets(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    source: Optional[str] = Query(None, description="티켓 소스 필터"),
    genre: Optional[str] = Query(None, description="장르 필터"),
    search: Optional[str] = Query(None, description="검색어"),
    date_from: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    date_filter: Optional[str] = Query(None, description="날짜 필터 (today, tomorrow, week)"),
    order_by: str = Query("open_datetime", description="정렬 기준"),
    order_desc: bool = Query(True, description="내림차순 정렬 여부")
):
    """
    티켓 목록 API (페이지네이션 지원)
    """
    try:
        # 오프셋 계산
        offset = (page - 1) * limit
        
        # 필터 조건 구성
        filters = {
            'source': source,
            'genre': genre,
            'search': search,
            'order_by': order_by,
            'order_desc': order_desc
        }
        
        # 날짜 필터 처리
        # 날짜 필터 우선 처리
        if date_filter:
            # UTC 기준 현재 시간에 9시간을 더해 한국 시간 계산
            kst_now = datetime.utcnow() + timedelta(hours=9)
            today = kst_now.date()
            
            if date_filter == 'today':
                filters['date_from'] = today
                filters['date_to'] = today
            elif date_filter == 'tomorrow':
                tomorrow = today + timedelta(days=1)
                filters['date_from'] = tomorrow
                filters['date_to'] = tomorrow
            elif date_filter == 'week':
                filters['date_from'] = today
                filters['date_to'] = today + timedelta(days=6)
            
            # 디버깅 로그 추가
            logger.info(f"Date filter '{date_filter}' applied. Today (KST): {today}, From: {filters.get('date_from')}, To: {filters.get('date_to')}")
        
        elif date_from:
            # 직접 날짜 입력 처리
            try:
                filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="잘못된 시작 날짜 형식")
        
        if date_to and not date_filter: # date_filter가 없을 때만 date_to를 독립적으로 처리
            try:
                filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="잘못된 종료 날짜 형식")
        
        # 티켓 조회
        tickets = data_manager.load_tickets(limit=limit, offset=offset, filters=filters)
        total_count = data_manager.get_ticket_count(filters)
        
        # 페이지네이션 정보
        total_pages = (total_count + limit - 1) // limit
        
        return JSONResponse({
            "tickets": tickets,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "limit": limit,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"티켓 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="티켓 조회 중 오류가 발생했습니다.")

@app.get("/api/stats")
async def get_stats():
    """티켓 통계 정보 API"""
    try:
        stats = data_manager.get_statistics()
        
        # 추가 통계 정보
        today = date.today()
        
        # 최근 7일간 등록된 티켓 수
        week_ago = today - timedelta(days=7)
        recent_filters = {
            'date_from': week_ago,
            'date_to': today
        }
        recent_count = data_manager.get_ticket_count(recent_filters)
        stats['recent_week_count'] = recent_count
        
        return JSONResponse(stats)
        
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="통계 조회 중 오류가 발생했습니다.")

@app.get("/api/sources")
async def get_sources():
    """사용 가능한 티켓 소스 목록 반환"""
    try:
        stats = data_manager.get_statistics()
        sources = list(stats.get('source_counts', {}).keys())
        return JSONResponse({"sources": sources})
    except Exception as e:
        logger.error(f"소스 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="소스 목록 조회 중 오류가 발생했습니다.")

@app.get("/api/genres")
async def get_genres():
    """사용 가능한 장르 목록 반환"""
    try:
        stats = data_manager.get_statistics()
        genres = list(stats.get('genre_counts', {}).keys())
        return JSONResponse({"genres": genres})
    except Exception as e:
        logger.error(f"장르 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="장르 목록 조회 중 오류가 발생했습니다.")

@app.get("/api/search")
async def search_tickets(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(20, ge=1, le=100, description="결과 수 제한")
):
    """티켓 검색 API"""
    try:
        filters = {
            'search': q,
            'order_by': 'created_at',
            'order_desc': True
        }
        
        tickets = data_manager.load_tickets(limit=limit, filters=filters)
        total_count = data_manager.get_ticket_count(filters)
        
        return JSONResponse({
            "query": q,
            "tickets": tickets,
            "total_count": total_count
        })
        
    except Exception as e:
        logger.error(f"검색 오류: {e}")
        raise HTTPException(status_code=500, detail="검색 중 오류가 발생했습니다.")

@app.post("/api/refresh")
async def refresh_data():
    """
    데이터 새로고침 API
    실제로는 크롤러를 실행하여 새로운 데이터를 수집해야 하지만,
    여기서는 현재 데이터베이스 상태만 반환
    """
    try:
        stats = data_manager.get_statistics()
        
        return JSONResponse({
            "status": "success",
            "message": "데이터가 새로고침되었습니다.",
            "last_update": datetime.now().isoformat(),
            "total_tickets": stats['total_count']
        })
        
    except Exception as e:
        logger.error(f"데이터 새로고침 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터 새로고침 중 오류가 발생했습니다.")

@app.get("/api/config")
async def get_config():
    """현재 설정 정보 반환"""
    try:
        config = data_manager.load_config()
        
        # 민감한 정보는 마스킹
        safe_config = config.copy()
        if 'DISCORD_WEBHOOK_URL' in safe_config:
            webhook_url = safe_config['DISCORD_WEBHOOK_URL']
            if len(webhook_url) > 20:
                safe_config['DISCORD_WEBHOOK_URL'] = webhook_url[:10] + "..." + webhook_url[-10:]
        
        return JSONResponse(safe_config)
        
    except Exception as e:
        logger.error(f"설정 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="설정 조회 중 오류가 발생했습니다.")

@app.get("/api/dashboard")
async def get_dashboard_data():
    """대시보드용 종합 데이터 API"""
    try:
        # 기본 통계
        stats = data_manager.get_statistics()
        
        # 최근 티켓들
        recent_tickets = data_manager.load_tickets(
            limit=10, 
            filters={'order_by': 'created_at', 'order_desc': True}
        )
        
        # 오늘/내일/이번주 오픈 티켓들
        today = date.today()
        tomorrow = today + timedelta(days=1)
        week_end = today + timedelta(days=7)
        
        today_tickets = data_manager.load_tickets(
            limit=5,
            filters={'date_from': today, 'date_to': today, 'order_by': 'open_datetime'}
        )
        
        tomorrow_tickets = data_manager.load_tickets(
            limit=5,
            filters={'date_from': tomorrow, 'date_to': tomorrow, 'order_by': 'open_datetime'}
        )
        
        return JSONResponse({
            "stats": stats,
            "recent_tickets": recent_tickets,
            "today_tickets": today_tickets,
            "tomorrow_tickets": tomorrow_tickets,
            "last_update": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="대시보드 데이터 조회 중 오류가 발생했습니다.")

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    try:
        # 데이터베이스 연결 확인
        stats = data_manager.get_statistics()
        
        return JSONResponse({
            "status": "healthy",
            "database": "connected",
            "total_tickets": stats['total_count'],
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

if __name__ == "__main__":
    # 개발 서버 실행
    uvicorn.run(
        "web_app_db:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )