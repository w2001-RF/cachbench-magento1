# cachebench

Benchmark d'algorithmes de cache pilotés par l'IA, appliqué aux boutiques Magento.
L'architecture est décrite dans [docs/architecture.md](docs/architecture.md).

État : **étapes 1 à 4** (cœur Python, politiques de référence, générateur Magento 1,
code officiel de CACHEUS, LeCaR, ARC et LIRS, éviction apprise façon DRL-Cache,
cache sémantique façon GPTCache / Upstash, CACHEUS++, module PHP pour Magento 1),
avec une interface web locale pour tout lancer sans la ligne de commande.

## Installation

```bash
pip install -e ".[dev,official]"
pip install -e ".[gpu]"        # facultatif : entraîner drl sur une carte NVIDIA (CUDA 13)
./scripts/fetch_vendor.sh      # code officiel de sylab/cacheus, commit figé
pytest -q
```

Sous Windows, avec PowerShell et Git installés :

```powershell
.\scripts\fetch_vendor.ps1
```

## Interface web

```bash
cachebench ui            # ouvre http://127.0.0.1:8765/ dans le navigateur
```

Lancée depuis la racine du projet (ou avec `--root`), elle donne accès, sans taper de
commande, à tout ce que fait la ligne de commande :

| Onglet | Ce qu'on y fait |
| --- | --- |
| **Expérience** | partir d'un YAML d'`experiments/` ou d'une expérience vide ; choisir les traces (synthétique ou fichier, motif, dossier), cocher les politiques (avec variantes et paramètres), les tailles de cache, les graines et le moteur ; lancer, suivre l'avancement, lire le tableau et le graphique ; voir ou modifier le YAML, l'enregistrer dans `experiments/` |
| **Traces** | statistiques d'un fichier, génération d'une trace synthétique, conversion d'un jeu externe au format commun, entraînement du modèle `drl` |
| **Résultats** | tous les `*_summary.csv` et `*.http.csv` de `results/`, en tableau (moyenne ± écart-type, meilleur hit rate en gras) et en graphique par taille de cache |
| **Test Magento** | lit la politique configurée dans `app/etc/local.xml`, puis rejoue une trace en vraies requêtes HTTP sur la boutique (`scripts/http_replay.py`) : temps moyen, médiane, p95 et échecs par type de page |
| **Tâches** | toutes les tâches lancées, leur commande et leur journal complet ; annulation |

Chaque action exécute la commande `cachebench` correspondante (affichée au-dessus de son
journal) : les résultats sont les mêmes qu'en ligne de commande et s'écrivent aux mêmes
endroits. L'interface n'utilise que la bibliothèque standard de Python, n'écoute que sur
127.0.0.1 et n'écrit que dans le dossier du projet. Un lien `#results=results/x_summary.csv`
ouvre directement un résultat.

Le test Magento ne modifie pas la boutique : pour comparer deux politiques, changez
`<policy>` dans `local.xml`, videz le cache de Magento, puis relancez le test en nommant le
fichier de sortie d'après la politique (`results/http/lru-8MB.http.csv`).

## Utilisation en ligne de commande

```bash
cachebench list                                         # politiques disponibles
cachebench gen-trace traces/synth.csv -n 100000 --seed 1
cachebench stats traces/synth.csv
cachebench stats magento_trace_2019_Dec.csv             # tout format externe, détecté
cachebench convert cluster001.csv traces/twitter.csv    # vers le format commun (rejeu PHP)
cachebench run experiments/magento-external.yaml        # traces externes (motif *.csv)
cachebench run experiments/magento1-baseline.yaml       # écrit results/*.csv
cachebench run experiments/magento1-official.yaml       # étape 2 : CACHEUS, LeCaR, ARC, LIRS
cachebench train-drl models/drl-unit.json --sizes unit  # étape 3 : entraînement (graine 1001)
cachebench train-drl models/drl-512.json --hidden 512 --batch 2048 --device gpu   # sur GPU
cachebench run experiments/magento1-learned.yaml        # étape 3 : éviction apprise
cachebench run experiments/magento1-semantic.yaml       # étape 3 : cache sémantique
cachebench ui                                           # interface web (voir ci-dessus)
python scripts/http_replay.py traces/mar2020.csv http://127.0.0.1/magento --out results/http/lru.http.csv -n 2000 -c 4
```

## Code officiel (étape 2)

`cacheus`, `lecar`, `arc` et `lirs` exécutent le code du dépôt
[sylab/cacheus](https://github.com/sylab/cacheus) **sans modification**, importé depuis
`vendor/cacheus` (voir `cachebench/policies/official.py`). Deux règles en découlent :

- ils comptent des objets : l'expérience doit utiliser `engine: {sizes: unit}` ;
- ils ne savent pas retirer une entrée : on compare avec `engine: {invalidation: lazy}`,
  où une page purgée reste en cache mais sa requête suivante compte comme un miss.
  Cette règle s'applique alors à **toutes** les politiques, pour une comparaison équitable.

Le dépôt cacheus n'a pas de fichier LICENSE : `vendor/` est réservé à un usage de recherche
et ne doit pas être redistribué.

## Éviction apprise (étape 3)

`drl` reprend la conception de [DRL-Cache](https://github.com/ayushgupta4897/DRL-Cache),
**pas son code** (lié à NGINX et PyTorch) : au moment d'évincer, un réseau note les K objets
les moins récemment utilisés à partir de leurs features (âge, taille, hits, temps depuis le
dernier accès, coût de recalcul, rang LRU, type de page) et évince le mieux noté. La
récompense est celle de DRL-Cache : -(hits futurs perdus dans un horizon), +0,1 si l'objet
ne revient pas. Elle se calcule pour chaque candidat depuis la trace, donc l'apprentissage
est un bandit contextuel, fait hors ligne.

- Le modèle s'entraîne sur une trace d'une **autre graine** (1001) que celles d'évaluation (1 à 5).
- C'est un petit réseau numpy (10 → 32 → 32 → 1) exporté en JSON (`models/`), que le module
  PHP pourra évaluer sans dépendance.
- Plus K est grand, meilleur est le hit rate, mais plus la décision coûte (voir `overhead_us`).

### Entraîner sur GPU

`train-drl --device gpu` fait l'entraînement du réseau sur une carte NVIDIA avec
[CuPy](https://cupy.dev), qui reprend l'API de numpy : même code, mêmes lots dans le même
ordre, même Adam, en float64. Les poids obtenus diffèrent de ceux du processeur de moins de
1e-14 (ordre des sommes) et s'exportent dans le même JSON, lu tel quel par le module PHP.
`--device auto` prend le GPU s'il répond, sinon le processeur ; `cpu` reste la valeur par
défaut et donne exactement les mêmes modèles qu'avant.

```bash
pip install -e ".[gpu]"           # cupy-cuda13x ; pour CUDA 12 : pip install cupy-cuda12x
cachebench train-drl models/drl-512.json --sizes unit --hidden 512 --batch 2048 --device gpu
```

Le GPU n'aide que pour un réseau plus gros que celui par défaut. Mesures sur une RTX 4060
(trace synthétique de 100 000 requêtes, 8 époques) :

| Réseau | Processeur | GPU |
| --- | --- | --- |
| 32 neurones par couche, lots de 512 (défaut) | 8 s au total, réseau < 1 s | plus lent (lancement des calculs sur la carte) |
| 512 neurones par couche, lots de 2048 | 153 s | 35 s |

Seul l'entraînement du réseau passe sur la carte. La collecte des décisions d'éviction (une
simulation) reste sur le processeur, comme l'évaluation du modèle pendant une expérience et
dans Magento. Un réseau plus gros coûte donc plus cher à chaque éviction : avec 512 neurones,
le calcul en PHP est environ 200 fois plus long qu'avec 32 (268 000 multiplications par
candidat au lieu de 1 400). Vérifiez `overhead_us` avant de
le déployer.

## CACHEUS++

`cacheus_pp` exécute **sans modification** `algorithms/cacheus_pp.py` du projet
cache_benchmark, copié dans `cachebench/_cache_benchmark/` avec les deux modules qu'il
importe (`base.py`, `models.py`). L'adaptateur (`cachebench/policies/cacheus_pp.py`)
l'appelle comme son runner : `get`, puis en cas de miss `should_cache` et `put`.

- trois experts (LRU, LFU, GDSF) arbitrés par minimisation du regret (LeCaR / CACHEUS),
  une couche REINFORCE, et une admission apprise par régression logistique ;
- la route Magento (`kind`) sert de catégorie et `cost_ms` de coût de miss pour GDSF ;
- octets ou unités ; en unités, il faut au moins 10 objets de capacité
  (`max_object_fraction` = 0,1) ;
- une purge eager retire l'entrée via `_evict`, sans compter comme une éviction choisie ;
- portage PHP pour Magento (`lib/Aicache/CacheusPP/`) : même générateur que
  `np.random.default_rng` (PCG64, `Pcg64.php`) et mêmes calculs dans l'ordre de numpy, y
  compris le `dgemv` d'OpenBLAS pour `theta @ state`. 100 % de hits identiques sur 100 000
  requêtes réelles, environ 20 µs par requête en PHP 7.1.

Le code d'origine fait repartir à la version 1 une clé réinsérée : ses anciennes entrées de
tas redeviennent « valides » et le tas ne passe plus sous le seuil de compactage, recompacté
alors à chaque accès. Sans effet sur les décisions, mais coûteux ; le portage PHP compacte
donc plus rarement.

## CACHEUS++ v2

`cacheus_pp2` (`cachebench/policies/cacheus_pp2.py`, portage PHP
`lib/Aicache/CacheusPP/AlgorithmV2.php`) corrige les défauts de CACHEUS++ trouvés en comparant
ses décisions à celles d'OPT (`scripts/analyze_opt_gap.py`, rapport dans `results/opt-gap/`).
C'est une sous-classe de l'original, qui reste intact ; chaque correction a son paramètre, et
avec les valeurs d'origine (`ORIGINAL` dans le module) v2 rend exactement les décisions de
`cacheus_pp`, ce que vérifie `tests/test_cacheus_pp2.py`.

| Paramètre | Original → v2 | Défaut corrigé |
| --- | --- | --- |
| `fix_versions` | non → oui | une clé réinsérée repartait à la version 0 : ses anciennes entrées de tas redevenaient valides |
| `feedback` | `regret` → `counterfactual` | seul l'expert tiré était puni ; maintenant, le candidat de chaque expert entre dans son fantôme à chaque éviction |
| `history_factor` | 1 → 4 | fantômes de 4 tailles de cache au lieu d'une : la plupart des erreurs passaient inaperçues |
| `freq_window` | 0 → 50 | fréquences divisées par deux toutes les 50 × (entrées du cache) requêtes |
| `admission` | `logistic` → `none` | l'admission apprise refusait des clés qui reviennent ; sur les réglages, tout admettre faisait aussi bien (à l'évaluation, l'admission apprise aide un peu : −0,04 pts sans elle) |
| `max_object_fraction` | 0,1 → 0,5 | les entrées de configuration de Magento, demandées à chaque page, dépassaient 10 % d'un petit cache et n'étaient jamais gardées |

Essayés et écartés (mesures dans `results/cacheus-pp2/`) : choisir l'expert de plus fort
poids au lieu de le tirer au sort, retirer la couche REINFORCE, l'admission TinyLFU, une zone
de probation, un retour « tournoi » entre les trois candidats. Même un oracle qui prend
toujours le meilleur des trois candidats ne fait guère mieux : l'écart restant avec OPT tient
surtout à ce qu'OPT connaît l'avenir.

```bash
python scripts/eval_cacheus_pp2.py            # hors ligne : synthétique, 7 mois réels, journal de la boutique
python scripts/magento_live_eval.py --users 100 --capacities 2MB,8MB --reps 6   # sur la boutique, sous charge
```

`eval_cacheus_pp2.py` rejoue chaque cas sur des répliques indépendantes (20 traces
synthétiques, 10 graines par mois et par taille), tenues à l'écart du réglage, et compare
v2 à CACHEUS++ en appariant les répliques : intervalles de confiance à 95 % (Student et
bootstrap), tests t et de Wilcoxon, correction de Holm, et une ablation qui retire une
correction à la fois. `magento_live_eval.py` fait passer chaque politique sur la vraie
boutique, sous charge, en blocs dans un ordre tiré au sort. Les résultats et leur lecture
sont dans `results/cacheus-pp2/report.md` et `results/cacheus-pp2-live/report.md`.

Résultats (synthèse dans `results/cacheus-pp2/conclusions.md`) :

- **Hors ligne**, sur les cas non vus au réglage, v2 gagne dans 13 cas sur 15 et ne perd
  dans aucun : +0,7 à +2,3 pts sur les traces synthétiques, +1,5 pts sur les mois réels à 5 %,
  +3,6 pts sur le journal de la boutique en petit cache ; jeu égal sur les mois réels à 1 % et
  le journal à 4 Mo.
- **Sur la boutique à 150 visiteurs simultanés** (le maximum tenu sans cache pleine page) :
  - à 2 Mo, v2 gagne +7,8 pts de hit rate sur CACHEUS++ et divise le temps de réponse par 4 ;
  - à 8 Mo, v2 perd −0,4 pts.
- **Le temps de réponse dépend surtout du coût de l'état partagé.** Chaque page relit et
  réécrit tout l'état sous verrou : 2 ms pour LRU, 18 ms pour CACHEUS++, 25 ms pour v2. LRU
  reste donc le plus rapide sous charge, malgré un hit rate plus faible ou égal.

## Cache sémantique (étape 3)

`semantic` applique aux pages de recherche la chaîne de GPTCache : embedding, plus proche
voisin, seuil de similarité (`threshold`, l'équivalent du `minProximity` d'Upstash). Les
autres pages passent par un LRU exact. Le générateur marque l'intention réelle de chaque
recherche, ce qui permet de mesurer `false_hit_rate` : la part des requêtes servies avec la
page d'une autre recherche. L'embedding par défaut (trigrammes de caractères hachés) absorbe
fautes de frappe, ordre des mots et pluriels, mais pas les synonymes.

Une expérience croise **politiques × traces × tailles de cache × graines**. La taille du cache
se donne en pourcentage du volume unique cachable de la trace (`"5%"`), en unité (`"64MB"`)
ou en octets.

## Format de trace (commun avec le module PHP)

CSV avec l'en-tête `ts,op,key,size,cost_ms,kind,cacheable,tags,text` :

| Colonne | Sens |
| --- | --- |
| `ts` | secondes depuis le début de la trace |
| `op` | `get` (page demandée) ou `purge` (nettoyage par tags, ex. mise à jour de stock) |
| `key` | clé de cache (URL, id de bloc) |
| `size` | octets |
| `cost_ms` | temps de rendu en cas de miss |
| `kind` | route Magento 1 (`catalog_product_view`...) |
| `cacheable` | 0 pour panier, compte client... |
| `tags` | tags Magento séparés par `\|` |
| `text` | texte de recherche (piste sémantique) |

## Ajouter un algorithme

```python
from cachebench import KeyedPolicy, register

@register("mon_algo")
class MonAlgo(KeyedPolicy):
    def _on_hit(self, key, req): ...
    def _on_insert(self, key, req): ...
    def _on_remove(self, key): ...
    def _victim(self) -> str: ...   # clé à évincer
```

`KeyedPolicy` gère déjà le stockage, les tags, le comptage d'octets et la capacité.
Un algorithme qui gère lui-même son stockage (code officiel enveloppé) hérite de
`CachePolicy` et implémente `access`, `invalidate`, `used_bytes` et `__contains__`.
Le moteur vérifie après chaque requête que la capacité n'est jamais dépassée.

## Jeux de données externes

`path:` accepte, en plus du format commun, les formats du projet cache_benchmark, lus par
son `loaders.py` copié sans modification (`cachebench/_cache_benchmark/`). Le format est
détecté d'après le nom et la première ligne du fichier, ou forcé par `format:`.

| `format` | Fichiers |
| --- | --- |
| `cachebench` | CSV commun ci-dessus (générateur, module PHP) |
| `magento` | `timestamp,url,size,category` (`magento_trace_*.csv`) |
| `rees46` (`kaggle`) | événements e-commerce REES46 / Kaggle, `.csv` ou `.csv.gz` ; tailles synthétiques |
| `retailrocket` | `events.csv` de Retailrocket |
| `twitter` | traces de production Twitter (`timestamp,key,key_size,value_size,client,op,ttl`) |
| `libcachesim` | oracleGeneral binaire (`.bin`) ou CSV `# time, object, size, ...` |
| `access_log` | journaux Apache / Nginx / Varnish (Common ou Combined Log Format) |

```yaml
traces:
  - name: magento
    path: "C:/Users/moi/Downloads/input/magento_trace_*.csv"   # motif ou dossier : une trace par fichier
    max_requests: 50000                  # facultatif
    costs: {api: 350, product: 400}      # facultatif : temps de rendu (ms) par catégorie ou route
    uncacheable: []                      # facultatif : par défaut panier et compte
    options: {include_writes: true}      # facultatif : passé au lecteur d'origine
```

Conversion vers `Request` : `ts` part de 0 ; la catégorie devient une route Magento 1
(`product` → `catalog_product_view`, `api` → `checkout_cart_index`, donc non cachable) ;
une catégorie inconnue (`kv`, `object`) reste telle quelle. Ces jeux n'ont pas de temps de
rendu : `cost_ms` vaut la médiane du générateur pour la route (400 ms pour un produit), 0
pour les autres. La latence simulée n'y vaut donc que comme ordre de grandeur. Ils ne
contiennent ni purge ni tags.

Pour un autre format : écrire un lecteur qui produit des `Request`, ou convertir au CSV
commun.

## Métriques

- **hit rate** : hits / requêtes cachables, après la chauffe (10 % par défaut) ;
- **latence simulée** (moyenne, p50, p95, p99) : `hit_cost_ms` si hit, `cost_ms` de la
  requête sinon ; les pages non cachables comptent avec leur coût, comme pour un vrai client ;
- **surcoût de décision** : temps moyen passé dans l'algorithme, en µs ;
- byte hit rate et nombre d'évictions.

`opt` (Belady) connaît le futur : c'est un plafond, pas un concurrent.

## Générateur Magento 1

Sessions de clients sur une chaîne de Markov de routes Magento 1, popularité en loi de
Zipf, cycle jour/nuit, promotions, nouveaux produits, purges par tags. Toutes les valeurs
par défaut (`Magento1Config`) sont des **hypothèses** à calibrer sur des traces réelles.
Surcharge possible dans le YAML (`params:`) ou en ligne de commande (`--params '{"product_alpha": 1.1}'`).

## Organisation

| Dossier | Contenu |
| --- | --- |
| `cachebench/traces/` | `Request`, lecture/écriture CSV, générateur Magento 1, traces externes |
| `cachebench/_cache_benchmark/` | fichiers du projet cache_benchmark, non modifiés (CACHEUS++, lecteurs) |
| `cachebench/policies/` | interface, registre, LRU, LFU, FIFO, OPT, adaptateurs du code officiel, `drl`, `semantic`, `cacheus_pp`, `cacheus_pp2` |
| `cachebench/ml/` | réseau numpy et export JSON |
| `models/` | modèles entraînés |
| `scripts/fetch_vendor.sh` | récupère le code officiel à un commit figé |
| `vendor/` | code officiel non modifié |
| `cachebench/engine.py` | simulation, capacité, métriques |
| `cachebench/experiment.py` | expériences YAML, résumé moyenne ± écart-type |
| `cachebench/cli.py` | ligne de commande `cachebench` |
| `cachebench/ui/` | interface web : `server.py` (API JSON, tâches en sous-processus) et `static/` (page, script, styles) |
| `experiments/` | configurations d'expériences |
| `scripts/http_replay.py` | rejoue une trace en requêtes HTTP sur une boutique Magento et mesure les temps |
| `scripts/magento_seed_customers.py` | ajoute des clients synthétiques (noms, adresses) dans la base MySQL de Magento |
| `scripts/magento_load_test.py` | test de charge par paliers : visiteurs simultanés tenus, débit maximal |
| `scripts/analyze_opt_gap.py` | pourquoi OPT fait mieux que CACHEUS++, décision par décision |
| `scripts/eval_cacheus_pp2.py`, `scripts/stats_tools.py` | évaluation hors ligne de CACHEUS++ v2, intervalles de confiance et tests appariés |
| `scripts/magento_live_eval.py`, `scripts/magento_cache_reset.php` | comparaison des politiques sur la boutique, sous charge, en blocs aléatoires |
| `results/` | résultats des expériences ; `magento-live*/` : tests HTTP sur la boutique locale |
| `docs/architecture.md` | architecture du projet |
| `php/` | module Magento 1 et bibliothèque PHP (même arborescence que Magento) |
| `tests/` | tests, dont la conformité PHP / Python |

## Module PHP Magento 1 (étape 4)

Le dossier `php/` a la même arborescence qu'une installation Magento 1.9 / OpenMage
(PHP 7.0 à 8.x, 64 bits) : on copie `lib/`, `app/` et `shell/` à la racine de Magento.

- `lib/Aicache/` : bibliothèque sans dépendance, nommée à la façon Magento
  (`Aicache_Policy_Lru` → `lib/Aicache/Policy/Lru.php`). Politiques `lru`, `fifo`, `lfu`,
  `drl` (lit le même JSON que Python), `semantic`, et portages de `lecar`, `cacheus`, `cacheus_pp` et `cacheus_pp2`
  (même générateur aléatoire que numpy, poids en float32 comme numpy).
- `app/code/local/Aicache/Benchmark/` : module `Aicache_Benchmark`.
  - **Journal des requêtes** : chaque page vitrine servie est écrite dans
    `var/aicache/trace.csv` au format de trace commun, avec son vrai temps de rendu
    (`cost_ms`), sa taille et ses tags ; les purges de cache par tags aussi. À activer dans
    Système → Configuration → Avancé → AI Cache Benchmark. Ce fichier remplace la trace
    synthétique : dans le YAML, `traces: [{name: reel, path: var/aicache/trace.csv}]`.
  - **Backend de cache** `Aicache_Benchmark_Model_Backend` : se place devant le backend
    existant (fichier, Redis) dans `app/etc/local.xml` ; la politique choisie décide quoi
    évincer quand la capacité est atteinte. Exemple et limites en tête du fichier. L'état
    de la politique est partagé entre requêtes via APCu (ou un fichier verrouillé).
- `shell/aicache_replay.php` : rejoue une trace avec les mêmes règles que le moteur Python.

```bash
php php/shell/aicache_replay.php --trace traces/m1.csv --policy lru --capacity 10%
php php/shell/aicache_replay.php --trace traces/m1.csv --policy cacheus --sizes unit --invalidation lazy
php php/shell/aicache_replay.php --trace traces/m1.csv --policy drl --param model=models/drl-bytes.json
```

**Conformité** (`tests/test_php_conformance.py`) : pour chaque politique, PHP et Python
donnent le même hit ou miss à chaque requête. Vérifié aussi à la main sur deux traces de
100 000 requêtes : 100 % d'accord pour toutes, LeCaR et CACHEUS compris. Le générateur
aléatoire PHP reproduit celui de numpy, ainsi que les deux façons d'arrondir de CACHEUS.

Coût par requête en PHP 8.3 (cache à 10 %, unités) : LRU, LFU, LeCaR, CACHEUS et le
cache sémantique entre 1 et 6 µs, plus rapides qu'en Python. DRL avec 64 candidats coûte
environ 370 µs sans JIT et 95 µs avec `opcache.jit=tracing` ; avec 16 candidats c'est
environ 4 fois moins. À comparer aux 150 ms de rendu moyen d'une page.

Pour que PHP et Python départagent deux recherches également proches de la même façon,
la similarité sémantique se calcule sur des comptes entiers de trigrammes
(produit scalaire exact, puis une seule division).

## Installer le module sur Magento 1 en local (Windows + WampServer)

Les chemins ci-dessous supposent WampServer 64 bits installé dans `C:\wamp64` et Magento
dans `C:\wamp64\www\magento`. Remplacez-les par les vôtres.

### 1. Vérifier la version de PHP

Le module demande **PHP 7.0 ou plus, en 64 bits** (LeCaR et CACHEUS en ont besoin pour leur
générateur aléatoire). Dans WampServer, clic gauche sur l'icône de la barre des tâches →
PHP → Version : c'est celle qu'utilise Apache, donc Magento. Pour le vérifier, créez
`C:\wamp64\www\info.php` contenant `<?php phpinfo();`, ouvrez http://localhost/info.php
et regardez « PHP Version » et « Architecture : x64 ». Supprimez le fichier ensuite.

Si votre Magento 1 tourne encore en PHP 5.6, le module ne fonctionnera pas : choisissez une
version 7.x dans ce même menu (Magento 1.9 en PHP 7 demande le correctif PHP 7 d'OpenMage
ou de Magento ; OpenMage 19.x et 20.x le gèrent déjà).

**APCu (conseillé)** : clic gauche sur l'icône → PHP → Extensions PHP → cochez `apcu`, puis
redémarrez les services. Sans APCu, l'état de la politique est gardé dans un fichier
verrouillé du dossier temporaire de PHP (`C:\wamp64\tmp` en général) : ça marche, en un
peu plus lent.

### 2. Copier les fichiers

Le dossier `php\` a la même arborescence que Magento. Dans une invite de commandes (`cmd`) :

```bat
set CB=C:\chemin\vers\cachebench
set MAGE=C:\wamp64\www\magento

xcopy /E /I /Y "%CB%\php\lib\Aicache"                        "%MAGE%\lib\Aicache"
xcopy /E /I /Y "%CB%\php\app\code\local\Aicache"             "%MAGE%\app\code\local\Aicache"
copy  /Y       "%CB%\php\app\etc\modules\Aicache_Benchmark.xml" "%MAGE%\app\etc\modules\"
copy  /Y       "%CB%\php\shell\aicache_replay.php"           "%MAGE%\shell\"
```

Si `app\code\local` n'existe pas encore, `xcopy /I` le crée. Pour DRL, copiez aussi le modèle :
`xcopy /I /Y "%CB%\models" "%MAGE%\var\aicache\models"`.

### 3. Faire reconnaître le module

1. Videz le cache de Magento : Système → Gestion du cache → « Vider le cache de Magento »,
   ou supprimez le contenu de `C:\wamp64\www\magento\var\cache`.
2. Si la compilation est activée (Système → Outils → Compilation), désactivez-la, ou
   relancez « Lancer la compilation » après la copie.
3. Déconnectez-vous de l'admin puis reconnectez-vous (sinon la nouvelle section de
   configuration renvoie « Accès refusé » ou 404).
4. Vérifiez : Système → Configuration → Avancé → Avancé → « Désactiver la sortie des
   modules » doit lister `Aicache_Benchmark`.

### 4. Enregistrer une vraie trace (sans toucher au cache)

Système → Configuration → Avancé → **AI Cache Benchmark** → Activer : Oui. Chaque page
vitrine visitée est alors ajoutée à `C:\wamp64\www\magento\var\aicache\trace.csv`, avec son
temps de rendu réel. Naviguez sur la boutique (accueil, catégories, fiches produit,
recherches), modifiez quelques produits dans l'admin pour produire des purges, puis :

```bat
cd /d C:\wamp64\www\magento
C:\wamp64\bin\php\php7.4.33\php.exe shell\aicache_replay.php --trace var\aicache\trace.csv --policy lru --capacity 10%
C:\wamp64\bin\php\php7.4.33\php.exe shell\aicache_replay.php --trace var\aicache\trace.csv --policy cacheus --sizes unit --invalidation lazy
```

(adaptez `php7.4.33` au dossier de votre version dans `C:\wamp64\bin\php`). Le même fichier
se rejoue côté Python : dans un YAML d'expérience,
`traces: [{name: reel, path: C:/wamp64/www/magento/var/aicache/trace.csv}]`.

Désactivez le journal quand vous avez fini : il écrit une ligne par page.

### 5. Laisser une politique gérer le cache de Magento

Créez le dossier `C:\wamp64\www\magento\var\cache_aicache`, puis dans
`C:\wamp64\www\magento\app\etc\local.xml`, à l'intérieur de `<global>`, ajoutez (ou remplacez
le bloc `<cache>` existant ; gardez-en une copie) :

```xml
<cache>
    <backend>Aicache_Benchmark_Model_Backend</backend>
    <backend_options>
        <inner_backend>Zend_Cache_Backend_File</inner_backend>
        <inner_options>
            <cache_dir>C:/wamp64/www/magento/var/cache_aicache</cache_dir>
        </inner_options>
        <policy>cacheus</policy>            <!-- lru, lfu, fifo, drl, lecar, cacheus, cacheus_pp, cacheus_pp2 -->
        <state_dir>C:/wamp64/www/magento/var/aicache/state</state_dir>  <!-- sans APCu : même état pour Apache et la CLI -->
        <capacity>2000</capacity>           <!-- octets ; nombre d'entrées pour lecar et cacheus -->
        <!-- pour drl : <policy>drl</policy> <capacity>67108864</capacity>
             <params><model>C:/wamp64/www/magento/var/aicache/models/drl-bytes.json</model></params> -->
        <trace_file>C:/wamp64/www/magento/var/aicache/cache-trace.csv</trace_file>  <!-- facultatif -->
    </backend_options>
</cache>
```

Videz ensuite `var\cache` et `var\cache_aicache`, et rechargez la boutique. Utilisez des
chemins absolus avec des `/` : le dossier courant d'Apache n'est pas toujours la racine
de Magento. Si vous utilisiez Redis (`Cm_Cache_Backend_Redis`), mettez-le en
`inner_backend` avec ses options dans `inner_options`.

Pour changer de politique, modifiez `<policy>`, puis videz le cache depuis l'admin (cela
remet aussi la politique à zéro). Pour revenir en arrière, remettez l'ancien bloc
`<cache>` et videz `var\cache`.

**Dépannage**
- Page blanche ou erreur : lisez `var\log\exception.log` et `C:\wamp64\logs\php_error.log`.
  « Class not found » veut dire qu'un dossier n'a pas été copié au bon endroit.
- « PHP 64 bits requis » : la version de PHP choisie dans WampServer est en 32 bits.
- Rien dans `trace.csv` : le journal est désactivé, ou le cache de configuration n'a pas
  été vidé après l'activation.

## Clients synthétiques et test de charge

Deux scripts, à lancer à la main depuis la racine du projet, mesurent combien de visiteurs
simultanés la boutique locale supporte.

**1. Créer des clients** (directement dans la base MySQL de Magento) :

```bash
python scripts/magento_seed_customers.py -n 5000 --backup C:/wamp64/www/magento/var/aicache_backup/customers.sql
python scripts/magento_seed_customers.py --delete        # les retirer
```

Noms, e-mails, dates de naissance et adresses vraisemblables (Maroc, France, Belgique,
Royaume-Uni, Allemagne, Pays-Bas), sur les domaines réservés `example.com/.net/.org` : aucun
e-mail ne peut partir vers une vraie personne. Mot de passe commun (`--password`, par défaut
`Test1234!`), haché comme Magento 1.9.4. Les clients ajoutés portent `increment_id =
synth-<n>`, ce qui permet à `--delete` de ne jamais toucher aux vrais. La liste des comptes
est écrite dans `data/magento_customers.csv` pour le test de charge. `--dry-run fichier.sql`
écrit le SQL sans l'exécuter.

**2. Lancer le test de charge** :

```bash
python scripts/magento_load_test.py                                  # 10 à 300 visiteurs, 1 min par palier
python scripts/magento_load_test.py --users 20,40,60,80 --step 120   # paliers plus fins autour de la limite
python scripts/magento_load_test.py --users 4,8,16,32 --think 0      # débit maximal, sans pause
```

Chaque visiteur virtuel garde ses cookies et parcourt la boutique comme un client : accueil,
catégories (pages suivantes, tris), recherche, fiches produit (produits populaires plus
souvent), ajout au panier, panier, connexion avec un des comptes créés, espace client, page
de commande, déconnexion, avec une pause de 2 à 8 s entre deux pages (`--think`). Aucune
commande n'est passée. Le nombre de visiteurs monte par paliers (`--users`, `--step`) ; un
palier **tient** si les erreurs restent sous 1 % (`--max-error`) et le p95 sous 3 s
(`--max-p95`). Le test s'arrête au premier palier qui ne tient pas et écrit dans
`results/loadtest/<date>/` : `report.md` (tableau des paliers, limite, détail par page),
`steps.csv`, `requests.csv` et `summary.json`. Il compte aussi les plantages d'Apache dans
`C:/wamp64/logs/apache_error.log` (`--apache-log`).

Le test mesure la boutique telle qu'elle est configurée (politique de cache de `local.xml`,
cache de pages, Xdebug) ; seules les pages HTML sont demandées, pas les images, CSS et JS.
Il remplit aussi des tables de Magento (sessions, paniers, journaux de visite) : à nettoyer
après coup (Système → Journaux, ou `php shell/log.php clean`).

## Étapes suivantes

5. Brancher le journal sur le Magento 1 local, collecter une vraie trace, recalibrer le
   générateur (`cost_ms`, tailles, popularité) et relancer les comparaisons dessus.
