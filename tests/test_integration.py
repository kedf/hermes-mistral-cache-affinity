import unittest
from copy import deepcopy
from providers import get_provider_profile
from hermes_cli.plugins import discover_plugins
from hermes_cli.middleware import apply_llm_request_middleware

class IntegrationTests(unittest.TestCase):
    def test_provider_default_is_eu_and_native_behavior_preserved(self):
        profile = get_provider_profile('mistral')
        self.assertEqual(profile.base_url, 'https://api.eu.mistral.ai/v1')
        self.assertTrue(profile.supports_prompt_cache_key)
        self.assertEqual(profile.build_api_kwargs_extras(model='zai-glm-5-3',reasoning_config={'enabled':True,'effort':'low'}), ({},{'reasoning_effort':'low'}))
        self.assertEqual(profile.native_reasoning_details_type, 'mistral.native_assistant')

    def test_runtime_resolution_uses_eu_without_changing_codex_default(self):
        from hermes_cli.runtime_provider import resolve_runtime_provider
        runtime=resolve_runtime_provider(requested='mistral', explicit_api_key='synthetic-no-network', target_model='mistral-large-4')
        self.assertEqual(runtime['base_url'].rstrip('/'), 'https://api.eu.mistral.ai/v1')
        self.assertEqual(runtime['provider'], 'mistral')

    def test_real_plugin_discovery_adds_header_for_both_endpoints(self):
        discover_plugins()
        for host in ('api.mistral.ai','api.eu.mistral.ai'):
            request={'model':'mistral-large-4','messages':[{'role':'system','content':'Synthetic'}],'prompt_cache_key':'pck_integration'}
            original=deepcopy(request)
            result=apply_llm_request_middleware(request,base_url=f'https://{host}/v1',provider='mistral',api_mode='chat_completions',session_id='synthetic')
            self.assertEqual(result.payload['extra_headers']['x-affinity'],request['prompt_cache_key'])
            self.assertEqual(request,original)
            self.assertTrue(any(x.get('source')=='mistral-cache-affinity' for x in result.trace))

if __name__=='__main__':unittest.main()
