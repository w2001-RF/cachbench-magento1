# Test de charge — http://127.0.0.1/magento

Paliers de 60 s (15 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 25 | 4.4 | 309 ms | 606 ms | 742 ms | 0.0% (0) | 0 | tient |
| 50 | 9.2 | 349 ms | 759 ms | 1001 ms | 6.3% (26) | 4 | **ne tient pas** |
| 100 | 17.6 | 434 ms | 1070 ms | 1453 ms | 0.0% (0) | 0 | tient |
| 150 | 22.1 | 1452 ms | 2592 ms | 3358 ms | 0.0% (0) | 0 | tient |
| 200 | 20.2 | 3597 ms | 6688 ms | 9385 ms | 0.0% (0) | 0 | **ne tient pas** |
| 250 | 52.1 | 4170 ms | 8764 ms | 10921 ms | 72.3% (1764) | 2 | **ne tient pas** |

**Limite** : 25 visiteurs simultanés (le palier suivant, 50, ne tient pas)
**Débit maximal sans erreur** : 22.1 pages/s, à 150 visiteurs.

## Par type de page (palier de 250 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 32 | 3458 ms | 5764 ms | 12.5% |
| add_to_cart | 54 | 6269 ms | 10921 ms | 18.5% |
| cart | 27 | 3354 ms | 5917 ms | 7.4% |
| category | 169 | 4859 ms | 6274 ms | 8.9% |
| login | 26 | 8571 ms | 11110 ms | 0.0% |
| login_page | 14 | 5438 ms | 5688 ms | 0.0% |
| logout | 26 | 5248 ms | 9817 ms | 3.8% |
| product | 360 | 3647 ms | 5804 ms | 8.3% |
| search | 30 | 3402 ms | 6387 ms | 3.3% |
| session | 1701 | 0 ms | 0 ms | 100.0% |
