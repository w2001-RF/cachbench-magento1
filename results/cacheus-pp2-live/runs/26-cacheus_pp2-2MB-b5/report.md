# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 23.1 | 1000 ms | 4617 ms | 7121 ms | 5.8% (240) | 2 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 21.8 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 127 | 866 ms | 3847 ms | 1.6% |
| add_to_cart | 219 | 1456 ms | 7900 ms | 3.2% |
| cart | 108 | 889 ms | 3898 ms | 1.9% |
| category | 1172 | 1261 ms | 4614 ms | 2.8% |
| checkout | 3 | 1106 ms | 3484 ms | 0.0% |
| home | 239 | 693 ms | 4103 ms | 1.3% |
| login | 116 | 1387 ms | 7280 ms | 0.9% |
| login_page | 122 | 640 ms | 3865 ms | 1.6% |
| logout | 130 | 1239 ms | 7145 ms | 4.6% |
| product | 1617 | 863 ms | 4078 ms | 1.8% |
| search | 149 | 1007 ms | 4452 ms | 0.0% |
| session | 155 | 0 ms | 0 ms | 100.0% |
