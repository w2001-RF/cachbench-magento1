# Revue de littérature : politiques d'éviction de cache, e-commerce et Magento

Ce document situe les résultats du projet par rapport aux travaux publiés. Il dit aussi ce qui,
dans notre protocole, empêche une comparaison directe des chiffres, et comment corriger le banc
d'essai sur la boutique pour que ses résultats deviennent comparables.

Résultats du projet cités ici : [results/cacheus-pp2/report.md](../results/cacheus-pp2/report.md)
(hors ligne), [results/cacheus-pp2-live/report.md](../results/cacheus-pp2-live/report.md) (boutique,
3 politiques) et `results/live-all-policies/report.md` (boutique, toutes les politiques, en cours).

## 1. Ce qui a été publié

Aucun article évalué par des pairs ne compare des politiques d'éviction en conditions réelles sur
Magento. Les travaux publiés se rangent en trois familles, qui ne mesurent pas la même chose.

### 1.1 Politiques d'éviction : simulation sur des traces de production

| Travail | Banc d'essai | Traces | Tailles de cache | Taille des objets | Mesure | Résultat principal |
| --- | --- | --- | --- | --- | --- | --- |
| **CACHEUS** (Rodriguez et al., FAST 2021) | simulateur | 329 traces d'E/S de stockage d'un jour (FIU, MSR, CloudPhysics, CloudVPS, CloudCache) ; 17 766 simulations | 6 tailles, de 0,05 % à 10 % de l'empreinte (données distinctes) | blocs (unité) | hit rate ; tests t appariés, d de Cohen, seuil 0,05 | C3 (SR-LRU + CR-LFU) est le meilleur ou indistinguable du meilleur dans 87 % des couples (trace, taille) ; distinctement meilleur dans 47 %. Pire cas −15,12 pts (MSR, 5 %, contre DLIRS), meilleur cas +38,32 pts (CloudPhysics, 10 %, contre ARC). Ni temps de réponse ni prototype. |
| **S3-FIFO** (Yang et al., SOSP 2023) | libCacheSim + prototype Cachelib | 6 594 traces de 14 sources (bloc, clé-valeur, objet ; 856 milliards de requêtes, 2007–2023) | 10 % (« grand ») et 0,1 % (« petit ») de l'empreinte en objets | **ignorée** (slabs) | réduction du taux de miss par rapport à FIFO, percentiles sur les traces | Meilleur sur 10 des 14 jeux à 10 % ; −32 % de miss au P90 par rapport à FIFO. LIRS, deuxième, n'est en tête que sur 2 jeux. Débit 6× celui de LRU à 16 cœurs. |
| **SIEVE** (Zhang et al., NSDI 2024) | libCacheSim + Cachelib (CloudLab) | 1 559 traces web de 7 jeux (Twitter KV, Meta KV/CDN, Wikimedia CDN, Tencent Photo, 2 CDN) | idem (grand et petit) | ignorée | réduction du miss par rapport à FIFO | Meilleur que 9 algorithmes sur plus de 45 % des traces. Par rapport à ARC : jusqu'à −63,2 %, **moyenne −1,5 %**. **ARC ne réduit le miss de LRU que de 6,3 % en moyenne.** Sur petit cache, ARC et surtout LIRS se dégradent (LIRS parfois pire que FIFO). Débit +17 % (1 fil) et +125 % (16 fils) par rapport à LRU. |
| **LRB** (Song et al., NSDI 2020) | simulateur + prototype Apache Traffic Server | 6 traces de 3 CDN | caches flash de 1 à 2 To | **variable** (octets) | byte miss ratio, trafic WAN | −4 à −25 % de trafic WAN ; écart de 25 à 40 % entre Belady (OPT) et toutes les heuristiques. Débit inchangé (11,7 Gbit/s), processeur au pic 16 % contre 9 %. |
| **Twemcache** (Yang et al., OSDI 2020) | analyse de 153 grappes Twitter | traces publiques | tailles de production | variable | taux de miss | À taille raisonnable, FIFO vaut souvent LRU ; LRU ne prend l'avantage que sur cache très contraint. Le TTL borne l'ensemble de travail utile. |

À retenir : ces évaluations sont **hors ligne**. Elles portent sur des centaines ou des milliers de
traces, fixent la taille du cache **en pourcentage de l'empreinte** et ignorent le plus souvent la
taille des objets. La mesure est le taux de miss par requête, ou sa réduction par rapport à une
référence (FIFO ou LRU). Les gains entre bonnes politiques y sont faibles, de l'ordre de 1 à 6 %
de réduction relative du miss, et changent de signe d'une trace à l'autre.

### 1.2 Cache applicatif des applications web d'e-commerce

- **Mertz et Nunes** (*Software: Practice and Experience* ; arXiv 2011.00247).
  - **Banc d'essai.** Trois applications Java, dont Cloud Store (e-commerce de type TPC-W) et
    Shopizer, sur Tomcat 2 Go et MySQL. Le serveur web et MySQL tournent sur une machine (i7,
    16 Go) et JMeter sur une autre (i7, 32 Go). Le cache est EhCache.
  - **Charge.** 1, 5, 10, 25 et 50 utilisateurs, 500 requêtes chacun, 10 répétitions. Les parcours
    suivent la répartition TPC-W et RUBiS : 80 % de lectures, 20 % d'écritures.
  - **Résultats.** Le débit gagne 2,78 à 17,18 %. LRU et LFU donnent le même débit et les mêmes
    hits que le TTL seul : avec les tailles de cache des développeurs, **aucune éviction n'a lieu**.
  - **Leçon.** Sur une boutique dont le cache est dimensionné normalement, la politique d'éviction
    ne change rien ; elle ne compte que si le cache est contraint.
- **ERF** (Springer LNEE, 2018) propose un score exponentiel en temps × fréquence pour des caches
  d'e-commerce à mémoire limitée. Les chiffres ne sont pas accessibles en ligne et l'article n'est
  pas comparable en l'état.
- **Mertz et Nunes, ACM Computing Surveys 50(6), 2017**, est la revue de référence sur le cache
  applicatif : quoi mettre en cache, quand l'invalider, réglage adaptatif.

### 1.3 Magento : mesures de praticiens (non évaluées par des pairs)

| Source | Banc d'essai | Charge | Résultats |
| --- | --- | --- | --- |
| Documentation Magento (FPC) | `ab -n 1000 -c 10`, une page produit, matériel non précisé | 10 connexions | sans cache : 5,2 req/s, moyenne 1 923 ms, p95 2 800 ms ; FPC Redis : 125 req/s, 80 ms, p95 120 ms ; Varnish + Redis : 850 req/s, 12 ms, p95 20 ms |
| Mirasvit (Magento 2.4.9, PHP 8.3, Varnish 6.6.1) | grappe de recette partagée, matériel non précisé ; 12 boutiques réelles | de 50 à 250 requêtes simultanées | FPC intégré : 41,8 → 36,2 req/s, p95 1 766 → 7 943 ms ; Varnish : 650–690 req/s ; hit rate du FPC sur boutiques réelles : 5 à 67 % |

Ces mesures portent sur le **cache pleine page** (FPC, Varnish), pas sur l'éviction du cache objet.
Redis, le backend habituel de Magento, n'évince que par LRU ou LFU **approchés**, en
échantillonnant 5 clés (`maxmemory-samples`), selon le réglage `maxmemory-policy`. C'est la vraie
référence de production. Nos politiques ne sont pas comparées à elle pour l'instant.

## 2. Nos résultats face à la littérature

### 2.1 Hors ligne : directement comparables, à condition de prendre la même mesure

Pour se placer à côté de SIEVE et de S3-FIFO, nous calculons la même mesure : la réduction du taux
de miss par rapport à LRU, (miss_LRU − miss_algo) / miss_LRU, en moyenne sur les traces. Sources :
`results/cacheus-pp2/offline.csv`, moyennes sur 10 graines pour les politiques aléatoires. Tailles
en pourcentage des objets distincts, en mode unité, comme CACHEUS et S3-FIFO.

| Jeu | Taille | Hit LRU | ARC | LIRS | CACHEUS | CACHEUS++ | v2 | OPT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 mois e-commerce (REES46 → pages Magento) | 1 % | 21,9 % | +2,6 % | +1,5 % | +2,7 % | +7,1 % | +7,2 % | +33,7 % |
| | 5 % | 48,7 % | +0,6 % | −12,0 % | −2,9 % | +5,1 % | **+8,0 %** | +35,1 % |
| | 10 % | 57,5 % | −0,5 % | −12,5 % | −2,4 % | +7,2 % | **+8,6 %** | +36,9 % |
| 20 traces synthétiques Magento 1 | 1 % | 32,2 % | +12,5 % | +13,0 % | +12,8 % | +14,8 % | +18,3 % | +31,8 % |
| | 10 % | 67,6 % | +16,6 % | +16,7 % | +19,4 % | +18,9 % | +21,0 % | +40,5 % |

Lecture :

- **Les traces e-commerce réelles ressemblent aux traces web de la littérature.** ARC y fait à peu
  près LRU (+0,6 % à 5 %), comme dans SIEVE où ARC ne gagne que 6,3 % en moyenne sur des traces
  web. LIRS y est nettement moins bon que LRU (−12 %), comme SIEVE et S3-FIFO le notent pour
  certaines traces web. CACHEUS, qui dans son article gagne sur des traces de **stockage**, perd
  légèrement face à LRU sur nos traces web e-commerce. Ce n'est pas une contradiction : CACHEUS
  n'a pas été évalué sur des traces web.
- **CACHEUS++ v2 réduit le miss de LRU de 7 à 9 %**, au-dessus d'ARC, LIRS et CACHEUS sur les 7
  mois. C'est un ordre de grandeur plausible face aux gains publiés, mais sur 7 traces d'une seule
  source, contre 1 559 à 6 594 dans SIEVE et S3-FIFO. Le résultat est donc **à confirmer à large
  échelle** avant d'être affirmé.
- **Le générateur synthétique exagère les écarts** (ARC +12 à +17 %, deux à trois fois le chiffre
  publié). Il est utile pour tester, pas pour se positionner.
- **L'écart avec OPT** (34 à 37 % de réduction du miss encore possible) est du même ordre que
  l'écart de 25 à 40 % entre Belady et les heuristiques mesuré par LRB.

### 2.2 Sur la boutique : pas comparable directement

Il n'existe aucune mesure publiée équivalente : éviction du cache objet de Magento, FPC coupé,
150 visiteurs. Les seuls points de repère sont ceux de la documentation Magento.

- **Notre ordre de grandeur est cohérent.** Sans FPC, nous mesurons un temps moyen de 0,6 à 6,5 s
  et un p95 de 1 à 10 s à 150 visiteurs. La documentation donne 1,9 s de moyenne sans cache, à
  10 connexions seulement.
- **Nos temps mesurent surtout notre implémentation.** Chaque page relit et réécrit tout l'état de
  la politique sous verrou : 2 ms pour LRU, 18 ms pour CACHEUS++, 25 ms pour v2. Un backend
  Redis réel n'a pas ce coût.
- **Les erreurs des passes LRU** (31 à 33 %) viennent de plantages d'Apache, qui ne dépendent pas
  de la politique.
- **Nos tailles de cache sont faibles exprès** : 1, 2 et 8 Mo, soit environ 1,6 %, 3 % et 13 % des
  63 Mo d'entrées distinctes. Cela les place dans la plage de la littérature (0,1 à 10 % de
  l'empreinte), alors qu'une boutique en production n'évince presque jamais, comme l'ont observé
  Mertz et Nunes.

## 3. Pourquoi nos chiffres ne se comparent pas tels quels aux résultats publiés

| # | Problème de notre protocole | Effet | Gravité |
| --- | --- | --- | --- |
| 1 | Une seule machine Windows (WAMP, PHP 7.1 thread-safe) : le générateur de charge partage le processeur avec Apache et MySQL | temps et débit faussés ; plantages d'Apache (php7ts.dll) qui produisent 31 à 33 % d'erreurs sur LRU | haute |
| 2 | État de la politique sérialisé dans un fichier et verrouillé à chaque requête | la latence mesure le coût de notre stockage d'état, pas la politique ; LRU est avantagé | haute |
| 3 | Charge en boucle fermée (150 visiteurs, pauses de 2 à 8 s) | une politique lente reçoit moins de requêtes ; la charge offerte change d'une politique à l'autre (*coordinated omission*) | haute |
| 4 | Pas de comparaison avec la vraie référence (Redis `allkeys-lru` / `allkeys-lfu` à la même mémoire) | impossible de dire si on bat ce que Magento utilise réellement | haute |
| 5 | Parcours virtuels du test de charge, petit catalogue, une seule boutique | une seule « trace » ; la littérature en utilise des centaines | moyenne |
| 6 | Passes courtes (3 à 4 min), départ à froid, 5 à 6 blocs | régime établi à peine atteint ; avec 6 blocs, le test de Wilcoxon ne descend pas sous p = 0,031 | moyenne |
| 7 | Hit défini à partir de notre journal (lecture de coût nul) | définition propre au projet ; la littérature compte le miss par requête au niveau du cache | moyenne |
| 8 | Politiques en objets (lecar, cacheus, arc, lirs) face à un budget en octets | octets occupés différents d'une politique à l'autre | moyenne |
| 9 | Bases récentes absentes : S3-FIFO, SIEVE, W-TinyLFU, 2Q, LHD, GDSF | on ne se compare pas à l'état de l'art actuel | moyenne |
| 10 | Charge sur la base inférée (lectures manquées par page), pas mesurée | lien avec la charge MySQL non prouvé | faible |

## 4. Suite : rendre les résultats comparables

### 4.1 Volet hors ligne, aligné sur SIEVE et S3-FIFO (priorité 1, le moins coûteux)

1. **Ajouter les bases actuelles** à `cachebench` : S3-FIFO, SIEVE, W-TinyLFU, 2Q, GDSF. Une
   alternative est de brancher **libCacheSim**, le simulateur de S3-FIFO et SIEVE, qui les
   contient déjà.
2. **Valider l'implémentation** en reproduisant un chiffre publié avant toute comparaison. Par
   exemple, la réduction moyenne du miss d'ARC par rapport à LRU sur les traces Twitter publiques
   (`twitter/cache-trace`) doit être proche des 6,3 % de SIEVE.
3. **Évaluer sur les mêmes jeux publics** que la littérature (Twitter KV, Meta KV, Wikimedia CDN,
   MSR, FIU), plus nos traces e-commerce (7 mois REES46, journal de la boutique). Exporter nos
   traces au format libCacheSim place Magento dans la même distribution que les autres jeux.
4. **Mêmes tailles et même mesure** : 0,1 % et 10 % de l'empreinte en objets, plus le mode octets.
   Rapporter la réduction du miss par rapport à FIFO et à LRU, en percentiles sur les traces (P10,
   P25, médiane, P75, P90) et en nombre de traces où chaque politique est la meilleure.
5. **Statistiques pour plusieurs politiques** : test de Friedman puis test post hoc de Nemenyi,
   avec un diagramme de différence critique (Demšar, JMLR 2006). Les tests t appariés avec
   d de Cohen font le lien avec CACHEUS.

### 4.2 Volet en conditions réelles, refondu (priorité 2)

1. **Matériel séparé et décrit.**
   - Générateur de charge sur une autre machine.
   - Linux, PHP-FPM 7.4 ou 8.x non thread-safe (OpenMage LTS pour Magento 1), MySQL et Redis à
     part ou fixés à des cœurs.
   - Publier la configuration complète : processeur, mémoire, versions, `php.ini`, `my.cnf`.
2. **Supprimer le coût de l'état partagé.** Porter les politiques au plus près de Redis : module
   Redis, script Lua, ou petit service en mémoire interrogé par le backend. Ne réécrire que les
   changements. Mesurer à part le coût de décision par requête, comme S3-FIFO et SIEVE mesurent un
   débit en millions d'opérations par seconde.
3. **La vraie référence.** Redis `maxmemory` fixé au même nombre d'octets avec `allkeys-lru` puis
   `allkeys-lfu` : c'est ce qu'une boutique Magento utilise. Ajouter aussi un cache assez grand
   pour ne jamais évincer, qui donne la borne haute réelle.
4. **Charge en boucle ouverte.**
   - Arrivées de Poisson à débit fixé (k6 `constant-arrival-rate`, wrk2 ou Gatling).
   - Paliers croissants jusqu'à saturation, d'où des courbes débit-latence (p50, p95, p99) par
     politique.
   - Rejouer de vraies sessions (mois REES46 traduits en URL Magento), pas seulement des parcours
     virtuels.
5. **Deux configurations.** FPC coupé (le cache objet est sollicité) et FPC actif (situation de
   production), pour mesurer ce que la politique apporte réellement en production.
6. **Tailles en pourcentage de l'empreinte** : mesurer l'empreinte du cache objet, puis tester
   0,5 %, 1 %, 3 %, 10 % et 30 %, en plus de « assez grand ».
7. **Régime établi et répétitions.**
   - Chauffe jusqu'à ce que le hit rate se stabilise.
   - Passes de 15 à 30 minutes.
   - Au moins 10 blocs dans un ordre tiré au sort, ce qui permet Wilcoxon et Friedman-Nemenyi.
   - Rapporter les IC à 95 %.
8. **Mesurer directement la charge sur la base.**
   - Requêtes MySQL par seconde (`SHOW GLOBAL STATUS` : `Questions`, `Com_select` ;
     `performance_schema`).
   - Processeur de `mysqld` ; temps passé en base par page (profiler de Magento).
9. **Définitions communes.** Taux de miss par requête et en octets au niveau du backend, TTFB (p50,
   p95, p99), erreurs. Les erreurs comptent dans les percentiles, avec un délai maximal, au lieu
   d'être retirées.
10. **Paquet de reproductibilité** : scripts, plan tiré au sort, configurations et traces publiés
    avec les résultats.

### 4.3 Ce que l'on pourra alors affirmer

- **Le volet hors ligne** répondra à : « CACHEUS++ v2 réduit-il le miss autant ou plus que
  S3-FIFO, SIEVE et W-TinyLFU, sur les mêmes traces publiques et sur les traces e-commerce ? »
  Cette question se compare directement aux tableaux de SIEVE et de S3-FIFO.
- **Le volet sur la boutique** répondra à : « à mémoire Redis égale, la politique réduit-elle la
  charge MySQL et le p95 par rapport à `allkeys-lru` / `allkeys-lfu`, sous charge en boucle
  ouverte, sur du matériel décrit ? » C'est le résultat qui manque dans la littérature : c'est là
  que le travail peut apporter quelque chose de nouveau.

## Références

- L. V. Rodriguez et al., « Learning Cache Replacement with CACHEUS », FAST 2021, p. 341–354.
  https://www.usenix.org/conference/fast21/presentation/rodriguez
- J. Yang et al., « FIFO queues are all you need for cache eviction », SOSP 2023.
  https://junchengyang.com/publication/sosp23-s3fifo.pdf
- Y. Zhang et al., « SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web
  Caches », NSDI 2024. https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo
- Z. Song et al., « Learning Relaxed Belady for Content Distribution Network Caching », NSDI 2020.
  https://www.usenix.org/conference/nsdi20/presentation/song
- J. Yang, Y. Yue, K. V. Rashmi, « A large scale analysis of hundreds of in-memory cache clusters
  at Twitter », OSDI 2020. https://www.usenix.org/conference/osdi20/presentation/yang
- J. Mertz, I. Nunes, « Automation of application-level caching in a seamless way », *Software:
  Practice and Experience*. https://arxiv.org/abs/2011.00247
- J. Mertz, I. Nunes, « Understanding Application-Level Caching in Web Applications »,
  *ACM Computing Surveys* 50(6), 2017. https://arxiv.org/abs/2011.00477
- « ERF: Efficient cache eviction strategy for e-commerce applications », *Lecture Notes in
  Electrical Engineering*, Springer, 2018. https://aurora.ajou.ac.kr/handle/2018.oak/36247
- N. Megiddo, D. Modha, « ARC: A Self-Tuning, Low Overhead Replacement Cache », FAST 2003.
  https://www.usenix.org/event/fast03/tech/megiddo.html
- B. Atikoglu et al., « Workload Analysis of a Large-Scale Key-Value Store », SIGMETRICS 2012.
  https://research.fb.com/publications/workload-analysis-of-a-large-scale-key-value-store/
- J. Demšar, « Statistical Comparisons of Classifiers over Multiple Data Sets », JMLR 7, 2006.
- Redis, « Key eviction ». https://redis.io/docs/latest/develop/reference/eviction/
- Magento Open Source, « Full Page Cache Strategy for High-Performance Magento ».
  https://docs.magento-opensource.com/developer/guide-howto-full-page-cache-strategy.html
- Mirasvit, « Magento 2 Full Page Cache vs Varnish: When Benchmarks Meet Real Stores ».
  https://mirasvit.com/blog/magento-2-full-page-cache-vs-varnish.html
