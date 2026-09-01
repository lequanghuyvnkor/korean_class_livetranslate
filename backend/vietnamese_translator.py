import urllib.request
import urllib.parse
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VietnameseTranslator")

class VietnameseTranslator:
    @staticmethod
    def translate_to_vietnamese(text: str, source_lang: str = "en") -> str:
        """Translates text (from English or Korean) to Vietnamese with low latency"""
        if not text or not text.strip():
            return ""
            
        clean_text = text.strip()
        
        # Fast Google Translate GTX HTTP endpoint (free, zero API key, ultra-fast)
        try:
            encoded_query = urllib.parse.quote(clean_text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl=vi&dt=t&q={encoded_query}"
            
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            
            with urllib.request.urlopen(req, timeout=1.5) as response:
                result_json = json.loads(response.read().decode("utf-8"))
                
                # result_json[0] contains list of translated sentences
                translated_parts = []
                if result_json and len(result_json) > 0 and result_json[0]:
                    for part in result_json[0]:
                        if part and len(part) > 0 and part[0]:
                            translated_parts.append(part[0])
                            
                vi_text = "".join(translated_parts).strip()
                if vi_text:
                    return vi_text
                    
        except Exception as e:
            # Fallback if offline / no wifi
            logger.debug(f"Online Vietnamese translation fallback: {e}")
            
        return ""
