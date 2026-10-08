"""Opt-in live test using only synthetic prompts and numeric telemetry."""
import hashlib
import json
import os
from pathlib import Path
import time
import unittest
import uuid

@unittest.skipUnless(os.environ.get('LIVE_MISTRAL_CACHE_TEST') == '1', 'Live API test not requested')
class LiveCacheTests(unittest.TestCase):
    def test_live_on_both_endpoints(self):
        import httpx
        from providers import get_provider_profile
        from hermes_cli.plugins import discover_plugins
        from hermes_cli.middleware import apply_llm_request_middleware
        from agent.transports.chat_completions import _add_prompt_cache_key
        key=os.environ['MISTRAL_API_KEY']
        discover_plugins()
        profile=get_provider_profile('mistral')
        report={'model':'mistral-large-4','synthetic_only':True,'endpoints':{}}
        report_path=Path(os.environ['LIVE_REPORT_PATH'])
        digest=lambda value:hashlib.sha256(value).hexdigest()
        for host in ('api.eu.mistral.ai','api.mistral.ai'):
            base_url=f'https://{host}/v1'
            endpoint_report={'calls':[],'wire':[]}
            report['endpoints'][host]=endpoint_report
            def observe_request(request):
                body=json.loads(request.content)
                entry={'host':request.url.host,'path':request.url.path,'body_sha256':digest(request.content),'messages_sha256':digest(json.dumps(body['messages'],sort_keys=True).encode()),'cache_key_sha256':digest(body['prompt_cache_key'].encode()),'affinity_matches_key':request.headers.get('x-affinity')==body['prompt_cache_key']}
                endpoint_report['wire'].append(entry)
            client=profile.create_client(api_key=key,base_url=base_url,max_retries=0,timeout=60,http_client=httpx.Client(event_hooks={'request':[observe_request]}))
            session_id='synthetic-cache-'+uuid.uuid4().hex
            text='\n'.join(f'Record {i:04d}: Synthetic cache probe. The blue square stays still; the green circle moves north.' for i in range(180))+'\nReply only OK.'
            messages=[{'role':'system','content':'Synthetic prompt-cache test. No tools. Reply only OK. Probe '+session_id},{'role':'user','content':text}]
            request={'model':'mistral-large-4','messages':messages,'max_tokens':8,'temperature':0,'top_p':1}
            _add_prompt_cache_key(request,messages=messages,tools=None,supports_prompt_cache_key=profile.supports_prompt_cache_key,session_id=session_id)
            effective=apply_llm_request_middleware(request,provider='mistral',base_url=base_url,api_mode='chat_completions',session_id=session_id)
            self.assertTrue(any(x.get('source')=='mistral-cache-affinity' for x in effective.trace))
            try:
                for i in range(6):
                    start=time.monotonic()
                    response=client.chat.completions.create(**effective.payload)
                    usage=response.usage.model_dump()
                    cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens') or 0
                    item={'call':i+1,'prompt_tokens':usage['prompt_tokens'],'cached_tokens':cached,'completion_tokens':usage['completion_tokens'],'cache_pct':round(100*cached/usage['prompt_tokens'],2),'elapsed_ms':round((time.monotonic()-start)*1000)}
                    endpoint_report['calls'].append(item)
                    report_path.write_text(json.dumps(report,indent=2))
                    print('LIVE_CACHE '+json.dumps({'host':host,**item}),flush=True)
                self.assertEqual(len(endpoint_report['wire']),6)
                self.assertTrue(all(x['affinity_matches_key'] for x in endpoint_report['wire']))
                self.assertEqual(len(set(x['body_sha256'] for x in endpoint_report['wire'])),1)
                self.assertTrue(any(x['cached_tokens']>0 for x in endpoint_report['calls'][1:]),'No cache reuse observed')
            finally:
                client.close()
                report_path.write_text(json.dumps(report,indent=2))

if __name__=='__main__':unittest.main()
