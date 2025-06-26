import time
from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger
from sync_kopis import sync_performances

# 로거 설정
logger.add("logs/scheduler.log", rotation="10 MB", level="INFO", format="{time} {level} {message}")

def scheduled_job():
    """
    KOPIS 데이터 동기화 작업을 실행하는 스케줄링된 잡입니다.
    """
    logger.info("스케줄러에 의해 KOPIS 동기화 작업을 시작합니다.")
    try:
        sync_performances()
        logger.info("KOPIS 동기화 작업이 성공적으로 완료되었습니다.")
    except Exception as e:
        logger.error(f"KOPIS 동기화 작업 중 오류 발생: {e}")

if __name__ == "__main__":
    # 스케줄러 생성
    scheduler = BlockingScheduler(timezone='Asia/Seoul')

    # 매일 새벽 3시에 'scheduled_job' 함수를 실행하도록 작업 등록
    # 사용법: scheduler.add_job(실행할_함수, 'cron', hour=시, minute=분)
    scheduler.add_job(scheduled_job, 'cron', hour=3, minute=0)

    logger.info("스케줄러가 시작되었습니다. 매일 새벽 3시에 동기화 작업이 실행됩니다.")
    logger.info("스케줄러를 중지하려면 Ctrl+C를 누르세요.")

    try:
        # 스케줄러 시작
        # 이 스크립트를 실행하면 스케줄러가 백그라운드에서 계속 실행됩니다.
        # 터미널에서 'python scheduler.py' 명령으로 실행할 수 있습니다.
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러가 종료되었습니다.")