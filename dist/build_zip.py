# -*- coding: utf-8 -*-
"""KH_LandHub_demo 폴더를 배포용 ZIP으로 압축. 실행: python dist/build_zip.py"""
import os, zipfile

DIST = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(DIST, "KH_LandHub_demo")
OUT = os.path.join(DIST, "KH_LandHub_demo.zip")

if not os.path.isdir(STAGE):
    raise SystemExit("먼저 build_portable.py 로 번들을 생성하세요.")

if os.path.exists(OUT):
    os.remove(OUT)

n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for dp, _, fs in os.walk(STAGE):
        for f in fs:
            full = os.path.join(dp, f)
            arc = os.path.join("KH_LandHub_demo", os.path.relpath(full, STAGE))
            z.write(full, arc)
            n += 1

size = os.path.getsize(OUT) / 1024 / 1024
print(f"ZIP 생성 완료: {OUT}")
print(f"  파일 {n:,}개,  {size:,.0f} MB")
