# Écart entre OPT et CACHEUS++

Rejeu des mêmes traces par opt (Belady, connaît le futur), cacheus_pp et lru ; CACHEUS++ observé de l'intérieur. Généré par `scripts/analyze_opt_gap.py`.

| Trace | Taille | opt | cacheus_pp | lru | écart opt − c++ | requêtes de l'écart | inverses |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| magento1-synth | 1% | 53.6 % | 41.9 % | 32.0 % | 11.70 pts | 10109 | 123 |
| magento1-synth | 5% | 73.5 % | 65.5 % | 56.0 % | 7.92 pts | 6879 | 117 |
| magento-2020-Mar | 1% | 50.2 % | 29.2 % | 25.3 % | 21.01 pts | 18094 | 42 |
| magento-2020-Mar | 5% | 66.9 % | 52.1 % | 50.2 % | 14.74 pts | 12665 | 0 |
| magento-live | 8MB | 98.8 % | 98.4 % | 98.5 % | 0.41 pts | 703 | 0 |

## magento1-synth, 1% (64 objets)

94862 requêtes cachables, 6489 clés ; 1.9 % des requêtes portent sur une clé vue une seule fois.

**Cause du miss dans CACHEUS++** (requêtes servies par opt) :

- évincée par LFU : 3796 (37.6 %)
- refusée à l'admission : 2657 (26.3 %)
- évincée par GDSF : 2435 (24.1 %)
- évincée par LRU : 1221 (12.1 %)

**Qualité des évictions** (rang de la victime : 0 = choix de Belady, 0,5 = au hasard, 1 = pire) :

- victime choisie : 0.299 ; meilleur des trois candidats : 0.107 ; expert tiré = meilleur des trois dans 45.0 % des cas
- candidat de chaque expert : LRU 0.458, LFU 0.233, GDSF 0.339
- évictions par expert : {'LFU': 14293, 'GDSF': 7770, 'LRU': 4721} ; poids finaux {'LRU': 0.965, 'LFU': 0.001, 'GDSF': 0.034}, min-max au fil du temps {'LRU': [0.179, 0.987], 'LFU': [0.001, 0.623], 'GDSF': [0.012, 0.621]}
- pollution : 0.7 % du cache occupé par des clés jamais redemandées ; victime déjà « morte » dans 2.7 % des évictions ; refus d'admission : 27915

**Écart par popularité** : 1-10 % 73.6 %, top 1 % des clés 19.1 %, 10-50 % 7.0 %, 50-100 % (traîne) 0.3 %

**Écart par distance de réutilisation** : 4-16 × capacité 52.9 %, 1-4 × capacité 34.9 %, < capacité (64 clés) 12.3 %

**Écart par type de page** : catalog_product_view 56.7 %, catalog_category_view 35.2 %, catalogsearch_result_index 8.1 %

## magento1-synth, 5% (324 objets)

94862 requêtes cachables, 6489 clés ; 1.9 % des requêtes portent sur une clé vue une seule fois.

**Cause du miss dans CACHEUS++** (requêtes servies par opt) :

- évincée par LFU : 3093 (45.0 %)
- évincée par GDSF : 1781 (25.9 %)
- refusée à l'admission : 1326 (19.3 %)
- évincée par LRU : 679 (9.9 %)

**Qualité des évictions** (rang de la victime : 0 = choix de Belady, 0,5 = au hasard, 1 = pire) :

- victime choisie : 0.233 ; meilleur des trois candidats : 0.075 ; expert tiré = meilleur des trois dans 49.6 % des cas
- candidat de chaque expert : LRU 0.433, LFU 0.162, GDSF 0.305
- évictions par expert : {'LFU': 13348, 'GDSF': 5474, 'LRU': 2628} ; poids finaux {'LRU': 0.957, 'LFU': 0.001, 'GDSF': 0.042}, min-max au fil du temps {'LRU': [0.115, 0.962], 'LFU': [0.001, 0.603], 'GDSF': [0.037, 0.696]}
- pollution : 2.2 % du cache occupé par des clés jamais redemandées ; victime déjà « morte » dans 10.6 % des évictions ; refus d'admission : 9907

**Écart par popularité** : 1-10 % 57.2 %, 10-50 % 40.1 %, 50-100 % (traîne) 1.9 %, top 1 % des clés 0.8 %

**Écart par distance de réutilisation** : 4-16 × capacité 55.8 %, 1-4 × capacité 31.1 %, < capacité (324 clés) 13.1 %

**Écart par type de page** : catalog_product_view 79.9 %, catalogsearch_result_index 12.8 %, catalog_category_view 7.4 %

## magento-2020-Mar, 1% (230 objets)

95522 requêtes cachables, 23066 clés ; 11.4 % des requêtes portent sur une clé vue une seule fois.

**Cause du miss dans CACHEUS++** (requêtes servies par opt) :

- refusée à l'admission : 4962 (27.4 %)
- évincée par LFU : 4927 (27.2 %)
- évincée par LRU : 4776 (26.4 %)
- évincée par GDSF : 3429 (19.0 %)

**Qualité des évictions** (rang de la victime : 0 = choix de Belady, 0,5 = au hasard, 1 = pire) :

- victime choisie : 0.342 ; meilleur des trois candidats : 0.103 ; expert tiré = meilleur des trois dans 42.5 % des cas
- candidat de chaque expert : LRU 0.481, LFU 0.280, GDSF 0.327
- évictions par expert : {'LFU': 23925, 'GDSF': 16017, 'LRU': 13897} ; poids finaux {'LRU': 0.942, 'LFU': 0.004, 'GDSF': 0.054}, min-max au fil du temps {'LRU': [0.001, 0.935], 'LFU': [0.006, 0.996], 'GDSF': [0.003, 0.524]}
- pollution : 11.1 % du cache occupé par des clés jamais redemandées ; victime déjà « morte » dans 28.4 % des évictions ; refus d'admission : 12640

**Écart par popularité** : 10-50 % 41.7 %, 1-10 % 35.3 %, top 1 % des clés 20.1 %, 50-100 % (traîne) 2.9 %

**Écart par distance de réutilisation** : 1-4 × capacité 48.5 %, 4-16 × capacité 32.2 %, < capacité (230 clés) 19.2 %

**Écart par type de page** : catalog_product_view 100.0 %

## magento-2020-Mar, 5% (1153 objets)

95522 requêtes cachables, 23066 clés ; 11.4 % des requêtes portent sur une clé vue une seule fois.

**Cause du miss dans CACHEUS++** (requêtes servies par opt) :

- évincée par LRU : 5235 (41.3 %)
- évincée par GDSF : 5130 (40.5 %)
- évincée par LFU : 2111 (16.7 %)
- refusée à l'admission : 189 (1.5 %)

**Qualité des évictions** (rang de la victime : 0 = choix de Belady, 0,5 = au hasard, 1 = pire) :

- victime choisie : 0.282 ; meilleur des trois candidats : 0.059 ; expert tiré = meilleur des trois dans 54.9 % des cas
- candidat de chaque expert : LRU 0.453, LFU 0.208, GDSF 0.251
- évictions par expert : {'GDSF': 22022, 'LFU': 10948, 'LRU': 10970} ; poids finaux {'LRU': 0.124, 'LFU': 0.874, 'GDSF': 0.001}, min-max au fil du temps {'LRU': [0.092, 0.954], 'LFU': [0.006, 0.885], 'GDSF': [0.001, 0.897]}
- pollution : 28.7 % du cache occupé par des clés jamais redemandées ; victime déjà « morte » dans 48.3 % des évictions ; refus d'admission : 577

**Écart par popularité** : 1-10 % 48.8 %, 10-50 % 38.4 %, top 1 % des clés 9.5 %, 50-100 % (traîne) 3.3 %

**Écart par distance de réutilisation** : 4-16 × capacité 57.7 %, 1-4 × capacité 29.4 %, < capacité (1153 clés) 12.8 %, > 16 × capacité 0.1 %

**Écart par type de page** : catalog_product_view 100.0 %

## magento-live, 8MB (8388608 octets)

190563 requêtes cachables, 2308 clés ; 0.0 % des requêtes portent sur une clé vue une seule fois.

**Cause du miss dans CACHEUS++** (requêtes servies par opt) :

- évincée par GDSF : 406 (57.8 %)
- évincée par LRU : 177 (25.2 %)
- évincée par LFU : 120 (17.1 %)

**Qualité des évictions** (rang de la victime : 0 = choix de Belady, 0,5 = au hasard, 1 = pire) :

- victime choisie : 0.191 ; meilleur des trois candidats : 0.025 ; expert tiré = meilleur des trois dans 74.6 % des cas
- candidat de chaque expert : LRU 0.150, LFU 0.093, GDSF 0.358
- évictions par expert : {'GDSF': 847, 'LFU': 1015, 'LRU': 953} ; poids finaux {'LRU': 0.339, 'LFU': 0.366, 'GDSF': 0.296}, min-max au fil du temps {'LRU': [0.326, 0.348], 'LFU': [0.333, 0.365], 'GDSF': [0.296, 0.333]}
- pollution : 60.8 % du cache occupé par des clés jamais redemandées ; victime déjà « morte » dans 72.7 % des évictions ; refus d'admission : 0

**Écart par popularité** : 1-10 % 66.6 %, 10-50 % 33.4 %

**Écart par distance de réutilisation** : > 16 × capacité 97.2 %, 4-16 × capacité 2.7 %, 1-4 × capacité 0.1 %

**Écart par type de page** : ? 100.0 %
