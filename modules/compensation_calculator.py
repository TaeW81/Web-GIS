"""
토지보상비 자동 산정 모듈 — KDI 표 Ⅳ-28 기반

데이터 출처:
  - 기획재정부 「예비타당성조사 수행 총괄지침」 (2018.4)
  - 한국지방행정연구원 「용지구입비 보상배율 적용방안」 (2018.7)
  - 한국교통연구원 「도로 및 교통부문 타당성 조사 지침」 (2021, p.83 표 Ⅳ-28)

데이터 파일: data/compensation_ratio.json (출처 및 매핑 메타정보 포함)

기본 API:
  get_compensation_ratios(pnu, zoning_text, land_use_text) → (용도배율, 이용배율)
  get_source_info() → 출처 정보 dict (UI 표시용)

산정 공식:
  보상배율 = (용도지역 배율 + 이용상황 배율) / 2
  토지보상비(원) = 개별공시지가(원/㎡) × 면적(㎡) × 보상배율
"""
import json
import os
from functools import lru_cache

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "compensation_ratio.json",
)


@lru_cache(maxsize=1)
def _load_table():
    """JSON 데이터 한 번만 로드 후 캐시."""
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_sido_from_pnu(pnu):
    """PNU 첫 2자리 → 시도명. 매핑 불가 시 None."""
    if not pnu or len(str(pnu)) < 2:
        return None
    table = _load_table()
    return table["sido_code_to_name"].get(str(pnu)[:2])


def get_zoning_group(zoning_text):
    """용도지역 텍스트 → 표 Ⅳ-28 그룹명 (주거상업공업/녹지/관리/농림자보).

    매핑 우선순위:
      1) 정확 매칭 (zoning_to_group 키)
      2) 부분 매칭 (텍스트 포함)
      3) 키워드 휴리스틱
    매핑 불가 시 None.
    """
    if not zoning_text or zoning_text in ("-", "미조회", ""):
        return None
    table = _load_table()
    z = str(zoning_text).strip()

    # 1) 정확 매칭 (메타 키 "_..."는 제외)
    mapping = {k: v for k, v in table["zoning_to_group"].items() if not k.startswith("_")}
    if z in mapping:
        return mapping[z]

    # 2) 부분 매칭
    for key, group in mapping.items():
        if key in z:
            return group

    # 3) 키워드 휴리스틱
    if any(k in z for k in ["주거지역", "상업지역", "공업지역"]):
        return "주거상업공업"
    if "녹지지역" in z:
        return "녹지"
    if "관리지역" in z:
        return "관리"
    if any(k in z for k in ["농림지역", "자연환경보전지역"]):
        return "농림자보"

    return None


def get_land_use_group(land_use_text):
    """이용상황 텍스트(NED ladUseSittnNm) → 표 Ⅳ-28 그룹명. 매핑 불가 시 None.

    국공유지 / 미조회 / 빈값은 None 반환 (보상배율 적용 안 함).
    """
    if not land_use_text:
        return None
    u = str(land_use_text).strip()
    if u in ("-", "미조회", "", "국ㆍ공유지"):
        return None
    table = _load_table()
    mapping = {k: v for k, v in table["land_use_to_group"].items() if not k.startswith("_")}
    return mapping.get(u)


def get_compensation_ratios(pnu, zoning_text, land_use_text):
    """주어진 필지의 (용도지역 배율, 이용상황 배율) 자동 조회.

    Args:
        pnu: 필지고유번호 (첫 2자리로 시도 식별)
        zoning_text: 용도지역명 (예: "계획관리지역")
        land_use_text: 이용상황명 (예: "전답", "자연림")

    Returns:
        tuple (zoning_ratio, land_use_ratio): float 또는 None.
        둘 중 하나라도 None이면 사용자가 수동 입력하거나, 다른 하나만으로
        토지보상비 = 공시지가 × 면적 × 그 배율 로 계산 가능 (예타지침 p.82).
    """
    table = _load_table()
    sido = get_sido_from_pnu(pnu)
    if not sido or sido not in table["ratios_by_sido"]:
        return None, None

    sido_data = table["ratios_by_sido"][sido]
    zoning_ratio = None
    land_use_ratio = None

    z_group = get_zoning_group(zoning_text)
    if z_group:
        zoning_ratio = sido_data.get("용도지역", {}).get(z_group)

    u_group = get_land_use_group(land_use_text)
    if u_group:
        land_use_ratio = sido_data.get("이용상황", {}).get(u_group)

    return zoning_ratio, land_use_ratio


def get_overall_ratio(pnu):
    """시도 전체 평균 배율 (용도지역·이용상황 모두 미식별 시 폴백용)."""
    table = _load_table()
    sido = get_sido_from_pnu(pnu)
    if not sido:
        return None
    return table["ratios_by_sido"].get(sido, {}).get("전체")


def get_source_info():
    """출처 메타정보 반환 — UI/문서 표시용."""
    table = _load_table()
    return table.get("_meta", {})


def estimate_compensation(공시지가, 면적_m2, zoning_ratio, land_use_ratio):
    """추정 토지보상비 계산.

    보상배율 = (용도지역 배율 + 이용상황 배율) / 2
    토지보상비 = 공시지가 × 면적 × 보상배율

    둘 중 하나만 있을 때는 그 값을 보상배율로 사용 (예타지침 p.82).
    둘 다 없으면 None 반환.
    """
    try:
        price = float(공시지가)
        area = float(면적_m2)
    except (TypeError, ValueError):
        return None
    if price <= 0 or area <= 0:
        return None

    ratios = [r for r in (zoning_ratio, land_use_ratio) if r is not None]
    if not ratios:
        return None
    multiplier = sum(ratios) / len(ratios)
    return round(price * area * multiplier, 0)
