### Faucet

## Env variable
Create .env file within fmfaucet in the format:

`SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/key
SOURCE_WALLET=0xwallet_address
WALLET_PRIVATE_KEY=hex_private_key
SECRET_KEY=django_key
DEBUG=True
RATE_LIMIT_PERIOD=1
CHAIN_ID=11155111
`


## Migrations
python manage.py makemigrations
python manage.py migrate

## Tests
python manage.py test faucet_api/tests

## Linting
pre-commit run --all-files

## Deploy
docker compose up --build

## Run
docker run -p 8000:8000 fmfaucet-web:latest
