# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 34.0 | 539 ms | 1321 ms | 1820 ms | 33.6% (2052) | 10 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 22.6 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 140 | 395 ms | 983 ms | 5.0% |
| add_to_cart | 254 | 702 ms | 1861 ms | 11.4% |
| cart | 112 | 461 ms | 1221 ms | 3.6% |
| category | 1213 | 781 ms | 1411 ms | 5.8% |
| checkout | 12 | 659 ms | 1161 ms | 0.0% |
| home | 236 | 245 ms | 759 ms | 4.7% |
| login | 133 | 516 ms | 1269 ms | 7.5% |
| login_page | 136 | 193 ms | 699 ms | 4.4% |
| logout | 140 | 376 ms | 1358 ms | 6.4% |
| product | 1769 | 452 ms | 1063 ms | 5.7% |
| search | 173 | 404 ms | 1565 ms | 4.0% |
| session | 1798 | 0 ms | 0 ms | 100.0% |
