# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 24.5 | 1545 ms | 2959 ms | 3637 ms | 9.5% (418) | 2 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 22.2 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 127 | 1361 ms | 1940 ms | 4.7% |
| add_to_cart | 229 | 2816 ms | 3859 ms | 2.6% |
| cart | 119 | 1466 ms | 1976 ms | 2.5% |
| category | 1155 | 1648 ms | 2315 ms | 2.2% |
| checkout | 6 | 1684 ms | 2091 ms | 0.0% |
| home | 263 | 1380 ms | 1897 ms | 4.6% |
| login | 117 | 2350 ms | 3573 ms | 1.7% |
| login_page | 114 | 1169 ms | 1842 ms | 0.0% |
| logout | 132 | 2481 ms | 3618 ms | 3.8% |
| product | 1664 | 1436 ms | 2072 ms | 1.9% |
| search | 164 | 1418 ms | 2519 ms | 3.7% |
| session | 321 | 0 ms | 0 ms | 100.0% |
