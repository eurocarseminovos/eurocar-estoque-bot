import requests
from bs4 import BeautifulSoup
import json
import re
import os

BASE_URL = "https://eurocarveiculos.com"
LISTING_URL = f"{BASE_URL}/multipla"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive"
}

COLOR_WORDS = [
    "branco", "preto", "prata", "cinza", "vermelho", "azul", "verde",
    "bege", "marrom", "amarelo", "vinho", "bordô", "grafite"
]

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def extract_price(full_text: str) -> str:
    m = re.search(r"R\$\s*([\d\.]+,\d{2})", full_text)
    if not m:
        return "0.00"
    valor = m.group(1).replace(".", "").replace(",", ".")
    return valor

def extract_year(full_text: str) -> str:
    # Pega padrões tipo 2022/2023 ou 2019/2019
    m = re.search(r"Ano[^0-9]*(\d{4}\s*/\s*\d{4})", full_text, re.IGNORECASE)
    if m:
        return clean_text(m.group(1))
    # fallback para só um ano (menos comum)
    m = re.search(r"Ano[^0-9]*(\d{4})", full_text, re.IGNORECASE)
    return clean_text(m.group(1)) if m else ""

def extract_km(full_text: str) -> str:
    # padrões tipo "39.000 KM" ou "39000 KM"
    m = re.search(r"(\d{1,3}\.\d{3}|\d{4,7})\s*KM", full_text, re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).replace(".", "")

def extract_color(full_text: str) -> str:
    # tenta pegar uma palavra de cor logo depois de "Cor"
    m = re.search(r"Cor[^A-Za-zÀ-ÿ]*([A-Za-zÀ-ÿ]+)", full_text, re.IGNORECASE)
    if m:
        cand = m.group(1).lower()
        for cor in COLOR_WORDS:
            if cor in cand:
                return cor.capitalize()
    # fallback: procura qualquer palavra de cor na página
    lower = full_text.lower()
    for cor in COLOR_WORDS:
        if cor in lower:
            return cor.capitalize()
    return ""

def extract_transmission(full_text: str) -> str:
    # Manual / Automático
    m = re.search(r"Câmbio[^A-Za-zÀ-ÿ]*([A-Za-zÀ-ÿ ]+)", full_text, re.IGNORECASE)
    if m:
        val = clean_text(m.group(1))
        # normalizar
        if "autom" in val.lower():
            return "Automático"
        if "manual" in val.lower():
            return "Manual"
        return val
    # fallback
    if "câmbio automático" in full_text.lower():
        return "Automático"
    if "câmbio manual" in full_text.lower():
        return "Manual"
    return ""

def extract_fuel(full_text: str) -> str:
    txt = full_text.lower()
    if "flex" in txt:
        return "FLEX"
    if "diesel" in txt or "díesel" in txt:
        return "DIESEL"
    if "gasolina" in txt:
        return "GASOLINA"
    if "etanol" in txt or "álcool" in txt:
        return "ETANOL"
    m = re.search(r"Combustível[^A-Za-zÀ-ÿ]*([A-Za-zÀ-ÿ ]+)", full_text, re.IGNORECASE)
    return clean_text(m.group(1)).upper() if m else ""

def extract_doors(full_text: str) -> str:
    m = re.search(r"Portas[^0-9]*(\d)", full_text, re.IGNORECASE)
    return m.group(1) if m else ""

def get_vehicle_details(url: str) -> dict:
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
        resp = requests.get(url, headers=HEADERS, timeout=25)
        print(f"   ↳ status detalhes: {resp.status_code}")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # texto total da página, num bloco só
        full_text = soup.get_text(" ", strip=True)

        # -------- CAMPOS PRINCIPAIS POR REGEX NO TEXTO COMPLETO --------
        details["price"] = extract_price(full_text)
        details["year"] = extract_year(full_text)
        details["km"] = extract_km(full_text)
        details["color"] = extract_color(full_text)
        details["transmission"] = extract_transmission(full_text)
        details["fuel"] = extract_fuel(full_text)
        details["doors"] = extract_doors(full_text)

        # -------- OPCIONAIS (aqui ainda dá pra usar HTML pq funciona bem) --------
        for ul in soup.select("ul.coluna"):
            for li in ul.select("li.linha span"):
                opt = clean_text(li.get_text())
                if opt:
                    details["options"].append(opt)

        print(
            f"      ↳ Ano: {details['year']} | KM: {details['km']} | Cor: {details['color']} | "
            f"Câmbio: {details['transmission']} | Combustível: {details['fuel']} | Portas: {details['doors']}"
        )

    except Exception as e:
        print(f"   [ERRO detalhes] {url}: {e}")

    return details

def scrape_listings():
    print(f"Acessando listagem: {LISTING_URL}")
    response = requests.get(LISTING_URL, headers=HEADERS, timeout=25)
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
