"""
report 패키지 — 보고서 자동 생성 모듈

역할:
  - 분석 결과를 기반으로 Word(.docx) 보고서를 자동 생성합니다.
  - 소유자별, 지목별 등 토지이용 현황을 표와 삽도로 구성합니다.
"""
from report.word_report import LandReportGenerator
