import folium
from jinja2 import Template
from folium.elements import MacroElement
from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_LAYERS, VWORLD_WMS_URL, VWORLD_WMS_CATEGORIES, VWORLD_WFS_LAYERS


class VWorldLayerControl(MacroElement):
    """
    브이월드 스타일의 커스텀 레이어 컨트롤 오버레이 (동적 로딩 방식)
    """
    def __init__(self, categories, vworld_key, wms_url, wfs_layers=None, **kwargs):
        super(VWorldLayerControl, self).__init__()
        self._name = 'VWorldLayerControl'
        self.categories = categories
        self.vworld_key = vworld_key
        self.wms_url = wms_url
        self.wfs_layer_names = list((wfs_layers or {}).keys())
        
        # JS에서 사용할 레이어 코드 맵 생성
        self.layer_codes = {}
        for cat, layers in categories.items():
            self.layer_codes.update(layers)
            
        self._template = Template(u"""
            {% macro script(this, kwargs) %}
            (function() {
                var map = {{this._parent.get_name()}};
                
                // 1. 레이어 정보 및 저장소
                var layerCodes = {{ this.layer_codes | tojson }};
                var layerStorage = {};
                var vworldKey = "{{ this.vworld_key }}";
                var wmsUrl = "{{ this.wms_url }}";
                var wfsLayerNames = {{ this.wfs_layer_names | tojson }};

                // 레이어 생성/취득 헬퍼
                function getOrCreateLayer(name) {
                    if (layerStorage[name]) return layerStorage[name];
                    
                    var code = layerCodes[name];
                    if (!code) return null;

                    var layer = L.tileLayer.wms(wmsUrl + "?key=" + vworldKey + "&domain=http://localhost", {
                        layers: code.toLowerCase(),
                        styles: code.toLowerCase(),
                        format: 'image/png',
                        transparent: true,
                        version: '1.3.0',
                        name: name,
                        overlay: true
                    });
                    layerStorage[name] = layer;
                    return layer;
                }

                // 초기 활성 레이어 (지적도)
                var jijeck = getOrCreateLayer("지적도");
                if (jijeck) map.addLayer(jijeck);

                // 2. UI 생성
                var controlDiv = L.DomUtil.create('div', 'vworld-layer-control');
                controlDiv.innerHTML = `
                    <div class="v-header">
                        <div class="v-tabs">
                            <div class="v-tab active" data-tab="general">일반레이어</div>
                            <div class="v-tab" data-tab="user">사용자레이어</div>
                        </div>
                        <button class="v-close-btn">&times;</button>
                    </div>
                    <div class="v-search-box">
                        <input type="text" id="v-layer-search" placeholder="검색어를 입력하세요.">
                    </div>
                    <div class="v-body" id="v-layer-body">
                        <div id="v-list-general" class="v-tab-content active">
                            {% for cat, layers in this.categories.items() %}
                            <div class="v-category" data-cat="{{ cat }}">
                                <div class="v-cat-header">
                                    <span class="v-folder-icon">📁</span>
                                    <span class="v-cat-title">{{ cat }}</span>
                                    <span class="v-arrow">▼</span>
                                </div>
                                <div class="v-cat-items">
                                    {% for layer_name in layers.keys() %}
                                    <div class="v-layer-item" data-name="{{ layer_name }}">
                                        <div class="v-layer-info">
                                            <input type="checkbox" id="chk-g-{{ layer_name }}" class="v-chk" 
                                                {{ 'checked' if layer_name == '지적도' else '' }}>
                                            <label for="chk-g-{{ layer_name }}">{{ layer_name }}</label>
                                        </div>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                        <div id="v-list-user" class="v-tab-content">
                            <!-- 여기에 동적으로 추가됨 -->
                        </div>
                    </div>
                    <div class="v-footer">
                        <button id="v-clear-all">전체 선택 해제</button>
                    </div>
                `;

                // 사용자 레이어 리스트 갱신 함수
                function updateUserLayerList() {
                    var userList = controlDiv.querySelector('#v-list-user');
                    userList.innerHTML = '';
                    
                    // 1. 구역계 (특수 항목)
                    var boundaryLayer = null;
                    map.eachLayer(function(l) { if(l.options && l.options.name === "구역계") boundaryLayer = l; });
                    
                    if (boundaryLayer) {
                        addLayerToUserUI(userList, "구역계", true, "📦");
                    }

                    // 2. 활성화된 WMS 레이어들
                    Object.keys(layerStorage).forEach(name => {
                        if (map.hasLayer(layerStorage[name])) {
                            var icon = name.includes('도') ? '🗺️' : '📄';
                            if (name === "지적도") icon = "🗺️";
                            addLayerToUserUI(userList, name, true, icon);
                        }
                    });
                }

                function addLayerToUserUI(container, name, checked, icon) {
                    var item = L.DomUtil.create('div', 'v-layer-item user-item', container);
                    item.dataset.name = name;
                    var isDownloadable = wfsLayerNames.indexOf(name) !== -1;
                    var dlIcon = isDownloadable ? '<span class="v-dl-badge" title="다운로드 가능">📥</span>' : '';
                    item.innerHTML = `
                        <div class="v-layer-info">
                            <input type="checkbox" id="chk-u-${name}" class="v-chk-u" ${checked ? 'checked' : ''}>
                            <span class="v-item-icon">${icon}</span>
                            <label for="chk-u-${name}">${name}</label>
                            ${dlIcon}
                        </div>
                        <div class="v-more-btn" title="${isDownloadable ? 'SHP/DXF 다운로드' : '설정'}">${isDownloadable ? '📥' : '⋮'}</div>
                    `;
                    
                    // 사용자 탭 체크박스 이벤트
                    item.querySelector('.v-chk-u').addEventListener('change', function() {
                        if (name === "구역계") {
                            map.eachLayer(function(l) { 
                                if(l.options && l.options.name === "구역계") {
                                    if(checked) map.removeLayer(l); else map.addLayer(l);
                                }
                            });
                        } else {
                            var gp_chk = controlDiv.querySelector(`#chk-g-${name}`);
                            if(gp_chk) {
                                gp_chk.checked = this.checked;
                                gp_chk.dispatchEvent(new Event('change'));
                            }
                        }
                    });

                    // 메뉴(다운로드) 버튼 이벤트 — WFS 지원 레이어 범용 처리
                    item.querySelector('.v-more-btn').addEventListener('click', function(e) {
                        e.stopPropagation();
                        if (isDownloadable) {
                            triggerLayerDownload(name);
                        } else if (name === "구역계") {
                            triggerLayerDownload("__boundary__");
                        } else {
                            alert(name + " 레이어는 WFS 다운로드를 지원하지 않습니다.");
                        }
                    });
                }

                // 범용 다운로드 트리거 함수
                function triggerLayerDownload(layerName) {
                    var bounds = map.getBounds();
                    var bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].join(',');
                    var parentDoc = window.parent.document;
                    var stInputs = parentDoc.querySelectorAll('input');
                    var target = null;
                    for(var i=0; i<stInputs.length; i++) {
                        if(stInputs[i].placeholder === "download_layer_bbox") {
                            target = stInputs[i]; break;
                        }
                    }
                    if(target) {
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        var ts = new Date().getTime();
                        nativeInputValueSetter.call(target, layerName + "|" + bbox + "|" + ts);
                        target.dispatchEvent(new Event('input', { bubbles: true }));
                        
                        setTimeout(function() {
                            var btns = parentDoc.querySelectorAll('button');
                            var targetBtn = null;
                            for(var j=0; j<btns.length; j++) {
                                if(btns[j].innerText.includes('__dl_trigger__')) {
                                    targetBtn = btns[j]; break;
                                }
                            }
                            if(targetBtn) {
                                targetBtn.click();
                                alert('📥 "' + layerName + '" 다운로드 요청이 접수되었습니다.\n잠시 후 지도 위에 다운로드 버튼이 나타납니다.');
                            } else {
                                alert("다운로드 트리거 버튼을 찾을 수 없습니다.");
                            }
                        }, 150);
                    } else {
                        alert("다운로드 브리지 컴포넌트를 찾을 수 없습니다.");
                    }
                }

                // 3. 스타일 추가
                var style = L.DomUtil.create('style');
                style.innerHTML = `
                    .vworld-layer-control {
                        position: absolute; top: 10px; left: 10px; z-index: 1000;
                        background: rgba(255, 255, 255, 0.98);
                        width: 300px; max-height: 85vh;
                        border-radius: 4px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                        display: flex; flex-direction: column; overflow: hidden;
                        font-family: 'Malgun Gothic', sans-serif;
                    }
                    .v-header { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; background: #fff; }
                    .v-tabs { display: flex; flex: 1; }
                    .v-tab { padding: 12px 0; flex: 1; text-align: center; cursor: pointer; font-size: 14px; color: #666; font-weight: 500; border-bottom: 2px solid transparent; }
                    .v-tab.active { color: #007bff; border-bottom-color: #007bff; font-weight: bold; }
                    .v-close-btn { border: none; background: none; font-size: 20px; padding: 0 15px; cursor: pointer; color: #999; }
                    .v-search-box { padding: 10px; background: #fff; }
                    .v-search-box input { width: 100%; border: 1px solid #eee; padding: 8px 12px; border-radius: 4px; background: #f9f9f9; }
                    .v-body { overflow-y: auto; flex: 1; padding: 5px 0; }
                    .v-tab-content { display: none; }
                    .v-tab-content.active { display: block; }
                    .v-cat-header { padding: 8px 15px; cursor: pointer; display: flex; align-items: center; gap: 8px; }
                    .v-cat-title { flex: 1; font-size: 13px; color: #333; font-weight: 600; }
                    .v-arrow { font-size: 10px; color: #ccc; transition: 0.3s; }
                    .v-category.collapsed .v-arrow { transform: rotate(-90deg); }
                    .v-category.collapsed .v-cat-items { display: none; }
                    .v-layer-item { padding: 6px 15px 6px 35px; display: flex; align-items: center; justify-content: space-between; }
                    .v-layer-item:hover { background: #f0f7ff; }
                    .v-layer-info { display: flex; align-items: center; gap: 8px; flex: 1; }
                    .v-layer-info label { font-size: 13px; color: #555; cursor: pointer; }
                    .v-item-icon { font-size: 14px; }
                    .v-more-btn { padding: 2px 8px; cursor: pointer; color: #999; font-weight: bold; font-size: 16px; border-radius: 4px; transition: 0.2s; user-select: none; }
                    .v-more-btn:hover { background: #e9ecef; color: #333; }
                    .v-dl-badge { font-size: 11px; margin-left: 4px; opacity: 0.7; }
                    .user-item { padding-left: 15px; border-bottom: 1px solid #f9f9f9; }
                    .v-footer { padding: 10px; border-top: 1px solid #eee; }
                    #v-clear-all { width: 100%; padding: 8px; border: 1px solid #ddd; background: #fff; cursor: pointer; font-size: 12px; color: #666; }
                    .v-body::-webkit-scrollbar { width: 5px; }
                    .v-body::-webkit-scrollbar-thumb { background: #ddd; border-radius: 10px; }
                `;
                document.head.appendChild(style);

                // 4. 이벤트 바인딩
                L.DomEvent.disableClickPropagation(controlDiv);
                L.DomEvent.disableScrollPropagation(controlDiv);

                controlDiv.querySelectorAll('.v-tab').forEach(tab => {
                    tab.addEventListener('click', function() {
                        controlDiv.querySelectorAll('.v-tab').forEach(t => t.classList.remove('active'));
                        controlDiv.querySelectorAll('.v-tab-content').forEach(c => c.classList.remove('active'));
                        this.classList.add('active');
                        controlDiv.querySelector('#v-list-' + this.dataset.tab).classList.add('active');
                        if(this.dataset.tab === 'user') updateUserLayerList();
                    });
                });

                controlDiv.querySelectorAll('.v-cat-header').forEach(header => {
                    header.addEventListener('click', function() {
                        this.parentElement.classList.toggle('collapsed');
                    });
                });

                function bindGeneralCheckboxes() {
                    controlDiv.querySelectorAll('.v-chk').forEach(chk => {
                        chk.addEventListener('change', function() {
                            var layerName = this.parentElement.parentElement.dataset.name;
                            var layer = getOrCreateLayer(layerName);
                            if (layer) {
                                if (this.checked) map.addLayer(layer);
                                else map.removeLayer(layer);
                            }
                        });
                    });
                }
                bindGeneralCheckboxes();

                var searchInput = controlDiv.querySelector('#v-layer-search');
                searchInput.addEventListener('input', function() {
                    var term = this.value.toLowerCase();
                    controlDiv.querySelectorAll('.v-layer-item').forEach(item => {
                        var name = item.dataset.name.toLowerCase();
                        item.style.display = name.includes(term) ? 'flex' : 'none';
                    });
                    if (term) {
                        controlDiv.querySelectorAll('.v-category').forEach(cat => {
                            cat.classList.remove('collapsed');
                            var items = cat.querySelectorAll('.v-layer-item');
                            var hasMatch = Array.from(items).some(i => i.style.display === 'flex');
                            cat.style.display = hasMatch ? 'block' : 'none';
                        });
                    } else {
                        controlDiv.querySelectorAll('.v-category').forEach(cat => cat.style.display = 'block');
                    }
                });

                controlDiv.querySelector('#v-clear-all').addEventListener('click', function() {
                    controlDiv.querySelectorAll('.v-chk').forEach(chk => { if (chk.checked) { chk.checked = false; chk.dispatchEvent(new Event('change')); } });
                });

                controlDiv.querySelector('.v-close-btn').addEventListener('click', function() { controlDiv.style.display = 'none'; });

                map.addControl(new (L.Control.extend({ onAdd: function() { return controlDiv; } }))({ position: 'topleft' }));
                
                // 초기 사용자 리스트 로드
                updateUserLayerList();

            })();
            {% endmacro %}
        """)


def create_map(center, gps_points, base_map="일반지도", wms_layers=None, zoom_start=16):
    """
    VWorld 배경지도 위에 구역계를 표시하는 Folium 지도를 생성합니다.
    
    Args:
        center (tuple): 지도 중심점 (lat, lon)
        gps_points (list): 구역계 좌표 리스트 [(lat, lon), ...]
        base_map (str): 배경지도 종류 ("일반지도", "위성영상", "하이브리드")
        wms_layers (list[str] or dict):
            - list: 활성화할 WMS 레이어 목록 (예: ["지적도", "도시지역"]) (하위 호환)
            - dict: {카테고리: [선택된 레이어명, ...]} 형식 (새 구조)
        zoom_start (int): 초기 줌 레벨 (기본값 16)
    
    Returns:
        folium.Map: 완성된 지도 객체
    """
    # 1. VWorld 배경지도로 지도 생성
    tile_url = VWORLD_TILE_URLS.get(base_map, VWORLD_TILE_URLS["일반지도"])
    
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles=tile_url,
        attr="브이월드",
    )
    
    # 2. 구역계 폴리곤 그리기 (빨간 선)
    if gps_points:
        folium.Polygon(
            locations=gps_points,
            color="red",
            weight=3,
            fill=True,
            fill_color="red",
            fill_opacity=0.15,
            popup="구역계",
            name="구역계"
        ).add_to(m)
    
    # 3. 커스텀 브이월드 레이어 컨트롤 추가 (여기서 지적도 등은 JS로 자동 추가)
    VWorldLayerControl(VWORLD_WMS_CATEGORIES, VWORLD_KEY, VWORLD_WMS_URL, wfs_layers=VWORLD_WFS_LAYERS).add_to(m)
    
    return m
