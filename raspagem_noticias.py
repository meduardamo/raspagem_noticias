# Preparando

import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import urllib3

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
url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2024/05"
data_especifica = "07/05/2024"
raspar_noticias(url)

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
