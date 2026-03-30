"""
PNU(필지고유번호) 추출 모듈

역할:
  - 구역계 Polygon의 Bounding Box로 브이월드에서 지적도를 가져옴
  - shapely intersects()로 구역계에 편입되는 PNU만 정밀 필터링
"""
import requests
from shapely.geometry import shape
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER


def extract_pnu_list(boundary_polygon, api_key):
    """
    구역계 폴리곤과 교차하는 모든 필지의 PNU 리스트를 추출합니다.
    
    Args:
        boundary_polygon (shapely.Polygon): 구역계 폴리곤 (lon, lat 순서)
        api_key (str): 브이월드 API 인증키
    
    Returns:
        list[dict]: [{"PNU": str, "주소": str, "지번": str}, ...]
        실패 시 빈 리스트
    """
    # 1. Bounding Box 계산 (콤마 구분, 띄어쓰기 없이!)
    min_x, min_y, max_x, max_y = boundary_polygon.bounds
    box_filter = f"BOX({min_x},{min_y},{max_x},{max_y})"
    
    # 2. 브이월드 지적도 API 호출
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": CADASTRAL_LAYER,
        "key": api_key,
        "domain": VWORLD_DOMAIN,
        "geomFilter": box_filter,
        "geometry": "true",     # 지적도 폴리곤 모양도 같이 가져오기
        "size": "1000",
    }
    
    try:
        res = requests.get(VWORLD_DATA_URL, params=params, timeout=30)
        data = res.json()
        
        # 응답 상태 확인
        status = data.get("response", {}).get("status")
        if status != "OK":
            error_text = data.get("response", {}).get("error", {}).get("text", "알 수 없음")
            raise RuntimeError(f"브이월드 응답 오류: {status} - {error_text}")
        
        features = (
            data.get("response", {})
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        
        # 3. 구역계와 교차하는 필지만 정밀 필터링
        included = []
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue
            
            # 지적도 도형을 shapely 객체로 변환
            parcel_shape = shape(geom)
            
            # 구역계와 교차 여부 판정
            if boundary_polygon.intersects(parcel_shape):
                included.append({
                    "PNU": props.get("pnu", ""),
                    "주소": props.get("addr", ""),
                    "지번": props.get("jibun", ""),
                })
        
        return included
    
    except requests.RequestException as e:
        raise RuntimeError(f"API 통신 오류: {e}")
