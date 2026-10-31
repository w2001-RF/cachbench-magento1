# Test de charge — http://127.0.0.1/magento

Paliers de 60 s (10 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 1.8 | 169 ms | 489 ms | 602 ms | 1.1% (1) | 1 | **ne tient pas** |
| 25 | 4.7 | 181 ms | 517 ms | 706 ms | 1.7% (4) | 2 | **ne tient pas** |
| 50 | 9.4 | 253 ms | 634 ms | 920 ms | 4.7% (22) | 3 | **ne tient pas** |
| 100 | 18.9 | 181 ms | 632 ms | 889 ms | 36.3% (343) | 10 | **ne tient pas** |
| 150 | 28.3 | 225 ms | 795 ms | 1066 ms | 36.1% (510) | 10 | **ne tient pas** |
| 200 | 38.3 | 360 ms | 1869 ms | 2409 ms | 40.6% (777) | 6 | **ne tient pas** |
| 300 | 73.8 | 6945 ms | 13553 ms | 17248 ms | 96.3% (3721) | 7 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 10, ne tient pas)
**Débit maximal sans erreur** : 22.8 pages/s, à 200 visiteurs.

## Par type de page (palier de 300 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 10 | 7439 ms | 10858 ms | 0.0% |
| add_to_cart | 6 | 16647 ms | 17297 ms | 16.7% |
| cart | 9 | 6246 ms | 9501 ms | 0.0% |
| category | 70 | 6399 ms | 9652 ms | 34.3% |
| home | 27 | 6990 ms | 10485 ms | 3.7% |
| login | 3 | 5303 ms | 7981 ms | 0.0% |
| login_page | 9 | 6932 ms | 9953 ms | 22.2% |
| logout | 10 | 12220 ms | 17501 ms | 0.0% |
| product | 47 | 6975 ms | 11130 ms | 53.2% |
| search | 6 | 7184 ms | 9107 ms | 33.3% |
| session | 3666 | 0 ms | 0 ms | 100.0% |
