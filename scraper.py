import requests
from bs4 import BeautifulSoup
import json
import re
import os

BASE_URL = "https://eurocarveiculos.com"
LISTING_URL = f"{BASE_URL}/multipla"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_vehicle_details(url):
    details = {
        "price": "0.00",
        "year": "",
        "km": "",
        "color": "",
        "transmission": "",
        "fuel": "",
        "doors": "",
        "options": []
    }

    try:
        print(f"   ➜ Detalhes: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=20)
        print(f"   ↳ status detalhes: {resp.status_code}")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # Preço
        price_tag = soup.select_one("h3.preco-indigo span#valor_promo")
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            details["price"] = re.sub(r"[^\d,]", "", price_text).replace(",", ".")

        # Ficha Técnica estruturada
        for div in soup.select("div.col-md-4"):
            text = div.get_text(strip=True)
            if "Ano:" in text:
                details["year"] = text.split("Ano:")[-1].strip()
            elif "KM:" in text:
                km_raw = text.split("KM:")[-1].strip()
                details["km"] = re.sub(r"[^\d]", "", km_raw)
            elif "Cor:" in text:
                details["color"] = text.split("Cor:")[-1].strip()
            elif "Câmbio:" in text:
                details["transmission"] = text.split("Câmbio:")[-1].strip()
            elif "Combustível:" in text:
                details["fuel"] = text.split("Combustível:")[-1].strip()
            elif "Portas:" in text:
                details["doors"] = re.sub(r"[^\d]", "", text.split("Portas:")[-1])

        # Opcionais
        for ul in soup.select("ul.coluna"):
            for li in ul.select("li.linha span"):
                opt = clean_text(li.get_text())
                if opt:
                    details["options"].append(opt)

        print(f"      ↳ Ano: {details['year']}, KM: {details['km']}, Cor: {details['color']}, Câmbio: {details['transmission']}, Combustível: {details['fuel']}, Portas: {details['doors']}")

    except Exception as e:
        print(f"   [ERRO detalhes] {url}: {e}")

    return details

def scrape_listings():
    print(f"Acessando listagem: {LISTING_URL}")
    response = requests.get(LISTING_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")

    cards = soup.select("div.col-md-4.col-result-pact")
    print(f"{len(cards)} veículos encontrados na listagem.")

    vehicles = []

    for card in cards:
        try:
            name_tag = card.select_one("a.big-inf2")
            if not name_tag:
                continue

            name = clean_text(name_tag.get_text())
            link = name_tag.get("href")
            if not link:
                continue

            if link.startswith("http"):
                full_link = link
            elif link.startswith("/"):
                full_link = BASE_URL + link
            else:
                full_link = BASE_URL + "/" + link

            img_tag = card.select_one("img.img-responsive.lazy")
            img_url = ""
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                elif img_url.startswith("/"):
                    img_url = BASE_URL + img_url

            details = get_vehicle_details(full_link)

            vehicle = {
                "name": name,
                "price": details["price"],
                "year": details["year"],
                "km": details["km"],
                "color": details["color"],
                "transmission": details["transmission"],
                "fuel": details["fuel"],
                "doors": details["doors"],
                "options": details["options"],
                "link_details": full_link,
                "main_image_url": img_url
            }

            vehicles.append(vehicle)
            print(f"✔ {name} | R$ {details['price']} | {details['km']} km | {details['year']} | Cor: {details['color']}")

        except Exception as e:
            print(f"[ERRO card] {e}")

    return vehicles

if __name__ == "__main__":
    data = scrape_listings()
    output_dir = os.path.join(os.getenv("GITHUB_WORKSPACE", "."), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "estoque_eurocar.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"Estoque salvo em {output_path}")
