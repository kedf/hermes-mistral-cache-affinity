import copy
import importlib.util
from pathlib import Path
import unittest

PLUGIN = Path(__file__).parent.parent / '__init__.py'
def load_plugin():
    spec = importlib.util.spec_from_file_location('affinity_plugin_test', PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class AffinityTests(unittest.TestCase):
    def test_add_affinity_for_both_endpoints_without_mutating_request(self):
        plugin = load_plugin()
        for host in ('api.mistral.ai', 'api.eu.mistral.ai'):
            with self.subTest(host=host):
                request = {'model':'mistral-large-4','messages':[{'role':'system','content':'Synthetic'}], 'tools':[], 'prompt_cache_key':'pck_synthetic', 'extra_headers':{'existing':'value'}}
                original = copy.deepcopy(request)
                result = plugin.add_affinity(request=request, base_url=f'https://{host}/v1', api_mode='chat_completions')
                self.assertIsNotNone(result, 'Mistral request must receive affinity')
                self.assertEqual(result['request']['extra_headers']['x-affinity'], 'pck_synthetic')
                self.assertEqual(request, original)
                self.assertEqual({k:v for k,v in result['request'].items() if k != 'extra_headers'}, {k:v for k,v in original.items() if k != 'extra_headers'})
                self.assertEqual(result['request']['extra_headers']['existing'], 'value')

    def test_preserve_explicit_affinity_case_insensitively(self):
        plugin = load_plugin()
        for header in ('x-affinity', 'X-Affinity'):
            request = {'prompt_cache_key':'pck_synthetic','extra_headers':{header:'operator-affinity'}}
            self.assertIsNone(plugin.add_affinity(request=request, base_url='https://api.eu.mistral.ai/v1', api_mode='chat_completions'))

    def test_skip_other_hosts_modes_and_missing_keys(self):
        plugin = load_plugin()
        for url, mode, key in [
            ('https://api.openai.com/v1','chat_completions','key'),
            ('https://api.mistral.ai.evil.example/v1','chat_completions','key'),
            ('http://api.mistral.ai/v1','chat_completions','key'),
            ('https://api.eu.mistral.ai/v1','codex_responses','key'),
            ('https://api.eu.mistral.ai/v1','chat_completions',None),
            ('https://api.eu.mistral.ai/v1','chat_completions',''),
        ]:
            with self.subTest(url=url, mode=mode, key=key):
                self.assertIsNone(plugin.add_affinity(request={'prompt_cache_key':key},base_url=url,api_mode=mode))

if __name__ == '__main__': unittest.main()
