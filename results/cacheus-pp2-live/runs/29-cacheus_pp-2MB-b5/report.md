# Test de charge — http://127.0.0.1/magento

Paliers de 240 s (60 s d'installation non mesurés), pause entre pages 2-8 s, 160 catégories, 5000 comptes clients. Un palier tient si les erreurs restent sous 1% et le p95 sous 3 s.

| Visiteurs | Req/s | Médiane | p95 | p99 | Erreurs | Plantages Apache | Verdict |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 150 | 13.5 | 5679 ms | 10884 ms | 12404 ms | 0.9% (23) | 0 | **ne tient pas** |

**Limite** : 0 visiteurs simultanés (le palier suivant, 150, ne tient pas)
**Débit maximal sans erreur** : 13.3 pages/s, à 150 visiteurs.

## Par type de page (palier de 150 visiteurs)

| Page | Requêtes | Médiane | p95 | Erreurs |
| --- | ---: | ---: | ---: | ---: |
| account | 79 | 4996 ms | 6240 ms | 0.0% |
| add_to_cart | 135 | 10627 ms | 13062 ms | 0.7% |
| cart | 67 | 5760 ms | 6774 ms | 0.0% |
| category | 701 | 5732 ms | 7080 ms | 0.4% |
| checkout | 2 | 5307 ms | 5612 ms | 0.0% |
| home | 151 | 5164 ms | 6293 ms | 0.7% |
| login | 70 | 10788 ms | 12186 ms | 1.4% |
| login_page | 70 | 4985 ms | 6335 ms | 0.0% |
| logout | 79 | 10272 ms | 11781 ms | 1.3% |
| product | 964 | 5435 ms | 6784 ms | 0.3% |
| search | 95 | 5057 ms | 6970 ms | 0.0% |
| session | 13 | 0 ms | 0 ms | 100.0% |
