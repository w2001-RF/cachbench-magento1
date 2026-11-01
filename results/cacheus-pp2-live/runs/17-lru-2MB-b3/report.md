# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 34.3 | 524 ms | 1282 ms | 1821 ms | 32.2% (1987) | 8 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.3 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 129 | 369 ms | 951 ms | 1.6% |
| add_to_cart | 261 | 729 ms | 1784 ms | 6.1% |
| cart | 129 | 468 ms | 1384 ms | 4.7% |
| category | 1160 | 781 ms | 1430 ms | 2.8% |
| checkout | 9 | 544 ms | 1113 ms | 11.1% |
| home | 267 | 234 ms | 788 ms | 2.6% |
| login | 128 | 513 ms | 1214 ms | 3.9% |
| login_page | 130 | 209 ms | 740 ms | 2.3% |
| logout | 128 | 355 ms | 1566 ms | 2.3% |
| product | 1827 | 453 ms | 1081 ms | 3.0% |
| search | 162 | 441 ms | 1511 ms | 5.6% |
| session | 1847 | 0 ms | 0 ms | 100.0% |
