import requests
from bs4 import BeautifulSoup
import json
import os
import re

BASE_URL = "https://eurocarveiculos.com"
LISTING_URL = f"{BASE_URL}/multipla"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def scrape_listings():
    print(f"Acessando: {LISTING_URL}")
    response = requests.get(LISTING_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")

    cards = soup.select("div.col-md-4.col-result-pact")
    print(f"{len(cards)} veículos encontrados.")

    vehicles = []

    for card in cards:
        try:
            # Nome e link
            name_tag = card.select_one("a.big-inf2")
            name = name_tag.get_text(strip=True) if name_tag else "Veículo sem nome"
            link = name_tag.get("href") if name_tag else ""
            if link and not link.startswith("http"):
                link = BASE_URL + link

            # Imagem
            image_tag = card.select_one("img.img-responsive.lazy")
            image_url = image_tag.get("src") if image_tag else ""
            if image_url.startswith("/"):
                image_url = BASE_URL + image_url
            elif image_url.startswith("//"):
                image_url = "https:" + image_url

            # Preço
            price_tag = card.select_one("span#valor_promo")
            price = price_tag.get_text(strip=True) if price_tag else "0"
            price = re.sub(r"[^\d,]", "", price).replace(",", ".")

            # KM
            km_tag = card.select_one("span.text-none.grey-text")
            km = re.sub(r"[^\d]", "", km_tag.get_text(strip=True)) if km_tag else ""

            # Ano
            year_match = re.search(r"\d{4}/\d{4}|\d{4}", name)
            year = year_match.group(0) if year_match else ""

            vehicles.append({
                "name": name,
                "link": link,
                "image": image_url,
                "price": price,
                "km": km,
                "year": year
            })

            print(f"Adicionado: {name} - R$ {price} - {km} km - Ano: {year}")

        except Exception as e:
            print(f"Erro ao processar card: {e}")

    return vehicles

if __name__ == "__main__":
    data = scrape_listings()
    output_dir = os.path.join(os.getenv("GITHUB_WORKSPACE", "."), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "estoque_eurocar.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Estoque salvo em {output_path}")
