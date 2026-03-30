"""
분석기(Analyzer) 추상 클래스

역할:
  - 모든 분석 모듈이 따라야 할 공통 인터페이스를 정의합니다.
  - 새 분석 항목을 추가하려면 이 클래스를 상속받아 구현하면 됩니다.

사용 예시:
  class MyAnalyzer(BaseAnalyzer):
      name = "내 분석기"
      description = "설명"
      
      def analyze(self, pnu_list, api_key):
          # PNU별로 API 호출하여 결과 반환
          return [{"PNU": ..., "결과": ...}, ...]
      
      def get_columns(self):
          return ["PNU", "결과"]
"""


class BaseAnalyzer:
    """분석기 추상 클래스. 모든 분석 모듈은 이 클래스를 상속받습니다."""
    
    # 하위 클래스에서 반드시 오버라이드해야 할 속성
    name = "기본 분석기"           # Streamlit 사이드바에 표시될 이름
    description = "분석기 설명"    # 툴팁이나 설명 텍스트

    def analyze(self, pnu_list, api_key):
        """
        PNU 리스트를 받아 분석을 수행하고 결과를 반환합니다.
        
        Args:
            pnu_list (list[dict]): [{"PNU": str, "주소": str, "지번": str}, ...]
            api_key (str): 브이월드 API 인증키
        
        Returns:
            list[dict]: 분석 결과 딕셔너리 리스트
                        (각 dict는 엑셀의 한 행이 됩니다)
        """
        raise NotImplementedError("analyze() 메서드를 구현해야 합니다.")

    def get_columns(self):
        """
        분석 결과의 엑셀 컬럼명 리스트를 반환합니다.
        
        Returns:
            list[str]: 컬럼명 리스트
        """
        raise NotImplementedError("get_columns() 메서드를 구현해야 합니다.")
