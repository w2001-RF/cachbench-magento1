# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 35.4 | 463 ms | 1179 ms | 1689 ms | 34.4% (2193) | 12 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.2 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 139 | 337 ms | 911 ms | 3.6% |
| add_to_cart | 243 | 645 ms | 1563 ms | 7.4% |
| cart | 119 | 413 ms | 830 ms | 0.8% |
| category | 1190 | 672 ms | 1311 ms | 6.6% |
| checkout | 9 | 678 ms | 1020 ms | 11.1% |
| home | 246 | 212 ms | 920 ms | 1.6% |
| login | 130 | 451 ms | 954 ms | 3.8% |
| login_page | 125 | 185 ms | 587 ms | 1.6% |
| logout | 138 | 322 ms | 1157 ms | 4.3% |
| product | 1837 | 414 ms | 1060 ms | 2.9% |
| search | 181 | 400 ms | 1448 ms | 4.4% |
| session | 2011 | 0 ms | 0 ms | 100.0% |
