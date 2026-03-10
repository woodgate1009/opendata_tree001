// マツ・ナラNDVI監視システム - メインスクリプト
let map;
let ndviLayer;
let citizenReportsLayer;
let locationMap = null;
let reportMarker = null;
let locationMarker = null;
let showingReports = false;

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM読み込み完了、初期化開始...');

    // 地図を先に初期化
    initializeMap();

    // 地図初期化後にデータ読み込み
    setTimeout(() => {
        if (map) {
            loadNDVIPoints();
        } else {
            console.error('地図初期化に失敗しました');
        }
    }, 100);

    // 市民レポート機能初期化
    initializeCitizenReports();

    console.log('マツ・ナラNDVI監視システム初期化完了');
});

// 地図の初期化
function initializeMap() {
    console.log('地図初期化開始...');

    try {
        const mapElement = document.getElementById('map');
        if (!mapElement) {
            console.error('地図要素が見つかりません');
            return;
        }

        const suginamiCenter = [35.6996, 139.6366]; // 杉並区役所上空
        map = L.map('map').setView(suginamiCenter, 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(map);

        map.zoomControl.setPosition('topleft');
        console.log('地図の初期化が完了しました');
    } catch (error) {
        console.error('地図初期化エラー:', error);
    }
}

// マツ・ナラNDVIデータの読み込み
async function loadNDVIPoints() {
    try {
        console.log('マツ・ナラNDVIデータを読み込み中...');

        if (!map) {
            console.error('地図が初期化されていません');
            return;
        }

        const response = await fetch('/api/ndvi-points');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const ndviData = await response.json();
        console.log('NDVIデータの読み込み完了:', ndviData.features?.length || 0, '件');

        if (ndviData.features && ndviData.features.length > 0) {
            // グローバルにデータを保存（ナビゲーション用）
            window.allNDVIData = ndviData;
            addNDVIPointsToMap(ndviData);
            updateNDVIStats(ndviData);
        } else {
            console.warn('NDVIデータが空です');
        }

    } catch (error) {
        console.error('NDVIデータの読み込みエラー:', error);
        alert('NDVIデータの読み込みに失敗しました: ' + error.message);
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
        const isCitizenReport = props.species === '市民報告';
        const icon = createNDVIIcon(color, ndviDiff, isCitizenReport);
        const marker = L.marker([lat, lon], { icon: icon });

        const popupContent = createNDVIPopup(props, ndviDiff);
        marker.bindPopup(popupContent);

        // マーカークリック時にサイドパネルを表示
        marker.on('click', function () {
            showPointDetails(props);
        });

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

    if (ndviDiff >= 0.1) return '#00ff00';      // 濃い緑（増加）
    if (ndviDiff >= -0.1) return '#ffff00';     // 黄色（安定）
    if (ndviDiff >= -0.5) return '#ff8c00';     // オレンジ（減少）
    return '#ff0000';                           // 赤（警戒）
}

// NDVIアイコンの作成
function createNDVIIcon(color, ndviDiff, isCitizenReport = false) {
    const size = 12; // 全て同じサイズに統一
    const borderColor = isCitizenReport ? '#888888' : 'white'; // 市民投稿はグレー枠
    const fillColor = (isCitizenReport && (ndviDiff === null || ndviDiff === undefined)) ? '#f0f0f0' : color;

    return L.divIcon({
        html: `<div style="
            background-color: ${fillColor};
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            border: 2px solid ${borderColor};
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        "></div>`,
        className: isCitizenReport ? 'ndvi-marker-citizen' : 'ndvi-marker-simple',
        iconSize: [size + 4, size + 4],
        iconAnchor: [(size + 4) / 2, (size + 4) / 2],
        popupAnchor: [0, -(size + 4) / 2]
    });
}

// NDVIポップアップの作成
function createNDVIPopup(props, ndviDiff) {
    const treeId = props.tree_id || 'N/A';
    const species = props.species || '不明';
    const period = '2025-08';
    const ndviCurrent = props.ndvi;
    const ndviPrevious = props.ndvi_prev_year;

    let diffDisplay = 'データなし';
    let diffClass = 'ndvi-no-data';

    if (ndviDiff !== null && ndviDiff !== undefined) {
        const sign = ndviDiff >= 0 ? '+' : '';
        diffDisplay = `${sign}${ndviDiff.toFixed(6)}`;

        if (ndviDiff >= 0.05) diffClass = 'ndvi-increase';
        else if (ndviDiff <= -0.05) diffClass = 'ndvi-decrease';
        else diffClass = 'ndvi-stable';
    }

    const speciesIcon = '';

    return `
        <div style="min-width: 250px; font-family: sans-serif;">
            <h4 style="margin: 0 0 10px 0; color: #2c5530; text-align: center;">
                ${speciesIcon} ${species}
            </h4>
            <div style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
                <p style="margin: 0; font-size: 0.85rem; color: #666;">ID: ${treeId}</p>
                <p style="margin: 0; font-size: 0.85rem; color: #666;">期間: ${period}</p>
            </div>
            
            <div class="ndvi-data">
                <div style="margin: 8px 0;">
                    <strong>NDVI差分（前年同期比）:</strong>
                    <span class="${diffClass}" style="
                        font-size: 1.1rem; 
                        font-weight: bold;
                        padding: 2px 6px;
                        border-radius: 3px;
                        ${diffClass === 'ndvi-increase' ? 'color: #006400; background: #e8f5e8;' :
            diffClass === 'ndvi-decrease' ? 'color: #8b0000; background: #ffe8e8;' :
                diffClass === 'ndvi-stable' ? 'color: #b8860b; background: #fffacd;' : 'color: #666;'}
                    ">${diffDisplay}</span>
                </div>
                
                ${ndviCurrent !== null ? `
                <div style="font-size: 0.9rem; color: #555; margin-top: 8px;">
                    <div>現在値: ${ndviCurrent.toFixed(6)}</div>
                    ${ndviPrevious !== null ? `<div>前年値: ${ndviPrevious.toFixed(6)}</div>` : ''}
                </div>
                ` : ''}
            </div>
            
            ${diffClass === 'ndvi-decrease' ? `
            <div style="
                background: #ffe8e8; 
                border: 1px solid #ffcccc; 
                padding: 6px; 
                border-radius: 4px; 
                margin-top: 8px;
                font-size: 0.85rem;
            ">
                ⚠️ 植生活力の減少が検出されました
            </div>
            ` : ''}
        </div>
    `;
}

// NDVI統計情報の更新
function updateNDVIStats(ndviData) {
    const features = ndviData.features || [];

    let totalPoints = features.length;
    let processedPoints = 0;
    let increaseCount = 0;
    let decreaseCount = 0;
    let stableCount = 0;
    let matsuCount = 0;
    let naraCount = 0;

    features.forEach(feature => {
        const props = feature.properties;
        const species = props.species || '';
        const ndviDiff = props.ndvi_diff;

        if (species.includes('マツ')) matsuCount++;
        else if (species.includes('ナラ') || species.includes('カシ')) naraCount++;

        if (ndviDiff !== null && ndviDiff !== undefined) {
            processedPoints++;

            if (ndviDiff >= 0.05) increaseCount++;
            else if (ndviDiff <= -0.05) decreaseCount++;
            else stableCount++;
        }
    });

    updateStatsPanel({
        totalPoints,
        processedPoints,
        increaseCount,
        decreaseCount,
        stableCount,
        matsuCount,
        naraCount
    });
}

// 統計パネルの更新
function updateStatsPanel(stats) {
    const statsHTML = `
        <div class="ndvi-stats">
            <h3 style="margin: 0 0 15px 0; color: #2c5530; text-align: center;">
                🌲 マツ・ナラNDVI監視状況
            </h3>
            
            <div class="stats-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div class="stat-item">
                    <div class="stat-label">総ポイント数</div>
                    <div class="stat-value">${stats.totalPoints}件</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">処理済み</div>
                    <div class="stat-value">${stats.processedPoints}件</div>
                </div>
            </div>
            
            <div class="stats-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div class="stat-item">
                    <div class="stat-label">🌲 マツ類</div>
                    <div class="stat-value">${stats.matsuCount}件</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">🌳 ナラ類</div>
                    <div class="stat-value">${stats.naraCount}件</div>
                </div>
            </div>
            
            <div class="ndvi-changes" style="margin-top: 15px;">
                <h4 style="margin: 0 0 10px 0; color: #2c5530;">植生変化状況</h4>
                <div class="change-item" style="display: flex; justify-content: space-between; margin: 5px 0; padding: 4px; background: #e8f5e8; border-radius: 3px;">
                    <span>🟢 増加（+0.05以上）</span>
                    <span style="font-weight: bold;">${stats.increaseCount}件</span>
                </div>
                <div class="change-item" style="display: flex; justify-content: space-between; margin: 5px 0; padding: 4px; background: #fffacd; border-radius: 3px;">
                    <span>🟡 安定（±0.05未満）</span>
                    <span style="font-weight: bold;">${stats.stableCount}件</span>
                </div>
                <div class="change-item" style="display: flex; justify-content: space-between; margin: 5px 0; padding: 4px; background: #ffe8e8; border-radius: 3px;">
                    <span>🔴 減少（-0.05以下）</span>
                    <span style="font-weight: bold; color: #d32f2f;">${stats.decreaseCount}件</span>
                </div>
            </div>
            
            <div class="update-info" style="margin-top: 15px; padding: 8px; background: #f0f0f0; border-radius: 4px; font-size: 0.85rem; color: #666;">
                💡 データは毎週月曜日午前3時に自動更新されます
            </div>
        </div>
    `;

    const panelContent = document.querySelector('.panel-content');
    if (panelContent) {
        panelContent.innerHTML = statsHTML;
    }
}

// エラー表示
function showError(message) {
    const panelContent = document.querySelector('.panel-content');
    panelContent.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <p style="color: #f44336; font-size: 1.1rem;">⚠️ ${message}</p>
            <button onclick="location.reload()" style="
                margin-top: 15px; 
                padding: 10px 20px; 
                background: #2c5530; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer;
                font-size: 0.9rem;
            ">
                再読み込み
            </button>
        </div>
    `;
}

// 市民レポート機能の初期化
function initializeCitizenReports() {
    // DOM要素の存在確認後にイベントリスナーを追加
    const reportBtn = document.getElementById('citizen-report-btn');

    if (reportBtn) {
        reportBtn.addEventListener('click', function () {
            console.log('新規樹木登録ボタンがクリックされました');
            openNewTreeForm();
        });
        console.log('新規樹木登録ボタンのイベントリスナーを追加しました');
    } else {
        console.error('citizen-report-btn not found');
    }

    // 市民レポート表示機能は削除済み

    // モーダル閉じるボタン
    document.querySelectorAll('.close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function () {
            const modal = this.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });

    // キャンセルボタン
    const cancelBtn = document.querySelector('.cancel-button');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function () {
            const modal = document.getElementById('citizen-report-modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    }

    window.addEventListener('click', function (event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    });

    document.querySelectorAll('input[name="location-method"]').forEach(radio => {
        radio.addEventListener('change', function () {
            toggleLocationMethod(this.value);
        });
    });

    const getCurrentLocationBtn = document.getElementById('get-current-location');
    if (getCurrentLocationBtn) {
        getCurrentLocationBtn.addEventListener('click', function () {
            getCurrentLocation();
        });
    }

    const severitySlider = document.getElementById('severity');
    if (severitySlider) {
        severitySlider.addEventListener('input', function () {
            const valueDisplay = document.getElementById('severity-value');
            if (valueDisplay) {
                valueDisplay.textContent = this.value;
            }
        });
    }

    const treeImageInput = document.getElementById('tree-image');
    if (treeImageInput) {
        treeImageInput.addEventListener('change', function () {
            previewImage(this);
        });
    }

    // フォーム送信の処理
    const reportForm = document.getElementById('citizen-report-form');
    if (reportForm) {
        reportForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitCitizenReport();
        });
    }

    // フローティングボタンの初期化
    initializeFloatingButtons();

    console.log('市民レポート機能の初期化完了');
}

// フローティングボタンの初期化
function initializeFloatingButtons() {
    const floatingBtn = document.getElementById('floating-action-btn');
    const floatingMenu = document.getElementById('floating-menu');
    const floatingReportBtn = document.getElementById('floating-report-btn');
    // フローティングトグルボタンは削除済み

    let menuOpen = false;

    if (floatingBtn) {
        floatingBtn.addEventListener('click', function () {
            menuOpen = !menuOpen;
            if (menuOpen) {
                floatingMenu.style.display = 'flex';
                floatingBtn.textContent = '×';
                floatingBtn.style.transform = 'rotate(45deg)';
            } else {
                floatingMenu.style.display = 'none';
                floatingBtn.textContent = '+';
                floatingBtn.style.transform = 'rotate(0deg)';
            }
        });
    }

    if (floatingReportBtn) {
        floatingReportBtn.addEventListener('click', function () {
            openNewTreeForm();
            // メニューを閉じる
            floatingMenu.style.display = 'none';
            floatingBtn.textContent = '+';
            floatingBtn.style.transform = 'rotate(0deg)';
            menuOpen = false;
        });
    }

    // 市民レポート表示機能は削除済み

    // 画面クリックでメニューを閉じる
    document.addEventListener('click', function (event) {
        if (!floatingBtn.contains(event.target) && !floatingMenu.contains(event.target)) {
            if (menuOpen) {
                floatingMenu.style.display = 'none';
                floatingBtn.textContent = '+';
                floatingBtn.style.transform = 'rotate(0deg)';
                menuOpen = false;
            }
        }
    });
}

// 位置情報取得方法の切り替え
function toggleLocationMethod(method) {
    const currentLocationDiv = document.getElementById('current-location');
    const mapLocationDiv = document.getElementById('map-location');

    if (method === 'current') {
        currentLocationDiv.style.display = 'block';
        mapLocationDiv.style.display = 'none';

        if (locationMap) {
            locationMap.remove();
            locationMap = null;
        }
    } else {
        currentLocationDiv.style.display = 'none';
        mapLocationDiv.style.display = 'block';
        initLocationMap();
    }
}

// 位置選択用地図の初期化
function initLocationMap() {
    if (locationMap) return;

    // DOM要素の存在確認後に初期化
    setTimeout(() => {
        const mapElement = document.getElementById('location-map');
        if (mapElement) {
            const suginamiCenter = [35.6996, 139.6366]; // 杉並区中心
            locationMap = L.map('location-map').setView(suginamiCenter, 13);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 18
            }).addTo(locationMap);

            locationMap.on('click', function (e) {
                const lat = e.latlng.lat;
                const lng = e.latlng.lng;

                if (locationMarker) {
                    locationMap.removeLayer(locationMarker);
                }

                locationMarker = L.marker([lat, lng], {
                    icon: L.icon({
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41],
                        popupAnchor: [1, -34],
                        shadowSize: [41, 41]
                    })
                }).addTo(locationMap);

                document.getElementById('latitude').value = lat;
                document.getElementById('longitude').value = lng;

                document.getElementById('selected-location').innerHTML = `
                    <div class="location-success">
                        選択位置: 緯度 ${lat.toFixed(6)}, 経度 ${lng.toFixed(6)}
                    </div>
                `;
            });

            console.log('位置選択用地図初期化完了');
        }
    }, 100);
}

// 現在位置の取得
function getCurrentLocation() {
    const statusDiv = document.getElementById('location-status');
    statusDiv.innerHTML = '<div class="loading"></div> 位置情報を取得中...';

    if (!navigator.geolocation) {
        statusDiv.innerHTML = '<div class="location-error">このブラウザは位置情報をサポートしていません</div>';
        return;
    }

    navigator.geolocation.getCurrentPosition(
        function (position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            document.getElementById('latitude').value = lat;
            document.getElementById('longitude').value = lng;

            statusDiv.innerHTML = `
                <div class="location-success">
                    位置情報を取得しました<br>
                    緯度: ${lat.toFixed(6)}, 経度: ${lng.toFixed(6)}
                </div>
            `;
        },
        function (error) {
            let errorMessage = '位置情報の取得に失敗しました: ';
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage += '位置情報の使用が拒否されました';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage += '位置情報が利用できません';
                    break;
                case error.TIMEOUT:
                    errorMessage += 'タイムアウトしました';
                    break;
                default:
                    errorMessage += '不明なエラーが発生しました';
                    break;
            }
            statusDiv.innerHTML = `<div class="location-error">${errorMessage}</div>`;
        }
    );
}

// 画像プレビュー
function previewImage(input) {
    const previewDiv = document.getElementById('image-preview');

    if (input.files && input.files[0]) {
        const reader = new FileReader();

        reader.onload = function (e) {
            previewDiv.innerHTML = `<img src="${e.target.result}" alt="選択された画像" style="max-width: 100%; height: auto; border-radius: 8px;">`;
        };

        reader.readAsDataURL(input.files[0]);
    }
}

// 市民レポートの送信
async function submitCitizenReport() {
    const form = document.getElementById('citizen-report-form');
    const submitButton = form.querySelector('.submit-button');

    // 既存樹木IDがある場合は位置情報不要
    const existingTreeIdElement = document.getElementById('existing-tree-id');
    const existingTreeIdInput = form.querySelector('input[name="existing_tree_id"]');
    const allExistingInputs = form.querySelectorAll('input[name="existing_tree_id"]');

    let isExistingTree = false;

    // 複数の方法で既存樹木IDをチェック
    if (existingTreeIdElement && existingTreeIdElement.value) {
        isExistingTree = true;
    } else if (existingTreeIdInput && existingTreeIdInput.value) {
        isExistingTree = true;
    } else {
        // 全ての隠しフィールドをチェック
        allExistingInputs.forEach(input => {
            if (input.value) {
                isExistingTree = true;
            }
        });
    }

    const latitude = document.getElementById('latitude').value;
    const longitude = document.getElementById('longitude').value;

    console.log('投稿チェック詳細:', {
        existingTreeIdElement: existingTreeIdElement,
        existingTreeIdInput: existingTreeIdInput,
        allExistingInputs: allExistingInputs.length,
        isExistingTree: isExistingTree,
        latitude: latitude,
        longitude: longitude
    });

    // 既存樹木の場合は位置情報チェックを完全スキップ
    if (!isExistingTree) {
        if (!latitude || !longitude) {
            alert('位置情報を取得してください');
            return;
        }
    } else {
        console.log('既存樹木のため位置情報チェックをスキップしました');
    }

    submitButton.disabled = true;
    submitButton.innerHTML = '<div class="loading"></div> 送信中...';

    try {
        const formData = new FormData(form);

        const response = await fetch('/api/submit', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            document.getElementById('citizen-report-modal').style.display = 'none';
            alert(result.message);

            // サイドパネルを強制的に閉じる
            const sidePanel = document.querySelector('.side-panel');
            if (sidePanel) {
                sidePanel.classList.remove('active');
            }

            form.reset();
            document.getElementById('image-preview').innerHTML = '';
            document.getElementById('location-status').innerHTML = '';
            document.getElementById('selected-location').innerHTML = '';

            if (locationMarker && locationMap) {
                locationMap.removeLayer(locationMarker);
                locationMarker = null;
            }

            document.getElementById('severity-value').textContent = '3';

            // 投稿成功後の処理
            if (isExistingTree) {
                // 既存樹木：報告履歴を即座に更新
                if (window.currentDisplayedTreeId) {
                    setTimeout(() => {
                        loadReportsTimeline(window.currentDisplayedTreeId);
                    }, 500);
                }
            } else {
                // 新規樹木：地図に即座追加して投稿位置に移動
                console.log('新規樹木投稿完了 - 地図を更新中...');
                setTimeout(() => {
                    loadNDVIPoints().then(() => {
                        // 新しい樹木の位置にマップを移動
                        if (map && latitude && longitude) {
                            map.setView([latitude, longitude], 17);
                        }
                    });
                    console.log('地図更新完了');
                }, 500);
            }

            // 全ての場合で報告履歴を更新（新規樹木が既存エリアに投稿された場合も対応）
            setTimeout(() => {
                const allTimelineDivs = document.querySelectorAll('[id^="reports-timeline-"]');
                allTimelineDivs.forEach(div => {
                    const treeId = div.id.replace('reports-timeline-', '');
                    loadReportsTimeline(treeId);
                });
            }, 1000);

        } else {
            alert(`エラー: ${result.error}`);
        }

    } catch (error) {
        console.error('送信エラー:', error);
        alert('送信に失敗しました。ネットワーク接続を確認してください。');
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = '報告を送信';
    }
}

// 市民レポート表示機能は削除されました

// 現在選択中の樹木情報
let currentTreeIndex = 0;
let nearbyTrees = [];

// 地点詳細をサイドパネルに表示
function showPointDetails(props) {
    const sidePanel = document.querySelector('.side-panel');
    const panelContent = document.querySelector('.panel-content');

    // 近くの木を検索
    findNearbyTrees(props);

    console.log('showPointDetails:', {
        nearbyTreesLength: nearbyTrees.length,
        currentTreeIndex: currentTreeIndex,
        props: props
    });

    const ndviDiff = props.ndvi_diff;
    const status = getNDVIStatus(ndviDiff);
    const color = getNDVIColor(ndviDiff);

    const detailsHTML = `
        <div class="point-details">
            <div class="detail-header">
                <h3>樹木詳細情報</h3>
                <div class="header-controls">
                    <div class="navigation-controls">
                        <button onclick="navigateToPrevTree()" class="nav-button" ${nearbyTrees.length <= 1 ? 'disabled' : ''}>‹</button>
                        <span class="tree-counter">${currentTreeIndex + 1}/${nearbyTrees.length || 1}</span>
                        <button onclick="navigateToNextTree()" class="nav-button" ${nearbyTrees.length <= 1 ? 'disabled' : ''}>›</button>
                    </div>
                    <button onclick="hideSidePanel()" class="close-panel">×</button>
                </div>
            </div>
            
            <div class="detail-section">
                <h4>基本情報</h4>
                <p><strong>樹木ID:</strong> ${props.tree_id || '不明'}</p>
                <p><strong>樹種:</strong> ${props.species || '不明'}</p>
                <p><strong>データ期間:</strong> 2025-08</p>
            </div>
            
            <div class="detail-section">
                <h4>NDVI分析結果</h4>
                <div class="ndvi-status" style="background-color: ${color}; color: white; padding: 10px; border-radius: 8px; text-align: center;">
                    <strong>${status}</strong>
                </div>
                <p><strong>現在NDVI:</strong> ${props.ndvi ? props.ndvi.toFixed(3) : 'データなし'}</p>
                <p><strong>前年NDVI:</strong> ${props.ndvi_prev_year ? props.ndvi_prev_year.toFixed(3) : 'データなし'}</p>
                <p><strong>変化量:</strong> ${ndviDiff ? (ndviDiff > 0 ? '+' : '') + ndviDiff.toFixed(3) : 'データなし'}</p>
            </div>
            
            <div class="detail-section">
                <h4>樹木の状態を報告</h4>
                <button onclick="openTreeReportForm('${props.id}')" class="tree-report-button">
                    この樹木について報告する
                </button>
            </div>
            
            <div class="detail-section">
                <h4>報告履歴</h4>
                <div id="reports-timeline-${props.id}" class="reports-timeline">
                    <div class="timeline-loading">履歴を読み込み中...</div>
                </div>
            </div>
            
            <div class="detail-section">
                <h4>AIのアドバイス</h4>
                <button onclick="getLLMAdvice('${props.tree_id}', '${props.species}', ${props.ndvi}, ${props.ndvi_prev_year}, ${props.ndvi_diff})" class="tree-report-button" style="background-color: #4CAF50; margin-bottom: 10px;">
                    🌲 AIに診断してもらう
                </button>
                <div id="llm-advice-result" style="padding: 10px; background-color: #f9f9f9; border-left: 4px solid #4CAF50; border-radius: 4px; display: none; font-size: 0.9rem;">
                </div>
            </div>
        </div>
    `;

    panelContent.innerHTML = detailsHTML;
    sidePanel.classList.add('active');

    // 現在表示中の樹木IDを保存
    window.currentDisplayedTreeId = props.id;

    // 報告履歴を読み込み
    loadReportsTimeline(props.id);
}

// 近くの木を検索（制限なし、距離順ソート）
function findNearbyTrees(currentProps) {
    if (!window.allNDVIData || !window.allNDVIData.features) {
        nearbyTrees = [currentProps];
        currentTreeIndex = 0;
        return;
    }

    const currentLat = currentProps.lat || (currentProps.geometry && currentProps.geometry.coordinates[1]);
    const currentLon = currentProps.lon || (currentProps.geometry && currentProps.geometry.coordinates[0]);

    if (!currentLat || !currentLon) {
        nearbyTrees = [currentProps];
        currentTreeIndex = 0;
        return;
    }

    // 全ての木を距離順でソート（制限なし）
    nearbyTrees = window.allNDVIData.features
        .map(feature => {
            const coords = feature.geometry.coordinates;
            const distance = calculateDistance(currentLat, currentLon, coords[1], coords[0]);
            return { ...feature.properties, geometry: feature.geometry, distance };
        })
        .sort((a, b) => a.distance - b.distance);

    // 現在の木のインデックスを設定
    currentTreeIndex = nearbyTrees.findIndex(tree => tree.id === currentProps.id);
    if (currentTreeIndex === -1) {
        // 見つからない場合は最初に追加
        nearbyTrees.unshift(currentProps);
        currentTreeIndex = 0;
    }

    console.log(`全ての木: ${nearbyTrees.length}件, 現在: ${currentTreeIndex + 1}`);
}

// 距離計算（簡易版）
function calculateDistance(lat1, lon1, lat2, lon2) {
    const dLat = lat2 - lat1;
    const dLon = lon2 - lon1;
    return Math.sqrt(dLat * dLat + dLon * dLon);
}

// 前の木へナビゲート
function navigateToPrevTree() {
    if (nearbyTrees.length <= 1) return;
    currentTreeIndex = (currentTreeIndex - 1 + nearbyTrees.length) % nearbyTrees.length;
    showPointDetails(nearbyTrees[currentTreeIndex]);
}

// 次の木へナビゲート
function navigateToNextTree() {
    if (nearbyTrees.length <= 1) return;
    currentTreeIndex = (currentTreeIndex + 1) % nearbyTrees.length;
    showPointDetails(nearbyTrees[currentTreeIndex]);
}

// サイドパネルを隠す
function hideSidePanel() {
    const sidePanel = document.querySelector('.side-panel');
    sidePanel.classList.remove('active');
}

// NDVI状態テキストを取得
function getNDVIStatus(ndviDiff) {
    if (ndviDiff === null || ndviDiff === undefined) return 'データなし';
    if (ndviDiff <= -0.5) return '警戒';
    if (ndviDiff <= -0.1) return '減少';
    if (ndviDiff < 0.1) return '安定';
    return '増加';
}

// AIから樹木のアドバイスを取得する
async function getLLMAdvice(treeId, species, ndvi, ndviPrevYear, ndviDiff) {
    const resultDiv = document.getElementById('llm-advice-result');
    if (!resultDiv) return;

    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="timeline-loading">✨ AIが診断中...</div>';

    try {
        const response = await fetch('/api/llm-advice', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tree_id: treeId,
                species: species,
                ndvi: ndvi,
                ndvi_prev_year: ndviPrevYear,
                ndvi_diff: ndviDiff
            })
        });

        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `<strong>🤖 AI樹木医:</strong><br>${data.advice.replace(/\\n/g, '<br>')}`;
        } else {
            resultDiv.innerHTML = `<span style="color: red;">エラー: ${data.error}</span>`;
        }
    } catch (error) {
        console.error('LLM API通信エラー:', error);
        resultDiv.innerHTML = '<span style="color: red;">通信エラーが発生しました。</span>';
    }
}

// AI予測結果を日本語テキストに変換
function getHealthStatusText(prediction, confidence) {
    if (!prediction || confidence === null) return 'AI判定なし';

    const confidenceValue = confidence || 0;

    if (prediction.includes('Class1')) {
        // 健康な木の場合
        if (confidenceValue >= 0.9) return '健康可能性 非常に高い';
        if (confidenceValue >= 0.7) return '健康可能性 高い';
        if (confidenceValue >= 0.5) return '健康可能性 ある程度高い';
        return '健康可能性 低い';
    } else if (prediction.includes('Class2')) {
        // 不健康な木の場合
        if (confidenceValue >= 0.9) return '枯れている可能性 非常に高い';
        if (confidenceValue >= 0.7) return '枯れている可能性 高い';
        if (confidenceValue >= 0.5) return '枯れている可能性 ある程度高い';
        return '枯れている可能性 低い';
    } else {
        return `AI判定: ${prediction}`;
    }
}

// 個別樹木の報告フォームを開く
function openTreeReportForm(treeId) {
    const modal = document.getElementById('citizen-report-modal');
    if (modal) {
        const form = document.getElementById('citizen-report-form');

        // 既存の隠しフィールドがあれば削除
        const existingInput = document.getElementById('existing-tree-id');
        if (existingInput) {
            existingInput.remove();
        }

        // フォームにtree_idを設定
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'existing_tree_id';
        hiddenInput.value = treeId;
        hiddenInput.id = 'existing-tree-id';

        form.appendChild(hiddenInput);

        console.log('既存樹木フォーム設定:', { treeId, hiddenInputValue: hiddenInput.value });

        // 位置情報セクションを完全に非表示
        const formSections = document.querySelectorAll('.form-section');
        formSections.forEach(section => {
            const h3 = section.querySelector('h3');
            if (h3 && h3.textContent.includes('位置情報')) {
                section.style.display = 'none';
            } else {
                section.style.display = 'block'; // 他のセクションは表示
            }
        });

        // モーダルタイトルを変更
        const modalTitle = modal.querySelector('.modal-header h2');
        if (modalTitle) {
            modalTitle.textContent = 'この樹木の状態を報告';
        }

        modal.style.display = 'block';
    }
}

// 報告履歴を読み込み
async function loadReportsTimeline(treeId) {
    try {
        const response = await fetch(`/api/tree-reports/${treeId}`);
        const timelineDiv = document.getElementById(`reports-timeline-${treeId}`);

        if (!response.ok) {
            timelineDiv.innerHTML = '<p class="no-reports">報告履歴がありません</p>';
            return;
        }

        const reports = await response.json();

        if (reports.length === 0) {
            timelineDiv.innerHTML = '<p class="no-reports">まだ報告がありません</p>';
            return;
        }

        // 新しい順にソート
        reports.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        const timelineHTML = reports.map(report => `
            <div class="timeline-item">
                <div class="timeline-avatar">👤</div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-severity severity-${report.severity}">深刻度: ${report.severity}/5</span>
                        <span class="timeline-date">${new Date(report.timestamp).toLocaleDateString('ja-JP')}</span>
                    </div>
                    ${report.tree_image ? `
                        <div class="timeline-image">
                            <img src="/api/image/${report.id}" alt="樹木画像" style="max-width: 100%; border-radius: 8px;">
                            ${report.ai_prediction ? `
                                <div class="ai-diagnosis-tag">
                                    <span class="ai-tag ${report.ai_prediction.includes('Class1') ? 'healthy' : 'unhealthy'}">
                                        🤖 ${getHealthStatusText(report.ai_prediction, report.ai_confidence)}
                                    </span>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                    ${report.description ? `<div class="timeline-text">${report.description}</div>` : ''}

                </div>
            </div>
        `).join('');

        timelineDiv.innerHTML = timelineHTML;

    } catch (error) {
        console.error('報告履歴の読み込みエラー:', error);
        const timelineDiv = document.getElementById(`reports-timeline-${treeId}`);
        timelineDiv.innerHTML = '<p class="timeline-error">履歴の読み込みに失敗しました</p>';
    }
}

// 新規樹木登録フォームを開く
function openNewTreeForm() {
    const modal = document.getElementById('citizen-report-modal');
    if (modal) {
        // 既存の隠しフィールドを削除
        const existingInput = document.getElementById('existing-tree-id');
        if (existingInput) {
            existingInput.remove();
        }

        // 全セクションを表示
        const formSections = document.querySelectorAll('.form-section');
        formSections.forEach(section => {
            section.style.display = 'block';
        });

        // モーダルタイトルを変更
        const modalTitle = modal.querySelector('.modal-header h2');
        if (modalTitle) {
            modalTitle.textContent = '新規樹木を登録';
        }

        modal.style.display = 'block';
    }
}

// ウィンドウサイズ変更時の処理
window.addEventListener('resize', function () {
    if (map) {
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    }
});

console.log('マツ・ナラNDVI監視システム スクリプト読み込み完了');
