# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 34.0 | 466 ms | 1213 ms | 1795 ms | 31.0% (1901) | 10 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.5 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 137 | 336 ms | 943 ms | 3.6% |
| add_to_cart | 268 | 613 ms | 1642 ms | 3.4% |
| cart | 148 | 390 ms | 1061 ms | 1.4% |
| category | 1213 | 685 ms | 1364 ms | 4.6% |
| checkout | 12 | 547 ms | 1010 ms | 0.0% |
| home | 239 | 220 ms | 1061 ms | 1.7% |
| login | 126 | 465 ms | 835 ms | 6.3% |
| login_page | 128 | 192 ms | 497 ms | 4.7% |
| logout | 135 | 336 ms | 1193 ms | 3.0% |
| product | 1827 | 408 ms | 1164 ms | 4.7% |
| search | 178 | 379 ms | 1605 ms | 5.1% |
| session | 1712 | 0 ms | 0 ms | 100.0% |
