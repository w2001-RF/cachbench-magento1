# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 33.3 | 536 ms | 1269 ms | 1816 ms | 27.8% (1667) | 7 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 24.0 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 148 | 386 ms | 1055 ms | 0.7% |
| add_to_cart | 280 | 701 ms | 1638 ms | 3.6% |
| cart | 145 | 435 ms | 880 ms | 2.1% |
| category | 1191 | 762 ms | 1522 ms | 4.9% |
| checkout | 13 | 616 ms | 875 ms | 0.0% |
| home | 262 | 250 ms | 795 ms | 6.1% |
| login | 139 | 511 ms | 1182 ms | 4.3% |
| login_page | 136 | 244 ms | 776 ms | 0.0% |
| logout | 149 | 359 ms | 1124 ms | 3.4% |
| product | 1845 | 478 ms | 1098 ms | 2.7% |
| search | 174 | 429 ms | 1530 ms | 3.4% |
| session | 1512 | 0 ms | 0 ms | 100.0% |
