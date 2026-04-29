"""
엑셀 내보내기 모듈 (안정성 극대화 버전)
"""
import io
import re
import pandas as pd
from openpyxl.styles import Alignment, PatternFill, Border, Side, Font

def format_land_ledger_sheet(ws):
    """토지조서 시트에 스타일 적용 (범위 안전성 확보)"""
    if ws.max_row < 1: return
    
    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    header_font = Font(bold=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal='center', vertical='center')
    
    # 열 너비 설정 (A~P, 16개 컬럼)
    ws.column_dimensions['A'].width = 8   # 일련번호
    ws.column_dimensions['B'].width = 22  # PNU
    ws.column_dimensions['C'].width = 30  # 소재지
    ws.column_dimensions['D'].width = 10  # 필지구분
    ws.column_dimensions['E'].width = 6   # 본번
    ws.column_dimensions['F'].width = 6   # 부번
    ws.column_dimensions['G'].width = 8   # 지목
    ws.column_dimensions['H'].width = 12  # 소유자
    ws.column_dimensions['I'].width = 8   # 소유자수
    ws.column_dimensions['J'].width = 12  # 공시지가
    ws.column_dimensions['K'].width = 12  # 대장면적
    ws.column_dimensions['L'].width = 12  # 편입면적
    ws.column_dimensions['M'].width = 10  # 편입구분
    ws.column_dimensions['N'].width = 25  # 용도지역
    ws.column_dimensions['O'].width = 15  # 이용상황
    ws.column_dimensions['P'].width = 15  # 비고

    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=16), 1):
        for cell in row:
            cell.border = thin_border
            if row_idx == 1:
                cell.fill = header_fill; cell.font = header_font; cell.alignment = center_align
            else:
                if cell.column_letter in ['C', 'N']: # 소재지, 용도지역
                    cell.alignment = Alignment(horizontal='left', vertical='center')
                else:
                    cell.alignment = center_align

def create_multi_sheet_excel(sheets_data):
    """IndexError를 원천 차단하는 가장 단순하고 확실한 방법"""
    buffer = io.BytesIO()
    
    # 데이터 유효성 검사 및 보정
    valid_data = {k: v for k, v in (sheets_data or {}).items() if v}
    if not valid_data:
        valid_data = {"결과없음": [{"상태": "분석된 데이터가 없습니다."}]}

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for i, (sheet_name, data_list) in enumerate(valid_data.items()):
            df = pd.DataFrame(data_list)
            
            # ⭐️ 시트명 금지 문자 처리 (/, \, ?, *, [, ], :) ⭐️
            clean_sheet_name = re.sub(r'[\\/*?:\[\]]', '_', sheet_name)[:31]
            
            df.to_excel(writer, index=False, sheet_name=clean_sheet_name)
            
            if "토지조서" in clean_sheet_name:
                format_land_ledger_sheet(writer.sheets[clean_sheet_name])

        # ⭐️ 핵심: 모든 작업이 끝난 후, 'Sheet'나 'Sheet1'이 남아있고 다른 시트가 있다면 삭제 ⭐️
        # 삭제 후에는 반드시 active 시트를 설정해야 함
        workbook = writer.book
        for default_sheet in ["Sheet", "Sheet1"]:
            if default_sheet in workbook.sheetnames and len(workbook.sheetnames) > 1:
                workbook.remove(workbook[default_sheet])
        
        # 마지막 안전장치: 첫 번째 시트를 활성 시트로 지정
        workbook.active = 0

    return buffer.getvalue()
