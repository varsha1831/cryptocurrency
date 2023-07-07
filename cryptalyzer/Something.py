import requests

url = "https://coin-pred-api-v1.p.rapidapi.com/rate-of-change/btc-fiat"

headers = {
	"X-RapidAPI-Key": "dc04fbbf9cmshc5c99a628fd0c8cp11f68bjsn07a3713f0a82",
	"X-RapidAPI-Host": "coin-pred-api-v1.p.rapidapi.com"
}

response = requests.get(url, headers=headers)

print(response.json())