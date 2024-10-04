# Preparando

import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import urllib3
import re

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

"""# ANS"""

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import urllib3

# Suprimir avisos de solicitação insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def initialize_sheet(sheet_url, json_keyfile):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    credentials = Credentials.from_service_account_file(json_keyfile, scopes=scope)
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(sheet_url)
    return sheet

# Função para verificar URLs já raspadas
def get_already_scraped_urls(sheet):
    try:
        urls_sheet = sheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.add_worksheet(title="URLs", rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])  # Excluir o cabeçalho

# Função para adicionar uma URL já raspada
def add_scraped_url(sheet, url):
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

# Função para raspar dados da página da ANS
def scrape_ans_news(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    data_list = []
    news_blocks = soup.find_all('div', class_='conteudo')

    for block in news_blocks:
        # Verificar subtítulo
        subtitulo_tag = block.find('div', class_='subtitulo-noticia')
        subtitulo = subtitulo_tag.get_text(strip=True) if subtitulo_tag else 'N/A'
        
        # Verificar título e link
        titulo_tag = block.find('a', href=True)
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else 'N/A'
        link = titulo_tag['href'] if titulo_tag else 'N/A'
        
        # Verificar data
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

# Função para exportar os dados para Google Sheets
def export_to_google_sheets(data_list, sheet_url, json_keyfile):
    sheet = initialize_sheet(sheet_url, json_keyfile)
    worksheet = sheet.get_worksheet(0)

    # Converter a lista de dicionários em DataFrame
    df = pd.DataFrame(data_list)

    # Limpar a aba antes de adicionar novos dados
    worksheet.clear()

    # Atualizar a aba com novos dados
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# Função principal para raspar e exportar os dados
def main():
    url = 'https://www.gov.br/ans/pt-br/assuntos/noticias'
    sheet_url = 'https://docs.google.com/spreadsheets/d/1TK5I9_2dTwXTIK2_uLA3_W-ZCnOCubkiYKR1sH_sCAE/edit?gid=0'
    json_keyfile = 'raspagemdou-151e0ee88b03.json'

    # Executar a raspagem
    data_list = scrape_ans_news(url)

    # Exportar para Google Sheets
    export_to_google_sheets(data_list, sheet_url, json_keyfile)

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

            # Verificar se a data é a mesma da data desejada
            if data_text == data_desejada:
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
                    sheet.sheet1.append_row([data_text, titulo, descricao, link])
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

"""# Povos Indígenas"""

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
        noticias = soup.find_all('article', class_='entry')

        nome_ministerio_tag = soup.find('a', href="https://www.gov.br/povosindigenas/pt-br")
        nome_ministerio = nome_ministerio_tag.text.strip() if nome_ministerio_tag else "Nome do Ministério não disponível"

        for noticia in noticias:
            titulo_tag = noticia.find('span', class_='summary').find('a')
            titulo = titulo_tag.text.strip() if titulo_tag else "Título não disponível"
            link = titulo_tag['href'] if titulo_tag else "Link não disponível"

            data_tag = noticia.find('span', class_='documentByLine')
            data = "Data não disponível"
            if data_tag:
                data_parts = data_tag.text.strip().split('última modificação')
                if len(data_parts) > 1:
                    data_raw = data_parts[-1].split()[0].strip()  # Extrair apenas a data

                    try:
                        data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
                    except ValueError:
                        print(f"Data encontrada inválida ou em formato desconhecido: {data_raw}")
                        continue  # Skip to next news item if the date is invalid

            if data == data_desejada and link not in already_scraped_urls:  # Verificar se a data corresponde à data desejada
                descricao_tag = noticia.find('p', class_='description discreet')
                descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"
                sheet.sheet1.append_row([data, nome_ministerio, "Não disponível", titulo, descricao, link])
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
url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2024/10"
data_especifica = "08/08/2024"
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
    worksheet = sheet.get_worksheet(0)

    # Converter a lista de dicionários em DataFrame para fácil manipulação
    df = pd.DataFrame(data_list)

    # Limpar a aba antes de adicionar novos dados
    worksheet.clear()

    # Atualizar a aba com novos dados
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# URL da página da ANS
url = 'https://www.gov.br/ans/pt-br/assuntos/noticias'

# Planilha Google Sheets (atualizada para o novo link fornecido)
sheet_url = 'https://docs.google.com/spreadsheets/d/1TK5I9_2dTwXTIK2_uLA3_W-ZCnOCubkiYKR1sH_sCAE/edit?gid=0'

# Caminho para o arquivo JSON de credenciais
json_keyfile = 'raspagemdou-151e0ee88b03.json'

# Executar a raspagem e exportar para Google Sheets
data_list = scrape_ans_news(url)
export_to_google_sheets(data_list, sheet_url, json_keyfile)

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
