// マツ・ナラNDVI監視システム - メインスクリプト
let map;
let ndviLayer;
let citizenReportsLayer;
let locationMap = null;
let reportMarker = null;
let locationMarker = null;
let showingReports = false;

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    loadNDVIData();
    initializeCitizenReports();
    console.log('マツ・ナラNDVI監視システム初期化完了');
});

// 地図の初期化
function initializeMap() {
    const tokyoCenter = [35.6762, 139.6503]; // 杉並区中心
    map = L.map('map').setView(tokyoCenter, 12);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    
    map.zoomControl.setPosition('topleft');
    console.log('地図の初期化が完了しました');
}

// マツ・ナラNDVIデータの読み込み
async function loadNDVIData() {
    try {
        console.log('マツ・ナラNDVIデータを読み込み中...');
        
        const response = await fetch('/api/ndvi-points');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const ndviData = await response.json();
        console.log('NDVIデータの読み込み完了:', ndviData);
        
        addNDVIPointsToMap(ndviData);
        updateNDVIStats(ndviData);
        
    } catch (error) {
        console.error('NDVIデータの読み込みエラー:', error);
        showError('NDVIデータの読み込みに失敗しました。');
    }
}

// NDVIポイントを地図に追加
function addNDVIPointsToMap(ndviData) {
    if (ndviLayer) {
        map.removeLayer(ndviLayer);
    }
    
    const features = ndviData.features || [];
    console.log(`${features.length}件のNDVIポイントを処理中...`);
    
    if (features.length === 0) {
        console.log('表示するNDVIデータがありません');
        return;
    }
    
    const markers = features.map((feature, index) => {
        const props = feature.properties;
        const coords = feature.geometry.coordinates;
        
        if (!coords || coords.length !== 2) {
            console.warn(`座標データが不正: ${props.tree_id}`);
            return null;
        }
        
        const lat = coords[1];
        const lon = coords[0];
        const ndviDiff = props.ndvi_diff;
        
        const color = getNDVIColor(ndviDiff);
        const icon = createNDVIIcon(color, ndviDiff);
        const marker = L.marker([lat, lon], { icon: icon });
        
        const popupContent = createNDVIPopup(props, ndviDiff);
        marker.bindPopup(popupContent);
        
        return marker;
    }).filter(marker => marker !== null);
    
    ndviLayer = L.layerGroup(markers);
    
    if (map) {
        ndviLayer.addTo(map);
        console.log(`${markers.length}件のNDVIマーカーを地図に追加しました`);
        
        if (markers.length > 0) {
            const group = new L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.1));
        }
    }
}

// NDVI差分に基づく色分け
function getNDVIColor(ndviDiff) {
    if (ndviDiff === null || ndviDiff === undefined) {
        return '#888888'; // グレー（データなし）
    }
    
    if (ndviDiff >= 0.1) return '#00ff00';      // 明るい緑（大幅増加）
    if (ndviDiff >= 0.05) return '#90ee90';     // 薄緑（増加）
    if (ndviDiff >= -0.05) return '#ffff00';    // 黄色（変化なし）
    if (ndviDiff >= -0.1) return '#ff8c00';     // オレンジ（減少）
    return '#ff0000';                           // 赤（大幅減少）
}

// NDVIアイコンの作成
function createNDVIIcon(color, ndviDiff) {
    const size = ndviDiff !== null ? 12 : 8;
    
    return L.divIcon({
        html: `<div style="
            background-color: ${color};
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 4px rgba(0,0,0,0.5);
        "></div>`,
        iconSize: [size + 4, size + 4],
        iconAnchor: [(size + 4) / 2, (size + 4) / 2],
        popupAnchor: [0, -(size + 4) / 2]
    });
}
