from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class DifyApp(db.Model):
    """Difyアプリケーション管理"""
    __tablename__ = 'dify_apps'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    api_key_env_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    conversations = db.relationship('Conversation', backref='dify_app', lazy=True)
    
    def __repr__(self):
        return f'<DifyApp {self.name}>'

class Conversation(db.Model):
    """会話セッション管理"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    dify_app_id = db.Column(db.Integer, db.ForeignKey('dify_apps.id'), nullable=False)
    dify_conversation_id = db.Column(db.String(100))  # Dify側のconversation_id
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Conversation {self.title}>'

class Message(db.Model):
    """個別メッセージ管理"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    raw_dify_response = db.Column(db.Text)  # Raw JSON response from Dify
    keyphrase_data = db.Column(db.Text)  # 抽出されたキーフレーズデータ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.role}: {self.content[:50]}...>'
