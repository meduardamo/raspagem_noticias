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
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")  # Formato de data: DD/MM/YYYY

    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Levantará uma exceção para respostas 4xx/5xx

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        meta_tag = soup.find('meta', property="og:site_name")
        nome_ministerio = meta_tag['content'] if meta_tag else "Nome do Ministério não identificado"
        noticias = soup.find_all('li')

        for noticia in noticias:
            data_element = noticia.find('span', class_='data')
            if data_element:
                data_text_raw = data_element.text.strip()
                try:
                    data_text = datetime.strptime(data_text_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
                except ValueError:
                    print(f"Data encontrada inválida ou em formato desconhecido: {data_text_raw}")
                    continue  # Skip to next news item if the date is invalid
                if data_text == data_desejada:
                    titulo_element = noticia.find('h2', class_='titulo')
                    url = titulo_element.find('a')['href']
                    if url not in already_scraped_urls:
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
                            url                  # URL
                        ]

                        sheet.sheet1.append_row(dados)
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
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")  # Formato de data: DD/MM/YYYY

    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Levantará uma exceção para respostas 4xx/5xx

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        meta_tag = soup.find('meta', property="og:site_name")
        nome_ministerio = meta_tag['content'] if meta_tag else "Nome do Ministério não identificado"
        noticias = soup.find_all('li')

        for noticia in noticias:
            data_element = noticia.find('span', class_='data')
            if data_element:
                data_text_raw = data_element.text.strip()
                try:
                    data_text = datetime.strptime(data_text_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
                except ValueError:
                    print(f"Data encontrada inválida ou em formato desconhecido: {data_text_raw}")
                    continue  # Skip to next news item if the date is invalid
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

                        sheet.sheet1.append_row(dados)
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
raspar_noticias_por_data(url, sheet)

"""# Ministério da Saúde"""

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

def raspar_noticias(url, data_desejada=None):
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Levantará uma exceção para respostas 4xx/5xx

        soup = BeautifulSoup(response.text, 'html.parser')

        nome_ministerio_tag = soup.find('a', href="https://www.gov.br/saude/pt-br")
        nome_ministerio = nome_ministerio_tag.text.strip() if nome_ministerio_tag else "Nome do Ministério não disponível"

        noticias = soup.find_all('article', class_='tileItem')

        for noticia in noticias:
            data_icon = noticia.find('i', class_='icon-day')
            data_raw = data_icon.find_next_sibling(string=True).strip() if data_icon else "Data não disponível"

            try:
                data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError:
                print(f"Data encontrada inválida ou em formato desconhecido: {data_raw}")
                continue  # Skip to next news item if the date is invalid

            if data == data_desejada:
                subt = noticia.find('span', class_='subtitle')
                subtitulo = subt.text.strip() if subt else "Subtítulo não disponível"

                tit = noticia.find('h2', class_='tileHeadline').find('a')
                titulo = tit.text.strip() if tit else "Título não disponível"
                link = tit['href'] if tit else "Link não disponível"

                if link not in already_scraped_urls:
                    desc = noticia.find('span', class_='description')
                    descricao = desc.text.strip() if desc else "Descrição não disponível"

                    sheet.sheet1.append_row([data, nome_ministerio, subtitulo, titulo, descricao, link])
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
raspar_noticias(url)

"""# Povos Indígenas - Notícias do dia"""

import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import urllib3

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
    return set(urls[1:])

def add_scraped_url(sheet, url):
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

def raspar_noticias(url):
    # Data de hoje no formato brasileiro
    tz = pytz.timezone('America/Sao_Paulo')
    data_hoje = datetime.now(tz).strftime("%d/%m/%Y")

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

                try:
                    data_formatada = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
                except ValueError:
                    continue  # Ignora se a data for inválida

                # ✅ Verifica se é do dia atual
                if data_formatada == data_hoje and link not in already_scraped_urls:
                    descricao_tag = noticia.find('p', class_='description discreet')
                    descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"

                    sheet.sheet1.append_row([data_formatada, nome_ministerio, "Não disponível", titulo, descricao, link])
                    add_scraped_url(sheet, link)

        print('Raspagem concluída com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar o site: {err}")

url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/06-1"
raspar_noticias(url)


"""# ANS"""

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import urllib3
import certifi

# Suprimir avisos de solicitação insegura (ainda útil caso haja sites inseguros, mas não usado no ANS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def initialize_sheet(sheet_id, json_keyfile):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_file(json_keyfile, scopes=scope)
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id)
    return sheet

def get_already_scraped_urls(sheet):
    try:
        urls_sheet = sheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.add_worksheet(title="URLs", rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])

def add_scraped_url(sheet, url):
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

def scrape_ans_news(url):
    try:
        response = requests.get(url, verify=certifi.where(), timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a URL {url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    data_list = []
    news_blocks = soup.find_all('div', class_='conteudo')

    for block in news_blocks:
        subtitulo_tag = block.find('div', class_='subtitulo-noticia')
        subtitulo = subtitulo_tag.get_text(strip=True) if subtitulo_tag else 'N/A'

        titulo_tag = block.find('a', href=True)
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else 'N/A'
        link = titulo_tag['href'] if titulo_tag else 'N/A'

        data_tag = block.find('span', class_='data')
        data = data_tag.get_text(strip=True) if data_tag else 'N/A'

        data_list.append({
            'Data': data,
            'Subtítulo': subtitulo,
            'Título': titulo,
            'Link': link
        })

    return data_list

def export_to_google_sheets(data_list, sheet_id, json_keyfile):
    sheet = initialize_sheet(sheet_id, json_keyfile)
    worksheet_name = "ans"

    try:
        worksheet = sheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=worksheet_name, rows="100", cols="4")

    df = pd.DataFrame(data_list)

    worksheet.clear()
    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        print("Dados inseridos com sucesso na aba 'ans'.")
    else:
        print("Nenhum dado encontrado para inserir.")

def main():
    url = 'https://www.gov.br/ans/pt-br/assuntos/noticias'
    sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    json_keyfile = 'credentials.json'

    data_list = scrape_ans_news(url)
    export_to_google_sheets(data_list, sheet_id, json_keyfile)

if __name__ == "__main__":
    main()
    
"""# CFM"""

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import urllib3
from datetime import datetime
import pytz

# Suprimir avisos de solicitação insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
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

def raspar_noticias(url, data_desejada=None):
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")  # Formato de data: DD/MM/YYYY

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Levantará uma exceção para respostas 4xx/5xx

        soup = BeautifulSoup(response.text, 'html.parser')

        noticias = soup.find_all('div', class_='noticia')  # Ajustar para a estrutura de notícias desejada

        for noticia in noticias:
            # Capturar data da notícia
            date_div = noticia.find('div', class_='noticia-date')
            day_tag = date_div.find('h3') if date_div else None
            month_year_div = date_div.find('div') if date_div else None

            # Capturar o dia
            day = day_tag.text.strip() if day_tag else 'N/A'

            # Capturar o mês e o ano
            if month_year_div:
                month_year_parts = month_year_div.get_text(separator=" ").split()
                if len(month_year_parts) >= 2:
                    month = month_year_parts[0]
                    year = month_year_parts[1]
                else:
                    month, year = 'N/A', 'N/A'
            else:
                month, year = 'N/A', 'N/A'

            # Combinar dia, mês e ano em uma única string
            data_text = f"{day} {month} {year}".strip()

            # Dicionário de conversão de mês por extenso para número
            meses = {
                'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
                'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
                'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
            }

            # Converter a data para o formato DD/MM/YYYY
            try:
                dia = day.zfill(2)
                mes_num = meses.get(month.lower())
                data_convertida = f"{dia}/{mes_num}/{year}" if mes_num else None
            except Exception:
                data_convertida = None

            # Verificar se a data é a mesma da data desejada
            if data_convertida == data_desejada:
                # Capturar título
                titulo_tag = noticia.find('h3')
                titulo = titulo_tag.text.strip() if titulo_tag else 'N/A'

                # Capturar link
                link_tag = noticia.find('a', class_='c-default', href=True)
                link = link_tag['href'] if link_tag else 'N/A'

                # Verificar se a URL já foi raspada
                if link not in already_scraped_urls:
                    # Capturar descrição
                    description_tag = noticia.find('p')
                    descricao = description_tag.text.strip() if description_tag else 'N/A'

                    # Inserir dados na planilha
                    sheet.sheet1.append_row([data_convertida, titulo, descricao, link])
                    add_scraped_url(sheet, link)

        print('Dados inseridos com sucesso na planilha.')

    except requests.exceptions.HTTPError as errh:
        print("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print("Oops: Something Else", err)

# Exemplo de uso
url = "https://portal.cfm.org.br/noticias/?s="
raspar_noticias(url)

"""# FIOCRUZ"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import urllib3

# Suprimir avisos de solicitação insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(''credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key('1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY')

def get_already_scraped_urls(sheet):
    try:
        urls_sheet = sheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.add_worksheet(title="URLs", rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    return set(urls_sheet.col_values(1)[1:])

def add_scraped_url(sheet, url):
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

def raspar_fiocruz(sheet):
    tz = pytz.timezone('America/Sao_Paulo')
    data_desejada = datetime.now(tz).strftime("%d/%m/%Y")
    url = "https://fiocruz.br/noticias"

    try:
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar Fiocruz: {e}")
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
        data = data_tag.find("time").text.strip()
        if data != data_desejada:
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
        print(f"✅ {len(novas_linhas)} notícia(s) da Fiocruz adicionadas.")
    else:
        print("⚠️ Nenhuma nova notícia da Fiocruz para hoje.")

# Executar
sheet = initialize_sheet()
raspar_fiocruz(sheet)

"""# Igualdade Racial"""

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

def raspar_noticias(url, data_desejada=None):
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")  # Data atual no fuso horário do Brasil

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Raises HTTPError for bad responses

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

            try:
                data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError:
                print(f"Data encontrada inválida ou em formato desconhecido: {data_raw}")
                continue  # Skip to next news item if the date is invalid

            descricao_tag = noticia.find('span', class_='descricao')
            descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"

            if data == data_desejada and link not in already_scraped_urls:
                sheet.sheet1.append_row([data, nome_ministerio, categoria, titulo, descricao, link])
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
data_especifica = "22/05/2024"
raspar_noticias(url)

"""# ANS"""

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Função para raspar dados da página da ANS
def scrape_ans_news(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    data_list = []

    # Encontre todos os blocos de notícias
    news_blocks = soup.find_all('div', class_='conteudo')

    for block in news_blocks:
        # Verificar se o subtítulo existe antes de tentar acessar seu texto
        subtitulo_tag = block.find('div', class_='subtitulo-noticia')
        subtitulo = subtitulo_tag.get_text(strip=True) if subtitulo_tag else 'N/A'
        
        # Verificar se o título e o link existem antes de tentar acessá-los
        titulo_tag = block.find('a', href=True)
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else 'N/A'
        link = titulo_tag['href'] if titulo_tag else 'N/A'
        
        # Verificar se a data existe antes de tentar acessar seu texto
        data_tag = block.find('span', class_='data')
        data = data_tag.get_text(strip=True) if data_tag else 'N/A'

        # Adicionar os dados à lista
        data_list.append({
            'Data': data,
            'Subtítulo': subtitulo,
            'Título': titulo,
            'Link': link
        })

    return data_list

# Autenticar e acessar a planilha do Google Sheets
def export_to_google_sheets(data_list, sheet_url, json_keyfile):
    # Configurações da API do Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    credentials = Credentials.from_service_account_file(json_keyfile, scopes=scope)
    client = gspread.authorize(credentials)

    # Acessar a planilha e aba específica
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet('ans')

    # Converter a lista de dicionários em DataFrame para fácil manipulação
    df = pd.DataFrame(data_list)

    # Limpar a aba antes de adicionar novos dados
    worksheet.clear()

    # Atualizar a aba com novos dados
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# URL da página da ANS
url = 'https://www.gov.br/ans/pt-br/assuntos/noticias'

# Planilha Google Sheets (atualizada para o novo link fornecido)
sheet_url = 'https://docs.google.com/spreadsheets/d/1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY/edit?gid=0#gid=0'

# Caminho para o arquivo JSON de credenciais
json_keyfile = 'credentials.json'

# Executar a raspagem e exportar para Google Sheets
data_list = scrape_ans_news(url)
export_to_google_sheets(data_list, sheet_url, json_keyfile)

# ANVISA – Raspagem de notícias do dia atual

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import urllib3

# Suprimir avisos SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key('1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY')

def get_already_scraped_urls(sheet):
    try:
        urls_sheet = sheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.add_worksheet(title="URLs", rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])

def add_scraped_url(sheet, url):
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

def raspar_anvisa_do_dia(sheet):
    tz = pytz.timezone('America/Sao_Paulo')
    data_hoje = datetime.now(tz).strftime("%d/%m/%Y")
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
            data_lida = partes[0].strip()
            descricao = partes[1].strip() if len(partes) > 1 else descricao_completa
        else:
            continue

        if data_lida == data_hoje:
            sheet.worksheet("anvisa").append_row([
                data_lida, "ANVISA", subtitulo, titulo, descricao, link
            ])
            add_scraped_url(sheet, link)

    print("✅ Notícias da Anvisa do dia atual inseridas com sucesso.")

# Executar
sheet = initialize_sheet()
raspar_anvisa_do_dia(sheet)

"""# Consed"""

def initialize_sheet(sheet_id, sheet_name='Página2'):
    # Escopo e credenciais para acessar a API do Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
    return sheet

def get_already_scraped_urls(sheet, url_sheet_name="URLs"):
    try:
        urls_sheet = sheet.spreadsheet.worksheet(url_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.spreadsheet.add_worksheet(title=url_sheet_name, rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])  # Exclude the header

def add_scraped_url(sheet, url, url_sheet_name="URLs"):
    urls_sheet = sheet.spreadsheet.worksheet(url_sheet_name)
    urls_sheet.append_row([url])

def raspar_noticias_por_data(sheet, data_desejada=None, max_pages=5):
    # URL base do site que queremos raspar
    base_url = "https://www.consed.org.br/noticias?page="

    # Lista para armazenar os dados extraídos
    data = []

    # Data atual
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")  # Formato de data: DD/MM/YYYY

    # Recupera URLs já raspadas
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
                date = date_tag.text.strip()
                description = description_tag.text.strip()
                link = item['href']

                # Verificar se a data é igual à data desejada
                if date == data_desejada:
                    # Armazenar os dados no formato de lista
                    full_link = link if link.startswith("http") else f"https://www.consed.org.br{link}"

                    # Verificar se a URL já foi raspada
                    if full_link not in already_scraped_urls:
                        dados = [date, title, description, full_link]

                        # Adicionar a lista de dados para ser inserida na planilha
                        data.append(dados)

                        # Adicionar URL à lista de URLs raspadas
                        add_scraped_url(sheet, full_link)

        # Incrementa o número da página
        page += 1

    # Inserir todos os dados na planilha de uma vez
    if data:
        sheet.append_rows(data)
        print('Dados inseridos com sucesso na planilha.')
    else:
        print('Nenhum dado encontrado para a data especificada.')

# Exemplo de uso
sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'  # Chave da planilha
sheet = initialize_sheet(sheet_id, sheet_name='consed')
# Para raspar notícias da data atual
raspar_noticias_por_data(sheet, max_pages=5)

"""# Undime"""

def initialize_sheet(sheet_id, sheet_name='Página3'):
    # Escopo e credenciais para acessar a API do Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
    return sheet

def get_already_scraped_urls(sheet, url_sheet_name="URLs"):
    try:
        urls_sheet = sheet.spreadsheet.worksheet(url_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.spreadsheet.add_worksheet(title=url_sheet_name, rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])  # Exclude the header

def add_scraped_url(sheet, url, url_sheet_name="URLs"):
    urls_sheet = sheet.spreadsheet.worksheet(url_sheet_name)
    urls_sheet.append_row([url])

def raspar_noticias(data_desejada, sheet):
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

            # Extrair data do link e transformar em xx/xx/xxxx
            data_match = re.search(r'\d{2}-\d{2}-\d{4}', link)
            if data_match:
                data_str = data_match.group(0)
                data = datetime.strptime(data_str, '%d-%m-%Y').strftime('%d/%m/%Y')
                if data == data_desejada:
                    datas.append(data)
                    links.append(link)
                    add_scraped_url(sheet, link)  # Adicionar URL à lista de URLs raspadas
                else:
                    continue
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
        descricao_elem = noticia.find('p', class_='acessibilidade')
        if descricao_elem and descricao_elem.find('a'):
            descricao = descricao_elem.find('a').text.strip()
            descricoes.append(descricao)
        else:
            descricoes.append(None)

    return zip(datas, titulos, descricoes, links)

def salvar_na_planilha(sheet, dados):
    linhas = []
    for data, titulo, descricao, link in dados:
        linhas.append([data, titulo, descricao, link])
    sheet.append_rows(linhas, value_input_option='USER_ENTERED')
    print('Dados inseridos com sucesso na planilha.')

# Chave da planilha Google Sheets
sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
sheet = initialize_sheet(sheet_id, sheet_name='undime')

# Data de hoje no fuso horário do Brasil
tz = pytz.timezone('America/Sao_Paulo')
data_hoje = datetime.now(tz).strftime('%d/%m/%Y')

# Raspar dados das notícias da data de hoje
dados_noticias = raspar_noticias(data_hoje, sheet)

# Salvar dados na planilha
salvar_na_planilha(sheet, dados_noticias)
