# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 24.4 | 1034 ms | 3309 ms | 5243 ms | 9.3% (407) | 4 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 22.1 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 118 | 941 ms | 3216 ms | 2.5% |
| add_to_cart | 252 | 1464 ms | 4786 ms | 4.0% |
| cart | 118 | 1030 ms | 3364 ms | 2.5% |
| category | 1177 | 1311 ms | 3226 ms | 3.3% |
| checkout | 4 | 1049 ms | 4481 ms | 0.0% |
| home | 237 | 649 ms | 2781 ms | 0.8% |
| login | 125 | 1330 ms | 5313 ms | 6.4% |
| login_page | 130 | 605 ms | 2476 ms | 6.9% |
| logout | 117 | 1222 ms | 5297 ms | 5.1% |
| product | 1696 | 944 ms | 2905 ms | 3.7% |
| search | 153 | 928 ms | 2696 ms | 3.9% |
| session | 258 | 0 ms | 0 ms | 100.0% |
