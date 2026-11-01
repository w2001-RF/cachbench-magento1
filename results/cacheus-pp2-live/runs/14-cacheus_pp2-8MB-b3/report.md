# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 22.1 | 1968 ms | 3734 ms | 5030 ms | 6.6% (262) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 20.6 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 100 | 1700 ms | 2782 ms | 2.0% |
| add_to_cart | 213 | 3599 ms | 5562 ms | 3.3% |
| cart | 95 | 1822 ms | 2868 ms | 1.1% |
| category | 1068 | 2058 ms | 3259 ms | 1.9% |
| checkout | 8 | 1814 ms | 2605 ms | 0.0% |
| home | 247 | 1816 ms | 2942 ms | 0.8% |
| login | 111 | 3554 ms | 5666 ms | 6.3% |
| login_page | 108 | 1625 ms | 2746 ms | 0.0% |
| logout | 101 | 3376 ms | 4954 ms | 3.0% |
| product | 1560 | 1875 ms | 2959 ms | 1.4% |
| search | 168 | 1744 ms | 3151 ms | 0.6% |
| session | 197 | 0 ms | 0 ms | 100.0% |
