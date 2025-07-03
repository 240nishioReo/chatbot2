#!/usr/bin/env python3
"""
既存の空メッセージを修正するスクリプト
ID:21のメッセージ内容を正しい形式で再構築
"""

import os
import sys
import json
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

def fix_empty_message():
    """空のメッセージを修正"""
    with app.app_context():
        # ID:21のメッセージを取得
        target_message = db.session.query(Message).filter_by(id=21).first()
        
        if not target_message:
            print("ID:21のメッセージが見つかりません")
            return
        
        if not target_message.raw_dify_response:
            print("raw_dify_responseが見つかりません")
            return
        
        print(f"修正前: Content='{target_message.content}', Length={len(target_message.content)}")
        
        try:
            # raw_responseからmessageイベントを抽出
            raw_data = json.loads(target_message.raw_dify_response)
            
            # messageイベントから回答を結合
            full_answer = ""
            message_chunks = [chunk for chunk in raw_data if chunk.get('event') == 'message']
            
            print(f"messageチャンク数: {len(message_chunks)}")
            
            for chunk in message_chunks:
                answer_part = chunk.get('answer', '')
                if answer_part:
                    full_answer += answer_part
            
            # メッセージ内容を更新
            target_message.content = full_answer
            db.session.commit()
            
            print(f"修正後: Content='{target_message.content[:100]}...', Length={len(target_message.content)}")
            print("メッセージ修正完了")
            
        except Exception as e:
            print(f"修正エラー: {e}")
            db.session.rollback()

if __name__ == '__main__':
    fix_empty_message()
