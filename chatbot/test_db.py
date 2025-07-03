#!/usr/bin/env python3
"""
データベース作成のテストスクリプト
"""
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# Flask アプリケーション初期化
app = Flask(__name__)

# データベースファイルパスを絶対パスで設定
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(basedir, 'database', 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# データベース初期化
from database.models import db, DifyApp, Conversation, Message
db.init_app(app)

def test_database_creation():
    """データベース作成をテストする"""
    try:
        with app.app_context():
            # データベースディレクトリが存在することを確認
            database_dir = os.path.dirname(database_path)
            os.makedirs(database_dir, exist_ok=True)
            print(f"データベースディレクトリ: {database_dir}")
            print(f"データベースファイル: {database_path}")
            
            # テーブル作成
            db.create_all()
            print("✓ データベーステーブルが正常に作成されました")
            
            # データベースファイルが作成されたかチェック
            if os.path.exists(database_path):
                print(f"✓ データベースファイルが作成されました: {database_path}")
                file_size = os.path.getsize(database_path)
                print(f"  ファイルサイズ: {file_size} バイト")
            else:
                print("✗ データベースファイルが作成されませんでした")
                return False
            
            # サンプルデータ挿入テスト
            if DifyApp.query.count() == 0:
                sample_app = DifyApp(
                    name='test_app', 
                    description='Test Dify Application', 
                    api_key_env_name='DIFY_API_KEY_TEST'
                )
                db.session.add(sample_app)
                db.session.commit()
                print("✓ サンプルデータが正常に挿入されました")
            
            # データ読み取りテスト
            apps_count = DifyApp.query.count()
            print(f"✓ Difyアプリ数: {apps_count}")
            
            return True
            
    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("データベース作成テストを開始...")
    success = test_database_creation()
    if success:
        print("🎉 データベーステストが正常に完了しました！")
        sys.exit(0)
    else:
        print("❌ データベーステストが失敗しました")
        sys.exit(1)
