# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 30.4 | 925 ms | 2021 ms | 2758 ms | 24.6% (1348) | 5 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 22.9 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 118 | 694 ms | 1640 ms | 3.4% |
| add_to_cart | 275 | 1340 ms | 2754 ms | 5.5% |
| cart | 133 | 837 ms | 1858 ms | 4.5% |
| category | 1214 | 1187 ms | 2112 ms | 3.5% |
| checkout | 8 | 1318 ms | 2321 ms | 0.0% |
| home | 235 | 679 ms | 1919 ms | 4.7% |
| login | 116 | 1101 ms | 2667 ms | 2.6% |
| login_page | 112 | 582 ms | 1445 ms | 0.0% |
| logout | 123 | 1026 ms | 2580 ms | 6.5% |
| product | 1774 | 809 ms | 1625 ms | 3.1% |
| search | 167 | 694 ms | 1832 ms | 0.6% |
| session | 1203 | 0 ms | 0 ms | 100.0% |
