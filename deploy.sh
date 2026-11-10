#!/bin/bash
set -euo pipefail

cd /var/www/survey_ebt/app
python=/var/www/survey_ebt/venv/bin/python
exec 9>/var/www/survey_ebt/deploy.lock
flock -n 9 || { echo "Обновление уже запущено." >&2; exit 1; }

if [[ $(git branch --show-current) != main ]] || [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "Для обновления нужна ветка main без изменений в отслеживаемых файлах." >&2
    git status --short
    exit 1
fi

sudo -v
git fetch origin main
old_commit=$(git rev-parse HEAD)
git merge --ff-only FETCH_HEAD
printf 'Версия: %s → %s\n' "$old_commit" "$(git rev-parse HEAD)"

"$python" -m pip install -r requirements.txt
"$python" -m pip check
"$python" manage.py check
sudo systemctl start survey-ebt-backup.service
"$python" manage.py migrate --noinput
"$python" manage.py collectstatic --noinput
chmod -R a+rX staticfiles

sudo systemctl restart survey_ebt.service
sudo systemctl is-active survey_ebt.service
curl --fail --silent --show-error --retry 5 --retry-delay 1 --retry-all-errors --max-time 10 \
    --output /dev/null https://nordstar.losa.gvedynamics.ru/api/auth/csrf/
echo "Обновление завершено. API отвечает по HTTPS."
