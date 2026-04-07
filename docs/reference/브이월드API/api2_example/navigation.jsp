<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
<head>
<title>요청성API 예제 안내</title>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta http-equiv="X-UA-Compatible" content="IE=Edge">
<!--[if lt IE 9]>
	<script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script> 
<![endif]-->
<style type="text/css">
*, body {font-family:돋움, Dotum, 나눔고딕;}
input[type=button]{padding:2px 10px;line-height:24px;height:26px;min-width:100px;}
input[type=text],select{color:red;font-weight:bold;padding:2px 10px;line-height:24px;height:26px;border:solid 1px #e3e3e3;}
input[type=file] {padding:2px 8px;border:solid 1px #e3e3e3;width:300px;}
select {padding-right:0px;min-width:100px;}
#toolbar{line-height:30px;min-height:30px;top:0px;font-weight:bold;}
</style>
</head> 
<body>
	<div id="desc" style="padding:0px 0px;">
		<div id="toolbar">
			1. 윈도우탐색기를 열어 C:\Windows\System32\Drivers\etc 경로의 host 파일을 수정합니다. <br/>
			<div style="margin-left:40px;">
			10.1.2.6    api.vworld.dev<br/>
			</div>
			<br/>
			2. 예제 샘플을 선택하십시오. <br/>			
			<div>
				<ul>
					<li class="btn"><a href="/test/search.jsp" class="adm_btn" title="(예제)검색API 2.0" target="_blank">
					<span>(기타API서비스) 검색API 2.0</span></a></li>
					<li class="btn"><a href="/test/geocoder.jsp" class="adm_btn" title="(예제)지오코더API 2.0(좌표조회)" target="_blank">
					<span>(기타API서비스) 지오코더API 2.0(주소에서 좌표추출)</span></a></li>
					<li class="btn"><a href="/test/geocoder_reverse.jsp" class="adm_btn" title="(예제)지오코더API 2.0(주소조회)" target="_blank">
					<span>(기타API서비스) 지오코더API 2.0(좌표에서 주소추출)</span></a></li>					
					<li class="btn"><a href="/test/staticmap.jsp" class="adm_btn" title="(예제)StaticMap API 2.0" target="_blank">
					<span>(기타API서비스) StaticMap API 2.0</span></a></li>
					<li class="btn"><a href="/test/legend.jsp" class="adm_btn" title="(예제)범례 API 2.0" target="_blank">
					<span>(기타API서비스) 범례 API 2.0</span></a></li>
					<li class="btn"><a href="/test/data.jsp" class="adm_btn" title="(예제)2D DATA API" target="_blank">
					<span>(2D DATA API) 2D DATA API 2.0</span></a></li>
					<!-- <li class="btn"><a href="/test/wfs.jsp" class="adm_btn" title="(예제)WFS API" target="_blank">
					<span>(2D DATA API) WFS API 2.0</span></a></li> -->
					<li class="btn"><a href="/test/map/viewer_tms.jsp" class="adm_btn" title="(예제)TMS뷰어" target="_blank">
					<span>(2D DATA API) TMS뷰어</span></a></li>
				</ul>
			</div>
		</div>
	</div>
</body>
</html>