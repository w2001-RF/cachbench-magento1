# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 12.3 | 6259 ms | 11969 ms | 12847 ms | 0.0% (0) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 12.3 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 64 | 5940 ms | 6718 ms | 0.0% |
| add_to_cart | 122 | 12172 ms | 13313 ms | 0.0% |
| cart | 66 | 6294 ms | 7024 ms | 0.0% |
| category | 671 | 6432 ms | 7375 ms | 0.0% |
| checkout | 6 | 6273 ms | 7426 ms | 0.0% |
| home | 139 | 5824 ms | 6589 ms | 0.0% |
| login | 67 | 11397 ms | 12638 ms | 0.0% |
| login_page | 73 | 5773 ms | 6687 ms | 0.0% |
| logout | 64 | 11647 ms | 12411 ms | 0.0% |
| product | 846 | 6032 ms | 6886 ms | 0.0% |
| search | 94 | 6054 ms | 7085 ms | 0.0% |
