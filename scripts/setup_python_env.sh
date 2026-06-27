#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON:-python3}"
venv_dir="${VENV_DIR:-.venv}"

"$python_bin" -m venv "$venv_dir"
# shellcheck disable=SC1091
source "$venv_dir/bin/activate"
python -m pip install -U pip
python -m pip install -r requirements.txt
python --version
python -m pip freeze
