# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 20.2 | 2233 ms | 4154 ms | 5624 ms | 2.3% (83) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 19.7 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 105 | 1982 ms | 2855 ms | 1.9% |
| add_to_cart | 196 | 3976 ms | 7155 ms | 1.5% |
| cart | 99 | 2100 ms | 2823 ms | 2.0% |
| category | 1051 | 2308 ms | 3705 ms | 1.3% |
| checkout | 4 | 2177 ms | 2821 ms | 0.0% |
| home | 230 | 1956 ms | 3321 ms | 0.9% |
| login | 107 | 3894 ms | 5716 ms | 1.9% |
| login_page | 107 | 1861 ms | 3425 ms | 1.9% |
| logout | 107 | 3815 ms | 6658 ms | 0.9% |
| product | 1455 | 2056 ms | 3283 ms | 1.2% |
| search | 140 | 2211 ms | 3772 ms | 0.0% |
| session | 37 | 0 ms | 0 ms | 100.0% |
