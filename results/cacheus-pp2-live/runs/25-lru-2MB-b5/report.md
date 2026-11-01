# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 34.0 | 540 ms | 1297 ms | 1837 ms | 31.9% (1955) | 10 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 23.1 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 125 | 394 ms | 1038 ms | 1.6% |
| add_to_cart | 260 | 721 ms | 1715 ms | 6.5% |
| cart | 133 | 429 ms | 1405 ms | 6.8% |
| category | 1244 | 788 ms | 1471 ms | 3.9% |
| checkout | 7 | 543 ms | 999 ms | 0.0% |
| home | 260 | 255 ms | 1090 ms | 4.2% |
| login | 132 | 537 ms | 1142 ms | 9.1% |
| login_page | 131 | 204 ms | 581 ms | 3.8% |
| logout | 123 | 364 ms | 1068 ms | 8.9% |
| product | 1790 | 442 ms | 1109 ms | 3.8% |
| search | 162 | 391 ms | 1556 ms | 6.2% |
| session | 1761 | 0 ms | 0 ms | 100.0% |
