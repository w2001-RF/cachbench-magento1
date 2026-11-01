# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 19.9 | 2282 ms | 4292 ms | 6078 ms | 0.8% (28) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 19.7 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 115 | 2124 ms | 3484 ms | 0.0% |
| add_to_cart | 208 | 4242 ms | 6330 ms | 0.0% |
| cart | 96 | 2082 ms | 3220 ms | 0.0% |
| category | 1007 | 2297 ms | 3569 ms | 0.0% |
| checkout | 8 | 2423 ms | 3282 ms | 0.0% |
| home | 218 | 2045 ms | 3216 ms | 0.0% |
| login | 118 | 3891 ms | 6209 ms | 0.0% |
| login_page | 123 | 1892 ms | 3369 ms | 0.0% |
| logout | 115 | 3912 ms | 6182 ms | 0.0% |
| product | 1425 | 2101 ms | 3241 ms | 0.0% |
| search | 116 | 2214 ms | 3308 ms | 0.0% |
| session | 28 | 0 ms | 0 ms | 100.0% |
