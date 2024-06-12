pip3 install ./autogen
pip3 install ./autogen/samples/apps/autogen-studio
pip3 install -U gunicorn
export AUTOGENSTUDIO_APPDIR=/app/autogenstudio-data
gunicorn -w 5 --timeout 12600 -k uvicorn.workers.UvicornWorker autogenstudio.web.app:app --bind "0.0.0.0:8081"