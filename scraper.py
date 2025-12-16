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

def clean_text(text: str) -> str:
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

        # -------- PREÇO --------
        price_text = ""
        price_tag = soup.select_one("h3.preco-indigo") or soup.find("h3", class_=re.compile("preco", re.I))
        if price_tag:
            price_text = price_tag.get_text(" ", strip=True)

        if not price_text:
            full_text = soup.get_text(" ", strip=True)
            m_price = re.search(r"R\$\s*([\d\.]+,\d{2})", full_text)
            if m_price:
                price_text = m_price.group(1)

        if price_text:
            m = re.search(r"([\d\.]+,\d{2})", price_text)
            if m:
                details["price"] = m.group(1).replace(".", "").replace(",", ".")
            else:
                details["price"] = "0.00"

        # -------- FICHA TÉCNICA --------
        ficha_div = soup.find(string=re.compile("FICHA TÉCNICA", re.I))
        if ficha_div and ficha_div.parent:
            ficha_container = ficha_div.parent
            for _ in range(3):
                if ficha_container.parent:
                    ficha_container = ficha_container.parent
            ficha_text = ficha_container.get_text("\n", strip=True)
        else:
            ficha_text = soup.get_text("\n", strip=True)

        ficha_text = ficha_text.replace("\r", "")

        def search_after(label):
            pattern = rf"{label}\s*:\s*(.+)"
            m = re.search(pattern, ficha_text, flags=re.IGNORECASE)
            return clean_text(m.group(1)) if m else ""

        # Ano
        details["year"] = search_after("Ano")

        # KM
        km_raw = search_after("KM")
        if km_raw:
            m_km = re.search(r"([\d\.]+)", km_raw)
            if m_km:
                details["km"] = m_km.group(1).replace(".", "")

        # Câmbio
        details["transmission"] = search_after("Câmbio")

        # Combustível
        details["fuel"] = search_after("Combustível")

        # Cor
        details["color"] = search_after("Cor")

        # Portas
        details["doors"] = search_after("Portas")

        # -------- OPCIONAIS --------
        for ul in soup.select("ul.coluna"):
            for li in ul.select("li.linha span"):
                opt = clean_text(li.get_text())
                if opt:
                    details["options"].append(opt)

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
            # Nome e link bruto vindo da listagem
            name_tag = card.select_one("a.big-inf2")
            if not name_tag:
                continue

            name = clean_text(name_tag.get_text())
            link = name_tag.get("href")
            if not link:
                continue

            # MONTA O LINK CORRETO
            if link.startswith("http"):
                full_link = link
            elif link.startswith("/"):
                full_link = BASE_URL + link
            else:
                full_link = BASE_URL + "/" + link

            # Imagem
            img_tag = card.select_one("img.img-responsive.lazy")
            img_url = ""
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                elif img_url.startswith("/"):
                    img_url = BASE_URL + img_url

            # Detalhes da página individual
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
            print(
                f"✔ {name} | R$ {details['price']} | {details['km']} km | "
                f"{details['year']} | Cor: {details['color']}"
            )

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
