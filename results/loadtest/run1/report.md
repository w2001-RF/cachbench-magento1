# Test de charge — http://127.0.0.1/magento

Paliers de 60 s (10 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 1.8 | 250 ms | 475 ms | 538 ms | 0.0% (0) | 0 | tient |
| 25 | 4.5 | 293 ms | 531 ms | 866 ms | 6.2% (14) | 4 | **ne tient pas** |

**Limite** : 10 visiteurs simultanés (le palier suivant, 25, ne tient pas)
**Débit maximal sans erreur** : 4.3 pages/s, à 25 visiteurs.

## Par type de page (palier de 25 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 5 | 323 ms | 390 ms | 0.0% |
| add_to_cart | 16 | 441 ms | 487 ms | 18.8% |
| cart | 1 | 274 ms | 274 ms | 0.0% |
| category | 65 | 415 ms | 556 ms | 4.6% |
| home | 11 | 155 ms | 420 ms | 0.0% |
| login | 7 | 373 ms | 439 ms | 0.0% |
| login_page | 7 | 163 ms | 218 ms | 0.0% |
| logout | 5 | 271 ms | 302 ms | 20.0% |
| product | 99 | 256 ms | 439 ms | 6.1% |
| search | 11 | 252 ms | 559 ms | 9.1% |
