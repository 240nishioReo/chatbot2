/**
 * チャット機能管理 - ストリーミング通信とタイプライター表示
 */

window.ChatManager = (function() {
    
    let currentMessageDiv = null;
    let typewriterIntervalId = null;
    
    /**
     * メッセージ送信
     */
    function sendMessage(message) {
        console.log('メッセージ送信:', message);
        
        // ローディング状態設定
        window.AppUtils.setLoading(true);
        
        // ウェルカムメッセージを削除
        $('.welcome-message').remove();
        
        // ユーザーメッセージを表示
        addUserMessage(message);
        
        // アシスタントメッセージエリア準備
        const assistantMessageDiv = addAssistantMessage('');
        currentMessageDiv = assistantMessageDiv.find('.message-content');
        
        // ストリーミング開始
        startStreaming(message);
    }
    
    /**
     * ストリーミング通信開始
     */
    function startStreaming(message) {
        const requestData = {
            message: message,
            dify_app_id: window.ChatApp.currentDifyAppId,
            conversation_id: window.ChatApp.currentConversationId
        };
        
        console.log('ストリーミングリクエスト:', requestData);
        
        fetch('/api/chat-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            // ストリーミングデータ読み取り
            function readStream() {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        console.log('ストリーミング完了');
                        window.AppUtils.setLoading(false);
                        return;
                    }
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // 最後の不完全な行は保持
                    
                    for (const line of lines) {
                        if (line.trim()) {
                            processSSELine(line.trim());
                        }
                    }
                    
                    return readStream();
                });
            }
            
            return readStream();
        })
        .catch(error => {
            console.error('ストリーミングエラー:', error);
            window.AppUtils.showError('チャット送信中にエラーが発生しました: ' + error.message);
            window.AppUtils.setLoading(false);
        });
    }
    
    /**
     * SSEライン処理
     */
    function processSSELine(line) {
        if (line.startsWith('data: ')) {
            const data = line.substring(6);
            if (data === '[DONE]') {
                return;
            }
            
            try {
                const parsed = JSON.parse(data);
                handleStreamData(parsed);
            } catch (e) {
                console.error('JSON解析エラー:', e, 'データ:', data);
            }
        }
    }
    
    /**
     * ストリームデータ処理
     */
    function handleStreamData(data) {
        console.log('受信データ:', data);
        
        if (data.event === 'message' && data.answer) {
            // Difyからの断片データをそのまま追加
            appendTextWithTypewriter(data.answer);
        }
        
        if (data.event === 'message_end') {
            // タイプライター効果完了処理
            if (typewriterIntervalId) {
                clearInterval(typewriterIntervalId);
                typewriterIntervalId = null;
            }
            
            // カーソル削除
            if (currentMessageDiv) {
                currentMessageDiv.removeClass('typing-cursor');
            }
            
            // 会話ID更新
            if (data.conversation_id) {
                window.ChatApp.currentConversationId = data.conversation_id;
                $('#current-conversation-id').val(data.conversation_id);
                console.log('会話ID更新:', data.conversation_id);
            }
            
            // メッセージアクションボタン追加
            if (data.message_id) {
                console.log('ストリーミング完了 - message_id:', data.message_id);
                console.log('currentMessageDiv:', currentMessageDiv);
                addMessageActions(currentMessageDiv.parent(), data.message_id);
            } else {
                console.warn('ストリーミング完了時にmessage_idが見つかりません:', data);
            }
            
            // 履歴更新
            if (typeof window.HistoryManager !== 'undefined') {
                window.HistoryManager.loadHistory();
            }
        }
        
        if (data.event === 'error') {
            window.AppUtils.showError(data.error || 'チャット処理中にエラーが発生しました');
        }
    }
    
    /**
     * ユーザーメッセージ追加
     */
    function addUserMessage(content) {
        const messageHtml = `
            <div class="message user-message">
                <div class="message-content">${escapeHtml(content)}</div>
            </div>
        `;
        
        $('#chat-container').append(messageHtml);
        scrollToBottom();
    }
    
    /**
     * アシスタントメッセージ追加
     */
    function addAssistantMessage(content) {
        const messageHtml = `
            <div class="message assistant-message">
                <div class="message-content" data-raw-content="">${content}</div>
            </div>
        `;
        
        const messageDiv = $(messageHtml);
        $('#chat-container').append(messageDiv);
        scrollToBottom();
        
        return messageDiv;
    }
    
    /**
     * タイプライター効果でテキスト追加
     */
    function appendTextWithTypewriter(text) {
        if (!currentMessageDiv || !text) return;
        
        // 現在の内容を取得（プレーンテキスト）
        let currentContent = currentMessageDiv.attr('data-raw-content') || '';
        
        // 新しいテキストを追加
        currentContent += text;
        
        // raw-contentに保存
        currentMessageDiv.attr('data-raw-content', currentContent);
        
        // マークダウンをHTMLに変換して表示
        if (typeof marked !== 'undefined') {
            currentMessageDiv.html(marked.parse(currentContent));
        } else {
            currentMessageDiv.text(currentContent);
        }
        
        scrollToBottom();
    }
    
    /**
     * メッセージアクションボタン追加
     */
    function addMessageActions(messageDiv, messageId) {
        console.log('addMessageActions呼び出し:', messageId);
        
        // 既存のアクションボタンがあるかチェック
        const existingActions = messageDiv.find('.message-actions');
        if (existingActions.length > 0) {
            console.log('既存のアクションボタンが存在するため、削除して再作成');
            existingActions.remove();
        }
        
        const actionsHtml = `
            <div class="message-actions">
                <button class="action-btn pdf-btn" data-message-id="${messageId}" title="ソースPDF表示（未実装）">
                    📄 ソースPDF表示
                </button>
                <button class="action-btn analysis-btn" data-message-id="${messageId}" title="レスポンス解析">
                    🔍 レスポンス解析
                </button>
            </div>
        `;
        
        const actionsElement = $(actionsHtml);
        messageDiv.append(actionsElement);
        
        console.log('アクションボタン追加完了:', messageId);
        console.log('作成されたHTML:', actionsElement.html());
        
        // イベントハンドラーを設定
        actionsElement.find('.pdf-btn').on('click', function() {
            const msgId = $(this).data('message-id');
            console.log('PDF ボタンクリック:', msgId);
            console.log('ボタン要素:', this);
            console.log('data-message-id属性:', $(this).attr('data-message-id'));
            showPDFSource(msgId);
        });
        
        actionsElement.find('.analysis-btn').on('click', function() {
            const msgId = $(this).data('message-id');
            console.log('解析ボタンクリック:', msgId);
            console.log('ボタン要素:', this);
            console.log('data-message-id属性:', $(this).attr('data-message-id'));
            console.log('messageDiv:', messageDiv);
            console.log('渡されたmessageId:', messageId);
            showResponseAnalysis(msgId);
        });
    }
    
    /**
     * チャット画面の最下部にスクロール
     */
    function scrollToBottom() {
        const chatContainer = $('#chat-container');
        chatContainer.scrollTop(chatContainer[0].scrollHeight);
    }
    
    /**
     * HTMLエスケープ
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * 会話履歴ロード（履歴から呼び出された場合）
     */
    function loadConversation(conversationData) {
        console.log('会話履歴ロード:', conversationData);
        console.log('メッセージ数:', conversationData.messages.length);
        
        // 現在の会話をクリア
        window.AppUtils.clearChatDisplay();
        
        // 会話情報を設定
        window.ChatApp.currentConversationId = conversationData.id;
        window.ChatApp.currentDifyAppId = conversationData.dify_app_id;
        
        $('#current-conversation-id').val(conversationData.id);
        $('#current-dify-app-id').val(conversationData.dify_app_id);
        $('#dify-app-select').val(conversationData.dify_app_id);
        
        // メッセージを順次表示
        conversationData.messages.forEach((msg, index) => {
            console.log(`メッセージ ${index}:`, msg);
            if (msg.role === 'user') {
                addUserMessage(msg.content);
                console.log('ユーザーメッセージ追加完了:', msg.content);
            } else if (msg.role === 'assistant') {
                console.log('アシスタントメッセージ処理開始:', msg.content);
                const assistantDiv = addAssistantMessage('');
                const contentDiv = assistantDiv.find('.message-content');
                
                console.log('contentDiv取得:', contentDiv.length);
                
                // data-raw-content属性を設定
                contentDiv.attr('data-raw-content', msg.content);
                
                // マークダウンレンダリング
                if (typeof marked !== 'undefined') {
                    const renderedContent = marked.parse(msg.content);
                    console.log('マークダウンレンダリング完了:', renderedContent);
                    contentDiv.html(renderedContent);
                } else {
                    console.log('マークダウンなしでテキスト設定');
                    contentDiv.text(msg.content);
                }
                
                // メッセージアクションボタン追加
                if (msg.id) {
                    console.log('アクションボタン追加:', msg.id);
                    addMessageActions(assistantDiv, msg.id);
                }
                console.log('アシスタントメッセージ追加完了');
            }
        });
        
        scrollToBottom();
    }
    
    // 外部関数として公開
    return {
        sendMessage: sendMessage,
        loadConversation: loadConversation
    };
})();

/**
 * グローバル関数 - メッセージアクションボタンから呼び出される
 */
function showPDFSource(messageId) {
    alert('ソースPDF表示機能は現在開発中です。\\n将来のバージョンで、回答生成に使用されたPDFの該当ページがハイライト表示される予定です。');
}

function showResponseAnalysis(messageId) {
    console.log('showResponseAnalysis呼び出し:', messageId);
    console.log('messageId type:', typeof messageId);
    
    if (!messageId) {
        console.error('messageId is undefined or null');
        alert('メッセージIDが取得できませんでした');
        return;
    }
    
    const url = `/analysis/${messageId}`;
    console.log('Opening URL:', url);
    
    // 解析ページに遷移
    window.open(url, '_blank');
}
