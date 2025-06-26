import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_name='kopis.db'):
        self.db_name = db_name
        self.conn = None

    def connect(self):
        """데이터베이스에 연결합니다."""
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row

    def disconnect(self):
        """데이터베이스 연결을 닫습니다."""
        if self.conn:
            self.conn.close()

    def init_db(self):
        """데이터베이스를 초기화하고 테이블을 생성합니다."""
        self.connect()
        cursor = self.conn.cursor()

        # performances 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performances (
                kopis_id TEXT PRIMARY KEY,
                name TEXT,
                start_date TEXT,
                end_date TEXT,
                facility_name TEXT,
                poster_url TEXT,
                genre TEXT,
                status TEXT,
                "cast" TEXT,
                crew TEXT,
                runtime TEXT,
                age_limit TEXT,
                price TEXT,
                synopsis TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # updated_at 트리거 생성
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_performances_updated_at
            AFTER UPDATE ON performances
            FOR EACH ROW
            BEGIN
                UPDATE performances SET updated_at = CURRENT_TIMESTAMP WHERE kopis_id = OLD.kopis_id;
            END;
        ''')

        self.conn.commit()
        self.disconnect()
        print("Database initialized and 'performances' table created successfully.")

    def get_all_performances(self):
        """모든 공연 정보를 조회합니다."""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM performances ORDER BY start_date DESC")
        performances = [dict(row) for row in cursor.fetchall()]
        self.disconnect()
        return performances

    def get_performance_by_id(self, kopis_id):
        """KOPIS ID로 특정 공연 정보를 조회합니다."""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM performances WHERE kopis_id = ?", (kopis_id,))
        performance = cursor.fetchone()
        self.disconnect()
        return dict(performance) if performance else None

    def get_all_kopis_ids(self):
        """데이터베이스에 저장된 모든 공연의 KOPIS ID 목록을 조회합니다."""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT kopis_id FROM performances")
        ids = [row['kopis_id'] for row in cursor.fetchall()]
        self.disconnect()
        return ids

    def insert_performance(self, performance_data):
        """새로운 공연 정보를 데이터베이스에 삽입합니다."""
        self.connect()
        cursor = self.conn.cursor()
        
        columns = ', '.join(performance_data.keys())
        placeholders = ', '.join('?' for _ in performance_data)
        
        query = f"INSERT INTO performances ({columns}) VALUES ({placeholders})"
        
        try:
            cursor.execute(query, tuple(performance_data.values()))
            self.conn.commit()
        except sqlite3.IntegrityError:
            print(f"Error: Performance with kopis_id {performance_data.get('kopis_id')} already exists.")
        finally:
            self.disconnect()

    def update_performance(self, kopis_id, update_data):
        """기존 공연 정보를 업데이트합니다."""
        self.connect()
        cursor = self.conn.cursor()
        
        update_fields = ', '.join([f"{key} = ?" for key in update_data.keys()])
        
        query = f"UPDATE performances SET {update_fields} WHERE kopis_id = ?"
        
        try:
            cursor.execute(query, tuple(update_data.values()) + (kopis_id,))
            self.conn.commit()
        finally:
            self.disconnect()

# 이 스크립트가 직접 실행될 때 데이터베이스를 초기화합니다.
if __name__ == '__main__':
    db_manager = DatabaseManager()
    db_manager.init_db()