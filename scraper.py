# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import json
import re
import os

def get_vehicle_details(vehicle_url):
    """Fetches details from an individual vehicle page."""
    details = {
        "description": "",
        "photos": [],
        "options": []
    }
    try:
        print(f"Buscando detalhes em: {vehicle_url}")
        response = requests.get(vehicle_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        description_tag = soup.find("div", class_="descricao-veiculo")
        if description_tag:
            details["description"] = description_tag.get_text(separator="\n", strip=True)
        else:
            description_div = soup.find("div", id="descricao")
            if description_div:
                 details["description"] = description_div.get_text(separator="\n", strip=True)

        photo_tags = soup.select("div.carousel-inner div.item img, ul.fotos-veiculo-miniaturas img, #fotoVeiculo img")
        
        processed_photos = set()
        for tag in photo_tags:
            photo_url = tag.get("src") or tag.get("data-src")
            if photo_url and not photo_url.startswith("data:image") and photo_url not in processed_photos:
                if photo_url.startswith("//"):
                    abs_photo_url = "https:" + photo_url
                elif photo_url.startswith("/") :
                    abs_photo_url = "https://eurocarveiculos.com" + photo_url
                else:
                    abs_photo_url = photo_url
                details["photos"].append(abs_photo_url) 
                processed_photos.add(photo_url)
        
        options_section = soup.find("div", class_="opcionais")
        if options_section:
            option_tags = options_section.find_all("li")
            for tag in option_tags:
                details["options"].append(tag.get_text(strip=True))
        else:
            options_ul = soup.find("ul", class_="list-unstyled lista-opcionais")
            if options_ul:
                option_tags = options_ul.find_all("li")
                for tag in option_tags:
                    details["options"].append(tag.get_text(strip=True))

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar detalhes do veículo {vehicle_url}: {e}")
    except Exception as e:
        print(f"Erro ao processar detalhes do veículo {vehicle_url}: {e}")
    return details

def scrape_eurocar_stock():
    base_url = "https://eurocarveiculos.com"
    stock_url = f"{base_url}/multipla"
    vehicles_data = []
    page_num = 1
    max_pages_to_scrape = 10 # Ajuste conforme necessário, 10 deve cobrir o site todo geralmente

    print(f"Iniciando scraping do estoque da Eurocar: {stock_url}") 

    while page_num <= max_pages_to_scrape:
        current_url = f"{stock_url}?pagina={page_num}"
        print(f"Buscando página: {current_url}")
        try:
            response = requests.get(current_url, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar a página {current_url}: {e}")
            break

        soup = BeautifulSoup(response.content, "html.parser")
        vehicle_cards = soup.select("div.carro.col-md-4.col-result-pact")

        if not vehicle_cards:
            print(f"Nenhum veículo encontrado na página {page_num}. Fim da paginação.")
            break

        print(f"{len(vehicle_cards)} veículos encontrados na página {page_num}.")

        for card in vehicle_cards:
            vehicle = {
                "name": "",
                "price": "0.00",
                "year": "",
                "km": "",
                "link_details": "",
                "main_image_url": "",
                "description": "",
                "photos": [],
                "options": []
            }
            
            try:
                name_link_tag = card.select_one("h2.tit-marca a.big-inf2")
                if name_link_tag:
                    vehicle["name"] = name_link_tag.get_text(strip=True)
                    vehicle["link_details"] = name_link_tag.get("href", "")
                    if vehicle["link_details"] and not vehicle["link_details"].startswith("http") :
                        vehicle["link_details"] = base_url + vehicle["link_details"]
                
                price_promo_tag = card.select_one("h3.preco span#valor_promo_veic")
                if price_promo_tag:
                    price_text = price_promo_tag.get_text(strip=True)
                else:
                    price_normal_tag = card.select_one("h3.preco-antigo span#valor_veic, h3.preco span")
                    if price_normal_tag:
                        price_text = price_normal_tag.get_text(strip=True)
                    else:
                        price_text = "0"
                vehicle["price"] = re.sub(r'[^0-9,]', '', price_text).replace(",",".") # Limpa e formata para numérico
                if not vehicle["price"]: vehicle["price"] = "0.00"

                info_tags = card.select("div.white-inf-rs.info-pact span.text-none.grey-text10")
                if len(info_tags) >= 2:
                    vehicle["year"] = info_tags[0].get_text(strip=True)
                    km_text = info_tags[1].get_text(strip=True)
                    km_match = re.search(r"([0-9.]+)", km_text)
                    if km_match:
                        vehicle["km"] = km_match.group(1).replace(".","")
                elif len(info_tags) == 1:
                    text_info = info_tags[0].get_text(strip=True)
                    year_match = re.search(r"(\d{4}/\d{4}|\d{4})", text_info)
                    if year_match:
                        vehicle["year"] = year_match.group(1)
                    km_match = re.search(r"([0-9.]+)\s*km", text_info, re.IGNORECASE)
                    if km_match:
                        vehicle["km"] = km_match.group(1).replace(".","")

                image_tag = card.select_one("div.carro-img img.img-responsive.lazy")
                if image_tag:
                    img_src = image_tag.get("src") or image_tag.get("data-src")
                    if img_src:
                        if img_src.startswith("//"):
                            vehicle["main_image_url"] = "https:" + img_src
                        elif img_src.startswith("/") :
                            vehicle["main_image_url"] = base_url + img_src
                        else:
                            vehicle["main_image_url"] = img_src

                if vehicle["link_details"]:
                    details_data = get_vehicle_details(vehicle["link_details"])
                    vehicle.update(details_data)
                
                if vehicle["name"]:
                    vehicles_data.append(vehicle)
                    print(f"Veículo adicionado: {vehicle['name']} - Preço: {vehicle['price']}")
                else:
                    print("Veículo sem nome encontrado no card, pulando.")

            except Exception as e:
                print(f"Erro ao processar um card de veículo: {e}. Card HTML: {card.prettify()[:200]}...")
        
        next_page_button = soup.select_one("ul.pagination li.active + li a")
        if not next_page_button:
            print("Não há mais botão de próxima página. Fim da paginação.")
            break
        
        page_num += 1

    print(f"Total de {len(vehicles_data)} veículos extraídos.")
    return vehicles_data

if __name__ == "__main__":
    # Cria o diretório 'data' se não existir, para o GitHub Actions
    # O GITHUB_WORKSPACE é o diretório raiz do repositório no Actions
    output_dir = os.path.join(os.getenv("GITHUB_WORKSPACE", "."), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "estoque_eurocar.json")

    stock_data = scrape_eurocar_stock()
    if stock_data:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=4)
        print(f"Dados do estoque salvos em {output_path}")
    else:
        print("Nenhum dado do estoque foi extraído ou salvo.")

