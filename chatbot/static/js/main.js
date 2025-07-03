/**
 * メインJavaScript - アプリケーション初期化とイベント管理
 */

$(document).ready(function() {
    console.log('Dify Chat Interface 初期化開始');
    
    // グローバル状態管理
    window.ChatApp = {
        currentConversationId: null,
        currentDifyAppId: parseInt($('#current-dify-app-id').val()) || null,
        isLoading: false,
        eventSource: null
    };
    
    // 初期化処理
    initializeApp();
    
    // イベントリスナー設定
    setupEventListeners();
    
    // 履歴ロード（エラーハンドリング強化）
    loadHistoryWithRetry();
    
    console.log('Dify Chat Interface 初期化完了');
});

/**
 * 履歴ロードのリトライ機能付き
 */
function loadHistoryWithRetry(retryCount = 0, maxRetries = 3) {
    if (typeof window.HistoryManager !== 'undefined') {
        try {
            window.HistoryManager.loadHistory();
        } catch (error) {
            console.error('履歴ロードエラー:', error);
            if (retryCount < maxRetries) {
                console.log(`履歴ロードをリトライします (${retryCount + 1}/${maxRetries})`);
                setTimeout(() => {
                    loadHistoryWithRetry(retryCount + 1, maxRetries);
                }, 1000 * (retryCount + 1)); // 1秒, 2秒, 3秒と増加
            } else {
                console.error('履歴ロードの最大リトライ回数に達しました');
                if (window.AppUtils && window.AppUtils.showError) {
                    window.AppUtils.showError('履歴の読み込みに失敗しました。ページを再読み込みしてください。');
                }
            }
        }
    } else if (retryCount < maxRetries) {
        // HistoryManagerがまだ読み込まれていない場合のリトライ
        setTimeout(() => {
            loadHistoryWithRetry(retryCount + 1, maxRetries);
        }, 100);
    }
}

/**
 * アプリケーション初期化
 */
function initializeApp() {
    // Difyアプリ選択の初期設定
    const difyAppSelect = $('#dify-app-select');
    if (difyAppSelect.length > 0) {
        window.ChatApp.currentDifyAppId = parseInt(difyAppSelect.val());
        $('#current-dify-app-id').val(window.ChatApp.currentDifyAppId);
    }
    
    // メッセージ入力の初期設定
    const messageInput = $('#message-input');
    if (messageInput.length > 0) {
        messageInput.focus();
        
        // Enterキーでの送信（Shift+Enterで改行）
        messageInput.on('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
}

/**
 * イベントリスナー設定
 */
function setupEventListeners() {
    // 送信ボタン
    $('#send-btn').on('click', function() {
        sendMessage();
    });
    
    // 新規チャットボタン
    $('#new-chat-btn').on('click', function() {
        startNewChat();
    });
    
    // Difyアプリ選択変更
    $('#dify-app-select').on('change', function() {
        const newAppId = parseInt($(this).val());
        changeDifyApp(newAppId);
    });
    
    // 履歴検索
    $('#history-search').on('input', function() {
        const searchTerm = $(this).val().toLowerCase();
        filterHistory(searchTerm);
    });
}

/**
 * メッセージ送信
 */
function sendMessage() {
    const messageInput = $('#message-input');
    const message = messageInput.val().trim();
    
    if (!message) {
        alert('メッセージを入力してください。');
        return;
    }
    
    if (window.ChatApp.isLoading) {
        alert('前のメッセージの処理中です。しばらくお待ちください。');
        return;
    }
    
    if (!window.ChatApp.currentDifyAppId) {
        alert('Difyアプリを選択してください。');
        return;
    }
    
    // チャット機能を呼び出し
    if (typeof window.ChatManager !== 'undefined') {
        window.ChatManager.sendMessage(message);
        messageInput.val('');
    } else {
        console.error('ChatManager が見つかりません');
    }
}

/**
 * 新規チャット開始
 */
function startNewChat() {
    console.log('新規チャット開始');
    
    // 状態リセット
    window.ChatApp.currentConversationId = null;
    $('#current-conversation-id').val('');
    
    // チャット画面をクリア
    clearChatDisplay();
    
    // 履歴のアクティブ状態をクリア
    $('.history-item').removeClass('active');
    
    // ウェルカムメッセージを表示
    showWelcomeMessage();
    
    console.log('新規チャット準備完了');
}

/**
 * Difyアプリ切り替え
 */
function changeDifyApp(newAppId) {
    console.log('Difyアプリ切り替え:', newAppId);
    
    if (newAppId === window.ChatApp.currentDifyAppId) {
        return; // 同じアプリの場合は何もしない
    }
    
    // 確認ダイアログ
    if (window.ChatApp.currentConversationId) {
        if (!confirm('Difyアプリを切り替えると現在の会話がリセットされます。よろしいですか？')) {
            // キャンセルされた場合は元の選択に戻す
            $('#dify-app-select').val(window.ChatApp.currentDifyAppId);
            return;
        }
    }
    
    // アプリ切り替え実行
    window.ChatApp.currentDifyAppId = newAppId;
    $('#current-dify-app-id').val(newAppId);
    
    // 新規チャット開始（会話リセット）
    startNewChat();
    
    console.log('Difyアプリ切り替え完了:', newAppId);
}

/**
 * チャット画面クリア
 */
function clearChatDisplay() {
    const chatContainer = $('#chat-container');
    chatContainer.empty();
}

/**
 * ウェルカムメッセージ表示
 */
function showWelcomeMessage() {
    const chatContainer = $('#chat-container');
    const welcomeHtml = `
        <div class="welcome-message">
            <h2>チャットを開始してください</h2>
            <p>上部のプルダウンからDifyアプリを選択し、メッセージを入力してください。</p>
        </div>
    `;
    chatContainer.html(welcomeHtml);
}

/**
 * 履歴フィルタリング
 */
function filterHistory(searchTerm) {
    $('.history-item').each(function() {
        const title = $(this).find('.history-title').text().toLowerCase();
        if (title.includes(searchTerm)) {
            $(this).show();
        } else {
            $(this).hide();
        }
    });
}

/**
 * エラー表示
 */
function showError(message) {
    console.error('エラー:', message);
    alert('エラー: ' + message);
}

/**
 * 成功メッセージ表示
 */
function showSuccess(message) {
    console.log('成功:', message);
    // 必要に応じてトースト通知などを実装
}

/**
 * ローディング状態制御
 */
function setLoading(isLoading) {
    window.ChatApp.isLoading = isLoading;
    const sendBtn = $('#send-btn');
    
    if (isLoading) {
        sendBtn.prop('disabled', true).text('送信中...');
    } else {
        sendBtn.prop('disabled', false).text('送信');
    }
}

/**
 * ユーティリティ関数
 */
window.AppUtils = {
    showError: showError,
    showSuccess: showSuccess,
    setLoading: setLoading,
    clearChatDisplay: clearChatDisplay,
    showWelcomeMessage: showWelcomeMessage
};
