pip3 install -U gunicorn autogenstudio && export AUTOGENSTUDIO_APPDIR=/app/autogenstudio-data && gunicorn -w 5 --timeout 12600 -k uvicorn.workers.UvicornWorker autogenstudio.web.app:app --bind "0.0.0.0:8081"