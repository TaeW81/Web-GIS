<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
<head>
<title>(예제)범례 API 2.0</title>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta http-equiv="X-UA-Compatible" content="IE=Edge">
<!-- API key를 포함하여 브이월드 API URL을 지정하여 호출 시작  -->
<script type="text/javascript" src="http://map.vworld.kr/jquery/jquery-1.7.1.min.js"></script>
<!--[if lt IE 9]>
	<script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script> 
<![endif]-->
<style type="text/css">
*, body {font-family:NanumGothic, 돋움, Dotum, 나눔고딕;font-weight:normal;font-size:13px;}
input[type=button]{padding:2px 10px;line-height:24px;height:26px;min-width:100px; cursor:pointer;}
input[type=text],select{color:red;font-weight:bold;padding:2px 10px;line-height:22px;height:24px;border:solid 1px #e3e3e3;min-width:189px;}
textarea {color:blue;font-weight:bold;padding:2px 10px;line-height:22px;height:24px;border:solid 1px #e3e3e3;width:95%;height:150px;}
#requesturl, #resultbody {color:black;font-weight:normal; border: solid 1px #e3e3e3; width:95%; height:70px; overflow-x:hidden; overflow-y:auto; word-break:break-all; }
#resultbody { height: 150px;}
input:read-only {color:blue;}
input[readonly] {color:blue;}
input[type=file] {padding:2px 8px;/*line-height:24px;height:24px;*/border:solid 1px #e3e3e3;width:300px;}
select {padding-right:0px;min-width:100px;color:black;}
#toolbar{line-height:30px;min-height:30px;top:0px;font-weight:bold;}
div.mandatory label {min-width:200px; margin-right:10px;}
div.temporary input[type=text] {color:black;}
div.temporary b {font-weight:bold;color:blue;}
div.maintitle {width:95%;height:50px;font-size:18px;line-height:50px;background-color:#6F1140;color:white;font-weight:bold;padding-left:20px;}
#resultbox img {min-width:350px;min-height:150px;}
.max input[type=text]{min-width:400px;}
</style>
<script type="text/javascript">
$(document).ready(function() {
	$("#result_img, #resultbody").hide();
});
function execute(){
	// api.vworld.kr도메인 외 다른 도메인에 사용시 proxy를 사용해야 합니다.
	var hosturl = location.protocol+'//'+location.hostname+(location.port ? ':'+location.port: '');
	var url = hosturl + $("#url").val();
	var requestStr = url;
	var dataType = $.trim($("#format").val()).toLowerCase();
	var requestType = $.trim($("#request").val()).toLowerCase();
	var param = "";
	
	$("#requestbody, #resultbody").empty();
	$("#result_img, #resultbody").hide();
	$("#result_img").removeAttr('src');
	$(".mandatory input[type=text]").each(function(){
		var val = $.trim($(this).val());
		var id = $(this).attr("id").toLowerCase();
		if (id != "url" && val != ''){
			if (requestType == 'getLegendStyle' && (id == 'format')) {
			} else {
				param = param + "&"+id + "=" + val;
			}
		}
	});

	requestStr += param.substring(1);
	
	$("#requesturl").text(requestStr);

	window.open("about:blank","responsewindow").location.href = requestStr;
}

function changeFormat(formatval){
	$("#format").val(formatval);
}

function changeValue(id, value){
	var targetid = id.split("_")[0];	
	$("#" + targetid).val(value);
	
	if(value == "GetLegendStyle"){
		$("#p_format").hide();
	}else if(value == "GetLegendGraphic"){
		$("#p_format").show();
	}
}

</script> 
</head> 
<body>
	<div id="desc" style="padding:0px 0px;">
		<div id="toolbar">
			<div class="maintitle">(예제) 범례 API 2.0</div>
			<div class="mandatory">				
			<table class="board-write txt-left">
				<colgroup>
				<col width="200px" />
				<col />
				</colgroup>
				<tbody>
				<tr><th>요청URL</th><td><input type="text" id="url" value="/req/image?" readonly /></td></tr>
				<tr class="max"><th>인증키(key)</th><td><input type="text" id="key" value="483E0418-2F46-3223-80A1-F66D16A24685" readonly/></td></tr>
				<tr><th>서비스종류(service)</th><td><input type="text" id="service" value="image" readonly /></td></tr>
				<tr><th>요청종류(request)</th><td><input type="text" id="request" value="GetLegendGraphic" readonly/>
					<select id="request_list" onchange="changeValue(this.id, this.value);">
					<option value="GetLegendGraphic">범례이미지</option>
					<option value="GetLegendStyle">SLD</option>
					</select>
				</td></tr>
				<tr id="p_format"><th>결과포맷(format)</th><td><input type="text" id="format" value="png" readonly/>
					<select id="format_list" onchange="changeValue(this.id, this.value);">
					<option value="png">png</option>
					<option value="jpeg">jpeg</option>
					<option value="bmp">bmp</option>
					</select>
				</td></tr>
				<tr><th>오류결과포맷(errorFormat)</th><td><input type="text" id="errorformat" value="" readonly/>
					<select id="errorformat_list" onchange="changeValue(this.id, this.value);">
					<option value="">선택</option>
					<option value="xml">xml</option>
					<option value="json">json</option>
					<option value="image">요청이미지포맷</option>
					<option value="blank">빈이미지</option>
					</select>
				</td></tr>
				<tr><th>요청지도(layer, 1개허용)</th><td><input type="text" id="layer" value="LT_C_UQ111" /> 예)LT_C_UQ111, LT_C_UQ113</td></tr>
				<tr><th>하위범례(style)</th><td><input type="text" id="style" value="LT_C_UQ111" /> 예)LT_C_UQ111, LT_C_UQ113</td></tr>
				<tr><th>범례타입(type)</th><td><input type="text" id="type" value="ALL" readonly/> 
					<select id="type_list" onchange="changeValue(this.id, this.value);">
					<option value="ALL">전체</option>
					<option value="LAYER">레이어 범례 부분만</option>
					<option value="SUB">하위 범례 부분만</option>
					</select>
				</tbody>
			</table>
			<div style="margin-bottom:5px;">
				요청구문은 다음과 같습니다 :
				<div id="requesturl">
				</div>
			</div>
			<input type="button" value="테스트요청" onclick="javascript:execute();" />
				
		</div>
		</div>
	</div>
</body>
</html>