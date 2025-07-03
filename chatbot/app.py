import os
import json
from flask import Flask, request, jsonify, render_template, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv
from datetime import datetime
import logging

from database.models import db, DifyApp, Conversation, Message
from utils.dify_client import DifyClient
from utils.response_parser import ResponseParser

# 環境変数読み込み
load_dotenv()

# Flask アプリケーション初期化
app = Flask(__name__)

# データベースファイルパスを絶対パスで設定
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(basedir, 'database', 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# データベース初期化
db.init_app(app)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    """メインチャット画面"""
    dify_apps = DifyApp.query.all()
    return render_template('index.html', dify_apps=dify_apps)

@app.route('/analysis/<message_id>')
def analysis_page(message_id):
    """レスポンス解析画面"""
    message = db.session.get(Message, message_id)
    if not message:
        return "メッセージが見つかりません", 404
    return render_template('analysis.html', message=message)

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():
    """ストリーミングチャット API"""
    try:
        data = request.get_json()
        message_content = data.get('message', '').strip()
        dify_app_id = data.get('dify_app_id')
        conversation_id = data.get('conversation_id')
        
        if not message_content:
            return jsonify({'error': 'メッセージが空です'}), 400
        
        # Difyアプリ情報取得
        dify_app = db.session.get(DifyApp, dify_app_id)
        if not dify_app:
            return jsonify({'error': '指定されたDifyアプリが見つかりません'}), 404
        
        # APIキー取得
        api_key = os.getenv(dify_app.api_key_env_name)
        if not api_key:
            return jsonify({'error': f'APIキー {dify_app.api_key_env_name} が設定されていません'}), 500
        
        # 会話管理（トランザクション統一）
        try:
            conversation = None
            if conversation_id:
                conversation = db.session.get(Conversation, conversation_id)
            
            if not conversation:
                # 新規会話作成
                conversation = Conversation(
                    title=f"新しい会話 - {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                    dify_app_id=dify_app_id
                )
                db.session.add(conversation)
                db.session.flush()  # IDを取得するためflush
                logger.info(f"新規会話作成 - ID: {conversation.id}")
            
            # ユーザーメッセージ保存
            user_message = Message(
                conversation_id=conversation.id,
                role='user',
                content=message_content
            )
            db.session.add(user_message)
            db.session.commit()  # 一度だけコミット
            logger.info(f"ユーザーメッセージ保存 - ID: {user_message.id}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"メッセージ保存エラー: {str(e)}")
            return jsonify({'error': f'メッセージの保存に失敗しました: {str(e)}'}), 500
        
        # ストリーミング関数に渡すためのデータ
        conversation_id_for_stream = conversation.id
        dify_conversation_id_for_stream = conversation.dify_conversation_id
        
        # Dify API クライアント初期化
        dify_client = DifyClient(api_key)
        
        def generate_response():
            """ストリーミングレスポンス生成"""
            with app.app_context():
                try:
                    assistant_message = Message(
                        conversation_id=conversation_id_for_stream,
                        role='assistant',
                        content='',
                        raw_dify_response=''
                    )
                    
                    full_response = ''
                    raw_response_data = []
                    
                    # Dify APIストリーミング呼び出し
                    for chunk in dify_client.stream_chat(
                        message_content, 
                        dify_conversation_id_for_stream
                    ):
                        if chunk:
                            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            
                            # レスポンスデータ蓄積
                            raw_response_data.append(chunk)
                            
                            # messageイベントから回答内容を蓄積（Difyワークフロー形式）
                            if chunk.get('event') == 'message':
                                answer_part = chunk.get('answer', '')
                                if answer_part:
                                    full_response += answer_part
                            
                            # conversation_id 更新とメッセージ保存
                            if chunk.get('event') == 'message_end':
                                try:
                                    # 新しいセッションでconversationを取得して更新
                                    with app.app_context():
                                        conv_to_update = db.session.get(Conversation, conversation_id_for_stream)
                                        if conv_to_update and chunk.get('conversation_id'):
                                            conv_to_update.dify_conversation_id = chunk.get('conversation_id')
                                            db.session.commit()
                                    
                                    # 完全なレスポンス構築（messageイベントから蓄積した内容を使用）
                                    assistant_message.content = full_response
                                    assistant_message.raw_dify_response = json.dumps(raw_response_data, ensure_ascii=False)
                                    
                                    # キーフレーズ抽出
                                    parser = ResponseParser()
                                    keyphrase_data = parser.extract_keyphrases(raw_response_data)
                                    assistant_message.keyphrase_data = json.dumps(keyphrase_data, ensure_ascii=False)
                                    
                                    db.session.add(assistant_message)
                                    db.session.commit()
                                    
                                    logger.info(f"メッセージ保存完了 - DB message_id: {assistant_message.id}, content_length: {len(assistant_message.content)}")
                                    
                                    # message_id を含む最終データ送信
                                    final_data = chunk.copy()
                                    final_data['message_id'] = assistant_message.id
                                    final_data['full_answer'] = full_response  # 完全な回答も送信
                                    logger.info(f"フロントエンドに送信するmessage_id: {final_data['message_id']}")
                                    yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                                    
                                except Exception as db_error:
                                    db.session.rollback()
                                    logger.error(f"データベース保存エラー: {str(db_error)}")
                                    error_data = {'error': f'データベース保存エラー: {str(db_error)}', 'event': 'error'}
                                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    
                    yield "data: [DONE]\n\n"
                    
                except Exception as e:
                    logger.error(f"ストリーミングエラー: {str(e)}")
                    error_data = {'error': str(e), 'event': 'error'}
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        return Response(
            generate_response(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        logger.error(f"チャットAPIエラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """会話履歴一覧取得"""
    try:
        conversations = db.session.query(Conversation).order_by(Conversation.updated_at.desc()).all()
        
        result = []
        for conv in conversations:
            try:
                # 最初のメッセージで会話タイトルを生成
                first_message = db.session.query(Message).filter_by(
                    conversation_id=conv.id, role='user'
                ).first()
                
                title = first_message.content[:50] + "..." if first_message and len(first_message.content) > 50 else (first_message.content if first_message else "空の会話")
                
                result.append({
                    'id': conv.id,
                    'title': title,
                    'dify_app_name': conv.dify_app.name if conv.dify_app else 'Unknown App',
                    'created_at': conv.created_at.isoformat(),
                    'updated_at': conv.updated_at.isoformat()
                })
            except Exception as conv_error:
                logger.warning(f"会話データ処理エラー (ID: {conv.id}): {str(conv_error)}")
                # エラーがあっても他の会話は表示
                continue
        
        logger.info(f"会話一覧取得完了: {len(result)}件")
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"会話履歴取得エラー: {str(e)}")
        return jsonify({'error': f'会話履歴の取得に失敗しました: {str(e)}'}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """特定の会話履歴取得"""
    try:
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({'error': '会話が見つかりません'}), 404
        
        messages = db.session.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()
        
        result = {
            'id': conversation.id,
            'title': conversation.title,
            'dify_app_id': conversation.dify_app_id,
            'dify_conversation_id': conversation.dify_conversation_id,
            'messages': [
                {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"会話取得エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """会話削除"""
    try:
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({'error': '会話が見つかりません'}), 404
        
        # 関連メッセージと会話を削除（カスケード削除）
        db.session.delete(conversation)
        db.session.commit()
        
        logger.info(f"会話削除完了 - ID: {conversation_id}")
        return jsonify({'message': '会話が削除されました', 'deleted_id': conversation_id})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"会話削除エラー: {str(e)}")
        return jsonify({'error': f'会話の削除に失敗しました: {str(e)}'}), 500

@app.route('/api/messages/<message_id>/analysis', methods=['GET'])
def get_message_analysis(message_id):
    """メッセージ解析データ取得"""
    try:
        message = db.session.get(Message, message_id)
        if not message:
            return jsonify({'error': 'メッセージが見つかりません'}), 404
        
        if not message.raw_dify_response:
            return jsonify({'error': 'レスポンスデータが見つかりません'}), 404
        
        raw_data = json.loads(message.raw_dify_response)
        keyphrase_data = json.loads(message.keyphrase_data) if message.keyphrase_data else {}
        
        result = {
            'message_id': message.id,
            'content': message.content,
            'raw_response': raw_data,
            'keyphrases': keyphrase_data,
            'created_at': message.created_at.isoformat()
        }
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"メッセージ解析取得エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dify-apps', methods=['GET'])
def get_dify_apps():
    """Difyアプリ一覧取得"""
    try:
        apps = DifyApp.query.all()
        result = [
            {
                'id': app.id,
                'name': app.name,
                'description': app.description
            }
            for app in apps
        ]
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Difyアプリ取得エラー: {str(e)}")
        return jsonify({'error': str(e)}), 500

# エラーハンドラー
@app.errorhandler(404)
def not_found_error(error):
    """404エラーハンドラー"""
    logger.warning(f"404エラー: {request.url}")
    return jsonify({'error': 'リソースが見つかりません'}), 404

@app.errorhandler(500)
def internal_error(error):
    """500エラーハンドラー"""
    db.session.rollback()
    logger.error(f"500エラー: {str(error)}")
    return jsonify({'error': 'サーバー内部エラーが発生しました'}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """未処理例外ハンドラー"""
    db.session.rollback()
    logger.error(f"未処理例外: {str(error)}", exc_info=True)
    return jsonify({'error': f'予期しないエラーが発生しました: {str(error)}'}), 500

# データベース初期化
@app.before_request
def ensure_database_initialized():
    """初回リクエスト時にデータベース初期化"""
    if not hasattr(app, '_database_initialized'):
        with app.app_context():
            # データベースディレクトリが存在することを確認
            database_dir = os.path.dirname(database_path)
            os.makedirs(database_dir, exist_ok=True)
            
            try:
                db.create_all()
                
                # 初期データがない場合のみ挿入
                if db.session.query(DifyApp).count() == 0:
                    sample_apps = [
                        DifyApp(name='sample1', description='Sample Dify Application 1', api_key_env_name='DIFY_API_KEY_SAMPLE1'),
                        DifyApp(name='sample2', description='Sample Dify Application 2', api_key_env_name='DIFY_API_KEY_SAMPLE2'),
                        DifyApp(name='sample3', description='Sample Dify Application 3', api_key_env_name='DIFY_API_KEY_SAMPLE3')
                    ]
                    
                    for app_data in sample_apps:
                        db.session.add(app_data)
                    
                    db.session.commit()
                    logger.info("初期Difyアプリデータを作成しました")
                
                # インデックス作成（パフォーマンス最適化）
                try:
                    with db.engine.connect() as connection:
                        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_dify_app_id ON conversations(dify_app_id)"))
                        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)"))
                        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)"))
                        connection.commit()
                    logger.info("データベースインデックスを作成しました")
                except Exception as e:
                    logger.warning(f"インデックス作成に失敗しました: {e}")
                
                app._database_initialized = True
                
            except Exception as e:
                logger.error(f"データベース初期化エラー: {str(e)}")
                raise

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
