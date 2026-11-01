# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 33.1 | 492 ms | 1133 ms | 1583 ms | 28.3% (1688) | 8 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.7 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 149 | 388 ms | 958 ms | 2.0% |
| add_to_cart | 276 | 678 ms | 1452 ms | 4.3% |
| cart | 118 | 435 ms | 1284 ms | 2.5% |
| category | 1197 | 758 ms | 1327 ms | 5.5% |
| checkout | 9 | 532 ms | 1590 ms | 11.1% |
| home | 255 | 229 ms | 512 ms | 2.0% |
| login | 147 | 478 ms | 895 ms | 4.8% |
| login_page | 143 | 187 ms | 435 ms | 1.4% |
| logout | 146 | 335 ms | 1089 ms | 1.4% |
| product | 1846 | 427 ms | 915 ms | 3.6% |
| search | 162 | 368 ms | 1607 ms | 3.7% |
| session | 1515 | 0 ms | 0 ms | 100.0% |
