# cachebench

Benchmark d'algorithmes de cache pilotés par l'IA, appliqué aux boutiques Magento.
L'architecture complète est décrite dans le document « Architecture — Benchmark de cache IA pour Magento ».

État : **étapes 1 à 3** (cœur Python, politiques de référence, générateur Magento 1,
code officiel de CACHEUS, LeCaR, ARC et LIRS, éviction apprise façon DRL-Cache,
cache sémantique façon GPTCache / Upstash).

## Installation

```bash
pip install -e ".[dev,official]"
./scripts/fetch_vendor.sh      # code officiel de sylab/cacheus, commit figé
pytest -q
```

Sous Windows, avec PowerShell et Git installés :

```powershell
.\scripts\fetch_vendor.ps1
```

## Utilisation

```bash
cachebench list                                         # politiques disponibles
cachebench gen-trace traces/synth.csv -n 100000 --seed 1
cachebench stats traces/synth.csv
cachebench run experiments/magento1-baseline.yaml       # écrit results/*.csv
cachebench run experiments/magento1-official.yaml       # étape 2 : CACHEUS, LeCaR, ARC, LIRS
cachebench train-drl models/drl-unit.json --sizes unit  # étape 3 : entraînement (graine 1001)
cachebench run experiments/magento1-learned.yaml        # étape 3 : éviction apprise
cachebench run experiments/magento1-semantic.yaml       # étape 3 : cache sémantique
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

## Ajouter un jeu de données

Écrire un lecteur qui produit des `Request` (ou convertir au CSV ci-dessus), puis le
déclarer dans le YAML avec `path:`.

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
| `cachebench/traces/` | `Request`, lecture/écriture CSV, générateur Magento 1 |
| `cachebench/policies/` | interface, registre, LRU, LFU, FIFO, OPT, adaptateurs du code officiel, `drl`, `semantic` |
| `cachebench/ml/` | réseau numpy et export JSON |
| `models/` | modèles entraînés |
| `scripts/fetch_vendor.sh` | récupère le code officiel à un commit figé |
| `vendor/` | code officiel non modifié |
| `cachebench/engine.py` | simulation, capacité, métriques |
| `cachebench/experiment.py` | expériences YAML, résumé moyenne ± écart-type |
| `experiments/` | configurations d'expériences |
| `php/` | module Magento 1 et bibliothèque PHP (même arborescence que Magento) |
| `tests/` | tests, dont la conformité PHP / Python |

## Module PHP Magento 1 (étape 4)

Le dossier `php/` a la même arborescence qu'une installation Magento 1.9 / OpenMage
(PHP 7.0 à 8.x, 64 bits) : on copie `lib/`, `app/` et `shell/` à la racine de Magento.

- `lib/Aicache/` : bibliothèque sans dépendance, nommée à la façon Magento
  (`Aicache_Policy_Lru` → `lib/Aicache/Policy/Lru.php`). Politiques `lru`, `fifo`, `lfu`,
  `drl` (lit le même JSON que Python), `semantic`, et portages de `lecar` et `cacheus`
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
        <policy>cacheus</policy>            <!-- lru, lfu, fifo, drl, lecar, cacheus -->
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

## Étapes suivantes

5. Brancher le journal sur le Magento 1 local, collecter une vraie trace, recalibrer le
   générateur (`cost_ms`, tailles, popularité) et relancer les comparaisons dessus.
