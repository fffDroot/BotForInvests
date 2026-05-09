import aiohttp
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class LLMProvider:
    async def analyze(self, api_key: str, news_text: str) -> Dict[str, Any]:
        raise NotImplementedError

class OpenAIProvider(LLMProvider):
    async def analyze(self, api_key: str, news_text: str) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        prompt = f"Ты финансовый аналитик. Прочитай следующие мировые новости и ответь СТРОГО в формате JSON: {{\"sentiment\": \"positive\" | \"negative\" | \"neutral\", \"confidence\": от 0.0 до 1.0, \"reasoning\": \"краткое объяснение\"}}. Новости: {news_text}"
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data['choices'][0]['message']['content']
                        import json
                        try:
                            # Try to parse json from text
                            start_idx = content.find('{')
                            end_idx = content.rfind('}') + 1
                            if start_idx != -1 and end_idx != -1:
                                return json.loads(content[start_idx:end_idx])
                        except json.JSONDecodeError:
                            pass
                        return {"sentiment": "neutral", "confidence": 0.5, "reasoning": "Failed to parse JSON."}
                    else:
                        logger.error(f"OpenAI error: {await resp.text()}")
            except Exception as e:
                logger.error(f"OpenAI connection error: {e}")
        return None

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, url: str, model: str):
        self.url = url
        self.model = model

    async def analyze(self, api_key: str, news_text: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        prompt = f"Ты финансовый аналитик. Прочитай следующие мировые новости и ответь СТРОГО в формате JSON: {{\"sentiment\": \"positive\" | \"negative\" | \"neutral\", \"confidence\": от 0.0 до 1.0, \"reasoning\": \"краткое объяснение\"}}. Новости: {news_text}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.url, headers=headers, json=payload, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data['choices'][0]['message']['content']
                        import json
                        try:
                            start_idx = content.find('{')
                            end_idx = content.rfind('}') + 1
                            if start_idx != -1 and end_idx != -1:
                                return json.loads(content[start_idx:end_idx])
                        except json.JSONDecodeError:
                            pass
                        return {"sentiment": "neutral", "confidence": 0.5, "reasoning": "Failed to parse JSON."}
                    else:
                        logger.error(f"LLM API error ({self.url}): {await resp.text()}")
            except Exception as e:
                logger.error(f"LLM Connection error ({self.url}): {e}")
        return None

# Mapping names to instances of providers
PROVIDERS = {
    "openai": OpenAICompatibleProvider("https://api.openai.com/v1/chat/completions", "gpt-3.5-turbo"),
    "deepseek": OpenAICompatibleProvider("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
    "groq": OpenAICompatibleProvider("https://api.groq.com/openai/v1/chat/completions", "llama3-70b-8192"),
    # Anthropic, Gemini and others require slightly different formats,
    # but many gateways exist. For MVP, we route them through standard wrappers if needed,
    # or treat them as OpenAI compatible if user uses a proxy (like OpenRouter).
    "openrouter": OpenAICompatibleProvider("https://openrouter.ai/api/v1/chat/completions", "anthropic/claude-3-haiku"),
}

class LLMCouncil:
    def __init__(self, api_keys: List[Dict[str, str]]):
        """
        api_keys format: [{'provider': 'openai', 'key': 'sk-...'}, ...]
        """
        self.api_keys = api_keys

    async def get_council_decision(self, news_text: str) -> Dict[str, Any]:
        if not self.api_keys:
            return {"sentiment": "neutral", "score": 0.0, "reasoning": "No LLMs connected."}

        tasks = []
        providers_used = []
        for key_info in self.api_keys:
            provider_name = key_info['provider'].lower()
            if provider_name in PROVIDERS:
                provider_inst = PROVIDERS[provider_name]
                tasks.append(provider_inst.analyze(key_info['key'], news_text))
                providers_used.append(provider_name)
            else:
                # Fallback: assume user provided a custom base URL as provider name,
                # or just fallback to openrouter as a generic OpenAI compatible endpoint
                provider_inst = OpenAICompatibleProvider("https://openrouter.ai/api/v1/chat/completions", "auto")
                tasks.append(provider_inst.analyze(key_info['key'], news_text))
                providers_used.append("custom_" + provider_name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception) or res is None:
                 logger.error(f"Provider failed: {res}")
            else:
                 res['provider'] = providers_used[i]
                 valid_results.append(res)

        if not valid_results:
             return {"sentiment": "neutral", "score": 0.0, "reasoning": "All LLMs failed."}

        # Voting logic
        sentiment_scores = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
        total_score = 0.0
        total_confidence = 0.0

        council_reasoning = "Консилиум решил:\n"

        for res in valid_results:
            sent = res.get('sentiment', 'neutral')
            conf = float(res.get('confidence', 0.5))
            val = sentiment_scores.get(sent, 0.0)

            total_score += val * conf
            total_confidence += conf
            council_reasoning += f"- {res['provider'].upper()}: {sent} (уверенность {conf}). Причина: {res.get('reasoning', '')}\n"

        avg_score = total_score / total_confidence if total_confidence > 0 else 0.0

        if avg_score > 0.2:
            final_label = "positive"
        elif avg_score < -0.2:
            final_label = "negative"
        else:
            final_label = "neutral"

        return {
            "sentiment": final_label,
            "score": avg_score,
            "reasoning": council_reasoning,
            "council_size": len(valid_results)
        }
