# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 26.9 | 861 ms | 1862 ms | 2375 ms | 11.4% (554) | 3 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.9 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 130 | 708 ms | 1511 ms | 1.5% |
| add_to_cart | 250 | 1260 ms | 2327 ms | 3.6% |
| cart | 134 | 738 ms | 1481 ms | 2.2% |
| category | 1289 | 1074 ms | 2045 ms | 3.7% |
| checkout | 12 | 734 ms | 1539 ms | 0.0% |
| home | 272 | 613 ms | 1331 ms | 3.3% |
| login | 138 | 1171 ms | 2436 ms | 3.6% |
| login_page | 144 | 474 ms | 1137 ms | 3.5% |
| logout | 132 | 1026 ms | 2013 ms | 2.3% |
| product | 1736 | 756 ms | 1574 ms | 2.2% |
| search | 188 | 768 ms | 2031 ms | 3.2% |
| session | 425 | 0 ms | 0 ms | 100.0% |
