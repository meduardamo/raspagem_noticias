# Preparando

import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import urllib3
import re
import pandas as pd

# Configurações globais
TZ = pytz.timezone('America/Sao_Paulo')

def format_date(date_str):
    """
    Padroniza formato de data para DD/MM/YYYY
    """
    if not date_str:
        return None
    try:
        # Tenta diferentes formatos de entrada
        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return None
    except:
        return None

def get_today_br():
    """Retorna data atual no formato DD/MM/YYYY"""
    return datetime.now(TZ).strftime("%d/%m/%Y")

"""# Ministério do Esporte"""

# Suprimir avisos de solicitação insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key('1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY')
    return sheet

def get_already_scraped_urls(sheet):
    try:
        urls_sheet = sheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.add_worksheet(title="URLs", rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])  # Exclude the header

def add_scraped_url(sheet, url):
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

def raspar_noticias_por_data(url, sheet, data_desejada=None):
    if data_desejada is None:
        data_desejada = get_today_br()

    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        meta_tag = soup.find('meta', property="og:site_name")
        nome_ministerio = meta_tag['content'] if meta_tag else "Nome do Ministério não identificado"
        noticias = soup.find_all('li')

        for noticia in noticias:
            data_element = noticia.find('span', class_='data')
            if data_element:
                data_text_raw = data_element.text.strip()
                data_text = format_date(data_text_raw)
                if not data_text:
                    print(f"Data encontrada inválida ou em formato desconhecido: {data_text_raw}")
                    continue
                    
                if data_text == data_desejada:
                    titulo_element = noticia.find('h2', class_='titulo')
                    url = titulo_element.find('a')['href']
                    if url not in already_scraped_urls:
                        subtitulo_tag = noticia.find('div', class_='subtitulo-noticia')
                        subtitulo = subtitulo_tag.text.strip() if subtitulo_tag else "Subtítulo não disponível"
                        titulo = titulo_element.text.strip()
                        descricao = noticia.find('span', class_='descricao')
                        descricao_text = descricao.text.split('-')[1].strip() if '-' in descricao.text else descricao.text.strip()

                        dados = [
                            data_text,           # Data
                            nome_ministerio,     # Nome do Ministério
                            subtitulo,           # Subtítulo
                            titulo,              # Título
                            descricao_text,      # Descrição
                            url                  # URL
                        ]

                        # Salvar na aba 'gov' para ministérios
                        try:
                            gov_sheet = sheet.worksheet("gov")
                        except gspread.exceptions.WorksheetNotFound:
                            gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
                            gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
                        
                        gov_sheet.append_row(dados)
                        add_scraped_url(sheet, url)

        print('Dados inseridos com sucesso na planilha.')

    except requests.exceptions.HTTPError as errh:
        print ("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print ("Oops: Something Else", err)

# Exemplo de uso
sheet = initialize_sheet()
url = "https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte"

# Para raspar notícias da data atual
raspar_noticias_por_data(url, sheet)

"""# Ministério da Educação"""

def raspar_noticias_por_data_mec(url, sheet, data_desejada=None):
    if data_desejada is None:
        data_desejada = get_today_br()

    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        meta_tag = soup.find('meta', property="og:site_name")
        nome_ministerio = meta_tag['content'] if meta_tag else "Nome do Ministério não identificado"
        noticias = soup.find_all('li')

        for noticia in noticias:
            data_element = noticia.find('span', class_='data')
            if data_element:
                data_text_raw = data_element.text.strip()
                data_text = format_date(data_text_raw)
                if not data_text:
                    print(f"Data encontrada inválida ou em formato desconhecido: {data_text_raw}")
                    continue
                    
                if data_text == data_desejada:
                    titulo_element = noticia.find('h2', class_='titulo')
                    link = titulo_element.find('a')['href']
                    if link not in already_scraped_urls:
                        subtitulo = noticia.find('div', class_='subtitulo-noticia').text.strip()
                        titulo = titulo_element.text.strip()
                        descricao = noticia.find('span', class_='descricao')
                        descricao_text = descricao.text.split('-')[1].strip() if '-' in descricao.text else descricao.text.strip()

                        dados = [
                            data_text,           # Data
                            nome_ministerio,     # Nome do Ministério
                            subtitulo,           # Subtítulo
                            titulo,              # Título
                            descricao_text,      # Descrição
                            link                 # URL
                        ]

                        # Salvar na aba 'gov' para ministérios
                        try:
                            gov_sheet = sheet.worksheet("gov")
                        except gspread.exceptions.WorksheetNotFound:
                            gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
                            gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
                        
                        gov_sheet.append_row(dados)
                        add_scraped_url(sheet, link)

        print('Dados inseridos com sucesso na planilha.')

    except requests.exceptions.HTTPError as errh:
        print ("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print ("Oops: Something Else", err)

# Exemplo de uso
sheet = initialize_sheet()
url = "https://www.gov.br/mec/pt-br/assuntos/noticias"

# Para raspar notícias da data atual
raspar_noticias_por_data_mec(url, sheet)

"""# Ministério da Saúde"""

def raspar_noticias_saude(url, data_desejada=None):
    if data_desejada is None:
        data_desejada = get_today_br()

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        nome_ministerio_tag = soup.find('a', href="https://www.gov.br/saude/pt-br")
        nome_ministerio = nome_ministerio_tag.text.strip() if nome_ministerio_tag else "Nome do Ministério não disponível"

        noticias = soup.find_all('article', class_='tileItem')

        for noticia in noticias:
            data_icon = noticia.find('i', class_='icon-day')
            data_raw = data_icon.find_next_sibling(string=True).strip() if data_icon else "Data não disponível"

            data = format_date(data_raw)
            if not data:
                print(f"Data encontrada inválida ou em formato desconhecido: {data_raw}")
                continue

            if data == data_desejada:
                subt = noticia.find('span', class_='subtitle')
                subtitulo = subt.text.strip() if subt else "Subtítulo não disponível"

                tit = noticia.find('h2', class_='tileHeadline').find('a')
                titulo = tit.text.strip() if tit else "Título não disponível"
                link = tit['href'] if tit else "Link não disponível"

                if link not in already_scraped_urls:
                    desc = noticia.find('span', class_='description')
                    descricao = desc.text.strip() if desc else "Descrição não disponível"

                    # Salvar na aba 'gov' para ministérios
                    try:
                        gov_sheet = sheet.worksheet("gov")
                    except gspread.exceptions.WorksheetNotFound:
                        gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
                        gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
                    
                    gov_sheet.append_row([data, nome_ministerio, subtitulo, titulo, descricao, link])
                    add_scraped_url(sheet, link)

        print('Dados inseridos com sucesso na planilha.')

    except requests.exceptions.HTTPError as errh:
        print ("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print ("Oops: Something Else", err)

# Exemplo de uso
url = "https://www.gov.br/saude/pt-br/assuntos/noticias"
raspar_noticias_saude(url)

"""# Povos Indígenas - Notícias do dia"""

def raspar_noticias_povos_indigenas(url):
    # Data de hoje no formato brasileiro
    data_hoje = get_today_br()

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        noticias = soup.find_all('article', class_='entry')

        nome_ministerio_tag = soup.find('a', href="https://www.gov.br/povosindigenas/pt-br")
        nome_ministerio = nome_ministerio_tag.text.strip() if nome_ministerio_tag else "Ministério dos Povos Indígenas"

        for noticia in noticias:
            titulo_tag = noticia.find('span', class_='summary').find('a')
            titulo = titulo_tag.text.strip() if titulo_tag else "Título não disponível"
            link = titulo_tag['href'] if titulo_tag else "Link não disponível"

            data_tag = noticia.find('span', class_='documentByLine')
            if not data_tag:
                continue

            texto_data = data_tag.text.strip()
            if "última modificação" in texto_data:
                partes = texto_data.split("última modificação")
                data_raw = partes[-1].strip().split()[0]  # Tenta pegar a data

                data_formatada = format_date(data_raw)
                if not data_formatada:
                    continue

                # Verifica se é do dia atual
                if data_formatada == data_hoje and link not in already_scraped_urls:
                    descricao_tag = noticia.find('p', class_='description discreet')
                    descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"

                    # Salvar na aba 'gov' para ministérios
                    try:
                        gov_sheet = sheet.worksheet("gov")
                    except gspread.exceptions.WorksheetNotFound:
                        gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
                        gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
                    
                    gov_sheet.append_row([data_formatada, nome_ministerio, "Não disponível", titulo, descricao, link])
                    add_scraped_url(sheet, link)

        print('Raspagem concluída com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar o site: {err}")

url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/07"
raspar_noticias_povos_indigenas(url)

# ANS

import time
from requests.exceptions import ChunkedEncodingError
import certifi

def scrape_ans_news(url, sheet, max_retries=3):
    def safe_request(url):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, verify=certifi.where(), timeout=15)
                response.raise_for_status()
                return response
            except ChunkedEncodingError as e:
                print(f"Tentativa {attempt+1}: erro de leitura incompleta (ChunkedEncodingError) - {e}")
            except requests.exceptions.RequestException as e:
                print(f"Tentativa {attempt+1}: erro ao acessar {url} - {e}")
            time.sleep(2)
        return None

    response = safe_request(url)
    if response is None:
        print("Falha ao obter resposta da ANS após múltiplas tentativas.")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    data_list = []
    news_blocks = soup.find_all('div', class_='conteudo')

    already_scraped = get_already_scraped_urls(sheet)

    for block in news_blocks:
        subtitulo_tag = block.find('div', class_='subtitulo-noticia')
        subtitulo = subtitulo_tag.get_text(strip=True) if subtitulo_tag else 'N/A'

        titulo_tag = block.find('a', href=True)
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else 'N/A'
        link = titulo_tag['href'] if titulo_tag else 'N/A'

        if link in already_scraped:
            continue
        add_scraped_url(sheet, link)

        data_tag = block.find('span', class_='data')
        data_raw = data_tag.get_text(strip=True) if data_tag else 'N/A'
        data = format_date(data_raw) or data_raw  # usa formato padronizado ou original se falhar

        descricao_tag = block.find('span', class_='descricao')
        descricao = 'N/A'
        if descricao_tag:
            full_text = descricao_tag.get_text(strip=True)
            data_text = data_tag.get_text(strip=True) if data_tag else ''
            descricao = full_text.replace(data_text, '').strip()

        data_list.append({
            'Data': data,
            'Subtítulo': subtitulo,
            'Título': titulo,
            'Descrição': descricao,
            'Link': link
        })

    return data_list

def export_to_google_sheets_ans(data_list, sheet_id, json_keyfile):
    sheet = initialize_sheet()
    worksheet_name = "ans"

    try:
        worksheet = sheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=worksheet_name, rows="100", cols="5")

    df = pd.DataFrame(data_list)

    worksheet.clear()
    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        print("Dados inseridos com sucesso na aba 'ans'.")
    else:
        print("Nenhum dado novo para inserir.")

def main_ans():
    url = 'https://www.gov.br/ans/pt-br/assuntos/noticias'
    sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    json_keyfile = 'credentials.json'

    sheet = initialize_sheet()
    data_list = scrape_ans_news(url, sheet)
    export_to_google_sheets_ans(data_list, sheet_id, json_keyfile)

if __name__ == "__main__":
    main_ans()
    
"""# CFM"""

from google.oauth2.service_account import Credentials

# Mapeamento dos meses
MESES = {
    'jan': '01',
    'fev': '02',
    'mar': '03',
    'abr': '04',
    'mai': '05',
    'jun': '06',
    'jul': '07',
    'ago': '08',
    'set': '09',
    'out': '10',
    'nov': '11',
    'dez': '12'
}

def scrape_cfm_news(url, sheet):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    data_list = []

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        already_scraped_urls = get_already_scraped_urls(sheet)

        title_tag = soup.find('h3')
        title = title_tag.text.strip() if title_tag else 'N/A'

        link_tag = soup.find('a', class_='c-default', href=True)
        link = link_tag['href'] if link_tag else 'N/A'

        if link not in already_scraped_urls:
            date_div = soup.find('div', class_='noticia-date')
            day_tag = date_div.find('h3') if date_div else None
            month_year_div = date_div.find('div') if date_div else None

            day = day_tag.text.strip() if day_tag else 'N/A'

            if month_year_div:
                month_year_parts = month_year_div.get_text(separator=" ").split()
                if len(month_year_parts) >= 2:
                    month = month_year_parts[0]
                    year = month_year_parts[1]
                else:
                    month, year = 'N/A', 'N/A'
            else:
                month, year = 'N/A', 'N/A'

            # Tentar converter para formato padronizado
            if day != 'N/A' and month in MESES and year != 'N/A':
                try:
                    date_formatted = f"{day.zfill(2)}/{MESES[month]}/{year}"
                    date_text = format_date(date_formatted) or f"{day} {month} {year}"
                except:
                    date_text = f"{day} {month} {year}"
            else:
                date_text = f"{day} {month} {year}".strip()

            description_tag = soup.find('p')
            description = description_tag.text.strip() if description_tag else 'N/A'

            data_list.append({
                'Data': date_text,
                'Título': title,
                'Descrição': description,
                'Link': link
            })

            worksheet = sheet.worksheet("cfm")

            if worksheet.row_count == 1 and worksheet.cell(1, 1).value is None:
                worksheet.append_row(["Data", "Título", "Descrição", "Link"])

            df = pd.DataFrame(data_list)

            if not df.empty:
                worksheet.append_rows(df.values.tolist())

            add_scraped_url(sheet, link)

            print('Dados inseridos com sucesso na aba "cfm".')

        else:
            print(f"URL já raspada: {link}")

    except requests.exceptions.HTTPError as errh:
        print("Erro HTTP:", errh)
    except requests.exceptions.ConnectionError as errc:
        print("Erro de Conexão:", errc)
    except requests.exceptions.Timeout as errt:
        print("Erro de Timeout:", errt)
    except requests.exceptions.RequestException as err:
        print("Outro erro ocorreu:", err)

# Exemplo de uso
sheet = initialize_sheet()
url = "https://portal.cfm.org.br/noticias/?s="
scrape_cfm_news(url, sheet)

"""# FIOCRUZ"""

def raspar_fiocruz(sheet):
    data_desejada = get_today_br()
    url = "https://fiocruz.br/noticias"

    try:
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar Fiocruz: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    blocos = soup.select("div.views-row")
    urls_existentes = get_already_scraped_urls(sheet)

    try:
        aba = sheet.worksheet("fiocruz")
    except gspread.exceptions.WorksheetNotFound:
        aba = sheet.add_worksheet(title="fiocruz", rows="100", cols="6")
        aba.append_row(["Data", "Título", "Descrição", "Link"])

    novas_linhas = []
    for bloco in blocos:
        data_tag = bloco.find("div", class_="data-busca")
        if not data_tag:
            continue
        time_tag = data_tag.find("time")
        data_raw = time_tag.text.strip() if time_tag else ""
        
        data = format_date(data_raw)
        if not data or data != data_desejada:
            continue

        titulo_tag = bloco.find("div", class_="titulo-busca").find("a")
        titulo = titulo_tag.text.strip()
        link = "https://www.fiocruz.br" + titulo_tag["href"]

        if link in urls_existentes:
            continue

        chamada_tag = bloco.find("div", class_="chamada-busca")
        descricao = chamada_tag.text.strip() if chamada_tag else ""

        novas_linhas.append([data, titulo, descricao, link])
        add_scraped_url(sheet, link)

    if novas_linhas:
        aba.append_rows(novas_linhas)
        print(f"{len(novas_linhas)} notícia(s) da Fiocruz adicionadas.")
    else:
        print("Nenhuma nova notícia da Fiocruz para hoje.")

# Executar
sheet = initialize_sheet()
raspar_fiocruz(sheet)

"""# Igualdade Racial"""

def raspar_noticias_igualdade_racial(url, data_desejada=None):
    if data_desejada is None:
        data_desejada = get_today_br()

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        noticias = soup.find_all('div', class_='conteudo')

        nome_ministerio_tag = soup.find('a', href="https://www.gov.br/igualdaderacial/pt-br")
        nome_ministerio = nome_ministerio_tag.text.strip() if nome_ministerio_tag else "Nome do Ministério não disponível"

        for noticia in noticias:
            categoria_tag = noticia.find('div', class_='categoria-noticia')
            categoria = categoria_tag.text.strip() if categoria_tag else "Categoria não disponível"

            titulo_tag = noticia.find('h2', class_='titulo').find('a')
            titulo = titulo_tag.text.strip() if titulo_tag else "Título não disponível"
            link = titulo_tag['href'] if titulo_tag else "Link não disponível"

            data_tag = noticia.find('span', class_='data')
            data_raw = data_tag.text.strip() if data_tag else "Data não disponível"

            data = format_date(data_raw)
            if not data:
                print(f"Data encontrada inválida ou em formato desconhecido: {data_raw}")
                continue

            descricao_tag = noticia.find('span', class_='descricao')
            descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"

            if data == data_desejada and link not in already_scraped_urls:
                # Salvar na aba 'gov' para ministérios
                try:
                    gov_sheet = sheet.worksheet("gov")
                except gspread.exceptions.WorksheetNotFound:
                    gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
                    gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
                
                gov_sheet.append_row([data, nome_ministerio, categoria, titulo, descricao, link])
                add_scraped_url(sheet, link)

        print('Dados inseridos com sucesso na planilha.')

    except requests.exceptions.HTTPError as errh:
        print("HTTP Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print("Oops: Something Else", err)

# Exemplo de uso
url = "https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias"
raspar_noticias_igualdade_racial(url)

"""# ANVISA – Raspagem de notícias do dia atual"""

def raspar_anvisa_do_dia(sheet):
    data_hoje = get_today_br()
    url = 'https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a Anvisa: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    noticias = soup.select('ul.noticias.listagem-noticias-com-foto > li')
    urls_existentes = get_already_scraped_urls(sheet)

    for noticia in noticias:
        titulo_tag = noticia.find('h2', class_='titulo').find('a')
        if not titulo_tag:
            continue

        titulo = titulo_tag.text.strip()
        link = titulo_tag['href']
        if link in urls_existentes:
            continue

        subtitulo_tag = noticia.find('div', class_='subtitulo-noticia')
        subtitulo = subtitulo_tag.text.strip() if subtitulo_tag else "Subtítulo não disponível"

        descricao_tag = noticia.find('span', class_='descricao')
        if descricao_tag:
            descricao_completa = descricao_tag.text.strip()
            partes = descricao_completa.split('-')
            data_lida_raw = partes[0].strip()
            data_lida = format_date(data_lida_raw) or data_lida_raw
            descricao = partes[1].strip() if len(partes) > 1 else descricao_completa
        else:
            continue

        if data_lida == data_hoje:
            sheet.worksheet("anvisa").append_row([
                data_lida, "ANVISA", subtitulo, titulo, descricao, link
            ])
            add_scraped_url(sheet, link)

    print("Notícias da Anvisa do dia atual inseridas com sucesso.")

# Executar
sheet = initialize_sheet()
raspar_anvisa_do_dia(sheet)

"""# Consed"""

def raspar_noticias_por_data_consed(sheet, data_desejada=None, max_pages=5):
    # URL base do site que queremos raspar
    base_url = "https://www.consed.org.br/noticias?page="

    # Lista para armazenar os dados extraídos
    data = []

    # Data atual
    if data_desejada is None:
        data_desejada = get_today_br()

    # Recupera URLs já raspadas - agora usando o objeto sheet correto
    already_scraped_urls = get_already_scraped_urls(sheet)

    # Número da página inicial
    page = 1

    while page <= max_pages:
        # Monta a URL da página atual
        url = f"{base_url}{page}"

        try:
            # Faz a requisição para obter o conteúdo da página
            response = requests.get(url, timeout=10)  # Timeout de 10 segundos
            response.raise_for_status()  # Levanta uma exceção para status de erro HTTP
        except requests.exceptions.RequestException as e:
            print(f"Erro ao acessar a URL {url}: {e}")
            break

        content = response.content

        # Parseia o conteúdo da página com BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        # Encontrar todos os artigos de notícias
        news_items = soup.find_all('a', href=True)

        # Verifica se há notícias na página
        if not news_items:
            break

        # Iterar sobre cada item de notícia e extrair as informações
        for item in news_items:
            title_tag = item.find('h2')
            date_tag = item.find('small')
            description_tag = item.find('p')

            # Verificar se todos os elementos são encontrados
            if title_tag and date_tag and description_tag:
                title = title_tag.text.strip()
                date_raw = date_tag.text.strip()
                description = description_tag.text.strip()
                link = item['href']

                # Padronizar formato da data
                date_formatted = format_date(date_raw)
                if not date_formatted:
                    continue

                # Verificar se a data é igual à data desejada
                if date_formatted == data_desejada:
                    # Armazenar os dados no formato de lista
                    full_link = link if link.startswith("http") else f"https://www.consed.org.br{link}"

                    # Verificar se a URL já foi raspada
                    if full_link not in already_scraped_urls:
                        dados = [date_formatted, title, description, full_link]

                        # Adicionar a lista de dados para ser inserida na planilha
                        data.append(dados)

                        # Adicionar URL à lista de URLs raspadas
                        add_scraped_url(sheet, full_link)

        # Incrementa o número da página
        page += 1

    # Inserir todos os dados na planilha de uma vez
    if data:
        try:
            consed_sheet = sheet.worksheet('consed')
        except gspread.exceptions.WorksheetNotFound:
            consed_sheet = sheet.add_worksheet(title='consed', rows="1000", cols="4")
            consed_sheet.append_row(["Data", "Título", "Descrição", "Link"])
        
        consed_sheet.append_rows(data)
        print('Dados inseridos com sucesso na planilha.')
    else:
        print('Nenhum dado encontrado para a data especificada.')

# Exemplo de uso
sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
sheet = initialize_sheet()
consed_sheet = sheet.worksheet('consed')
# Para raspar notícias da data atual
raspar_noticias_por_data_consed(consed_sheet, max_pages=5)

"""# Undime"""

def raspar_noticias_undime(data_desejada, sheet):
    url = "https://undime.org.br/noticia/page/1"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    noticias = soup.find_all('div', class_='noticia mt-4 shadow2 p-3 border-radius')

    datas = []
    titulos = []
    descricoes = []
    links = []

    # Recupera URLs já raspadas
    already_scraped_urls = get_already_scraped_urls(sheet)

    for noticia in noticias:
        # Link e Data
        link_elem = noticia.find('a', href=True)
        if link_elem:
            link = "https://undime.org.br" + link_elem['href']

            # Verificar se a URL já foi raspada
            if link in already_scraped_urls:
                continue

            # Extrair data do link e transformar em dd/mm/yyyy
            data_match = re.search(r'\d{2}-\d{2}-\d{4}', link)
            if data_match:
                data_str = data_match.group(0)
                data_formatted = format_date(data_str.replace('-', '/'))
                if not data_formatted or data_formatted != data_desejada:
                    continue
                    
                datas.append(data_formatted)
                links.append(link)
                add_scraped_url(sheet, link)
            else:
                continue
        else:
            continue

        # Título
        titulo_elem = noticia.find('h4')
        if titulo_elem:
            titulo = titulo_elem.text.strip()
            titulos.append(titulo)
        else:
            titulos.append(None)

        # Descrição
        try:
            descricao_elem = noticia.select_one('p.acessibilidade > a')
            descricao = descricao_elem.text.strip() if descricao_elem else None
        except:
            descricao = None
        descricoes.append(descricao)

    return zip(datas, titulos, descricoes, links)

def salvar_na_planilha_undime(sheet, dados):
    linhas = []
    for data, titulo, descricao, link in dados:
        linhas.append([data, titulo, descricao, link])
    sheet.append_rows(linhas, value_input_option='USER_ENTERED')
    print('Dados inseridos com sucesso na planilha.')

# Exemplo de uso
sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
sheet = initialize_sheet()
undime_sheet = sheet.worksheet('undime')

# Data de hoje no fuso horário do Brasil
data_hoje = get_today_br()

# Raspar dados das notícias da data de hoje
dados_noticias = raspar_noticias_undime(data_hoje, sheet)

# Salvar dados na planilha
salvar_na_planilha_undime(undime_sheet, dados_noticias)

"""# Função principal para executar todos os scrapers"""

def executar_todos_scrapers():
    """
    Executa todos os scrapers de notícias com gestão de datas padronizada
    """
    print("Iniciando raspagem de notícias com datas padronizadas...")
    print(f"Data atual: {get_today_br()}")
    
    try:
        # Ministério do Esporte
        print("\n--- Ministério do Esporte ---")
        sheet = initialize_sheet()
        raspar_noticias_por_data("https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte", sheet)
        
        # Ministério da Educação
        print("\n--- Ministério da Educação ---")
        raspar_noticias_por_data_mec("https://www.gov.br/mec/pt-br/assuntos/noticias", sheet)
        
        # Ministério da Saúde
        print("\n--- Ministério da Saúde ---")
        raspar_noticias_saude("https://www.gov.br/saude/pt-br/assuntos/noticias")
        
        # Povos Indígenas
        print("\n--- Ministério dos Povos Indígenas ---")
        raspar_noticias_povos_indigenas("https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/07")
        
        # ANS
        print("\n--- ANS ---")
        main_ans()
        
        # CFM
        print("\n--- CFM ---")
        sheet = initialize_sheet()
        scrape_cfm_news("https://portal.cfm.org.br/noticias/?s=", sheet)
        
        # Fiocruz
        print("\n--- Fiocruz ---")
        sheet = initialize_sheet()
        raspar_fiocruz(sheet)
        
        # Igualdade Racial
        print("\n--- Ministério da Igualdade Racial ---")
        raspar_noticias_igualdade_racial("https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias")
        
        # ANVISA
        print("\n--- ANVISA ---")
        sheet = initialize_sheet()
        raspar_anvisa_do_dia(sheet)
        
        # Consed
        print("\n--- Consed ---")
        sheet = initialize_sheet()
        consed_sheet = sheet.worksheet('consed')
        raspar_noticias_por_data_consed(consed_sheet, max_pages=5)
        
        # Undime
        print("\n--- Undime ---")
        sheet = initialize_sheet()
        undime_sheet = sheet.worksheet('undime')
        data_hoje = get_today_br()
        dados_noticias = raspar_noticias_undime(data_hoje, sheet)
        salvar_na_planilha_undime(undime_sheet, dados_noticias)
        
        print(f"\n✅ Raspagem concluída com sucesso! Todas as datas foram padronizadas para o formato DD/MM/YYYY")
        
    except Exception as e:
        print(f"\n❌ Erro durante a execução: {e}")

# Executar todos os scrapers
if __name__ == "__main__":
    executar_todos_scrapers()
