import requests
import pandas as pd # 엑셀 및 표 데이터 처리 라이브러리

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"

# 앞 단계(get_pnu_list.py)에서 성공해서 얻은 PNU 리스트를 여기에 넣습니다.
# (실제 프로그램에서는 앞의 코드와 이 코드가 하나로 이어지게 됩니다)
extracted_parcels = [
    {"PNU": "4121010700201030000", "주소": "경기도 광명시 가학동 산 103"}
]

def make_land_report_excel(parcel_list, api_key):
    print("1. 토지 속성 데이터(공시지가 등) 수집을 시작합니다...")
    
    # 엑셀에 담을 최종 데이터를 모아둘 빈 리스트
    final_data = []
    
    for parcel in parcel_list:
        pnu = parcel["PNU"]
        address = parcel["주소"]
        
        print(f"-> [{address}] 데이터 조회 중...")
        
        # 브이월드 개별공시지가 API 주소
        url = "https://api.vworld.kr/req/data"
        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN", # 개별공시지가 데이터셋
            "key": api_key,
            "domain": "http://localhost",
            "attrFilter": f"pnu:like:{pnu}"
        }
        
        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            
            # API에서 데이터를 성공적으로 받아왔다면
            if data.get('response', {}).get('status') == 'OK':
                features = data['response']['result']['featureCollection']['features']
                props = features[0]['properties']
                
                # 필요한 항목만 골라서 딕셔너리로 묶기
                parcel_info = {
                    "PNU": pnu,
                    "주소": address,
                    "지목": props.get('bchk', '알수없음'),      # 지목 (예: 임, 대, 전)
                    "공시지가(원/㎡)": props.get('pnilp', 0),    # 공시지가
                    "기준연월": props.get('pnu_yr', '') + "-" + props.get('pnu_mt', '')
                }
                final_data.append(parcel_info)
            else:
                print(f"   [경고] {address}의 공시지가 데이터가 없습니다.")
                # 데이터가 없어도 기본 주소는 엑셀에 넣기 위해 추가
                final_data.append({
                    "PNU": pnu, "주소": address, "지목": "-", "공시지가(원/㎡)": "-", "기준연월": "-"
                })
                
        except Exception as e:
            print(f"   [오류] {address} 조회 중 에러: {e}")

    # --- 엑셀로 저장하기 (Pandas 마법) ---
    print("\n2. 수집된 데이터를 엑셀로 변환합니다...")
    
    # 1. 딕셔너리 리스트를 Pandas 데이터프레임(표)으로 변환
    df = pd.DataFrame(final_data)
    
    # 2. 엑셀 파일로 저장
    excel_filename = "토지조서_자동화결과.xlsx"
    df.to_excel(excel_filename, index=False)
    
    print(f"✅ 성공! 바탕화면(현재 폴더)에 '{excel_filename}' 파일이 생성되었습니다.")

if __name__ == "__main__":
    make_land_report_excel(extracted_parcels, VWORLD_KEY)