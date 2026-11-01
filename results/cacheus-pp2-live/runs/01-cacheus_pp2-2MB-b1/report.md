# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 21.9 | 1735 ms | 3097 ms | 4149 ms | 1.9% (76) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 21.5 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 131 | 1418 ms | 2562 ms | 0.8% |
| add_to_cart | 230 | 2775 ms | 4475 ms | 1.3% |
| cart | 126 | 1678 ms | 2404 ms | 3.2% |
| category | 1081 | 1992 ms | 2981 ms | 1.1% |
| checkout | 10 | 1488 ms | 2177 ms | 0.0% |
| home | 231 | 1350 ms | 2360 ms | 0.0% |
| login | 131 | 2593 ms | 4239 ms | 0.0% |
| login_page | 133 | 1318 ms | 2304 ms | 0.0% |
| logout | 128 | 2574 ms | 3914 ms | 0.8% |
| product | 1558 | 1559 ms | 2500 ms | 0.8% |
| search | 149 | 1664 ms | 3151 ms | 1.3% |
| session | 40 | 0 ms | 0 ms | 100.0% |
