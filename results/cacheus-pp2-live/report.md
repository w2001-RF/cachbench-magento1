# Test en conditions réelles sur la boutique Magento

Généré par `scripts/magento_live_eval.py`. 36 passes : 3 politiques × 2 capacités × 6 blocs, ordre tiré au sort dans chaque bloc. 150 visiteurs simultanés ; 240 s par passe dont 60 s non mesurées ; cache pleine page coupé. Moyenne ± demi-largeur de l'IC à 95 % (Student) sur les blocs.

## Hit rate (%)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 95.30 ± 0.61 | 88.77 ± 0.64 | 96.55 ± 0.45 |
| 8MB | 97.74 ± 0.04 | 98.21 ± 0.08 | 97.83 ± 0.14 |

## Byte hit rate (%)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 94.69 ± 0.12 | 57.91 ± 0.69 | 93.67 ± 1.95 |
| 8MB | 95.75 ± 0.06 | 96.33 ± 0.09 | 95.84 ± 0.15 |

## Temps moyen (ms)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 616.11 ± 22.65 | 6477.92 ± 345.41 | 1631.21 ± 789.19 |
| 8MB | 570.18 ± 32.82 | 1920.46 ± 279.01 | 2434.75 ± 346.76 |

## Médiane (ms)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 525.03 ± 18.44 | 6066.50 ± 212.15 | 1451.18 ± 938.65 |
| 8MB | 477.46 ± 33.48 | 1793.77 ± 175.56 | 2240.96 ± 242.77 |

## P95 (ms)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 1290.10 ± 78.88 | 11511.07 ± 373.45 | 3508.39 ± 1702.63 |
| 8MB | 1200.97 ± 55.58 | 3394.81 ± 405.35 | 4243.72 ± 553.25 |

## Débit (pages/s)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 34.04 ± 0.56 | 13.08 ± 0.48 | 24.34 ± 4.24 |
| 8MB | 34.80 ± 1.35 | 22.77 ± 1.47 | 20.59 ± 1.07 |

## Erreurs (%)

| Capacité | lru | cacheus_pp | cacheus_pp2 |
| --- | ---: | ---: | ---: |
| 2MB | 31.34 ± 2.00 | 0.41 ± 0.57 | 9.44 ± 8.60 |
| 8MB | 32.88 ± 4.80 | 6.46 ± 4.16 | 2.93 ± 2.44 |

## Comparaisons appariées par bloc

Δ = B − A sur les mêmes blocs. p de Holm corrigé sur toutes les lignes du tableau, à partir du test t : avec peu de blocs, le test de Wilcoxon ne peut pas descendre assez bas pour survivre à la correction.

| Mesure | Capacité | A | B | n | Δ | IC 95 % Student | IC 95 % bootstrap | p t | p Wilcoxon | p Holm | v/é/d |
| --- | --- | --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |
| hit rate | 2MB | lru | cacheus_pp | 6 | **-6.54 pts** | [-7.38, -5.69] | [-7.07, -5.86] | < 0.0001 | 0.0312 | 0.0001 | 0/0/6 |
| hit rate | 2MB | lru | cacheus_pp2 | 6 | **+1.25 pts** | [+0.79, +1.71] | [+0.94, +1.58] | 0.0009 | 0.0312 | 0.0113 | 6/0/0 |
| hit rate | 2MB | cacheus_pp | cacheus_pp2 | 6 | **+7.79 pts** | [+7.07, +8.51] | [+7.30, +8.29] | < 0.0001 | 0.0312 | < 0.0001 | 6/0/0 |
| hit rate | 8MB | lru | cacheus_pp | 6 | **+0.48 pts** | [+0.39, +0.57] | [+0.41, +0.54] | < 0.0001 | 0.0312 | 0.0007 | 6/0/0 |
| hit rate | 8MB | lru | cacheus_pp2 | 6 | **+0.10 pts** | [-0.04, +0.23] | [+0.01, +0.20] | 0.1310 | 0.0938 | 0.3930 | 5/0/1 |
| hit rate | 8MB | cacheus_pp | cacheus_pp2 | 6 | **-0.38 pts** | [-0.58, -0.19] | [-0.51, -0.24] | 0.0040 | 0.0312 | 0.0396 | 0/0/6 |
| byte hit rate | 2MB | lru | cacheus_pp | 6 | **-36.78 pts** | [-37.53, -36.03] | [-37.18, -36.17] | < 0.0001 | 0.0312 | < 0.0001 | 0/0/6 |
| byte hit rate | 2MB | lru | cacheus_pp2 | 6 | **-1.03 pts** | [-2.93, +0.88] | [-2.57, -0.08] | 0.2252 | 0.4375 | 0.3930 | 3/0/3 |
| byte hit rate | 2MB | cacheus_pp | cacheus_pp2 | 6 | **+35.75 pts** | [+33.65, +37.85] | [+34.13, +37.06] | < 0.0001 | 0.0312 | < 0.0001 | 6/0/0 |
| byte hit rate | 8MB | lru | cacheus_pp | 6 | **+0.58 pts** | [+0.47, +0.69] | [+0.51, +0.65] | < 0.0001 | 0.0312 | 0.0006 | 6/0/0 |
| byte hit rate | 8MB | lru | cacheus_pp2 | 6 | **+0.09 pts** | [-0.05, +0.23] | [-0.00, +0.20] | 0.1721 | 0.2188 | 0.3930 | 5/0/1 |
| byte hit rate | 8MB | cacheus_pp | cacheus_pp2 | 6 | **-0.49 pts** | [-0.71, -0.27] | [-0.64, -0.33] | 0.0021 | 0.0312 | 0.0235 | 0/0/6 |
| temps moyen | 2MB | lru | cacheus_pp | 6 | **+5861.82 ms** | [+5510.52, +6213.11] | [+5577.54, +6055.04] | < 0.0001 | 0.0312 | < 0.0001 | 6/0/0 |
| temps moyen | 2MB | lru | cacheus_pp2 | 6 | **+1015.11 ms** | [+224.79, +1805.43] | [+538.33, +1629.82] | 0.0214 | 0.0312 | 0.1675 | 6/0/0 |
| temps moyen | 2MB | cacheus_pp | cacheus_pp2 | 6 | **-4846.71 ms** | [-5740.52, -3952.90] | [-5407.26, -4175.36] | < 0.0001 | 0.0312 | 0.0006 | 0/0/6 |
| temps moyen | 8MB | lru | cacheus_pp | 6 | **+1350.28 ms** | [+1089.82, +1610.73] | [+1161.62, +1523.60] | < 0.0001 | 0.0312 | 0.0007 | 6/0/0 |
| temps moyen | 8MB | lru | cacheus_pp2 | 6 | **+1864.57 ms** | [+1531.52, +2197.62] | [+1634.98, +2103.26] | < 0.0001 | 0.0312 | 0.0006 | 6/0/0 |
| temps moyen | 8MB | cacheus_pp | cacheus_pp2 | 6 | **+514.30 ms** | [+78.47, +950.12] | [+220.18, +825.41] | 0.0290 | 0.0312 | 0.1675 | 6/0/0 |
| médiane | 2MB | lru | cacheus_pp | 6 | **+5541.47 ms** | [+5322.52, +5760.41] | [+5366.31, +5663.21] | < 0.0001 | 0.0312 | < 0.0001 | 6/0/0 |
| médiane | 2MB | lru | cacheus_pp2 | 6 | **+926.15 ms** | [-14.19, +1866.49] | [+408.78, +1661.52] | 0.0524 | 0.0312 | 0.2097 | 6/0/0 |
| médiane | 2MB | cacheus_pp | cacheus_pp2 | 6 | **-4615.32 ms** | [-5525.15, -3705.48] | [-5131.76, -3900.29] | < 0.0001 | 0.0312 | 0.0007 | 0/0/6 |
| médiane | 8MB | lru | cacheus_pp | 6 | **+1316.31 ms** | [+1163.65, +1468.97] | [+1201.34, +1416.08] | < 0.0001 | 0.0312 | < 0.0001 | 6/0/0 |
| médiane | 8MB | lru | cacheus_pp2 | 6 | **+1763.50 ms** | [+1535.98, +1991.02] | [+1610.93, +1922.27] | < 0.0001 | 0.0312 | 0.0001 | 6/0/0 |
| médiane | 8MB | cacheus_pp | cacheus_pp2 | 6 | **+447.19 ms** | [+182.47, +711.91] | [+264.84, +639.75] | 0.0074 | 0.0312 | 0.0667 | 6/0/0 |
| p95 | 2MB | lru | cacheus_pp | 6 | **+10220.96 ms** | [+9852.31, +10589.61] | [+9934.19, +10447.66] | < 0.0001 | 0.0312 | < 0.0001 | 6/0/0 |
| p95 | 2MB | lru | cacheus_pp2 | 6 | **+2218.28 ms** | [+502.38, +3934.19] | [+1072.87, +3439.69] | 0.0209 | 0.0312 | 0.1675 | 6/0/0 |
| p95 | 2MB | cacheus_pp | cacheus_pp2 | 6 | **-8002.68 ms** | [-9910.23, -6095.13] | [-9277.53, -6622.69] | 0.0001 | 0.0312 | 0.0015 | 0/0/6 |
| p95 | 8MB | lru | cacheus_pp | 6 | **+2193.85 ms** | [+1823.28, +2564.42] | [+1948.23, +2468.08] | < 0.0001 | 0.0312 | 0.0005 | 6/0/0 |
| p95 | 8MB | lru | cacheus_pp2 | 6 | **+3042.75 ms** | [+2517.20, +3568.31] | [+2715.76, +3427.11] | < 0.0001 | 0.0312 | 0.0005 | 6/0/0 |
| p95 | 8MB | cacheus_pp | cacheus_pp2 | 6 | **+848.91 ms** | [+174.53, +1523.28] | [+403.08, +1336.42] | 0.0231 | 0.0312 | 0.1675 | 6/0/0 |

Avec 6 blocs, le plus petit p possible du test de Wilcoxon (bilatéral, exact) est 0.0312.

## Passes

| Ordre | Passe | Politique | Capacité | Bloc | Requêtes | Erreurs | Plantages | Hit rate | Temps moyen |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 01-cacheus_pp2-2MB-b1 | cacheus_pp2 | 2MB | 1 | 3999 | 1.9 % | 1 | 97.02 % | 1811 ms |
| 2 | 02-lru-8MB-b1 | lru | 8MB | 1 | 6000 | 27.8 % | 7 | 97.73 % | 623 ms |
| 3 | 03-cacheus_pp-8MB-b1 | cacheus_pp | 8MB | 1 | 3778 | 0.3 % | 0 | 98.29 % | 2287 ms |
| 4 | 04-cacheus_pp2-8MB-b1 | cacheus_pp2 | 8MB | 1 | 3654 | 0.5 % | 0 | 97.79 % | 2515 ms |
| 5 | 05-cacheus_pp-2MB-b1 | cacheus_pp | 2MB | 1 | 2297 | 0.0 % | 0 | 88.60 % | 6731 ms |
| 6 | 06-lru-2MB-b1 | lru | 2MB | 1 | 6104 | 29.9 % | 10 | 96.15 % | 621 ms |
| 7 | 07-lru-2MB-b2 | lru | 2MB | 2 | 6273 | 32.4 % | 9 | 95.47 % | 627 ms |
| 8 | 08-lru-8MB-b2 | lru | 8MB | 2 | 6621 | 39.5 % | 11 | 97.74 % | 589 ms |
| 9 | 09-cacheus_pp-2MB-b2 | cacheus_pp | 2MB | 2 | 2370 | 0.0 % | 0 | 89.03 % | 6458 ms |
| 10 | 10-cacheus_pp-8MB-b2 | cacheus_pp | 8MB | 2 | 4261 | 9.2 % | 2 | 98.33 % | 1904 ms |
| 11 | 11-cacheus_pp2-8MB-b2 | cacheus_pp2 | 8MB | 2 | 3454 | 2.9 % | 1 | 97.72 % | 2974 ms |
| 12 | 12-cacheus_pp2-2MB-b2 | cacheus_pp2 | 2MB | 2 | 5491 | 24.5 % | 5 | 96.61 % | 1029 ms |
| 13 | 13-cacheus_pp-2MB-b3 | cacheus_pp | 2MB | 3 | 2343 | 1.2 % | 0 | 88.22 % | 6507 ms |
| 14 | 14-cacheus_pp2-8MB-b3 | cacheus_pp2 | 8MB | 3 | 3991 | 6.6 % | 1 | 97.75 % | 1993 ms |
| 15 | 15-cacheus_pp-8MB-b3 | cacheus_pp | 8MB | 3 | 4248 | 10.6 % | 2 | 98.19 % | 1816 ms |
| 16 | 16-cacheus_pp2-2MB-b3 | cacheus_pp2 | 2MB | 3 | 3380 | 3.7 % | 2 | 95.77 % | 2999 ms |
| 17 | 17-lru-2MB-b3 | lru | 2MB | 3 | 6186 | 32.1 % | 8 | 94.61 % | 616 ms |
| 18 | 18-lru-8MB-b3 | lru | 8MB | 3 | 6372 | 36.1 % | 10 | 97.73 % | 548 ms |
| 19 | 19-cacheus_pp2-2MB-b4 | cacheus_pp2 | 2MB | 4 | 4391 | 9.3 % | 4 | 96.51 % | 1341 ms |
| 20 | 20-lru-8MB-b4 | lru | 8MB | 4 | 6090 | 28.5 % | 8 | 97.75 % | 536 ms |
| 21 | 21-cacheus_pp-2MB-b4 | cacheus_pp | 2MB | 4 | 2317 | 0.3 % | 0 | 88.83 % | 6606 ms |
| 22 | 22-cacheus_pp2-8MB-b4 | cacheus_pp2 | 8MB | 4 | 3632 | 0.8 % | 1 | 98.08 % | 2477 ms |
| 23 | 23-cacheus_pp-8MB-b4 | cacheus_pp | 8MB | 4 | 4002 | 4.5 % | 1 | 98.15 % | 1896 ms |
| 24 | 24-lru-2MB-b4 | lru | 2MB | 4 | 5972 | 28.3 % | 8 | 95.73 % | 573 ms |
| 25 | 25-lru-2MB-b5 | lru | 2MB | 5 | 6141 | 31.8 % | 10 | 94.92 % | 628 ms |
| 26 | 26-cacheus_pp2-2MB-b5 | cacheus_pp2 | 2MB | 5 | 4172 | 5.8 % | 2 | 96.57 % | 1666 ms |
| 27 | 27-cacheus_pp-8MB-b5 | cacheus_pp | 8MB | 5 | 4428 | 9.4 % | 2 | 98.16 % | 1507 ms |
| 28 | 28-lru-8MB-b5 | lru | 8MB | 5 | 6382 | 34.4 % | 12 | 97.79 % | 561 ms |
| 29 | 29-cacheus_pp-2MB-b5 | cacheus_pp | 2MB | 5 | 2511 | 0.9 % | 0 | 89.79 % | 5845 ms |
| 30 | 30-cacheus_pp2-8MB-b5 | cacheus_pp2 | 8MB | 5 | 3676 | 2.3 % | 1 | 97.83 % | 2444 ms |
| 31 | 31-lru-8MB-b6 | lru | 8MB | 6 | 6133 | 31.0 % | 10 | 97.67 % | 565 ms |
| 32 | 32-lru-2MB-b6 | lru | 2MB | 6 | 6130 | 33.5 % | 10 | 94.94 % | 632 ms |
| 33 | 33-cacheus_pp2-2MB-b6 | cacheus_pp2 | 2MB | 6 | 4857 | 11.4 % | 3 | 96.84 % | 941 ms |
| 34 | 34-cacheus_pp-8MB-b6 | cacheus_pp | 8MB | 6 | 3880 | 4.8 % | 1 | 98.17 % | 2112 ms |
| 35 | 35-cacheus_pp2-8MB-b6 | cacheus_pp2 | 8MB | 6 | 3826 | 4.5 % | 1 | 97.82 % | 2206 ms |
| 36 | 36-cacheus_pp-2MB-b6 | cacheus_pp | 2MB | 6 | 2293 | 0.0 % | 0 | 88.13 % | 6721 ms |
