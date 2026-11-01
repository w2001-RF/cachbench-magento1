# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 12.7 | 6029 ms | 11482 ms | 12580 ms | 0.0% (0) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 12.7 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 65 | 5621 ms | 6484 ms | 0.0% |
| add_to_cart | 140 | 11647 ms | 12956 ms | 0.0% |
| cart | 62 | 5988 ms | 7046 ms | 0.0% |
| category | 675 | 6213 ms | 7132 ms | 0.0% |
| checkout | 2 | 6997 ms | 7381 ms | 0.0% |
| home | 140 | 5650 ms | 6391 ms | 0.0% |
| login | 65 | 10969 ms | 12608 ms | 0.0% |
| login_page | 64 | 5513 ms | 6401 ms | 0.0% |
| logout | 58 | 10927 ms | 12426 ms | 0.0% |
| product | 942 | 5829 ms | 6841 ms | 0.0% |
| search | 78 | 5704 ms | 7382 ms | 0.0% |
