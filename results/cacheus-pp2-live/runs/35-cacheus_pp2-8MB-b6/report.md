# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 21.1 | 2009 ms | 3729 ms | 4625 ms | 4.6% (174) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 20.1 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 116 | 1847 ms | 2602 ms | 1.7% |
| add_to_cart | 217 | 3638 ms | 4979 ms | 3.7% |
| cart | 109 | 1880 ms | 2534 ms | 1.8% |
| category | 1088 | 2117 ms | 2968 ms | 1.2% |
| checkout | 10 | 1956 ms | 2324 ms | 0.0% |
| home | 222 | 1700 ms | 2402 ms | 0.9% |
| login | 115 | 3544 ms | 5062 ms | 0.9% |
| login_page | 121 | 1709 ms | 2465 ms | 4.1% |
| logout | 118 | 3383 ms | 4696 ms | 3.4% |
| product | 1424 | 1890 ms | 2652 ms | 1.9% |
| search | 145 | 1850 ms | 2907 ms | 0.7% |
| session | 109 | 0 ms | 0 ms | 100.0% |
