# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 18.9 | 2586 ms | 5152 ms | 9170 ms | 2.9% (100) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 18.3 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 88 | 2385 ms | 4538 ms | 2.3% |
| add_to_cart | 209 | 4753 ms | 9655 ms | 4.3% |
| cart | 97 | 2489 ms | 4880 ms | 1.0% |
| category | 983 | 2644 ms | 5059 ms | 1.9% |
| checkout | 4 | 2663 ms | 5038 ms | 0.0% |
| home | 205 | 2247 ms | 4972 ms | 1.0% |
| login | 92 | 4463 ms | 9428 ms | 0.0% |
| login_page | 96 | 2161 ms | 4045 ms | 4.2% |
| logout | 90 | 4443 ms | 9284 ms | 2.2% |
| product | 1374 | 2430 ms | 4969 ms | 1.8% |
| search | 123 | 2456 ms | 4979 ms | 0.8% |
| session | 35 | 0 ms | 0 ms | 100.0% |
