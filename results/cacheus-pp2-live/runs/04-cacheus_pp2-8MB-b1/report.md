# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 20.1 | 2386 ms | 4416 ms | 5295 ms | 0.5% (19) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 20.0 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 125 | 2220 ms | 3058 ms | 0.0% |
| add_to_cart | 216 | 4297 ms | 5641 ms | 0.0% |
| cart | 110 | 2317 ms | 2802 ms | 0.0% |
| category | 1003 | 2470 ms | 3147 ms | 0.0% |
| checkout | 9 | 2211 ms | 2745 ms | 0.0% |
| home | 211 | 2076 ms | 2648 ms | 0.0% |
| login | 122 | 4183 ms | 5424 ms | 0.0% |
| login_page | 123 | 2042 ms | 2664 ms | 0.0% |
| logout | 120 | 4067 ms | 5267 ms | 0.0% |
| product | 1418 | 2259 ms | 2901 ms | 0.0% |
| search | 137 | 2281 ms | 3306 ms | 0.0% |
| session | 19 | 0 ms | 0 ms | 100.0% |
