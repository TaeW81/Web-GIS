<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
<head>
<title>(예제) WFS API 2.0</title>
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
function execute(newWin){
	// api.vworld.kr도메인 외 다른 도메인에 사용시 proxy를 사용해야 합니다.
	var hosturl = location.protocol+'//'+location.hostname+(location.port ? ':'+location.port: '');
	var url = hosturl + $("#url").val();
	var requestStr = url;
	var dataType = $.trim($("#format").val()).toLowerCase();
	var param = "";
	$("#requesturl, #resultbody").empty();
	$(".mandatory input[type=text]").each(function(){
		var val = $.trim($(this).val());
		var id = $(this).attr("id").toLowerCase();
		if (id == 'sortby') {val = encodeURIComponent(val);}
		if (id != "url" && val != ''){
			param = param + "&"+id + "=" + val;
		}
	});
	
	requestStr += param.substring(1);
	$("#requesturl").text(requestStr);
	if(newWin == 1){
		window.open("about:blank").location.href = requestStr;
	}else{
		$.ajax({
	    	type:'GET',
	    	dataType : dataType,
	    	url: requestStr,
	    	success:function(data, status, response) {
	    		var contentType = response.getResponseHeader("Content-Type");

	    		if(contentType.indexOf("json") != -1){
	    			$("#resultbody").text(JSON.stringify(data));
	    			$("#resultbody").show();
	    		}else{
	    			var result = (new XMLSerializer()).serializeToString(data);
	    			$("#resultbody").text(result);
	    			$("#resultbody").show();
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
			<div class="maintitle">(예제)WFS API 2.0</div>
			<div class="mandatory">				
			<table class="board-write txt-left">
				<colgroup>
				<col width="200px" >
				<col width="50px" >
				<col />
				</colgroup>
				<tbody>
					<tr><th>요청URL</th><td></td><td><input type="text" id="url" value="/req/wfs?" readonly /></td></tr>
					<tr><th>서비스ID(service)</th><td>O/1</td><td><input type="text" id="service" value="WFS" readonly/></td></tr>
					<tr><th>서비스버전(version)</th><td>O/1</td><td><input type="text" id="version" value="1.1.0" readonly/></td></tr>
					<tr><th>오퍼레이션(request)</th><td>M/1</td><td><input type="text" id="request" value="GetFeature" readonly/>
							<select id="request_list" onchange="changeValue(this.id, this.value);">
							<option value="GetFeature">GetFeature</option>
							<option value="GetCapabilities">GetCapabilities</option>
							</select>
						</td>
					</tr>
					<tr><th>인증키(key)</th><td>M/1</td><td><input type="text" id="key" value="483E0418-2F46-3223-80A1-F66D16A24685" readonly/></td></tr>
					<tr><th>결과포맷(output)</th><td>O/1</td><td><input type="text" id="output" value="text/xml;subType=gml/3.1.1/profiles/gmlsf/1.0.0/0" readonly/>
						<select id="output_list" onchange="changeValue(this.id, this.value);">
						<option value="text/xml;subType=gml/3.1.1/profiles/gmlsf/1.0.0/0">text/xml</option>
						</select>
					</td></tr>
					<tr><th>오류결과포맷(exceptions)</th><td>O/1</td><td><input type="text" id="exceptions" value="" readonly/>
						<select id="exceptions_list" onchange="changeValue(this.id, this.value);">
						<option value="">선택</option>
						<option value="xml">xml</option>
						<option value="json">json</option>
						</select>
					</td></tr>
					<tr><th>검색대상(typename)</th><td>M/1</td><td><input type="text" id="typename" value="LT_C_UQ111"/>예)LT_C_UQ111, LT_C_UQ113	</td></tr>
					<tr><th>요청 FEATURE ID(featureid)</th><td>O/1</td><td><input type="text" id="featureid" value="" /></td></tr>
					<tr><th>BBOX(bbox)</th><td>M/1</td><td><input type="text" id="bbox" value="13987670,3912271,14359383,4642932" /></td></tr>
					<tr><th>속성(propertyname)</th><td>O/1</td><td><input type="text" id="propertyname" value="MNUM,SIDO_CD,SIGUNGU_CD,DYEAR,DNUM,UCODE,BON_BUN,BU_BUN,UNAME,SIDO_NAME,SIGG_NAME,AG_GEOM" /></td></tr>
					<tr><th>최대개수(maxfeatures)</th><td>O/1</td><td><input type="text" id="maxfeatures" value="20" /></td></tr>
					<tr><th>정렬(sortby)</th><td>O/1</td><td><input type="text" id="sortby" value="DYEAR D" /></td></tr>
					<tr><th>좌표계(srsname)</th><td>O/1</td><td><input type="text" id="srsname" value="EPSG:3857" readonly/>
						<select id="crs_list" onchange="changeValue(this.id, this.value);">
						<option value="EPSG:3857">Google Mercator</option>
						<option value="EPSG:4326">WGS84 경위도</option>
						<option value="EPSG:4019">GRS80</option>
						<option value="EPSG:5181">중부원점(GRS80, 50만)</option>
						<option value="EPSG:5185">서부원점(GRS80)</option>
						<option value="EPSG:5186">중부원점(GRS80)</option>
						<option value="EPSG:5187">동부원점(GRS80)</option>
						<option value="EPSG:5188">동해(울릉)원점(GRS80)</option>
						<option value="EPSG:5179">UTM-K(GRS80)</option>
						</select>
					</td></tr>
				</tbody>
			</table>
			<div style="margin-bottom:5px;">
				요청구문은 다음과 같습니다 :
				<div id="requesturl" style="">
				</div>
			</div>
			<input type="button" value="테스트요청" onclick="javascript:execute(0);" />
			<input type="button" value="테스트요청(새창)" onclick="javascript:execute(1);" />
				
		</div>
		<div class="resultbox">
			<div>
				요청결과는 다음과 같습니다 :
				<div id="resultbody"></div>
			</div>
		</div>
		</div>
	</div>
</body>
</html>