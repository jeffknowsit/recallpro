import requests
import os

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_API_URL = os.environ.get('GROQ_API_URL', 'https://api.groq.com/v1/')

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}

def get_decks(user_id):
    response = requests.get(f"{GROQ_API_URL}decks?user_id={user_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def get_deck(deck_id):
    response = requests.get(f"{GROQ_API_URL}decks/{deck_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def create_deck(data):
    response = requests.post(f"{GROQ_API_URL}decks", headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def update_deck(deck_id, data):
    response = requests.put(f"{GROQ_API_URL}decks/{deck_id}", headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def delete_deck(deck_id):
    response = requests.delete(f"{GROQ_API_URL}decks/{deck_id}", headers=headers)
    response.raise_for_status()
    return response.status_code == 204

def get_cards(deck_id):
    response = requests.get(f"{GROQ_API_URL}decks/{deck_id}/cards", headers=headers)
    response.raise_for_status()
    return response.json()

def get_card(card_id):
    response = requests.get(f"{GROQ_API_URL}cards/{card_id}", headers=headers)
    response.raise_for_status()
    return response.json()

def create_card(deck_id, data):
    response = requests.post(f"{GROQ_API_URL}decks/{deck_id}/cards", headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def update_card(card_id, data):
    response = requests.put(f"{GROQ_API_URL}cards/{card_id}", headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def delete_card(card_id):
    response = requests.delete(f"{GROQ_API_URL}cards/{card_id}", headers=headers)
    response.raise_for_status()
    return response.status_code == 204 