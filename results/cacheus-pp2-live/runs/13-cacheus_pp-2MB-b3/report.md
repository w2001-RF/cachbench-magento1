# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 12.6 | 6149 ms | 11589 ms | 12732 ms | 1.3% (29) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 12.4 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 46 | 5850 ms | 6555 ms | 0.0% |
| add_to_cart | 129 | 11836 ms | 13137 ms | 1.6% |
| cart | 62 | 6193 ms | 6852 ms | 0.0% |
| category | 672 | 6329 ms | 7175 ms | 0.1% |
| checkout | 4 | 6637 ms | 6747 ms | 0.0% |
| home | 151 | 5564 ms | 6488 ms | 0.7% |
| login | 58 | 11168 ms | 12700 ms | 0.0% |
| login_page | 67 | 5673 ms | 6521 ms | 3.0% |
| logout | 46 | 10984 ms | 12555 ms | 0.0% |
| product | 913 | 5969 ms | 6782 ms | 0.2% |
| search | 94 | 5827 ms | 6944 ms | 0.0% |
| session | 21 | 0 ms | 0 ms | 100.0% |
