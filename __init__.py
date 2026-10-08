"""Add Mistral transport affinity without changing model-visible context."""
from urllib.parse import urlsplit

MISTRAL_HOSTS = frozenset({'api.mistral.ai', 'api.eu.mistral.ai'})


def add_affinity(*, request, base_url='', api_mode='', **context):
    """Reuse Hermes' existing cache key as a Mistral routing hint."""
    endpoint = urlsplit(str(base_url))
    if (api_mode not in ('', 'chat_completions') or endpoint.scheme != 'https'
            or endpoint.hostname not in MISTRAL_HOSTS):
        return None
    key = request.get('prompt_cache_key')
    if not isinstance(key, str) or not key:
        return None
    headers = dict(request.get('extra_headers') or {})
    if any(name.lower() == 'x-affinity' for name in headers):
        return None
    headers['x-affinity'] = key
    return {'request': {**request, 'extra_headers': headers},
            'source': 'mistral-cache-affinity', 'reason': 'stable Mistral cache affinity'}


def register(ctx):
    ctx.register_middleware('llm_request', add_affinity)
