# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 34.7 | 525 ms | 1315 ms | 2263 ms | 32.4% (2026) | 9 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.5 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 134 | 357 ms | 1034 ms | 3.0% |
| add_to_cart | 274 | 671 ms | 1741 ms | 5.5% |
| cart | 141 | 447 ms | 1422 ms | 7.1% |
| category | 1192 | 780 ms | 1588 ms | 5.0% |
| checkout | 9 | 530 ms | 984 ms | 22.2% |
| home | 241 | 247 ms | 682 ms | 0.4% |
| login | 139 | 481 ms | 1194 ms | 3.6% |
| login_page | 135 | 211 ms | 626 ms | 0.0% |
| logout | 135 | 339 ms | 960 ms | 2.2% |
| product | 1833 | 445 ms | 1027 ms | 3.4% |
| search | 166 | 410 ms | 2082 ms | 2.4% |
| session | 1859 | 0 ms | 0 ms | 100.0% |
