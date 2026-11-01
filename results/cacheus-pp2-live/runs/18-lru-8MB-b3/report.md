# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 35.3 | 459 ms | 1123 ms | 1556 ms | 36.2% (2300) | 10 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 22.5 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 120 | 343 ms | 1010 ms | 2.5% |
| add_to_cart | 263 | 649 ms | 1486 ms | 6.8% |
| cart | 128 | 419 ms | 1015 ms | 6.2% |
| category | 1181 | 663 ms | 1239 ms | 7.1% |
| checkout | 8 | 479 ms | 880 ms | 0.0% |
| home | 258 | 224 ms | 726 ms | 4.7% |
| login | 122 | 467 ms | 1024 ms | 4.9% |
| login_page | 125 | 179 ms | 455 ms | 7.2% |
| logout | 119 | 321 ms | 1005 ms | 5.9% |
| product | 1824 | 416 ms | 1031 ms | 5.4% |
| search | 165 | 377 ms | 1377 ms | 4.2% |
| session | 2047 | 0 ms | 0 ms | 100.0% |
