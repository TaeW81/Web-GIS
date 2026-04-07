<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
<head>
<title>(예제) TMS API 2.0</title>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=Edge">
<!-- API key를 포함하여 브이월드 API URL을 지정하여 호출 시작  -->
<script type="text/javascript" src="http://map.vworld.kr/jquery/jquery-1.7.1.min.js"></script>
<!--[if lt IE 9]>
	<script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script> 
<![endif]-->
<style type="text/css">
*, body {font-family:NanumGothic, 돋움, Dotum, 나눔고딕;font-weight:normal;font-size:13px;}
input[type=button]{padding:2px 10px;line-height:24px;height:26px;min-width:100px; cursor:pointer;}
input[type=text],select{color:red;font-weight:bold;padding:2px 10px;line-height:22px;height:24px;border:solid 1px #e3e3e3;min-width:400px;}
textarea {color:blue;font-weight:bold;padding:2px 10px;line-height:22px;height:24px;border:solid 1px #e3e3e3;width:95%;height:150px;}
#requesturl, #resultbody {color:black;font-weight:normal; border: solid 1px #e3e3e3; width:95%; height:70px; overflow-x:hidden; overflow-y:auto; word-break:break-all; }
#resultbody { height: 150px;}
input:read-only {color:blue;}
input[readonly] {color:blue;}
input[type=file] {padding:2px 8px;/*line-height:24px;height:24px;*/border:solid 1px #e3e3e3;width:300px;}
select {padding-right:0px;min-width:100px;color:black;}
#toolbar{line-height:30px;min-height:30px;top:0px;font-weight:bold;}
div.mandatory label {min-width:200px; margin-right:10px;}
div.maintitle {width:95%;height:50px;font-size:18px;line-height:50px;background-color:#004080;color:white;font-weight:bold;padding-left:20px;}
</style>
<script type="text/javascript">
$(document).ready(function() {
	$("#result_img, #resultbody").hide();
});
function execute(newWin){
	// api.vworld.kr도메인 외 다른 도메인에 사용시 proxy를 사용해야 합니다.
	var hosturl = location.protocol+'//'+location.hostname+(location.port ? ':'+location.port: '');
	var _url = hosturl + $("#url").val();

	$("#requestbody, #resultbody").empty();
	$("#result_img, #resultbody").hide();
	$("#result_img").attr("src","");
	
	var requestStr = _url;
	var version = $("#version").val();
	var key = $("#key").val();
	var map = $("#tileMap").val();
	var z = $("#tileMatrix").val();
	var y = $("#tileRow").val();
	var x = $("#tileCol").val();
		
	var dataType = (map == "Satellite"?"jpeg":"png");
	
	requestStr += "/" + version + "/" + key + "/" + map + "/" + z + "/" + y + "/" + x + "." + dataType;
	
	$("#requesturl").text(requestStr);
	$("#requesturl").text(requestStr);
	if(newWin == 1){
		window.open("about:blank").location.href = requestStr;
	}else{
		$.ajax({
	    	type:'GET',
	    	url: requestStr,
	    	contentType: dataType,
	    	success:function(data, status, response) {
	    		var contentType = response.getResponseHeader("Content-Type");
		
				if(contentType.indexOf("json") != -1){
	    			$("#resultbody").text(JSON.stringify(data));
	    			$("#resultbody").show();
				}else if(contentType.indexOf("xml") != -1){
	    			var result = (new XMLSerializer()).serializeToString(data);
	    			$("#resultbody").text(result);
	    			$("#resultbody").show();
				}else {
	    			$("#result_img").attr('src',requestStr );
	    			$("#result_img").show();
				}
	    	}
		});
	}
}

function changeFormat(formatval){
	$("#format").val(formatval);
}

function changeValue(id, value){
	var targetid = id.split("_")[0];	
	$("#" + targetid).val(value);
}

</script> 
</head> 
<body>
	<div id="desc" style="padding:0px 0px;">
		<div id="toolbar">	
			<div class="maintitle">(예제)TMS API 2.0</div>
			<div class="mandatory">				
			<table class="board-write txt-left">
				<colgroup>
				<col width="200px" >
				<col width="50px" >
				<col />
				</colgroup>
				<tbody>
					<tr><th>요청URL</th><td></td><td><input type="text" id="url" value="/req/tms" readonly /></td></tr>
					<tr><th>서비스버전(version)</th><td>M/1</td><td><input type="text" id="version" value="1.0.0" readonly/></td></tr>
					<tr><th>인증키(key)</th><td>M/1</td><td><input type="text" id="key" value="483E0418-2F46-3223-80A1-F66D16A24685" readonly/></td></tr>
					<tr><th>tileMap</th><td>M/1</td><td><input type="text" id="tileMap" value="Base" readonly/>
						<select id="tileMap_list" onchange="changeValue(this.id, this.value);">
						<option value="Base">배경지도</option>
						<option value="gray">그레이</option>
						<option value="midnight">미드나잇</option>
						<option value="Hybrid">하이브리드</option>
						<option value="Satellite">영상</option>
						</select>
					</td></tr>
					<tr><th>tileMatrix</th><td>M/1</td><td><input type="text" id="tileMatrix" value="8" /></td></tr>
					<tr><th>tileRow</th><td>M/1</td><td><input type="text" id="tileRow" value="218" /></td></tr>
					<tr><th>tileCol</th><td>M/1</td><td><input type="text" id="tileCol" value="156" /></td></tr>
				</tbody>
			</table>
			<div style="margin-bottom:5px;">
				요청구문은 다음과 같습니다 :
				<div id="requesturl">
				</div>
			</div>
			<input type="button" value="테스트요청" onclick="javascript:execute(0);" />
			<input type="button" value="테스트요청(새창)" onclick="javascript:execute(1);" />
				
		</div>
		<div class="resultbox">
			요청결과는 다음과 같습니다 :
			<div id="resultboxcon">
				<img id="result_img" src="" alt="결과이미지"/>
				<div id="resultbody"></div>
			</div>
		</div>
		</div>
	</div>
</body>
</html>