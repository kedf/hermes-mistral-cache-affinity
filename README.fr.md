# hermes-mistral-cache-affinity

Version anglaise : [README.md](README.md)

Plugin Hermes (middleware `llm_request`) qui ajoute l'en-tête `x-affinity`
avec la valeur du `prompt_cache_key` déjà généré par Hermes, uniquement pour
les requêtes HTTPS Chat Completions vers `api.mistral.ai` et
`api.eu.mistral.ai`.

L'objectif est de stabiliser l'affinité de routage côté Mistral pour
favoriser les cache hits de prompt. Avant ce plugin, des sessions Mistral
plafonnaient autour de 25 % de cache hit ; avec le plugin, les sessions
observées atteignent 93–95 % (voir `verification/live-report.json` et les
logs `agent.log` : champ `cache=H/T (P%)`).

## Ce que fait le plugin

- Si la requête est en mode `chat_completions`, en HTTPS, vers un hôte
  Mistral autorisé, et porte une `prompt_cache_key` non vide : il ajoute
  `x-affinity: <prompt_cache_key>` dans `extra_headers`.
- Il ne change **ni** les messages, **ni** les outils, **ni** le prompt
  système, **ni** la clé de cache. La requête originale n'est pas mutée
  (le middleware retourne une copie).
- Un en-tête `x-affinity` explicite (quelle que soit sa casse) est préservé :
  le plugin ne fait rien.
- Sans clé de cache, sur un autre fournisseur, un autre hôte, un schéma
  non-HTTPS ou un autre mode API : le plugin ne fait rien.
- Aucun accès réseau, secret, historique ou journal n'est effectué par le
  plugin ; l'appel réseau reste celui du client Hermes.

## Installation

Copier (ou symlinker) ce dossier dans le répertoire `plugins/` du profil
Hermes concerné :

```bash
cp -r hermes-mistral-cache-affinity ~/.hermes/profiles/<profil>/plugins/
```

Puis activer le plugin dans `config.yaml` du profil :

```yaml
plugins:
  enabled:
    - mistral-cache-affinity
```

Désactivation : `hermes plugins disable mistral-cache-affinity` dans le profil
concerné.

> Ce plugin ne choisit pas l'endpoint : le complément `mistral-eu-endpoint`
> règle le défaut du fournisseur Mistral sur l'EU.

## Limites

- C'est une amélioration du **routage** du cache, pas une garantie de cache
  hit. Une modification du préfixe, une expiration ou un comportement
  fournisseur peut toujours provoquer un cache miss.
- La portée est le middleware `llm_request` de Hermes ; ne pas supposer que
  tout appel auxiliaire emprunte ce middleware.

## Tests

```bash
# Tests unitaires (synthétiques, sans réseau)
python -m unittest discover -s tests -p 'test_affinity.py' -v

# Tests d'intégration (nécessitent un checkout hermes-agent sur sys.path)
python -m unittest tests.test_integration -v

# Test live contre l'API Mistral (opt-in, prompts synthétiques uniquement)
LIVE_MISTRAL_CACHE_TEST=1 \
LIVE_REPORT_PATH=verification/live-report.json \
MISTRAL_API_KEY=... \
python -m unittest tests.test_live -v
```

Les tests live sont opt-in, avec sorties bornées et sans retries
automatiques. Les rapports ne conservent que les compteurs, latences et
empreintes SHA-256 — jamais les clés API ni les conversations.

## Related work

- [fengrunda/hermes-deepseek-cache](https://github.com/fengrunda/hermes-deepseek-cache) —
  même classe de problème (cache hit plafonnant ~25 %) côté DeepSeek, résolu par
  « wire shaping » (retrait de `reasoning_content` des tours sans tool_calls).
  Approche complémentaire : ici le corps de la requête n'est jamais modifié,
  seul l'en-tête `x-affinity` est ajouté.
- Le mécanisme `x-affinity` est un standard inter-harnais : OpenClaw, Pi, Zed et
  d'autres envoient `x-affinity: <sessionId>` à Mistral pour le KV-cache.
  Hermes génère déjà un `prompt_cache_key` (`supports_prompt_cache_key=True`)
  mais ne l'envoyait pas en en-tête ; ce plugin comble ce trou.

## Contexte upstream

Ce plugin répond à un problème connu et documenté dans
`NousResearch/hermes-agent` : invalidation du cache de prompt entre les
tours (préfixe instable, timestamps, ordre des outils, changement de
fournisseur). Voir notamment les issues :

- #27339 — invalidation du KV cache par « dynamic tool shuffling »
- #18547 — préfixe système instable (timestamps, compteurs mémoire)
- #128817 — re-prefill des tours suivants (schémas d'outils qui changent)
- #133575 — cache « stuck » à un plancher fixe sur un provider plugin
- #79602 — laisser un ProviderProfile déclarer sa politique de cache

## Licence

Usage kedf.
