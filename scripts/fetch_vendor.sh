#!/usr/bin/env sh
# Récupère le code officiel des dépôts de référence, à un commit figé, sans le modifier.
set -eu
cd "$(dirname "$0")/.."
mkdir -p vendor

fetch() {  # fetch <dossier> <url> <commit>
  if [ -d "vendor/$1/.git" ]; then
    git -C "vendor/$1" fetch -q origin
  else
    git clone -q "$2" "vendor/$1"
  fi
  git -C "vendor/$1" checkout -q "$3"
  echo "vendor/$1 -> $3"
}

# CACHEUS, LeCaR, ARC, LIRS (FAST'21). Le dépôt n'a pas de fichier LICENSE :
# usage de recherche, ne pas redistribuer ce dossier.
fetch cacheus https://github.com/sylab/cacheus.git 1eec63ce166502be33ddd1f35bc041ed73a24f4d
