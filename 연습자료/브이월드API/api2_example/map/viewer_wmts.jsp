<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
<head>
<title>WMS 성능테스트</title>
<script type="text/javascript" src="http://map.vworld.kr/jquery/jquery-1.7.1.min.js"></script>
<script type="text/javascript" src="http://map.vworld.kr/js/map/proj4js.js"></script>
<script type="text/javascript" src="http://map.vworld.kr/js/map/OpenLayers-2.13/OpenLayers.js"></script>

<script>

	$(document).ready(function() {
		//
		Proj4js.defs["EPSG:4019"] = "+proj=longlat +ellps=GRS80 +no_defs";
		Proj4js.defs["EPSG:3857"] = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs";
		Proj4js.defs["EPSG:900913"] = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs";
		
		//UTM-K
		Proj4js.defs["EPSG:5179"] = "+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.9996 +x_0=1000000 +y_0=2000000 +ellps=GRS80 +units=m +no_defs";
		//중부원점(50만)
		Proj4js.defs["EPSG:5181"]="+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=500000 +ellps=GRS80 +units=m +no_defs";
		//서부원점
		Proj4js.defs["EPSG:5185"] = "+proj=tmerc +lat_0=38 +lon_0=125 +k=1 +x_0=200000 +y_0=600000 +ellps=GRS80 +units=m +no_defs";
		//중부원점-o
		Proj4js.defs["EPSG:5186"] = "+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=600000 +ellps=GRS80 +units=m +no_defs";
		//동부원점
		Proj4js.defs["EPSG:5187"] = "+proj=tmerc +lat_0=38 +lon_0=129 +k=1 +x_0=200000 +y_0=600000 +ellps=GRS80 +units=m +no_defs";
		//동해(울릉)원점
		Proj4js.defs["EPSG:5188"] = "+proj=tmerc +lat_0=38 +lon_0=131 +k=1 +x_0=200000 +y_0=600000 +ellps=GRS80 +units=m +no_defs";
		//동해(울릉)원점
		Proj4js.defs["EPSG:4326"] = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs";
		
	});
	
	function transCoord(x, y, scrs, tcrs){
		try {
			var lonlat = new OpenLayers.LonLat(x, y);
			var SCRS = new OpenLayers.Projection(scrs);
			var TCRS = new OpenLayers.Projection(tcrs);
			var point = lonlat.transform(SCRS, TCRS);
			return point;
		}catch(e){}
	}
	function tile2long(x, z) {
		return (x / Math.pow(2, z) * 360 - 180);
	}
	
	function tile2lat(y, z) {
		var n = Math.PI - 2 * Math.PI * y / Math.pow(2, z);
		return (180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n))));
	}

	function getBBox(z, x, y){
		var equator = 20037508.342789244;
		
		var minx = tile2long(x, z);
		var maxy = tile2lat(y, z);
		
		var point = transCoord(minx, maxy, "EPSG:4326", "EPSG:3857");

		minx = point.lon;
		maxy = point.lat;
		
		var maxx = minx + (equator / Math.pow(2, z-1));
		var miny = maxy - (equator / Math.pow(2, z-1));
		
		return minx + "," + miny + "," + maxx + "," + maxy;
	}
	
	function WMSTestRun() {
		/* 
		var url = "http://localhost:8080/req/wms?SERVICE=WMS&REQUEST=GetMap"
			+ "&LAYERS=LT_P_MOCTNODE&STYLES=LT_P_MOCTNODE"
			+ "&FORMAT=image/png&WIDTH=256&HEIGHT=256&VERSION=1.3.0&CRS=EPSG:900913&EXCEPTIONS=text/xml&TRANSPARENT=false"
			+ "&APIKEY=E2FA6086-8B48-3EA8-8F9F-B3D77C9BBF23&DOMAIN=api.vworld.dev"
			+ "&BBOX=";
		 */
		var url = "/req/wmts/1.0.0/E2FA6086-8B48-3EA8-8F9F-B3D77C9BBF23/Base";
		
		$("#wms").empty();

		var sz = 8;
		var ez = 14;
		var srow = 218;
		var erow = 218;
		var scol = 99;
		var ecol = 99;
		var total=0;
		for(z=sz; z<=ez; z++){
			var sx = srow * Math.pow(2, z-sz);
			var ex = erow * Math.pow(2, z-sz) + Math.pow(2, z-sz) - 1;
			var sy = scol * Math.pow(2, z-sz);
			var ey = ecol * Math.pow(2, z-sz) + Math.pow(2, z-sz)-1;

			/* var sx = 52;
			var ex = 56;
			var sy = 23;
			var ey = 26;
			*/
			//console.log(z + "//" + sx + "//" + ex + "//" + sy + "//" + ey);
			for(x=sx; x<=ex; x++){
				for(y=sy; y<=ey; y++){
					total++;
					var bbox = getBBox(z, x, y);

					$.ajax({
				    	type:'GET',
				    	async: false,
				    	url: url + "/" + z + "/" + y  + "/" + x + ".png",
				    	contentType: 'png',
				    	success:function(data) {
				    	}
					});
					
/* 					
		    		var top = (y - sy) * 256;
		    		var left = (x - sx) * 256;
		    		var img = "<img src='"+url + "/" + z + "/" + y  + "/" + x + ".png' width='256px' height='256px' style='position:absolute;top:"+top+"px;left:"+left+"px'/>"
		    		$("#wms").append(img);
					console.log(img);
 */
				}
			}
			//console.log(z + "//" + total);
		}
	}
</script>
</head>
<body>
	<a href="javascript:WMSTestRun()">WMS 테스트시작</a>
	<div id="wms" style="width:calc(100% - 50px); height:calc(100% - 70px); position:absolute; top:50px; border: solid 1px red">
	</div>
</body>
</html>
