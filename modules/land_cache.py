"""
토지 데이터 로컬 캐시 모듈 — SQLite 기반

역할:
  - API에서 한번 가져온 필지 데이터를 로컬 DB에 저장
  - 다음 분석 시 캐시에서 즉시 로드 (API 호출 불필요)
  - 데이터 갱신 주기: 기본 90일 (공시지가 연 1회 변경)

사용:
  cache = LandDataCache()
  data = cache.get(pnu)        # 캐시에서 조회 (없으면 None)
  cache.put(pnu, data_dict)    # 캐시에 저장
  cache.get_stats()            # 캐시 적중률 통계
"""
import sqlite3
import json
import os
import time
import threading
from datetime import datetime, timedelta

# 캐시 DB 파일 위치 (프로젝트 루트)
CACHE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DB_PATH = os.path.join(CACHE_DIR, "land_cache.db")

# 캐시 유효기간 (일)
CACHE_TTL_DAYS = 90


class LandDataCache:
    """SQLite 기반 토지 데이터 로컬 캐시 (스레드 안전)"""
    
    def __init__(self, db_path=None, ttl_days=CACHE_TTL_DAYS):
        self.db_path = db_path or CACHE_DB_PATH
        self.ttl_days = ttl_days
        self._local = threading.local()
        self._stats = {"hits": 0, "misses": 0}
        self._stats_lock = threading.Lock()
        self._init_db()
    
    def _get_conn(self):
        """스레드별 독립 DB 연결 반환"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=10)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")  # 동시 읽기/쓰기 성능 향상
        return self._local.conn
    
    def _init_db(self):
        """캐시 테이블 생성"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS land_cache (
                pnu TEXT PRIMARY KEY,
                jimok TEXT,
                parea REAL DEFAULT 0,
                pnilp TEXT DEFAULT '-',
                owner_type TEXT DEFAULT '개인',
                owner_count TEXT DEFAULT '1',
                land_use TEXT DEFAULT '미조회',
                sojaeji TEXT DEFAULT '',
                extra_json TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                source TEXT DEFAULT 'API'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_land_cache_updated 
            ON land_cache(updated_at)
        """)
        conn.commit()
    
    def get(self, pnu):
        """
        PNU로 캐시 데이터 조회.
        TTL 이내의 유효한 데이터만 반환, 만료 시 None 반환.
        '완전한' 데이터(지목+면적+공시지가 모두 유효)만 캐시 히트로 처리.
        """
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM land_cache WHERE pnu = ?", (pnu,)
            ).fetchone()
            
            if row is None:
                with self._stats_lock:
                    self._stats["misses"] += 1
                return None
            
            # TTL 확인
            updated = datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - updated > timedelta(days=self.ttl_days):
                with self._stats_lock:
                    self._stats["misses"] += 1
                return None  # 만료된 데이터
            
            # 데이터 완전성 확인 — 불완전한 캐시는 미스로 처리
            jimok = row["jimok"] or "-"
            parea = row["parea"] or 0
            land_use = row["land_use"] or ""
            if jimok in ["-", "", "기타"] or parea <= 0:
                with self._stats_lock:
                    self._stats["misses"] += 1
                return None
            # 이용상황 검증: "미조회"만 재페치 트리거.
            # "" (빈문자열)는 "API 조회했으나 NED에 데이터 없음"을 의미하므로 valid hit.
            # (None도 같은 의미로 valid 처리 — 일부 컬럼이 NULL일 수 있음)
            if land_use == "미조회":
                with self._stats_lock:
                    self._stats["misses"] += 1
                return None
            
            with self._stats_lock:
                self._stats["hits"] += 1
            
            return {
                "jimok": row["jimok"],
                "parea": row["parea"],
                "pnilp": row["pnilp"],
                "owner_type": row["owner_type"],
                "owner_count": row["owner_count"],
                "land_use": row["land_use"],
                "sojaeji": row["sojaeji"],
            }
        except Exception:
            return None
    
    def put(self, pnu, data):
        """
        필지 데이터를 캐시에 저장/갱신.
        불완전한 데이터(면적=0 등)도 저장하되, get()에서 완전성 검증 시 걸러짐.
        """
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO land_cache 
                (pnu, jimok, parea, pnilp, owner_type, owner_count, land_use, sojaeji, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (
                pnu,
                data.get("jimok", "-"),
                data.get("parea", 0),
                data.get("pnilp", "-"),
                data.get("owner_type", "개인"),
                data.get("owner_count", "1"),
                data.get("land_use", "미조회"),
                data.get("sojaeji", ""),
            ))
            conn.commit()
        except Exception:
            pass
    
    def put_batch(self, items):
        """
        여러 필지를 한번에 저장 (트랜잭션 일괄 처리).
        items: [(pnu, data_dict), ...]
        """
        try:
            conn = self._get_conn()
            conn.executemany("""
                INSERT OR REPLACE INTO land_cache 
                (pnu, jimok, parea, pnilp, owner_type, owner_count, land_use, sojaeji, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, [
                (pnu, d.get("jimok", "-"), d.get("parea", 0), d.get("pnilp", "-"),
                 d.get("owner_type", "개인"), d.get("owner_count", "1"),
                 d.get("land_use", "미조회"), d.get("sojaeji", ""))
                for pnu, d in items
            ])
            conn.commit()
        except Exception:
            pass
    
    def get_stats(self):
        """캐시 적중률 통계 반환"""
        with self._stats_lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "total": total,
                "hit_rate": f"{hit_rate:.1f}%"
            }
    
    def reset_stats(self):
        """통계 초기화"""
        with self._stats_lock:
            self._stats = {"hits": 0, "misses": 0}
    
    def get_cache_size(self):
        """캐시에 저장된 총 레코드 수"""
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT COUNT(*) as cnt FROM land_cache").fetchone()
            return row["cnt"]
        except:
            return 0
    
    def clear_expired(self):
        """만료된 캐시 데이터 정리"""
        try:
            conn = self._get_conn()
            cutoff = (datetime.now() - timedelta(days=self.ttl_days)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("DELETE FROM land_cache WHERE updated_at < ?", (cutoff,))
            conn.commit()
        except:
            pass
    
    def clear_all(self):
        """캐시 전체 삭제"""
        try:
            conn = self._get_conn()
            conn.execute("DELETE FROM land_cache")
            conn.commit()
        except:
            pass
