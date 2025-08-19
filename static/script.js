// グローバル変数
let map;
let locationMap = null;
let parksLayer;
let citizenReportsLayer;
let currentChart = null;
let selectedPark = null;
let reportMarker = null;
let locationMarker = null;
let showingReports = false;

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    loadParksData();
    initializeCitizenReports();
    
    // 初期化完了
    console.log('市民レポート機能の初期化準備完了');
});

// 地図の初期化
function initializeMap() {
    // 東京中心部を初期表示位置に設定
    const tokyoCenter = [35.6762, 139.6503];
    
    // Leafletマップを初期化
    map = L.map('map').setView(tokyoCenter, 11);
    
    // OpenStreetMapタイルレイヤーを追加
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    
    // 地図のコントロール設定
    map.zoomControl.setPosition('topleft');
    
    console.log('地図の初期化が完了しました');
}

// 公園データの読み込み
async function loadParksData() {
    try {
        console.log('公園データを読み込み中...');
        
        const response = await fetch('/api/parks');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const parksData = await response.json();
        console.log('公園データの読み込み完了:', parksData);
        
        // 公園ポリゴンを地図に追加
        addParksToMap(parksData);
        
    } catch (error) {
        console.error('公園データの読み込みエラー:', error);
        showError('公園データの読み込みに失敗しました。');
    }
}

// 公園ポリゴンを地図に追加
function addParksToMap(parksData) {
    // 既存のレイヤーがあれば削除
    if (parksLayer) {
        map.removeLayer(parksLayer);
    }
    
    // 公園ポリゴンのスタイル設定
    const parkStyle = {
        color: '#4682b4',
        weight: 2,
        opacity: 0.8,
        fillColor: '#4682b4',
        fillOpacity: 0.3
    };
    
    // 選択時のスタイル設定
    const selectedStyle = {
        color: '#ff6347',
        weight: 3,
        opacity: 1,
        fillColor: '#ff6347',
        fillOpacity: 0.5
    };
    
    // GeoJSONレイヤーを作成
    parksLayer = L.geoJSON(parksData, {
        style: parkStyle,
        onEachFeature: function(feature, layer) {
            const parkName = feature.properties.park_name;
            const parkId = feature.properties.park_id;
            
            // ポップアップの設定
            layer.bindPopup(`
                <div style="text-align: center;">
                    <h3 style="margin: 0 0 5px 0; color: #2c5530;">${parkName}</h3>
                    <p style="margin: 0; color: #666; font-size: 0.9rem;">ID: ${parkId}</p>
                    <p style="margin: 5px 0 0 0; font-size: 0.85rem;">クリックして時系列データを表示</p>
                </div>
            `);
            
            // クリックイベントの設定
            layer.on('click', function(e) {
                console.log('公園がクリックされました:', parkName, parkId);
                selectPark(feature, layer);
                loadTimeseriesData(parkId, parkName);
            });
            
            // ホバーエフェクト
            layer.on('mouseover', function(e) {
                if (selectedPark !== layer) {
                    layer.setStyle({
                        weight: 3,
                        opacity: 1,
                        fillOpacity: 0.4
                    });
                }
            });
            
            layer.on('mouseout', function(e) {
                if (selectedPark !== layer) {
                    layer.setStyle(parkStyle);
                }
            });
        }
    }).addTo(map);
    
    // 地図の表示範囲を公園データに合わせて調整
    try {
        map.fitBounds(parksLayer.getBounds(), {
            padding: [20, 20]
        });
    } catch (e) {
        console.log('地図の範囲調整をスキップ:', e.message);
    }
    
    console.log('公園ポリゴンの表示完了');
    
    // 公園データの読み込み完了後に市民レポートも読み込む
    setTimeout(() => {
        console.log('公園データ読み込み完了後に市民レポートを読み込みます');
        showingReports = true;
        loadCitizenReports();
        updateToggleButtonText();
    }, 1000);
}

// 公園の選択処理
function selectPark(feature, layer) {
    // 前回選択した公園のスタイルをリセット
    if (selectedPark) {
        selectedPark.setStyle({
            color: '#4682b4',
            weight: 2,
            opacity: 0.8,
            fillColor: '#4682b4',
            fillOpacity: 0.3
        });
    }
    
    // 新しく選択した公園のスタイルを変更
    layer.setStyle({
        color: '#ff6347',
        weight: 3,
        opacity: 1,
        fillColor: '#ff6347',
        fillOpacity: 0.5
    });
    
    selectedPark = layer;
}

// 時系列データの読み込み
async function loadTimeseriesData(parkId, parkName) {
    try {
        console.log('時系列データを読み込み中:', parkId);
        
        // ローディング表示
        showLoading();
        
        const response = await fetch(`/api/timeseries/${parkId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const timeseriesData = await response.json();
        console.log('時系列データの読み込み完了:', timeseriesData);
        
        // グラフを表示
        displayChart(timeseriesData, parkName, parkId);
        
    } catch (error) {
        console.error('時系列データの読み込みエラー:', error);
        showError('時系列データの読み込みに失敗しました。');
    }
}

// グラフの表示
function displayChart(data, parkName, parkId) {
    // ローディング要素を削除
    const loadingDisplay = document.getElementById('loading-display');
    if (loadingDisplay) {
        loadingDisplay.remove();
    }
    
    // UIの表示切り替え
    document.getElementById('no-selection').style.display = 'none';
    document.getElementById('chart-container').style.display = 'block';
    
    // 公園情報の更新
    document.getElementById('park-name').textContent = parkName;
    document.getElementById('park-id').textContent = `ID: ${parkId}`;
    
    // 既存のグラフを削除
    if (currentChart) {
        currentChart.destroy();
    }
    
    // データの準備
    const labels = data.map(item => {
        const date = new Date(item.date);
        return date.toLocaleDateString('ja-JP', { 
            year: 'numeric', 
            month: 'short' 
        });
    });
    
    const ndviData = data.map(item => item.ndvi);
    const ndreData = data.map(item => item.ndre);
    const psriData = data.map(item => item.psri);
    
    // Chart.jsでグラフを作成
    const ctx = document.getElementById('timeseriesChart').getContext('2d');
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'NDVI (正規化植生指数)',
                    data: ndviData,
                    borderColor: '#4caf50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'NDRE (正規化差分レッドエッジ)',
                    data: ndreData,
                    borderColor: '#ff9800',
                    backgroundColor: 'rgba(255, 152, 0, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'PSRI (植物老化反射指数)',
                    data: psriData,
                    borderColor: '#f44336',
                    backgroundColor: 'rgba(244, 67, 54, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `${parkName} - 植生指数の時系列変化`,
                    font: {
                        size: 16,
                        weight: 'bold'
                    },
                    color: '#2c5530'
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        font: {
                            size: 11
                        },
                        usePointStyle: true,
                        padding: 15
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0,
                    title: {
                        display: true,
                        text: '指数値',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.1)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '時期',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.1)'
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            elements: {
                point: {
                    radius: 4,
                    hoverRadius: 6
                }
            }
        }
    });
    
    console.log('グラフの表示完了');
}

// ローディング表示
function showLoading() {
    // 既存の要素を隠す
    document.getElementById('no-selection').style.display = 'none';
    document.getElementById('chart-container').style.display = 'none';
    
    // ローディング要素があれば削除
    const existingLoading = document.getElementById('loading-display');
    if (existingLoading) {
        existingLoading.remove();
    }
    
    // 新しいローディング要素を追加
    const panelContent = document.querySelector('.panel-content');
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loading-display';
    loadingDiv.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="loading"></div>
            <p style="margin-top: 15px; color: #666;">データを読み込み中...</p>
        </div>
    `;
    panelContent.appendChild(loadingDiv);
}

// エラー表示
function showError(message) {
    document.getElementById('no-selection').style.display = 'none';
    document.getElementById('chart-container').style.display = 'none';
    
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

// ウィンドウサイズ変更時の処理
window.addEventListener('resize', function() {
    if (map) {
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    }
});

// 市民レポート機能の初期化
function initializeCitizenReports() {
    // 市民レポートボタンのイベントリスナー
    document.getElementById('citizen-report-btn').addEventListener('click', function() {
        document.getElementById('citizen-report-modal').style.display = 'block';
    });
    
    // レポート表示切替ボタン
    document.getElementById('toggle-reports-btn').addEventListener('click', function() {
        toggleCitizenReports();
    });
    
    // モーダルの閉じるボタン
    document.querySelectorAll('.close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            this.closest('.modal').style.display = 'none';
        });
    });
    
    // キャンセルボタン
    document.querySelector('.cancel-button').addEventListener('click', function() {
        document.getElementById('citizen-report-modal').style.display = 'none';
    });
    
    // モーダル外クリックで閉じる
    window.addEventListener('click', function(event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    });
    
    // 位置情報取得方法の切り替え
    document.querySelectorAll('input[name="location-method"]').forEach(radio => {
        radio.addEventListener('change', function() {
            toggleLocationMethod(this.value);
        });
    });
    
    // 現在位置取得ボタン
    document.getElementById('get-current-location').addEventListener('click', function() {
        getCurrentLocation();
    });
    
    // 深刻度スライダー
    document.getElementById('severity').addEventListener('input', function() {
        document.getElementById('severity-value').textContent = this.value;
    });
    
    // 画像プレビュー
    document.getElementById('tree-image').addEventListener('change', function() {
        previewImage(this);
    });
    
    // フォーム送信
    document.getElementById('citizen-report-form').addEventListener('submit', function(e) {
        e.preventDefault();
        submitCitizenReport();
    });
    
    // 地図クリックイベント（地図選択モード用）
    setupMapClickForLocation();
    
    console.log('市民レポート機能の初期化完了');
}

// 位置情報取得方法の切り替え
function toggleLocationMethod(method) {
    const currentLocationDiv = document.getElementById('current-location');
    const mapLocationDiv = document.getElementById('map-location');
    
    if (method === 'current') {
        currentLocationDiv.style.display = 'block';
        mapLocationDiv.style.display = 'none';
        
        // 位置選択用地図を破棄
        if (locationMap) {
            locationMap.remove();
            locationMap = null;
        }
    } else {
        currentLocationDiv.style.display = 'none';
        mapLocationDiv.style.display = 'block';
        
        // 位置選択用地図を初期化
        initLocationMap();
    }
}

// 位置選択用地図の初期化
function initLocationMap() {
    if (locationMap) {
        return; // 既に初期化済み
    }
    
    // 東京中心部を初期表示位置に設定
    const tokyoCenter = [35.6762, 139.6503];
    
    // 位置選択用地図を作成
    locationMap = L.map('location-map').setView(tokyoCenter, 12);
    
    // OpenStreetMapタイルレイヤーを追加
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(locationMap);
    
    // 地図クリックイベント
    locationMap.on('click', function(e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        
        // 既存のマーカーを削除
        if (locationMarker) {
            locationMap.removeLayer(locationMarker);
        }
        
        // 新しいマーカーを配置
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
        
        // フォームに値を設定
        document.getElementById('latitude').value = lat;
        document.getElementById('longitude').value = lng;
        
        // 選択位置を表示
        document.getElementById('selected-location').innerHTML = `
            <div class="location-success">
                📍 選択位置: 緯度 ${lat.toFixed(6)}, 経度 ${lng.toFixed(6)}
            </div>
        `;
    });
    
    console.log('位置選択用地図を初期化しました');
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
        function(position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            document.getElementById('latitude').value = lat;
            document.getElementById('longitude').value = lng;
            
            statusDiv.innerHTML = `
                <div class="location-success">
                    ✅ 位置情報を取得しました<br>
                    緯度: ${lat.toFixed(6)}, 経度: ${lng.toFixed(6)}
                </div>
            `;
        },
        function(error) {
            let errorMessage = '位置情報の取得に失敗しました: ';
            switch(error.code) {
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

// 地図クリック処理（旧）は不要になったため削除
function setupMapClickForLocation() {
    // 位置選択は専用の地図で行うため、ここでは何もしない
    console.log('地図クリック処理は位置選択専用地図で実装済み');
}

// 画像プレビュー
function previewImage(input) {
    const previewDiv = document.getElementById('image-preview');
    
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            previewDiv.innerHTML = `<img src="${e.target.result}" alt="選択された画像">`;
        };
        
        reader.readAsDataURL(input.files[0]);
    }
}

// 市民レポートの送信
async function submitCitizenReport() {
    const form = document.getElementById('citizen-report-form');
    const submitButton = form.querySelector('.submit-button');
    
    // バリデーション
    const latitude = document.getElementById('latitude').value;
    const longitude = document.getElementById('longitude').value;
    
    if (!latitude || !longitude) {
        alert('位置情報を取得してください');
        return;
    }
    
    // 送信ボタンを無効化
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
            // モーダルを閉じる
            document.getElementById('citizen-report-modal').style.display = 'none';
            
            // 成功メッセージ
            alert(`✅ ${result.message}\n\n分析完了まで約${result.estimated_analysis_time}お待ちください。`);
            
            // フォームリセット
            form.reset();
            document.getElementById('image-preview').innerHTML = '';
            document.getElementById('location-status').innerHTML = '';
            document.getElementById('selected-location').innerHTML = '';
            
            // 位置選択地図のマーカーをクリア
            if (locationMarker && locationMap) {
                locationMap.removeLayer(locationMarker);
                locationMarker = null;
            }
            
            // 深刻度スライダーをリセット
            document.getElementById('severity-value').textContent = '3';
            
            // 分析結果を取得（デモ用に3秒後）
            setTimeout(() => {
                getAnalysisResult(result.report_id);
            }, 3000);
            
        } else {
            alert(`❌ エラー: ${result.error}`);
        }
        
    } catch (error) {
        console.error('送信エラー:', error);
        alert('❌ 送信に失敗しました。ネットワーク接続を確認してください。');
    } finally {
        // 送信ボタンを有効化
        submitButton.disabled = false;
        submitButton.innerHTML = '🚀 報告を送信';
    }
}

// 分析結果の取得
async function getAnalysisResult(reportId) {
    try {
        const response = await fetch(`/api/get_analysis_result/${reportId}`);
        const result = await response.json();
        
        if (result.success && result.analysis_complete) {
            showAnalysisResult(result.result);
        } else {
            console.log('分析がまだ完了していません');
        }
        
    } catch (error) {
        console.error('分析結果取得エラー:', error);
    }
}

// 分析結果の表示
function showAnalysisResult(analysis) {
    const modal = document.getElementById('analysis-result-modal');
    const content = document.getElementById('analysis-content');
    
    // 健康スコアに応じたクラス
    let healthClass = 'health-good';
    if (analysis.health_score < 50) healthClass = 'health-danger';
    else if (analysis.health_score < 75) healthClass = 'health-warning';
    
    content.innerHTML = `
        <div class="analysis-result">
            <div class="result-header">
                <h3>🤖 AI分析結果</h3>
                <p>分析日時: ${analysis.analysis_date}</p>
            </div>
            <div class="result-body">
                <div class="result-row">
                    <span class="result-label">樹種:</span>
                    <span class="result-value">${analysis.tree_species} (信頼度: ${(analysis.species_confidence * 100).toFixed(1)}%)</span>
                </div>
                <div class="result-row">
                    <span class="result-label">健康状態:</span>
                    <span class="result-value">${analysis.health_status}</span>
                </div>
                <div class="result-row">
                    <span class="result-label">健康スコア:</span>
                    <span class="result-value health-score ${healthClass}">${analysis.health_score}/100</span>
                </div>
                
                ${analysis.issues_detected && analysis.issues_detected.length > 0 ? `
                <div class="result-section">
                    <h4>⚠️ 検出された問題</h4>
                    <ul class="issues-list">
                        ${analysis.issues_detected.map(issue => `<li>${issue}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}
                
                ${analysis.recommendations && analysis.recommendations.length > 0 ? `
                <div class="result-section">
                    <h4>💡 推奨アクション</h4>
                    <ul class="recommendations-list">
                        ${analysis.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
    
    // 市民レポートレイヤーを更新（新しいレポートを反映）
    setTimeout(() => {
        console.log('分析完了後に市民レポートを更新します');
        if (showingReports) {
            loadCitizenReports();
        } else {
            // 自動的に表示モードに切り替え
            showingReports = true;
            loadCitizenReports();
            updateToggleButtonText();
        }
    }, 1000);
}

// 市民レポートの表示切替
function toggleCitizenReports() {
    showingReports = !showingReports;
    console.log('市民レポート表示切替:', showingReports);
    
    if (showingReports) {
        loadCitizenReports();
    } else {
        if (citizenReportsLayer) {
            console.log('市民レポートレイヤーを非表示にします');
            map.removeLayer(citizenReportsLayer);
            citizenReportsLayer = null;
        }
    }
    
    updateToggleButtonText();
}

// ボタンテキストの更新
function updateToggleButtonText() {
    const button = document.getElementById('toggle-reports-btn');
    if (showingReports) {
        button.textContent = '👥 レポートを隠す';
    } else {
        button.textContent = '👥 市民レポートを表示';
    }
}

// 市民レポートの読み込み
async function loadCitizenReports() {
    try {
        console.log('市民レポートを読み込み中...');
        const response = await fetch('/api/citizen-reports');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reports = await response.json();
        console.log('取得した市民レポート:', reports);
        
        // 既存のレイヤーを削除
        if (citizenReportsLayer) {
            console.log('既存の市民レポートレイヤーを削除');
            map.removeLayer(citizenReportsLayer);
        }
        
        if (reports.length === 0) {
            console.log('表示する市民レポートがありません');
            return;
        }
        
        // マーカーを作成
        const markers = reports.map((report, index) => {
            console.log(`マーカー${index + 1}を作成:`, report);
            
            const marker = L.marker([report.latitude, report.longitude], {
                icon: L.icon({
                    iconUrl: getSeverityIcon(report.severity),
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    shadowSize: [41, 41]
                })
            });
            
            // ポップアップ内容
            const statusText = {
                'submitted': '送信済み',
                'analyzing': '分析中',
                'completed': '分析完了'
            }[report.status] || report.status;
            
            const popupContent = `
                <div style="min-width: 200px; font-family: sans-serif;">
                    <h4 style="margin: 0 0 10px 0; color: #2c5530;">${report.report_type}</h4>
                    <p style="margin: 5px 0;"><strong>深刻度:</strong> ${report.severity}/5</p>
                    <p style="margin: 5px 0;"><strong>状態:</strong> ${statusText}</p>
                    <p style="margin: 5px 0;"><strong>報告日時:</strong> ${new Date(report.timestamp).toLocaleString('ja-JP')}</p>
                    ${report.tree_species ? `<p style="margin: 5px 0;"><strong>樹種:</strong> ${report.tree_species}</p>` : ''}
                    ${report.health_score ? `<p style="margin: 5px 0;"><strong>健康スコア:</strong> ${report.health_score}/100</p>` : ''}
                    <p style="margin: 5px 0; font-size: 0.8em; color: #666;">ID: ${report.id}</p>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            return marker;
        });
        
        // レイヤーグループを作成
        citizenReportsLayer = L.layerGroup(markers);
        
        // 地図に追加
        if (map) {
            citizenReportsLayer.addTo(map);
            console.log(`${reports.length}件の市民レポートマーカーを地図に追加しました`);
        } else {
            console.error('地図オブジェクトが見つかりません');
        }
        
    } catch (error) {
        console.error('市民レポートの読み込みエラー:', error);
        alert('市民レポートの読み込みに失敗しました。ページを再読み込みしてください。');
    }
}

// 深刻度に応じたアイコンを取得
function getSeverityIcon(severity) {
    console.log('深刻度に応じたアイコンを選択:', severity);
    
    const icons = {
        1: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',   // 軽微
        2: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',    // 低
        3: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-gold.png',    // 中
        4: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png',  // 高
        5: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png'      // 緊急
    };
    
    const selectedIcon = icons[severity] || icons[3];
    console.log('選択されたアイコン:', selectedIcon);
    return selectedIcon;
}

console.log('スクリプトの読み込み完了'); 