# ADR-0001 : Interface web locale au-dessus de la ligne de commande

**Statut :** Proposé
**Date :** 2026-10-30
**Décideurs :** responsable du projet (w2001-RF)

## Contexte

Jusqu'ici, tout passait par la commande `cachebench` (`run`, `gen-trace`, `stats`,
`convert`, `train-drl`) et par `scripts/http_replay.py` pour les tests sur la boutique.
Lancer un test demandait d'écrire un YAML, de connaître les options de chaque commande et
de lire des CSV de résultats à la main. On veut une interface simple pour préparer,
lancer et lire les tests sans taper de commande.

Contraintes :

- **Machine de développement Windows** (WampServer, Python 3.13 dans un venv) ; pas de
  serveur à déployer, un seul utilisateur.
- **Dépendances** : le projet n'exige que `numpy` et `pyyaml`. Ajouter une grosse
  dépendance pour l'interface alourdit l'installation et le venv.
- **Tâches longues** : une expérience dure de quelques secondes à plusieurs dizaines de
  minutes, un test HTTP plusieurs minutes. Il faut suivre l'avancement et pouvoir annuler.
- **Mêmes résultats qu'en ligne de commande** : les résultats servent à comparer des
  politiques ; l'interface ne doit pas introduire un second chemin d'exécution qui
  pourrait diverger.
- **Code tiers sensible** : le code officiel de cacheus et CACHEUS++ garde un état global
  (générateurs aléatoires, imports de matplotlib) ; plusieurs exécutions dans un même
  processus ne sont pas garanties isolées.
- **Sécurité locale** : l'interface lance des processus et écrit des fichiers ; une page
  web quelconque ouverte dans le même navigateur ne doit pas pouvoir le faire à sa place.

## Décision

Une interface web servie par **`cachebench ui`**, construite ainsi :

- serveur en **bibliothèque standard** (`http.server.ThreadingHTTPServer`), écoutant sur
  127.0.0.1 uniquement, avec une petite API JSON (`cachebench/ui/server.py`) ;
- page **HTML, CSS et JavaScript sans bibliothèque ni étape de construction**, graphiques en
  SVG (`cachebench/ui/static/`) ;
- **chaque action lance la commande `cachebench` correspondante dans un sous-processus** ;
  le serveur garde son journal, que la page relit toutes les 0,7 s, puis lit le fichier
  produit (résumé CSV, JSON, CSV des temps HTTP) et le renvoie à la page ;
- garde-fous : POST en JSON uniquement, en-tête `Host` limité à 127.0.0.1 / localhost,
  fichiers écrits limités au dossier du projet.

## Options étudiées

### Option A : bibliothèque standard + page sans framework + sous-processus (retenue)

| Dimension | Évaluation |
| --- | --- |
| Complexité | Moyenne : environ 500 lignes de Python et 600 de JavaScript, écrites à la main |
| Coût | Aucune dépendance ajoutée |
| Montée en charge | Suffisante pour un utilisateur local ; non prévue pour un serveur partagé |
| Familiarité | Python et JavaScript simples, sans outil à apprendre |

**Pour :**
- rien à installer : `pip install -e .` suffit, y compris hors ligne ;
- résultats identiques à la ligne de commande par construction : c'est la même commande,
  affichée au-dessus de son journal ;
- annulation fiable (arrêt du processus) et isolation du code tiers à chaque tâche ;
- un plantage d'une politique n'arrête pas l'interface.

**Contre :**
- formulaires, tableau et graphique écrits à la main : plus de code à maintenir ;
- l'avancement n'est connu que par le journal texte de la commande ;
- le démarrage d'un sous-processus coûte environ une seconde (import de numpy).

### Option B : Streamlit

| Dimension | Évaluation |
| --- | --- |
| Complexité | Faible : l'interface s'écrit en Python, en peu de lignes |
| Coût | Dépendance lourde (Streamlit, pandas, pyarrow, tornado…), plusieurs centaines de Mo |
| Montée en charge | Bonne pour un usage local ou de petite équipe |
| Familiarité | Facile à prendre en main |

**Pour :** très rapide à écrire ; tableaux et graphiques intégrés.

**Contre :**
- grosse dépendance pour un projet qui n'en a que deux ;
- le script est réexécuté à chaque interaction : les tâches longues demandent des
  contournements (état de session, threads) ;
- tentation d'appeler `experiment.run` dans le même processus : isolation et annulation
  plus difficiles.

### Option C : FastAPI ou Flask + application React

| Dimension | Évaluation |
| --- | --- |
| Complexité | Élevée : deux projets, une chaîne de construction JavaScript |
| Coût | Dépendances Python et Node.js |
| Montée en charge | La meilleure, si l'outil devient un service partagé |
| Familiarité | Demande Node.js et un framework sur le poste |

**Pour :** structure solide si l'interface grandit beaucoup ; écosystème de composants.

**Contre :** démesuré pour un outil local à un utilisateur ; ajoute Node.js à l'installation
et une étape de construction à chaque modification.

### Option D : application de bureau Tkinter

| Dimension | Évaluation |
| --- | --- |
| Complexité | Moyenne |
| Coût | Aucune dépendance (Tkinter est fourni avec Python sous Windows) |
| Montée en charge | Une seule machine |
| Familiarité | API ancienne, peu agréable pour tableaux et graphiques |

**Pour :** pas de serveur ni de navigateur.

**Contre :** graphiques via matplotlib intégré, plus lourds à rendre interactifs ;
interface moins lisible ; pas de lien direct vers un résultat.

## Analyse des compromis

Le point décisif est la **fidélité des résultats** : l'outil sert à comparer des politiques,
souvent à quelques centièmes de point de hit rate près. Passer par la commande existante
garantit que l'interface n'introduit aucune différence, et le sous-processus isole le code
tiers qui garde un état global. Ce choix est indépendant du framework, mais Streamlit
pousse vers l'exécution dans le même processus, et React apporte une complexité que le
besoin (un utilisateur, cinq écrans) ne justifie pas.

Entre A et B, on échange **plus de code à écrire** (A) contre **une dépendance lourde et un
modèle d'exécution mal adapté aux tâches longues** (B). Le code de A est simple et testé
(`tests/test_ui.py`) ; la dépendance de B toucherait chaque installation du projet.

Le **rafraîchissement par interrogation** (toutes les 0,7 s) est préféré aux WebSockets ou
Server-Sent Events : plus simple avec la bibliothèque standard, et la latence d'affichage
n'a pas d'importance pour des tâches de plusieurs secondes.

## Conséquences

**Plus facile :**
- lancer une expérience, inspecter une trace ou tester la boutique sans connaître les
  commandes ;
- lire et comparer les résultats (tableau, graphique, liens `#results=...`) ;
- toute nouvelle commande de la ligne de commande s'ajoute à l'interface par un
  constructeur de tâche dans `server.py` et un formulaire dans la page.

**Plus difficile :**
- chaque option de la ligne de commande doit être reportée à la main dans le formulaire ;
- les tâches vivent en mémoire : un redémarrage de `cachebench ui` perd la liste des
  tâches (les fichiers de résultats restent) ;
- l'interface n'est pas faite pour être exposée sur un réseau : pas d'authentification.

**À revoir si :**
- l'outil doit servir à plusieurs personnes ou depuis un autre poste : il faudra une
  authentification, et l'option C redevient pertinente ;
- le suivi de l'avancement doit être plus fin que le journal texte : faire écrire à
  `cachebench run` un avancement structuré (JSON par ligne) ;
- le test Magento doit aussi changer de politique : écrire `local.xml` et vider le cache
  depuis l'interface demande une sauvegarde et une confirmation explicites.

## Actions

1. [x] Serveur, API et page (`cachebench/ui/`), commande `cachebench ui`.
2. [x] Tests de l'API, des tâches, de l'annulation et des refus (`tests/test_ui.py`).
3. [x] README et `docs/architecture.md` mis à jour.
4. [ ] Valider l'interface en usage réel : une expérience complète et un test Magento lancés
   depuis la page.
5. [ ] Commiter `cachebench/ui/` avec `git add -f` (le dossier `cachebench/` est ignoré par
   la règle du venv).
6. [ ] Décider s'il faut un avancement structuré pour `cachebench run` (voir « À revoir »).
