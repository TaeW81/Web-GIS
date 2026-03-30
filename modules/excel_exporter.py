"""
엑셀 내보내기 모듈

역할:
  - 분석 결과 데이터(dict 리스트)를 Pandas DataFrame → 엑셀 파일로 변환
  - Streamlit에서 다운로드 가능한 bytes 객체로 반환
"""
import io
import pandas as pd


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
                df.to_excel(writer, index=False, sheet_name=sheet_name)
    
    return buffer.getvalue()
