# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 12.4 | 6142 ms | 11535 ms | 12621 ms | 0.3% (7) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 12.4 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 68 | 5821 ms | 6690 ms | 1.5% |
| add_to_cart | 136 | 11570 ms | 12819 ms | 0.0% |
| cart | 71 | 6249 ms | 7009 ms | 0.0% |
| category | 639 | 6279 ms | 7097 ms | 0.3% |
| checkout | 6 | 5950 ms | 6533 ms | 0.0% |
| home | 135 | 5600 ms | 6424 ms | 0.7% |
| login | 68 | 11364 ms | 12542 ms | 0.0% |
| login_page | 74 | 5725 ms | 6625 ms | 0.0% |
| logout | 63 | 10884 ms | 12306 ms | 1.6% |
| product | 896 | 5985 ms | 6775 ms | 0.1% |
| search | 75 | 5923 ms | 7443 ms | 1.3% |
