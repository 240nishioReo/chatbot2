import requests
import json
import logging
from typing import Generator, Dict, Any

logger = logging.getLogger(__name__)

class DifyClient:
    """Dify API ストリーミングクライアント"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.dify.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def stream_chat(self, message: str, conversation_id: str = None) -> Generator[Dict[Any, Any], None, None]:
        """
        Dify APIでストリーミングチャットを実行
        
        Args:
            message: ユーザーメッセージ
            conversation_id: 継続する会話のID（初回はNone）
        
        Yields:
            Dict: パースされたレスポンスデータ
        """
        url = f"{self.base_url}/chat-messages"
        
        payload = {
            "query": message,
            "inputs": {},
            "user": "user-session",
            "response_mode": "streaming"
        }
        
        # 会話継続の場合
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        logger.info(f"Dify API リクエスト: {payload}")
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                stream=True,
                timeout=30
            )
            
            response.raise_for_status()
            
            buffer = ""
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    buffer += chunk
                    lines = buffer.split('\n')
                    buffer = lines.pop()  # 最後の不完全な行は保持
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('data: '):
                            data_content = line[6:]  # "data: " を除去
                            
                            if data_content == '[DONE]':
                                logger.info("ストリーミング完了")
                                return
                            
                            try:
                                parsed_data = json.loads(data_content)
                                logger.debug(f"受信データ: {parsed_data}")
                                yield parsed_data
                                
                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON解析エラー: {e}, データ: {data_content}")
                                continue
            
            # 残りのバッファ処理
            if buffer.strip():
                if buffer.strip().startswith('data: '):
                    data_content = buffer.strip()[6:]
                    if data_content != '[DONE]':
                        try:
                            parsed_data = json.loads(data_content)
                            yield parsed_data
                        except json.JSONDecodeError:
                            pass
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Dify API リクエストエラー: {e}")
            raise Exception(f"Dify API 接続エラー: {str(e)}")
        
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            raise Exception(f"チャット処理エラー: {str(e)}")
