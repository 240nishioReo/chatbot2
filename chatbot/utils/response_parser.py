import json
import re
from typing import List, Dict, Any

class ResponseParser:
    """Difyレスポンス解析ユーティリティ"""
    
    @staticmethod
    def extract_keyphrases(raw_response_data: List[Dict[Any, Any]]) -> Dict[str, Any]:
        """
        Difyレスポンスからキーフレーズとソース文書を抽出
        
        Args:
            raw_response_data: Dify APIからの生レスポンスデータリスト
        
        Returns:
            Dict: 整理されたキーフレーズと文書データ
        """
        result = {
            'source_documents': [],
            'all_keyphrases': [],
            'document_keyphrases': []
        }
        
        try:
            # message_endイベントからretriever_resourcesを抽出
            for item in raw_response_data:
                if item.get('event') == 'message_end':
                    metadata = item.get('metadata', {})
                    retriever_resources = metadata.get('retriever_resources', [])
                    
                    for i, resource in enumerate(retriever_resources):
                        content = resource.get('content', '')
                        
                        # ソース文書として保存
                        doc_info = {
                            'index': i + 1,
                            'content': content,
                            'content_length': len(content)
                        }
                        result['source_documents'].append(doc_info)
                        
                        # キーフレーズ抽出（\r\nで分割）
                        keyphrases = ResponseParser._extract_keyphrases_from_content(content)
                        
                        doc_keyphrases = {
                            'document_index': i + 1,
                            'keyphrases': keyphrases,
                            'keyphrase_count': len(keyphrases)
                        }
                        result['document_keyphrases'].append(doc_keyphrases)
                        
                        # 全キーフレーズに追加
                        result['all_keyphrases'].extend(keyphrases)
            
            # 重複除去と統計
            result['unique_keyphrases'] = list(set(result['all_keyphrases']))
            result['total_keyphrase_count'] = len(result['all_keyphrases'])
            result['unique_keyphrase_count'] = len(result['unique_keyphrases'])
            
        except Exception as e:
            result['error'] = f"キーフレーズ抽出エラー: {str(e)}"
        
        return result
    
    @staticmethod
    def _extract_keyphrases_from_content(content: str) -> List[str]:
        """
        文書内容から\r\nで区切られたキーフレーズを抽出
        
        Args:
            content: 抽出対象の文書内容
        
        Returns:
            List[str]: 抽出されたキーフレーズリスト
        """
        if not content:
            return []
        
        # \r\nで分割
        phrases = content.split('\r\n')
        
        # 空の文字列や短すぎる文字列を除去、前後の空白を削除
        keyphrases = [
            phrase.strip() 
            for phrase in phrases 
            if phrase.strip() and len(phrase.strip()) > 3
        ]
        
        return keyphrases
    
    @staticmethod
    def format_response_for_display(raw_response_data: List[Dict[Any, Any]]) -> Dict[str, Any]:
        """
        表示用にレスポンスデータを整形
        
        Args:
            raw_response_data: Dify APIからの生レスポンスデータリスト
        
        Returns:
            Dict: 表示用に整形されたデータ
        """
        formatted = {
            'events': [],
            'final_answer': '',
            'conversation_id': '',
            'total_tokens': 0,
            'elapsed_time': 0
        }
        
        try:
            for item in raw_response_data:
                event_type = item.get('event', 'unknown')
                
                # イベント情報を整理
                event_info = {
                    'event': event_type,
                    'timestamp': item.get('created_at', ''),
                    'data': {}
                }
                
                if event_type == 'message':
                    event_info['data'] = {
                        'answer': item.get('answer', ''),
                        'id': item.get('id', '')
                    }
                    formatted['final_answer'] += item.get('answer', '')
                
                elif event_type == 'message_end':
                    event_info['data'] = {
                        'conversation_id': item.get('conversation_id', ''),
                        'usage': item.get('metadata', {}).get('usage', {}),
                        'retriever_resources': item.get('metadata', {}).get('retriever_resources', [])
                    }
                    formatted['conversation_id'] = item.get('conversation_id', '')
                    usage = item.get('metadata', {}).get('usage', {})
                    formatted['total_tokens'] = usage.get('total_tokens', 0)
                
                formatted['events'].append(event_info)
        
        except Exception as e:
            formatted['error'] = f"レスポンス整形エラー: {str(e)}"
        
        return formatted
