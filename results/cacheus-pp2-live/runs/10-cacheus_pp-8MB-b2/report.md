# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 23.3 | 1793 ms | 3272 ms | 3865 ms | 9.3% (392) | 2 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 21.1 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 104 | 1673 ms | 2162 ms | 4.8% |
| add_to_cart | 249 | 3245 ms | 4030 ms | 1.6% |
| cart | 117 | 1724 ms | 2311 ms | 2.6% |
| category | 1098 | 1861 ms | 2414 ms | 1.0% |
| checkout | 6 | 1500 ms | 1962 ms | 0.0% |
| home | 227 | 1608 ms | 2175 ms | 0.0% |
| login | 109 | 3107 ms | 4026 ms | 3.7% |
| login_page | 106 | 1519 ms | 1937 ms | 0.0% |
| logout | 104 | 2991 ms | 3992 ms | 1.0% |
| product | 1593 | 1716 ms | 2274 ms | 1.4% |
| search | 147 | 1714 ms | 2673 ms | 2.7% |
| session | 338 | 0 ms | 0 ms | 100.0% |
