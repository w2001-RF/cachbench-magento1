# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 18.7 | 3173 ms | 6136 ms | 8224 ms | 3.7% (125) | 2 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 18.0 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 83 | 2449 ms | 4358 ms | 1.2% |
| add_to_cart | 178 | 6112 ms | 8815 ms | 2.8% |
| cart | 85 | 3302 ms | 4487 ms | 1.2% |
| category | 964 | 3572 ms | 5030 ms | 3.6% |
| checkout | 8 | 3192 ms | 4525 ms | 0.0% |
| home | 234 | 2959 ms | 4444 ms | 1.7% |
| login | 90 | 5983 ms | 8465 ms | 3.3% |
| login_page | 93 | 2859 ms | 4306 ms | 0.0% |
| logout | 82 | 4464 ms | 8094 ms | 3.7% |
| product | 1365 | 2903 ms | 4538 ms | 2.3% |
| search | 144 | 2901 ms | 4883 ms | 0.7% |
| session | 40 | 0 ms | 0 ms | 100.0% |
