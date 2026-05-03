"""
LLM Client Wrapper
Unified OpenAI format API calls
Supports Ollama num_ctx parameter to prevent prompt truncation
"""

import json
import os
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI
import logging

from ..config import Config

logger = logging.getLogger(__name__)


def repair_truncated_json(text: str) -> Optional[Dict[str, Any]]:
    """
    尝试修复被截断的JSON字符串。
    
    两阶段策略：
    1. 精确修复：找到最后一个结构完整的安全截断点，关闭括号
    2. 激进修复：剥离末尾不完整的字符串/值，关闭所有括号
    
    Args:
        text: 被截断的JSON字符串
        
    Returns:
        修复后的字典，如果无法修复则返回 None
    """
    if not text or not text.strip():
        return None
    
    text = text.strip()
    
    # 清理 markdown 代码块标记
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()
    
    # 先尝试直接解析（也许已经是有效JSON）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # === 阶段1：精确安全点修复 ===
    # 扫描结构，找到 }, ] 或顶层逗号作为安全截断点
    safe_points = []
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape_next = False
    
    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        
        if ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace -= 1
            safe_points.append(i + 1)
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket -= 1
            safe_points.append(i + 1)
        elif ch == ',' and depth_brace >= 1:
            safe_points.append(i)
    
    # 从最后一个安全点开始尝试
    for point in reversed(safe_points):
        candidate = text[:point].rstrip().rstrip(',')
        result = _try_close_and_parse(candidate)
        if result is not None:
            logger.info(f"JSON repair (phase 1) succeeded at position {point}/{len(text)}")
            return result
    
    # === 阶段2：激进修复 ===
    # 处理截断发生在字符串值中间的情况（如 "description": "A）
    # 策略：从末尾向前找到最后一个完整的 }, 然后关闭括号
    
    for strip_len in range(1, min(len(text), 500)):
        candidate = text[:len(text) - strip_len]
        
        # 尝试在最后一个完整对象/数组闭合符处截断
        last_close = max(candidate.rfind('}'), candidate.rfind(']'))
        if last_close < 0:
            continue
        
        truncated = candidate[:last_close + 1].rstrip().rstrip(',')
        result = _try_close_and_parse(truncated)
        if result is not None:
            logger.info(f"JSON repair (phase 2) succeeded, stripped {strip_len + len(text) - last_close - 1} chars")
            return result
    
    logger.warning("JSON repair failed: no recoverable structure found")
    return None


def _try_close_and_parse(candidate: str) -> Optional[Dict[str, Any]]:
    """
    使用栈追踪未闭合的括号，按正确顺序关闭它们，然后尝试解析。
    
    Returns:
        解析后的字典，或 None
    """
    stack = []
    in_str = False
    esc = False
    
    for ch in candidate:
        if esc:
            esc = False
            continue
        if ch == '\\' and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            stack.append('}')
        elif ch == '[':
            stack.append(']')
        elif ch in ('}', ']'):
            if stack and stack[-1] == ch:
                stack.pop()
    
    if in_str:
        return None
    
    closing = ''.join(reversed(stack))
    repaired = candidate + closing
    
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


class LLMClient:
    """LLM Client"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 300.0
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY not configured")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )

        # Ollama context window size — prevents prompt truncation.
        # Read from env OLLAMA_NUM_CTX, default 8192 (Ollama default is only 2048).
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    @classmethod
    def for_graph_extraction(cls, **overrides) -> 'LLMClient':
        """Create an LLMClient configured for the graph extraction layer.

        Uses GRAPH_LLM_* config (falls back to primary LLM_* if not set).
        Intended for high-volume, structured extraction tasks (NER, ontology).
        """
        return cls(
            api_key=overrides.get('api_key', Config.GRAPH_LLM_API_KEY),
            base_url=overrides.get('base_url', Config.GRAPH_LLM_BASE_URL),
            model=overrides.get('model', Config.GRAPH_LLM_MODEL_NAME),
        )

    def _is_ollama(self) -> bool:
        """Check if we're talking to an Ollama server."""
        return '11434' in (self.base_url or '')

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send chat request

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama() and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        # Some models (like MiniMax M2.5) include <think>thinking content in response, need to remove
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON format from LLM, attempting repair")
            repaired = repair_truncated_json(response)
            if repaired is not None:
                logger.info("JSON repaired successfully")
                return repaired
            raise ValueError(f"Invalid JSON format from LLM and repair failed: {cleaned_response}")
