#!/usr/bin/env python3
"""
データベースデバッグスクリプト
履歴削除後のブラウザ更新エラーの原因調査用
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# Flask アプリケーション初期化（最小構成）
from flask import Flask

# データベースファイルパスを絶対パスで設定
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(basedir, 'database', 'database.db')

# グローバルにFlaskアプリを初期化
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# データベース初期化
from database.models import db, DifyApp, Conversation, Message

db.init_app(app)

def debug_database():
    """データベース状態のデバッグ"""
    global app
    with app.app_context():
        print("=" * 50)
        print("データベースデバッグ情報")
        print("=" * 50)
        
        # データベースファイルの存在確認
        print(f"データベースファイルパス: {database_path}")
        print(f"データベースファイル存在: {os.path.exists(database_path)}")
        
        if os.path.exists(database_path):
            print(f"ファイルサイズ: {os.path.getsize(database_path)} bytes")
        
        print()
        
        try:
            # テーブル存在確認
            print("テーブル存在確認:")
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"存在するテーブル: {tables}")
            print()
            
            # 各テーブルのレコード数確認
            print("レコード数:")
            try:
                dify_apps_count = db.session.query(DifyApp).count()
                print(f"DifyApp: {dify_apps_count} 件")
                
                conversations_count = db.session.query(Conversation).count()
                print(f"Conversation: {conversations_count} 件")
                
                messages_count = db.session.query(Message).count()
                print(f"Message: {messages_count} 件")
            except Exception as e:
                print(f"レコード数取得エラー: {e}")
            
            print()
            
            # DifyAppの詳細
            print("DifyApp詳細:")
            try:
                dify_apps = db.session.query(DifyApp).all()
                for app in dify_apps:
                    print(f"  ID:{app.id}, Name:{app.name}, APIKey:{app.api_key_env_name}")
            except Exception as e:
                print(f"DifyApp取得エラー: {e}")
            
            print()
            
            # 会話の詳細
            print("Conversation詳細:")
            try:
                conversations = db.session.query(Conversation).order_by(Conversation.created_at.desc()).limit(5).all()
                for conv in conversations:
                    print(f"  ID:{conv.id}, Title:{conv.title[:30]}..., DifyApp:{conv.dify_app_id}, Created:{conv.created_at}")
            except Exception as e:
                print(f"Conversation取得エラー: {e}")
            
            print()
            
            # メッセージの詳細（特定の会話のメッセージを確認）
            print("Message詳細（最新の会話）:")
            try:
                latest_conversation = db.session.query(Conversation).order_by(Conversation.created_at.desc()).first()
                if latest_conversation:
                    messages = db.session.query(Message).filter_by(conversation_id=latest_conversation.id).order_by(Message.created_at).all()
                    print(f"  会話ID {latest_conversation.id} のメッセージ:")
                    for msg in messages:
                        content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        print(f"    ID:{msg.id}, Role:{msg.role}, Content:'{content_preview}', ContentLength:{len(msg.content)}")
                        if msg.role == 'assistant' and msg.raw_dify_response:
                            print(f"    Raw Response Length: {len(msg.raw_dify_response)}")
                else:
                    print("  会話が見つかりません")
            except Exception as e:
                print(f"Message取得エラー: {e}")
            
            print()
            
            # 特定のメッセージの詳細分析（ID:21のraw_responseを確認）
            print("特定メッセージ詳細分析（ID:21）:")
            try:
                target_message = db.session.query(Message).filter_by(id=21).first()
                if target_message and target_message.raw_dify_response:
                    import json
                    raw_data = json.loads(target_message.raw_dify_response)
                    print(f"  Raw Response データ数: {len(raw_data)}")
                    
                    # 各チャンクの構造を確認
                    for i, chunk in enumerate(raw_data[:3]):  # 最初の3つだけ表示
                        print(f"  Chunk {i}: {chunk}")
                    
                    # message_endイベントを探す
                    message_end_chunks = [chunk for chunk in raw_data if chunk.get('event') == 'message_end']
                    if message_end_chunks:
                        print(f"  message_end チャンク数: {len(message_end_chunks)}")
                        print(f"  message_end チャンク: {message_end_chunks[0]}")
                    else:
                        print("  message_end チャンクが見つかりません")
                else:
                    print("  ID:21のメッセージまたはraw_responseが見つかりません")
            except Exception as e:
                print(f"特定メッセージ分析エラー: {e}")
            
            print()
            
            # text イベントを探す（実際の回答内容）
            print("text イベント分析:")
            try:
                text_chunks = [chunk for chunk in raw_data if chunk.get('event') == 'text']
                if text_chunks:
                    print(f"  text チャンク数: {len(text_chunks)}")
                    full_text = ""
                    for i, chunk in enumerate(text_chunks[:5]):  # 最初の5つを表示
                        text_content = chunk.get('data', '')
                        full_text += text_content
                        print(f"  Text chunk {i}: '{text_content[:100]}...'")
                    print(f"  結合されたテキスト（最初の200文字）: '{full_text[:200]}...'")
                else:
                    print("  text イベントが見つかりません")
                    
                # messageイベントを探す（Difyワークフロー形式の場合）
                message_chunks = [chunk for chunk in raw_data if chunk.get('event') == 'message']
                if message_chunks:
                    print(f"  message チャンク数: {len(message_chunks)}")
                    full_message_text = ""
                    for i, chunk in enumerate(message_chunks[:5]):  # 最初の5つを表示
                        message_content = chunk.get('data', {}).get('text', '')
                        full_message_text += message_content
                        print(f"  Message chunk {i}: '{message_content[:100]}...'")
                    print(f"  結合されたメッセージ（最初の200文字）: '{full_message_text[:200]}...'")
                    
                    # 最初のmessageチャンクの詳細構造を表示
                    if message_chunks:
                        print(f"  最初のmessageチャンクの構造: {message_chunks[0]}")
                else:
                    print("  message イベントが見つかりません")
                    
                # 他のイベントタイプも確認
                event_types = set(chunk.get('event') for chunk in raw_data)
                print(f"  全イベントタイプ: {event_types}")
            except Exception as e:
                print(f"  text/message イベント分析エラー: {e}")
            
            print()
            
        except Exception as e:
            print(f"データベース操作エラー: {e}")
            print("データベースを再作成します...")
            
            # データベース再作成
            try:
                db.create_all()
                print("テーブル作成完了")
                
                # 初期データ挿入
                if db.session.query(DifyApp).count() == 0:
                    sample_apps = [
                        DifyApp(name='sample1', description='Sample Dify Application 1', api_key_env_name='DIFY_API_KEY_SAMPLE1'),
                        DifyApp(name='sample2', description='Sample Dify Application 2', api_key_env_name='DIFY_API_KEY_SAMPLE2'),
                        DifyApp(name='sample3', description='Sample Dify Application 3', api_key_env_name='DIFY_API_KEY_SAMPLE3')
                    ]
                    
                    for app_data in sample_apps:
                        db.session.add(app_data)
                    
                    db.session.commit()
                    print("初期データ挿入完了")
                
            except Exception as init_error:
                print(f"データベース初期化エラー: {init_error}")
        
        print("=" * 50)

def reset_database():
    """データベースリセット"""
    global app
    with app.app_context():
        print("データベースをリセットします...")
        
        # 既存のテーブルを削除
        db.drop_all()
        print("既存テーブル削除完了")
        
        # 新しいテーブルを作成
        db.create_all()
        print("新しいテーブル作成完了")
        
        # 初期データ挿入
        sample_apps = [
            DifyApp(name='sample1', description='Sample Dify Application 1', api_key_env_name='DIFY_API_KEY_SAMPLE1'),
            DifyApp(name='sample2', description='Sample Dify Application 2', api_key_env_name='DIFY_API_KEY_SAMPLE2'),
            DifyApp(name='sample3', description='Sample Dify Application 3', api_key_env_name='DIFY_API_KEY_SAMPLE3')
        ]
        
        for app_data in sample_apps:
            db.session.add(app_data)
        
        db.session.commit()
        print("初期データ挿入完了")
        
        print("データベースリセット完了")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        reset_database()
    else:
        debug_database()
