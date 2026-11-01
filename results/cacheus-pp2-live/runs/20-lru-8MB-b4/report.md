# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 33.8 | 449 ms | 1133 ms | 1540 ms | 28.6% (1737) | 8 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 24.1 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 142 | 340 ms | 759 ms | 0.0% |
| add_to_cart | 291 | 604 ms | 1314 ms | 3.8% |
| cart | 137 | 386 ms | 890 ms | 2.2% |
| category | 1168 | 685 ms | 1386 ms | 2.7% |
| checkout | 7 | 419 ms | 697 ms | 0.0% |
| home | 249 | 212 ms | 566 ms | 0.8% |
| login | 145 | 466 ms | 1029 ms | 4.1% |
| login_page | 143 | 172 ms | 463 ms | 1.4% |
| logout | 143 | 295 ms | 1000 ms | 2.8% |
| product | 1862 | 404 ms | 939 ms | 2.2% |
| search | 159 | 372 ms | 1329 ms | 1.9% |
| session | 1634 | 0 ms | 0 ms | 100.0% |
