with open("scratch/wfs_capabilities.xml", "r", encoding="utf-8") as f:
    content = f.read()
    if "um001" in content.lower():
        print("Found um001")
    else:
        print("um001 NOT found in WFS capabilities.")
        
    # 환경 관련 키워드 검색
    import re
    matches = re.findall(r'<Name>(.*?)</Name>', content)
    env_layers = [m for m in matches if "um" in m.lower() or "eco" in m.lower()]
    print("Environmental layers found:", env_layers)
