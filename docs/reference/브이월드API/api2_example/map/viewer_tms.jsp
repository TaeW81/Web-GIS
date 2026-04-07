<%@ page language="java" contentType="text/html;charset=utf-8" pageEncoding="utf-8"%>
<!DOCTYPE html>
<html>
  <head>
    <title>TMS 뷰어</title>
    <link rel="stylesheet" href="https://openlayers.org/en/v3.19.1/css/ol.css" type="text/css">
    <!-- The line below is only needed for old environments like Internet Explorer and Android 4.x -->
    <script src="https://cdn.polyfill.io/v2/polyfill.min.js?features=requestAnimationFrame,Element.prototype.classList,URL"></script>
    <script src="https://openlayers.org/en/v3.19.1/build/ol.js"></script>
  </head>
  <body>
   <div id="map" style="width: 100%; height: 350px; left: 0px; top: 0px"></div>
    <script>
	  var maxZoom = 20;
      var projection = ol.proj.get('EPSG:900913');
      var projectionExtent = projection.getExtent();
      var size = ol.extent.getWidth(projectionExtent) / 256;
      var resolutions = new Array(maxZoom);
      var matrixIds = new Array(maxZoom);
      for (var z = 0; z < maxZoom; ++z) {
        // generate resolutions and matrixIds arrays for this TMS
        resolutions[z] = size / Math.pow(2, z);
        matrixIds[z] = z;
      }

      var map = new ol.Map({
        layers: [
          new ol.layer.Tile({
            source: new ol.source.OSM()
          }),
           new ol.layer.Tile({
               source: new ol.source.XYZ({
                 tileUrlFunction: function (coordinate) {
                     if (coordinate == null) {
                         return "";
                     }
                     
                     var z = coordinate[0];
                     var x = coordinate[1];
                     var y = Math.pow(2, z) + coordinate[2]; //(1 << z) - coordinate[2] - 1;

                     if (x < 0 || y < 0) { 
                       return "";}

                     var url = '/req/tms/1.0.0/E2FA6086-8B48-3EA8-8F9F-B3D77C9BBF23/Base/' + z + '/' + y + '/' + x + '.png';

                     return url;
                 },
                 projection: projection,
                 tileGrid: new ol.tilegrid.TileGrid({
                   origin: ol.extent.getTopLeft(projectionExtent),
                   resolutions: resolutions,
                   extent : [12523442.714243278,3130860.6785608195,15654303.392804097,5635549.221409474]
                 })
               })
          })
        ],
        target: 'map',
        controls: ol.control.defaults({
          attributionOptions: /** @type {olx.control.AttributionOptions} */ ({
            collapsible: false
          })
        }),
        view: new ol.View({
          center: [14245416.08745173,4383204.9499851465],
          zoom: 6,
          maxZoom : 19
        })
      });
      
    </script>
  </body>
</html>
