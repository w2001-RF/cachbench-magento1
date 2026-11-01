# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 36.7 | 487 ms | 1221 ms | 1793 ms | 39.5% (2613) | 11 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 22.2 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 121 | 353 ms | 1071 ms | 7.4% |
| add_to_cart | 287 | 630 ms | 1555 ms | 6.3% |
| cart | 142 | 423 ms | 932 ms | 7.0% |
| category | 1176 | 699 ms | 1367 ms | 6.9% |
| checkout | 12 | 645 ms | 1223 ms | 0.0% |
| home | 239 | 235 ms | 832 ms | 6.7% |
| login | 125 | 500 ms | 1187 ms | 5.6% |
| login_page | 122 | 188 ms | 523 ms | 0.8% |
| logout | 121 | 359 ms | 1347 ms | 3.3% |
| product | 1756 | 422 ms | 1008 ms | 5.5% |
| search | 144 | 396 ms | 1437 ms | 4.9% |
| session | 2364 | 0 ms | 0 ms | 100.0% |
