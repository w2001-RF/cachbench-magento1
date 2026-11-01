# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 21.5 | 1870 ms | 3695 ms | 5375 ms | 4.8% (185) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 20.5 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 116 | 1669 ms | 3431 ms | 0.9% |
| add_to_cart | 222 | 3258 ms | 6251 ms | 4.1% |
| cart | 115 | 1770 ms | 3365 ms | 0.9% |
| category | 1103 | 1940 ms | 3521 ms | 2.0% |
| checkout | 13 | 1929 ms | 3472 ms | 0.0% |
| home | 218 | 1578 ms | 3202 ms | 0.0% |
| login | 126 | 3143 ms | 6465 ms | 2.4% |
| login_page | 123 | 1466 ms | 2634 ms | 0.8% |
| logout | 119 | 3190 ms | 6630 ms | 3.4% |
| product | 1443 | 1718 ms | 3484 ms | 1.2% |
| search | 150 | 1808 ms | 3426 ms | 3.3% |
| session | 121 | 0 ms | 0 ms | 100.0% |
