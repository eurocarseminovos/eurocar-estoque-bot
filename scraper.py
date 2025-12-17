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

def extract_number(text: str) -> str:
    match = re.search(r"([\d\.]+)", text or "")
    return match.group(1).replace(".", "") if match else ""

def extract_from_fulltext(full_text: str, label: str) -> str:
    """Pega linha que contém o rótulo e devolve o que vem depois dele."""
    lines = full_text.split("\n")
    for line in lines:
        if label.lower() in line.lower():
            # Ex: 'Ano: 2022/2023'
            parts = re.split(label + r"\s*[:\-]?", line, flags=re.IGNORECASE)
            if len(parts) > 1:
                return clean_text(parts[1])
    return ""

def extract_color_from_text(candidate: str) -> str:
    cand_lower = candidate.lower()
    for cor in COLOR_WORDS:
        if cor in cand_lower:
            return cor.capitalize()
    return ""

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
        resp = requests.get(url, headers=HEADERS, timeout=25)
        print(f"   ↳ status detalhes: {resp.status_code}")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        full_text = soup.get_text("\n", strip=True)

        # -------- PREÇO --------
        price_tag = soup.select_one("h3.preco-indigo span#valor_promo")
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            details["price"] = re.sub(r"[^\d,]", "", price_text).replace(",", ".")
        else:
            price_match = re.search(r"R\$\s*([\d\.]+,\d{2})", full_text)
            if price_match:
                details["price"] = price_match.group(1).replace(".", "").replace(",", ".")

        # -------- FICHA TÉCNICA VIA HTML (strong/span) --------
        for bloco in soup.select("div.col-md-4"):
            strong = bloco.find(["strong", "b"])
            if not strong:
                continue

            label = clean_text(strong.get_text()).lower()

            # tenta valor em span
            span = bloco.find("span")
            if span:
                value = clean_text(span.get_text())
            else:
                # se não tiver span, pega texto do bloco e remove o label
                bloco_text = clean_text(bloco.get_text(" ", strip=True))
                value = clean_text(bloco_text.replace(strong.get_text(), ""))

            if "ano" in label and not details["year"]:
                details["year"] = value

            elif "km" in label and not details["km"]:
                details["km"] = extract_number(value)

            elif "cor" in label and not details["color"]:
                cor = extract_color_from_text(value)
                if cor:
                    details["color"] = cor

            elif "câmbio" in label and not details["transmission"]:
                details["transmission"] = value

            elif "combustível" in label and not details["fuel"]:
                details["fuel"] = value

            elif "portas" in label and not details["doors"]:
                details["doors"] = extract_number(value)

        # -------- FALLBACK VIA TEXTO COMPLETO --------
        if not details["year"]:
            year_candidate = extract_from_fulltext(full_text, "Ano")
            if year_candidate:
                details["year"] = year_candidate

        if not details["km"]:
            km_candidate = extract_from_fulltext(full_text, "KM")
            if km_candidate:
                details["km"] = extract_number(km_candidate)

        if not details["color"]:
            color_candidate = extract_from_fulltext(full_text, "Cor")
            if color_candidate:
                cor = extract_color_from_text(color_candidate)
                if cor:
                    details["color"] = cor

        if not details["transmission"]:
            trans_candidate = extract_from_fulltext(full_text, "Câmbio")
            if trans_candidate:
                details["transmission"] = clean_text(trans_candidate)

        if not details["fuel"]:
            fuel_candidate = extract_from_fulltext(full_text, "Combustível")
            if fuel_candidate:
                details["fuel"] = clean_text(fuel_candidate)

        if not details["doors"]:
            doors_candidate = extract_from_fulltext(full_text, "Portas")
            if doors_candidate:
                details["doors"] = extract_number(doors_candidate)

        # -------- OPCIONAIS --------
        for ul in soup.select("ul.coluna"):
            for li in ul.select("li.linha span"):
                opt = clean_text(li.get_text())
                if opt:
                    details["options"].append(opt)

        print(
            f"      ↳ Ano: {details['year']}, KM: {details['km']}, Cor: {details['color']}, "
            f"Câmbio: {details['transmission']}, Combustível: {details['fuel']}, Portas: {details['doors']}"
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
