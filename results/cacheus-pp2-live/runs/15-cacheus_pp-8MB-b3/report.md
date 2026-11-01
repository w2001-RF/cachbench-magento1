# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 23.4 | 1725 ms | 3121 ms | 3830 ms | 10.7% (451) | 2 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 20.9 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 99 | 1635 ms | 2149 ms | 2.0% |
| add_to_cart | 219 | 3106 ms | 4086 ms | 3.2% |
| cart | 106 | 1578 ms | 2150 ms | 2.8% |
| category | 1085 | 1815 ms | 2433 ms | 2.9% |
| checkout | 8 | 1910 ms | 2021 ms | 0.0% |
| home | 273 | 1506 ms | 2059 ms | 5.9% |
| login | 115 | 3032 ms | 3835 ms | 3.5% |
| login_page | 111 | 1505 ms | 1982 ms | 0.0% |
| logout | 101 | 2897 ms | 3895 ms | 5.9% |
| product | 1616 | 1645 ms | 2252 ms | 3.2% |
| search | 160 | 1654 ms | 2441 ms | 2.5% |
| session | 326 | 0 ms | 0 ms | 100.0% |
