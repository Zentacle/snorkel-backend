Not included in the github is the environment variables file. You will need to get a copy of the environment variable file and store it at environment.env

```
export FLASK_APP='app'
export FLASK_ENV='development'
export DATABASE_URL='postgresql://localhost:5432/snorkel'
export SENDGRID_API_KEY=''
export AWS_ACCESS_KEY_ID=''
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
assign environment variable to windows' system properties environment variables
don't need environment.env file
venv\Scripts\activate

#run
pip install -r requirements.txt
psql
`CREATE DATABASE snorkel;`
#exit out of postgres
flask db upgrade
flask run
```

You should be able to check if the db works by typing in `psql snorkel` and then typing `\dt` which prints out a list of the tables that were created.

You can then backfill the db with some test data using Postman and importing this collection and running it `https://www.getpostman.com/collections/96c8d497940f948f89b0`.
