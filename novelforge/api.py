from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AIResult:
    content: str
    usage: dict[str, Any]
    raw: Any = None


class DeepSeekClient:
    def __init__(self, cfg):
        self.cfg = cfg

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url, timeout=self.cfg.timeout_seconds)

    @staticmethod
    def parse_json(text: str):
        text = (text or '').strip()
        try:
            return json.loads(text)
        except Exception as original:
            candidates = []
            m = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.S | re.I)
            if m:
                candidates.append(m.group(1))
            for opener, closer in [('{', '}'), ('[', ']')]:
                a, b = text.find(opener), text.rfind(closer)
                if a >= 0 and b > a:
                    candidates.append(text[a:b + 1])
            for raw in candidates:
                try:
                    return json.loads(raw)
                except Exception:
                    continue
            raise ValueError(f'AI 返回内容不是合法 JSON：{original}') from original

    def request_kwargs(self, system: str, user: str, json_mode: bool = False) -> dict[str, Any]:
        # DeepSeek 当前 thinking 模式支持 reasoning_effort 与 extra_body.thinking；temperature
        # 在 thinking 模式下不会生效，因此避免把它伪装成有效参数。见官方 API 文档。
        body: dict[str, Any] = {
            'model': self.cfg.model,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'stream': False,
            'max_tokens': int(self.cfg.max_tokens),
        }
        if json_mode:
            body['response_format'] = {'type': 'json_object'}
        if self.cfg.thinking:
            body['reasoning_effort'] = self.cfg.reasoning_effort
            body['extra_body'] = {'thinking': {'type': 'enabled'}}
            body['top_p'] = max(0.95, min(1.0, float(self.cfg.top_p)))
        else:
            body['extra_body'] = {'thinking': {'type': 'disabled'}}
            body['temperature'] = max(0.0, min(2.0, float(self.cfg.temperature)))
            body['top_p'] = max(0.0, min(1.0, float(self.cfg.top_p)))
        return body

    def call(self, system, user, json_mode=False, cancel: Callable[[], bool] | None = None):
        if not self.cfg.api_key.strip():
            raise RuntimeError('尚未填写 DeepSeek API Key。')
        k = self.request_kwargs(system, user, json_mode)
        last = None
        attempts = max(1, int(self.cfg.retry_times))
        for a in range(attempts):
            if cancel and cancel():
                raise RuntimeError('任务已取消')
            try:
                r = self._client().chat.completions.create(**k)
                content = r.choices[0].message.content or ''
                if not content.strip():
                    raise RuntimeError('DeepSeek 返回空内容。')
                if json_mode:
                    self.parse_json(content)
                u = getattr(r, 'usage', None)
                usage = u.model_dump() if hasattr(u, 'model_dump') else {}
                return AIResult(content, usage, r)
            except Exception as e:
                last = e
                if a + 1 >= attempts:
                    break
                # 可取消的退避等待，避免长时间重试时 UI 僵死。
                for _ in range(min(20, 2 ** a * 4)):
                    if cancel and cancel():
                        raise RuntimeError('任务已取消')
                    time.sleep(0.25)
        raise RuntimeError(f'DeepSeek API 调用失败：{last}')

    def json(self, system, user, cancel=None):
        return self.call(system, user, True, cancel)

    def text(self, system, user, cancel=None):
        return self.call(system, user, False, cancel)
