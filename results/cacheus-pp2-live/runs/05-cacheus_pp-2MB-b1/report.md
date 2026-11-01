# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 12.3 | 6213 ms | 11783 ms | 12783 ms | 0.0% (0) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 12.3 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 75 | 5768 ms | 6845 ms | 0.0% |
| add_to_cart | 133 | 11538 ms | 13139 ms | 0.0% |
| cart | 71 | 6288 ms | 6785 ms | 0.0% |
| category | 606 | 6390 ms | 7322 ms | 0.0% |
| checkout | 4 | 6655 ms | 7091 ms | 0.0% |
| home | 136 | 5754 ms | 6518 ms | 0.0% |
| login | 72 | 11575 ms | 12932 ms | 0.0% |
| login_page | 76 | 5642 ms | 6715 ms | 0.0% |
| logout | 72 | 11315 ms | 12405 ms | 0.0% |
| product | 887 | 6014 ms | 6986 ms | 0.0% |
| search | 83 | 5922 ms | 7586 ms | 0.0% |
