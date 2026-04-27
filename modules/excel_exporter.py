"""
엑셀 내보내기 모듈

역할:
  - 분석 결과 데이터(dict 리스트)를 Pandas DataFrame → 엑셀 파일로 변환
  - Streamlit에서 다운로드 가능한 bytes 객체로 반환
"""
import io
import pandas as pd
from openpyxl.styles import Alignment, PatternFill, Border, Side, Font


def create_excel_bytes(data_list, sheet_name="분석결과"):
    """
    딕셔너리 리스트를 엑셀 바이트 데이터로 변환합니다.
    (Streamlit의 st.download_button에 바로 넣을 수 있음)
    
    Args:
        data_list (list[dict]): 엑셀에 넣을 데이터 리스트
        sheet_name (str): 시트 이름
    
    Returns:
        bytes: 엑셀 파일 바이트 데이터
    """
    df = pd.DataFrame(data_list)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    
    return buffer.getvalue()


def format_land_ledger_sheet(ws, df):
    """
    토지조서 시트에 1단 헤더 및 스타일을 적용합니다.
    """
    # 1. 1행 헤더 작성
    headers = list(df.columns)
    ws.append(headers)
    
    # 2. 데이터 작성
    for r in df.values:
        ws.append(list(r))
        
    # 3. 셀 병합 (제거됨 - 단일 헤더 사용)
    
    # 4. 스타일 적용
    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    header_font = Font(bold=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal='center', vertical='center')
    
    # 열 너비 설정 (16개 컬럼)
    ws.column_dimensions['A'].width = 8   # 일련번호
    ws.column_dimensions['B'].width = 22  # PNU
    ws.column_dimensions['C'].width = 25  # 소재지
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
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
            else:
                if cell.column_letter in ['C', 'N']: # 소재지, 용도지역은 좌측 정렬
                    cell.alignment = Alignment(horizontal='left', vertical='center')
                else:
                    cell.alignment = center_align


def create_multi_sheet_excel(sheets_data):
    """
    여러 분석 결과를 각각 별도 시트에 담은 엑셀 파일을 생성합니다.
    
    Args:
        sheets_data (dict): {"시트이름": [dict, dict, ...], ...}
    
    Returns:
        bytes: 엑셀 파일 바이트 데이터
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, data_list in sheets_data.items():
            if data_list:
                df = pd.DataFrame(data_list)
                if sheet_name == "토지조서 (편입면적/공시지가 등)":
                    workbook = writer.book
                    worksheet = workbook.create_sheet(sheet_name)
                    format_land_ledger_sheet(worksheet, df)
                else:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
        
        # 첫 번째 빈 시트 제거 (오픈파이셀 기본 시트)
        if "Sheet" in writer.book.sheetnames and len(writer.book.sheetnames) > 1:
            writer.book.remove(writer.book["Sheet"])
            
    return buffer.getvalue()
