#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 오픈 알림 웹 인터페이스

KOPIS 공연 정보를 데이터베이스에서 조회하여 보여주는 웹 애플리케이션입니다.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# 로컬 모듈 임포트
from database_manager import get_all_performances, get_performance_by_id, create_table

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="티켓 알람",
    description="KOPIS 공연 정보 조회 시스템",
    version="2.0.0"
)

# 정적 파일 및 템플릿 설정
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

@app.on_event("startup")
def on_startup():
    """
    애플리케이션 시작 시 데이터베이스 테이블을 생성합니다.
    """
    logger.info("애플리케이션 시작. 데이터베이스 초기화를 확인합니다.")
    create_table()
    logger.info("데이터베이스 준비 완료.")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    메인 페이지를 렌더링합니다.
    데이터베이스에서 모든 공연 목록을 가져와 표시합니다.
    """
    logger.info("메인 페이지 요청 수신")
    try:
        performances = get_all_performances()
        logger.info(f"{len(performances)}개의 공연 정보를 가져왔습니다.")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "kopis_performances": performances
        })
    except Exception as e:
        logger.error(f"공연 목록을 가져오는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@app.get("/performance/{kopis_id}", response_class=HTMLResponse)
async def performance_detail(request: Request, kopis_id: str):
    """
    개별 공연의 상세 페이지를 렌더링합니다.
    """
    logger.info(f"상세 페이지 요청 수신: kopis_id={kopis_id}")
    try:
        performance = get_performance_by_id(kopis_id)
        if performance is None:
            logger.warning(f"ID에 해당하는 공연을 찾을 수 없음: {kopis_id}")
            raise HTTPException(status_code=404, detail="공연 정보를 찾을 수 없습니다.")
        
        logger.info(f"'{performance['name']}' 공연 정보를 찾았습니다.")
        return templates.TemplateResponse("detail.html", {
            "request": request,
            "performance": performance
        })
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"공연 상세 정보를 가져오는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


if __name__ == "__main__":
    # 개발 서버 실행
    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )