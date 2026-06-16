"""
report 패키지 — 보고서/조서 자동 생성 모듈

현황 분석 보고서는 HWP(hwpx)로 생성합니다. (status_report_generator)
※ 레거시 워드(.docx) 보고서(word_report.LandReportGenerator)는 더 이상 사용하지 않으며,
   python-docx 의존성을 강제하지 않도록 패키지 초기화에서 import 하지 않습니다.
   필요 시 해당 모듈을 직접 import 해서 사용하세요.
"""
