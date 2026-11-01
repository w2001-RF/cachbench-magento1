# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 22.0 | 1788 ms | 3335 ms | 4140 ms | 4.5% (179) | 1 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 21.0 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 114 | 1617 ms | 2281 ms | 1.8% |
| add_to_cart | 247 | 3247 ms | 4294 ms | 1.2% |
| cart | 99 | 1622 ms | 2126 ms | 3.0% |
| category | 1076 | 1855 ms | 2576 ms | 1.8% |
| checkout | 6 | 1982 ms | 2519 ms | 0.0% |
| home | 232 | 1567 ms | 2174 ms | 2.6% |
| login | 128 | 3200 ms | 4508 ms | 1.6% |
| login_page | 131 | 1507 ms | 2053 ms | 1.5% |
| logout | 120 | 2992 ms | 4031 ms | 2.5% |
| product | 1568 | 1709 ms | 2355 ms | 1.5% |
| search | 131 | 1670 ms | 2437 ms | 0.8% |
| session | 114 | 0 ms | 0 ms | 100.0% |
