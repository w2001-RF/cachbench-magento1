# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 33.8 | 522 ms | 1328 ms | 1779 ms | 30.0% (1826) | 10 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.7 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 146 | 368 ms | 996 ms | 3.4% |
| add_to_cart | 274 | 671 ms | 1611 ms | 4.7% |
| cart | 135 | 430 ms | 1297 ms | 2.2% |
| category | 1208 | 791 ms | 1506 ms | 4.7% |
| checkout | 15 | 627 ms | 1842 ms | 0.0% |
| home | 249 | 228 ms | 857 ms | 3.2% |
| login | 146 | 501 ms | 908 ms | 6.2% |
| login_page | 146 | 188 ms | 498 ms | 4.1% |
| logout | 145 | 344 ms | 1137 ms | 2.8% |
| product | 1810 | 445 ms | 1031 ms | 3.6% |
| search | 168 | 411 ms | 1571 ms | 4.8% |
| session | 1648 | 0 ms | 0 ms | 100.0% |
