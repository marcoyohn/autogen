cd ./autogen
pip install --no-index --find-links=packages -r requirements.txt

cd ./samples/apps/autogen-studio
pip install --no-index --find-links=packages -r requirements.txt

cd ../../../../
pip3 install -U gunicorn

gunicorn -w 5 --timeout 12600 -k uvicorn.workers.UvicornWorker autogenstudio.web.app:app --bind "0.0.0.0:8081"