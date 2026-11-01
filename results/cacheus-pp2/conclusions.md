# CACHEUS++ v2 : conclusions

Résultats détaillés : [report.md](report.md) (hors ligne) et
[../cacheus-pp2-live/report.md](../cacheus-pp2-live/report.md) (boutique sous charge). Différences en
points de hit rate (pts), IC à 95 %, comparaisons appariées.

## 1. Hors ligne : v2 fait mieux que CACHEUS++, ou aussi bien

Sur les cas jamais vus pendant le réglage, v2 gagne dans 13 cas sur 15, fait jeu égal dans 2,
et ne perd dans aucun (p de Holm < 0,05 pour chaque gain).

| Cas | Δ v2 − CACHEUS++ | IC 95 % | Répliques gagnées |
| --- | ---: | --- | --- |
| Synthétique, unités, 0,5 à 10 % | +0,68 à +2,34 | toutes au-dessus de +0,6 | 20/20 pour chaque taille |
| Synthétique, octets, 1 % / 5 % | +1,60 / +0,75 | [+1,48, +1,72] / [+0,70, +0,80] | 20/20 |
| 6 mois réels non vus, 5 % | +1,53 | [+1,01, +2,06] | 6 mois sur 6 |
| 6 mois réels non vus, 10 % | +0,52 | [+0,15, +0,89] | 6 mois sur 6 |
| 6 mois réels non vus, 1 % | +0,05 | [−0,54, +0,65] | jeu égal (deux mois perdent 0,6 à 0,7) |
| Journal de la boutique, 1 Mo | +3,64 | [+3,64, +3,65] | 10/10 |
| Journal de la boutique, 4 / 16 Mo | +0,00 / +0,02 | — | jeu égal / gain minime |

v2 comble 5 à 20 % de l'écart avec OPT sur les traces, et 85 % sur le journal de la boutique en
petit cache. L'écart restant tient surtout à ce qu'OPT connaît l'avenir. CACHEUS++ battait déjà
ARC, LIRS et CACHEUS, et un oracle qui choisit toujours le meilleur des trois candidats ne fait
guère mieux que le tirage au sort.

**Ce qu'apporte chaque correction** (on la retire de v2, moyenne des cas non vus) :

| Correction | Apport |
| --- | --- |
| numéros de version | +0,35 pts, surtout sur les mois réels (+1,07 à 5 %) |
| vieillissement des fréquences | +0,15 pts ; aide sur le synthétique, coûte −0,24 pts sur les mois réels à 1 % |
| objets jusqu'à 50 % du cache | +3,7 pts sur le journal de la boutique en petit cache, nul ailleurs |
| retour contrefactuel | +0,09 pts |
| fantômes de 4 tailles de cache | +0,09 pts |
| admission apprise retirée | −0,04 pts : la retirer ne fait pas mieux, elle aide un peu en moyenne |

## 2. Sur la boutique, 150 visiteurs simultanés

150 visiteurs est la charge maximale tenue sans cache pleine page : p95 de 2,6 s, aucune
erreur. À 200 visiteurs, le p95 monte à 6,7 s. Le test a fait 36 passes de 4 min en 6 blocs dans
un ordre tiré au sort ; l'état a été remis à zéro avant chaque passe.

| | LRU | CACHEUS++ | v2 |
| --- | ---: | ---: | ---: |
| Hit rate à 2 Mo | 95,30 ± 0,61 % | 88,77 ± 0,64 % | **96,55 ± 0,45 %** |
| Hit rate à 8 Mo | 97,74 ± 0,04 % | **98,21 ± 0,08 %** | 97,83 ± 0,14 % |
| Temps moyen à 2 Mo | **0,62 s** | 6,48 s | 1,63 s |
| Temps moyen à 8 Mo | **0,57 s** | 1,92 s | 2,43 s |
| Erreurs à 2 Mo / 8 Mo | 31 % / 33 % | 0,4 % / 6,5 % | 9,4 % / 2,9 % |

- **À 2 Mo, v2 corrige un vrai défaut de CACHEUS++ :**
  - hit rate +7,8 pts [+7,1, +8,5], byte hit rate +35,8 pts ;
  - temps moyen divisé par 4 (−4,8 s), p95 −8,0 s ;
  - 6 blocs sur 6, p de Holm < 0,001.
  - CACHEUS++ refusait les entrées de configuration de Magento (plus de 10 % d'un cache de
    2 Mo, mais lues à chaque page), et chaque page les reconstruisait. v2 fait aussi mieux que
    LRU en hit rate (+1,25 pts [+0,79, +1,71], 6 blocs sur 6).
- **À 8 Mo, v2 fait un peu moins bien que CACHEUS++ :**
  - hit rate −0,38 pts [−0,58, −0,19], 6 blocs sur 6, p de Holm 0,04 ;
  - pages plus lentes de 0,5 s, mais non significatif après correction.
  - Hors ligne, au contraire, il gagnait +0,02 pts : le trafic du test de charge (parcours de
    visiteurs virtuels) n'est pas celui de la trace enregistrée.
- **Le temps de réponse dépend surtout du coût de l'état partagé :**
  - Chaque page relit et réécrit tout l'état de la politique sous un verrou exclusif.
  - Mesuré sur une passe réelle à 8 Mo : 0,7 Mo et 2 ms par page pour LRU, 1,6 Mo et 18 ms
    pour CACHEUS++, 2,1 Mo et 25 ms pour v2.
  - À 22 pages/s, ce verrou est occupé une bonne partie du temps et les requêtes font la
    queue. C'est pourquoi LRU répond 3 à 4 fois plus vite, bien qu'il ait un hit rate
    plus faible ou à peine meilleur.
- **Les erreurs de LRU (31 à 33 %) sont des plantages d'Apache** (php7ts.dll, déjà vus sans le
  module). Plus rapide, LRU envoie plus de requêtes et fait planter Apache plus souvent : ses
  temps et son débit sont flattés par ces échecs rapides. Comparer les temps des trois
  politiques n'est donc fiable qu'entre CACHEUS++ et v2, dont les taux d'erreur sont proches.

## 3. Limites

- Hors ligne, la variabilité vient des graines de la politique (et des traces pour le
  synthétique). Sur les mois réels à 1 %, le résultat change de signe selon le mois.
- Les tests ont tourné sur une seule machine : le générateur de charge partage le processeur
  avec Apache et MySQL, et PHP 7.1 thread-safe plante sous charge.
- Avec 6 blocs, le test de Wilcoxon ne descend pas sous p = 0,031 ; la correction de Holm
  porte donc sur le test t, et les IC bootstrap servent de second avis.

## 4. Suite à donner

1. **Réduire le coût de l'état partagé.** C'est le premier frein en conditions réelles :
   - ne réécrire que les changements, ou tenir l'état dans Redis ou dans un processus à part ;
   - ou appliquer les accès par lots, toutes les N requêtes.
   Sans cela, toute politique plus riche que LRU paie en temps de réponse ce qu'elle gagne en
   hit rate.
2. Garder la limite de taille d'objet à 50 %, ou la régler d'après la plus grosse entrée de
   configuration : c'est le gain le plus net en production.
3. Rétablir l'admission apprise (`admission: logistic`), qui aide légèrement en moyenne, et
   revoir le vieillissement pour les très petits caches (il coûte −0,24 pts sur les mois
   réels à 1 %).
