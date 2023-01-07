Not included in the github is the environment variables file. You will need to get a copy of the environment variable file and store it at environment.env

```
export FLASK_APP='app'
export FLASK_DEBUG='True'
export DATABASE_URL='postgresql://localhost:5432/snorkel'
export SENDGRID_API_KEY=''
export AWS_ACCESS_KEY_ID='
export AWS_SECRET_ACCESS_KEY=''
export GOOGLE_CLIENT_ID=''
export GOOGLE_API_KEY=''
export FLASK_SECRET_KEY=''
export S3_BUCKET_NAME='snorkel-dev'
```

#Running the code
```
#make sure to create a virtual environment

#Mac/Linux
virtualenv env
source env/bin/activate
source environment.env

#Windows
#assign environment variable to windows' system properties environment variables
#don't need environment.env file
#Install WSL to simulate linux shell on windows: https://learn.microsoft.com/en-us/windows/wsl/install
venv\Scripts\activate

#run
pip install -r requirements.txt
flask run
```

You should be able to check if the db works by typing in `psql snorkel` and then typing `\dt` which prints out a list of the tables that were created.

If you have a database backup, you can set up with the following command:

```
$ psql
`CREATE DATABASE snorkel;`
# exit out of postgres eg control+D
$ pg_restore --no-owner -d snorkel <dump filnamename>
# eg `$ pg_restore --no-owner -d snorkel cef2f6d5-89fc-468a-97fc-f1064fd85140`
```
