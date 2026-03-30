<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
<head>
<title>(예제)지오코더API 2.0(좌표조회)</title>
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
	var url = "http://api.vworld.kr/req/address?"
	var requestStr = url;
	var dataType = $.trim($("#format").val()).toLowerCase();
	var param = "";
	$("#requesturl, #resultbody").empty();
	$(".mandatory input[type=text]").each(function(){
		var val = $.trim($(this).val());
		var id = $(this).attr("id").toLowerCase();
		if (id == 'address') {val = encodeURIComponent(val);}
		if (id != "url" && val != ''){
			param = param + "&"+id + "=" + val;
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
}

</script> 
</head> 
<body>
	<div id="desc" style="padding:0px 0px;">
		<div id="toolbar">	
			<div class="maintitle">(예제) 지오코더 API 2.0 (좌표조회)</div>
			<div class="mandatory">				
			<table class="board-write txt-left">
				<colgroup>
				<col width="200px" >
				<col width="50px" >
				<col />
				</colgroup>
				<tbody>
					<tr><th>요청URL</th><td></td><td><input type="text" id="url" value="/req/address?" readonly /></td></tr>
					<tr><th>서비스ID(service)</th><td>O/1</td><td><input type="text" id="service" value="address" readonly/></td></tr>
					<tr><th>서비스버전(version)</th><td>O/1</td><td><input type="text" id="version" value="2.0" readonly/></td></tr>
					<tr><th>오퍼레이션(request)</th><td>M/1</td><td><input type="text" id="request" value="getcoord" readonly/>
					<tr><th>인증키(key)</th><td>M/1</td><td><input type="text" id="key" value="CEB52025-E065-364C-9DBA-44880E3B02B8" readonly/></td></tr>
					<tr><th>결과포맷(format)</th><td>O/1</td><td><input type="text" id="format" value="xml" readonly/>
						<select id="format_list" onchange="changeValue(this.id, this.value);">
						<option value="xml">xml</option>
						<option value="json">json</option>
						</select>
					</td></tr>
					<tr><th>오류결과포맷(errorFormat)</th><td>O/1</td><td><input type="text" id="errorformat" value="" readonly/>
						<select id="errorformat_list" onchange="changeValue(this.id, this.value);">
						<option value="">선택</option>
						<option value="xml">xml</option>
						<option value="json">json</option>
						</select>
					</td></tr>
					<tr><th>검색대상(type)</th><td>O/1</td><td><input type="text" id="type" value="road" readonly/>
						<select id="type_list" onchange="changeValue(this.id, this.value);">
						<option value="road">도로명</option>
						<option value="parcel">지번주소</option>
						</select>
					</td></tr>
					<tr><th>입력주소(address)</th><td>O/1</td><td><input type="text" id="address" value="효령로72길 60"/>
						<select id="address_list" onchange="changeValue(this.id, this.value);">
						<option value="효령로72길 60">효령로72길 60</option>
						<option value="서초동 1355">서초동 1355</option>
						</select>
					</td></tr>
					<tr><th>정재주소반환여부(refine)</th><td>O/1</td><td><input type="text" id="refine" value="true" readonly/>
						<select id="refine_list" onchange="changeValue(this.id, this.value);">
						<option value="true">true</option>
						<option value="false">false</option>
						</select>
					</td></tr>
					<tr><th>간략결과여부(simple)</th><td>O/1</td><td><input type="text" id="simple" value="false" readonly/>
						<select id="simple_list" onchange="changeValue(this.id, this.value);">
						<option value="true">true</option>
						<option value="false" selected="selected">false</option>
						</select>
					</td></tr>
					<tr><th>좌표계(crs)</th><td>O/1</td><td><input type="text" id="crs" value="epsg:4326" readonly/>
						<select id="crs_list" onchange="changeValue(this.id, this.value);">
						<option value="epsg:4326">WGS84 경위도</option>
						<option value="epsg:4019">GRS80</option>
						<option value="epsg:3857">Google Mercator</option>
						<option value="epsg:5181">중부원점(GRS80, 50만)</option>
						<option value="epsg:5185">서부원점(GRS80)</option>
						<option value="epsg:5186">중부원점(GRS80)</option>
						<option value="epsg:5187">동부원점(GRS80)</option>
						<option value="epsg:5188">동해(울릉)원점(GRS80)</option>
						<option value="epsg:5179">UTM-K(GRS80)</option>
						</select>
					</td></tr>
					
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