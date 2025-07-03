/**
 * 履歴管理機能 - 会話履歴の表示・検索・操作
 */

window.HistoryManager = (function() {
    
    let historyData = [];
    
    /**
     * 履歴データロード
     */
    function loadHistory() {
        console.log('履歴データロード開始');
        
        fetch('/api/conversations')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                historyData = data;
                displayHistory(historyData);
                console.log('履歴データロード完了:', historyData.length, '件');
            })
            .catch(error => {
                console.error('履歴ロードエラー:', error);
                window.AppUtils.showError('履歴の読み込みに失敗しました: ' + error.message);
            });
    }
    
    /**
     * 履歴表示
     */
    function displayHistory(conversations) {
        const historyList = $('#history-list');
        historyList.empty();
        
        if (conversations.length === 0) {
            historyList.html(`
                <div style="text-align: center; color: #666; padding: 2rem;">
                    まだ会話履歴がありません
                </div>
            `);
            return;
        }
        
        conversations.forEach(conv => {
            const historyItemHtml = createHistoryItemHtml(conv);
            historyList.append(historyItemHtml);
        });
        
        // アクティブな会話をハイライト
        if (window.ChatApp.currentConversationId) {
            $(`.history-item[data-conversation-id="${window.ChatApp.currentConversationId}"]`)
                .addClass('active');
        }
    }
    
    /**
     * 履歴アイテムHTML作成
     */
    function createHistoryItemHtml(conversation) {
        const createdDate = new Date(conversation.created_at).toLocaleDateString('ja-JP');
        const createdTime = new Date(conversation.created_at).toLocaleTimeString('ja-JP', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        return `
            <div class="history-item" data-conversation-id="${conversation.id}">
                <div class="history-title">${escapeHtml(conversation.title)}</div>
                <div class="history-meta">
                    <span class="history-app">${conversation.dify_app_name}</span>
                    <div class="history-actions">
                        <button class="history-action-btn load-btn" 
                                onclick="loadConversationFromHistory(${conversation.id})"
                                title="この会話を読み込む">
                            📂
                        </button>
                        <button class="history-action-btn delete-btn" 
                                onclick="deleteConversationFromHistory(${conversation.id})"
                                title="この会話を削除">
                            🗑️
                        </button>
                    </div>
                </div>
                <div class="history-date">${createdDate} ${createdTime}</div>
            </div>
        `;
    }
    
    /**
     * 履歴検索・フィルタリング
     */
    function filterHistory(searchTerm) {
        if (!searchTerm) {
            displayHistory(historyData);
            return;
        }
        
        const filteredData = historyData.filter(conv => 
            conv.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
            conv.dify_app_name.toLowerCase().includes(searchTerm.toLowerCase())
        );
        
        displayHistory(filteredData);
    }
    
    /**
     * 会話削除
     */
    function deleteConversation(conversationId) {
        if (!confirm('この会話を削除してもよろしいですか？')) {
            return;
        }
        
        console.log('会話削除:', conversationId);
        
        fetch(`/api/conversations/${conversationId}`, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.error || `HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('会話削除成功:', data);
            window.AppUtils.showSuccess('会話が削除されました');
            
            // 削除された会話が現在の会話の場合、新規チャットに切り替え
            if (window.ChatApp && window.ChatApp.currentConversationId == conversationId) {
                window.ChatApp.currentConversationId = null;
                $('#current-conversation-id').val('');
                if (window.AppUtils && window.AppUtils.clearChatDisplay) {
                    window.AppUtils.clearChatDisplay();
                }
                if (window.AppUtils && window.AppUtils.showWelcomeMessage) {
                    window.AppUtils.showWelcomeMessage();
                }
            }
            
            // ローカルのhistoryDataから削除
            historyData = historyData.filter(conv => conv.id !== conversationId);
            
            // UIから即座に削除
            const historyItem = $(`.history-item[data-conversation-id="${conversationId}"]`);
            historyItem.fadeOut(300, function() {
                $(this).remove();
                
                // 残り履歴数チェック
                if ($('.history-item').length === 0) {
                    $('#history-list').html(`
                        <div style="text-align: center; color: #666; padding: 2rem;">
                            まだ会話履歴がありません
                        </div>
                    `);
                }
            });
            
            // 履歴を完全に再読み込み（安全のため）
            setTimeout(() => {
                loadHistory();
            }, 500);
        })
        .catch(error => {
            console.error('会話削除エラー:', error);
            window.AppUtils.showError('会話の削除に失敗しました: ' + error.message);
            
            // エラー時も履歴を再読み込みして同期を保つ
            setTimeout(() => {
                loadHistory();
            }, 1000);
        });
    }
    
    /**
     * 会話読み込み
     */
    function loadConversation(conversationId) {
        console.log('会話読み込み:', conversationId);
        
        fetch(`/api/conversations/${conversationId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(conversationData => {
                console.log('会話データ取得成功:', conversationData);
                
                // チャット管理に会話ロードを依頼
                if (typeof window.ChatManager !== 'undefined') {
                    window.ChatManager.loadConversation(conversationData);
                }
                
                // 履歴のアクティブ状態を更新
                $('.history-item').removeClass('active');
                $(`.history-item[data-conversation-id="${conversationId}"]`).addClass('active');
            })
            .catch(error => {
                console.error('会話読み込みエラー:', error);
                window.AppUtils.showError('会話の読み込みに失敗しました: ' + error.message);
            });
    }
    
    /**
     * HTMLエスケープ
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // 外部から呼び出される関数
    return {
        loadHistory: loadHistory,
        filterHistory: filterHistory,
        deleteConversation: deleteConversation,
        loadConversation: loadConversation
    };
})();

/**
 * グローバル関数 - 履歴アイテムから呼び出される
 */
function loadConversationFromHistory(conversationId) {
    window.HistoryManager.loadConversation(conversationId);
}

function deleteConversationFromHistory(conversationId) {
    window.HistoryManager.deleteConversation(conversationId);
}

/**
 * 履歴検索機能の初期化
 */
$(document).ready(function() {
    $('#history-search').on('input', function() {
        const searchTerm = $(this).val();
        window.HistoryManager.filterHistory(searchTerm);
    });
});
