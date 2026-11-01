# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 20.7 | 2047 ms | 4006 ms | 5885 ms | 0.3% (10) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 20.6 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 127 | 1910 ms | 3250 ms | 0.0% |
| add_to_cart | 226 | 3756 ms | 6463 ms | 0.0% |
| cart | 112 | 1889 ms | 3613 ms | 0.0% |
| category | 1034 | 2115 ms | 3778 ms | 0.0% |
| checkout | 9 | 1884 ms | 2761 ms | 0.0% |
| home | 217 | 1754 ms | 3105 ms | 0.0% |
| login | 123 | 3502 ms | 6534 ms | 0.0% |
| login_page | 124 | 1716 ms | 3192 ms | 0.0% |
| logout | 124 | 3371 ms | 6059 ms | 0.0% |
| product | 1471 | 1957 ms | 3483 ms | 0.0% |
| search | 142 | 1934 ms | 3862 ms | 0.0% |
| session | 10 | 0 ms | 0 ms | 100.0% |
