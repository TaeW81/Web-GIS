"""
analyzers 패키지 초기화 — 분석기 자동 로딩 레지스트리

역할:
  - analyzers/ 폴더 안의 BaseAnalyzer 하위 클래스를 자동으로 찾아서 등록합니다.
  - app.py에서는 get_all_analyzers()만 호출하면 됩니다.
"""
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.land_attribute import LandAttributeAnalyzer
from analyzers.zoning_region import ZoningRegionAnalyzer


def get_all_analyzers():
    """
    등록된 모든 분석기 인스턴스를 리스트로 반환합니다.
    새 분석기를 추가하면 여기에 import + 리스트 추가만 하면 됩니다.
    
    Returns:
        list[BaseAnalyzer]: 사용 가능한 분석기 인스턴스 리스트
    """
    return [
        LandAttributeAnalyzer(),
        ZoningRegionAnalyzer(),
        # ===== 여기에 새 분석기를 추가하세요 =====
        # LandUseAnalyzer(),
        # BuildingInfoAnalyzer(),
        # ZoningDistrictAnalyzer(),
        # ZoningAreaAnalyzer(),
        # UrbanPlanAnalyzer(),
        # NaturalElevationAnalyzer(),
        # NaturalSlopeAnalyzer(),
        # NaturalEcologyAnalyzer(),
        # NaturalEnvironmentAnalyzer(),
    ]
