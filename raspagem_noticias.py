# =============================================================================
# SCRAPER DE NOTÍCIAS GOVERNAMENTAIS - VERSÃO CORRIGIDA COM DATAS
# =============================================================================

import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
import urllib3
import re
import pandas as pd
import certifi
import time
from requests.exceptions import ChunkedEncodingError

# Suprimir avisos de solicitação insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# FUNÇÕES UTILITÁRIAS COMPARTILHADAS
# =============================================================================

def initialize_sheet():
    """Inicializa conexão com Google Sheets usando oauth2client"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key('1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY')
    return sheet

def initialize_sheet_modern(sheet_id, json_keyfile):
    """Inicializa conexão com Google Sheets usando google.oauth2"""
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

def configurar_formato_data(sheet, worksheet_name, column_range="A:A"):
    """Configura uma coluna para formato de data brasileiro"""
    try:
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.format(column_range, {
            "numberFormat": {
                "type": "DATE",
                "pattern": "dd/mm/yyyy"
            }
        })
        print(f"Formato de data configurado para {worksheet_name}")
    except Exception as e:
        print(f"Erro ao configurar formato de data: {e}")

def get_already_scraped_urls(sheet):
    """Obtém URLs já raspadas para evitar duplicatas"""
    try:
        urls_sheet = sheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        urls_sheet = sheet.add_worksheet(title="URLs", rows="1", cols="1")
        urls_sheet.append_row(["URLs"])
    urls = urls_sheet.col_values(1)
    return set(urls[1:])  # Exclui o cabeçalho

def add_scraped_url(sheet, url):
    """Adiciona URL à lista de URLs já raspadas"""
    urls_sheet = sheet.worksheet("URLs")
    urls_sheet.append_row([url])

def converter_data_para_objeto(data_string, formato="%d/%m/%Y"):
    """Converte string de data para objeto datetime"""
    try:
        return datetime.strptime(data_string, formato)
    except ValueError:
        print(f"Erro ao converter data: {data_string}")
        return None

# =============================================================================
# MINISTÉRIO DO ESPORTE
# =============================================================================

def raspar_ministerio_esporte(url=None, data_desejada=None):
    """Raspa notícias do Ministério do Esporte"""
    if url is None:
        url = "https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte"
    
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz)
    elif isinstance(data_desejada, str):
        data_desejada = converter_data_para_objeto(data_desejada)

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)
    
    # Criar ou acessar aba gov
    try:
        gov_sheet = sheet.worksheet("gov")
    except gspread.exceptions.WorksheetNotFound:
        gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
        gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
    
    # Configurar formato de data
    configurar_formato_data(sheet, "gov", "A:A")

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
                data_obj = converter_data_para_objeto(data_text_raw)
                
                if data_obj and data_obj.date() == data_desejada.date():
                    titulo_element = noticia.find('h2', class_='titulo')
                    url_noticia = titulo_element.find('a')['href']
                    
                    if url_noticia not in already_scraped_urls:
                        subtitulo_tag = noticia.find('div', class_='subtitulo-noticia')
                        subtitulo = subtitulo_tag.text.strip() if subtitulo_tag else "Subtítulo não disponível"
                        titulo = titulo_element.text.strip()
                        descricao = noticia.find('span', class_='descricao')
                        descricao_text = descricao.text.split('-')[1].strip() if '-' in descricao.text else descricao.text.strip()

                        dados = [
                            data_obj,           # Objeto datetime
                            nome_ministerio,
                            subtitulo,
                            titulo,
                            descricao_text,
                            url_noticia
                        ]

                        gov_sheet.append_row(dados)
                        add_scraped_url(sheet, url_noticia)

        print('Ministério do Esporte: Dados inseridos com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar Ministério do Esporte: {err}")

# =============================================================================
# MINISTÉRIO DA EDUCAÇÃO
# =============================================================================

def raspar_ministerio_educacao(url=None, data_desejada=None):
    """Raspa notícias do Ministério da Educação"""
    if url is None:
        url = "https://www.gov.br/mec/pt-br/assuntos/noticias"
    
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz)
    elif isinstance(data_desejada, str):
        data_desejada = converter_data_para_objeto(data_desejada)

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)
    
    # Criar ou acessar aba gov
    try:
        gov_sheet = sheet.worksheet("gov")
    except gspread.exceptions.WorksheetNotFound:
        gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
        gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
    
    # Configurar formato de data
    configurar_formato_data(sheet, "gov", "A:A")

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
                data_obj = converter_data_para_objeto(data_text_raw)
                
                if data_obj and data_obj.date() == data_desejada.date():
                    titulo_element = noticia.find('h2', class_='titulo')
                    link = titulo_element.find('a')['href']
                    
                    if link not in already_scraped_urls:
                        subtitulo = noticia.find('div', class_='subtitulo-noticia').text.strip()
                        titulo = titulo_element.text.strip()
                        descricao = noticia.find('span', class_='descricao')
                        descricao_text = descricao.text.split('-')[1].strip() if '-' in descricao.text else descricao.text.strip()

                        dados = [
                            data_obj,           # Objeto datetime
                            nome_ministerio,
                            subtitulo,
                            titulo,
                            descricao_text,
                            link
                        ]

                        gov_sheet.append_row(dados)
                        add_scraped_url(sheet, link)

        print('Ministério da Educação: Dados inseridos com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar Ministério da Educação: {err}")

# =============================================================================
# MINISTÉRIO DA SAÚDE
# =============================================================================

def raspar_ministerio_saude(url=None, data_desejada=None):
    """Raspa notícias do Ministério da Saúde"""
    if url is None:
        url = "https://www.gov.br/saude/pt-br/assuntos/noticias"
    
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz)
    elif isinstance(data_desejada, str):
        data_desejada = converter_data_para_objeto(data_desejada)

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)
    
    # Criar ou acessar aba gov
    try:
        gov_sheet = sheet.worksheet("gov")
    except gspread.exceptions.WorksheetNotFound:
        gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
        gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
    
    # Configurar formato de data
    configurar_formato_data(sheet, "gov", "A:A")

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

            data_obj = converter_data_para_objeto(data_raw)
            if data_obj and data_obj.date() == data_desejada.date():
                subt = noticia.find('span', class_='subtitle')
                subtitulo = subt.text.strip() if subt else "Subtítulo não disponível"

                tit = noticia.find('h2', class_='tileHeadline').find('a')
                titulo = tit.text.strip() if tit else "Título não disponível"
                link = tit['href'] if tit else "Link não disponível"

                if link not in already_scraped_urls:
                    desc = noticia.find('span', class_='description')
                    descricao = desc.text.strip() if desc else "Descrição não disponível"

                    gov_sheet.append_row([data_obj, nome_ministerio, subtitulo, titulo, descricao, link])
                    add_scraped_url(sheet, link)

        print('Ministério da Saúde: Dados inseridos com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar Ministério da Saúde: {err}")

# =============================================================================
# MINISTÉRIO DOS POVOS INDÍGENAS
# =============================================================================

def raspar_povos_indigenas(url=None):
    """Raspa notícias do Ministério dos Povos Indígenas"""
    if url is None:
        url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/07"
    
    tz = pytz.timezone('America/Sao_Paulo')
    data_hoje = datetime.now(tz)

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)
    
    # Criar ou acessar aba gov
    try:
        gov_sheet = sheet.worksheet("gov")
    except gspread.exceptions.WorksheetNotFound:
        gov_sheet = sheet.add_worksheet(title="gov", rows="1000", cols="6")
        gov_sheet.append_row(["Data", "Ministério", "Subtítulo", "Título", "Descrição", "Link"])
    
    # Configurar formato de data
    configurar_formato_data(sheet, "gov", "A:A")

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
                data_raw = partes[-1].strip().split()[0]

                data_obj = converter_data_para_objeto(data_raw)
                if data_obj and data_obj.date() == data_hoje.date() and link not in already_scraped_urls:
                    descricao_tag = noticia.find('p', class_='description discreet')
                    descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"

                    sheet.sheet1.append_row([data_obj, nome_ministerio, "Não disponível", titulo, descricao, link])
                    add_scraped_url(sheet, link)

        print('Povos Indígenas: Raspagem concluída com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar Povos Indígenas: {err}")

# =============================================================================
# ANS - AGÊNCIA NACIONAL DE SAÚDE SUPLEMENTAR
# =============================================================================

def raspar_ans(url=None, max_retries=3):
    """Raspa notícias da ANS"""
    if url is None:
        url = 'https://www.gov.br/ans/pt-br/assuntos/noticias'
    
    sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    json_keyfile = 'credentials.json'

    def safe_request(url):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, verify=certifi.where(), timeout=15)
                response.raise_for_status()
                return response
            except ChunkedEncodingError as e:
                print(f"Tentativa {attempt+1}: erro de leitura incompleta - {e}")
            except requests.exceptions.RequestException as e:
                print(f"Tentativa {attempt+1}: erro ao acessar {url} - {e}")
            time.sleep(2)
        return None

    response = safe_request(url)
    if response is None:
        print("Falha ao obter resposta da ANS após múltiplas tentativas.")
        return

    sheet = initialize_sheet_modern(sheet_id, json_keyfile)
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
        data_obj = converter_data_para_objeto(data_raw) if data_raw != 'N/A' else None

        descricao_tag = block.find('span', class_='descricao')
        descricao = 'N/A'
        if descricao_tag:
            full_text = descricao_tag.get_text(strip=True)
            data_text = data_tag.get_text(strip=True) if data_tag else ''
            descricao = full_text.replace(data_text, '').strip()

        data_list.append({
            'Data': data_obj if data_obj else data_raw,
            'Subtítulo': subtitulo,
            'Título': titulo,
            'Descrição': descricao,
            'Link': link
        })

    try:
        worksheet = sheet.worksheet("ans")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title="ans", rows="100", cols="5")

    configurar_formato_data(sheet, "ans", "A:A")

    df = pd.DataFrame(data_list)
    worksheet.clear()
    
    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        print("ANS: Dados inseridos com sucesso.")
    else:
        print("ANS: Nenhum dado novo para inserir.")

# =============================================================================
# CFM - CONSELHO FEDERAL DE MEDICINA
# =============================================================================

def raspar_cfm(url=None):
    """Raspa notícias do CFM"""
    if url is None:
        url = "https://portal.cfm.org.br/noticias/?s="

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)

    try:
        cfm_sheet = sheet.worksheet("cfm")
    except gspread.exceptions.WorksheetNotFound:
        cfm_sheet = sheet.add_worksheet(title="cfm", rows="100", cols="4")
        cfm_sheet.append_row(["Data", "Título", "Descrição", "Link"])

    configurar_formato_data(sheet, "cfm", "A:A")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

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

            date_text = f"{day} {month} {year}".strip()

            description_tag = soup.find('p')
            description = description_tag.text.strip() if description_tag else 'N/A'

            # Tentar converter para datetime se possível
            try:
                if day != 'N/A' and month != 'N/A' and year != 'N/A':
                    # Mapear meses em português
                    meses_map = {
                        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
                        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
                        'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
                    }
                    month_num = meses_map.get(month.lower(), month)
                    date_formatted = f"{day.zfill(2)}/{month_num}/{year}"
                    date_obj = converter_data_para_objeto(date_formatted)
                else:
                    date_obj = date_text
            except:
                date_obj = date_text

            cfm_sheet.append_row([date_obj if date_obj else date_text, title, description, link])
            add_scraped_url(sheet, link)

            print('CFM: Dados inseridos com sucesso.')
        else:
            print(f"CFM: URL já raspada: {link}")

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar CFM: {err}")

# =============================================================================
# FIOCRUZ
# =============================================================================

def raspar_fiocruz():
    """Raspa notícias da Fiocruz"""
    tz = pytz.timezone('America/Sao_Paulo')
    data_desejada = datetime.now(tz)
    url = "https://fiocruz.br/noticias"

    sheet = initialize_sheet()

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
        aba = sheet.add_worksheet(title="fiocruz", rows="100", cols="4")
        aba.append_row(["Data", "Título", "Descrição", "Link"])

    configurar_formato_data(sheet, "fiocruz", "A:A")

    novas_linhas = []
    for bloco in blocos:
        data_tag = bloco.find("div", class_="data-busca")
        if not data_tag:
            continue
        
        data_raw = data_tag.find("time").text.strip()
        data_obj = converter_data_para_objeto(data_raw)
        
        if data_obj and data_obj.date() != data_desejada.date():
            continue

        titulo_tag = bloco.find("div", class_="titulo-busca").find("a")
        titulo = titulo_tag.text.strip()
        link = "https://www.fiocruz.br" + titulo_tag["href"]

        if link in urls_existentes:
            continue

        chamada_tag = bloco.find("div", class_="chamada-busca")
        descricao = chamada_tag.text.strip() if chamada_tag else ""

        novas_linhas.append([data_obj, titulo, descricao, link])
        add_scraped_url(sheet, link)

    if novas_linhas:
        aba.append_rows(novas_linhas)
        print(f"Fiocruz: {len(novas_linhas)} notícia(s) adicionadas.")
    else:
        print("Fiocruz: Nenhuma nova notícia para hoje.")

# =============================================================================
# MINISTÉRIO DA IGUALDADE RACIAL
# =============================================================================

def raspar_igualdade_racial(url=None, data_desejada=None):
    """Raspa notícias do Ministério da Igualdade Racial"""
    if url is None:
        url = "https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias"
    
    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz)
    elif isinstance(data_desejada, str):
        data_desejada = converter_data_para_objeto(data_desejada)

    sheet = initialize_sheet()
    already_scraped_urls = get_already_scraped_urls(sheet)
    
    # Configurar formato de data
    configurar_formato_data(sheet, "Sheet1", "A:A")

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

            data_obj = converter_data_para_objeto(data_raw)
            if not data_obj:
                continue

            descricao_tag = noticia.find('span', class_='descricao')
            descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"

            if data_obj.date() == data_desejada.date() and link not in already_scraped_urls:
                sheet.sheet1.append_row([data_obj, nome_ministerio, categoria, titulo, descricao, link])
                add_scraped_url(sheet, link)

        print('Igualdade Racial: Dados inseridos com sucesso.')

    except requests.exceptions.RequestException as err:
        print(f"Erro ao acessar Igualdade Racial: {err}")

# =============================================================================
# ANVISA
# =============================================================================

def raspar_anvisa():
    """Raspa notícias da Anvisa do dia atual"""
    tz = pytz.timezone('America/Sao_Paulo')
    data_hoje = datetime.now(tz)
    url = 'https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa'
    
    sheet = initialize_sheet()
    
    try:
        anvisa_sheet = sheet.worksheet("anvisa")
    except gspread.exceptions.WorksheetNotFound:
        anvisa_sheet = sheet.add_worksheet(title="anvisa", rows="100", cols="6")
        anvisa_sheet.append_row(["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    configurar_formato_data(sheet, "anvisa", "A:A")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

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
            
            data_obj = converter_data_para_objeto(data_lida)
            if data_obj and data_obj.date() == data_hoje.date():
                anvisa_sheet.append_row([
                    data_obj, "ANVISA", subtitulo, titulo, descricao, link
                ])
                add_scraped_url(sheet, link)

    print("Anvisa: Notícias do dia atual inseridas com sucesso.")

# =============================================================================
# CONSED - CONSELHO NACIONAL DE SECRETÁRIOS DE EDUCAÇÃO
# =============================================================================

def raspar_consed(data_desejada=None, max_pages=5):
    """Raspa notícias do Consed"""
    sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    
    try:
        sheet = initialize_sheet()
        consed_sheet = sheet.worksheet('consed')
    except gspread.exceptions.WorksheetNotFound:
        consed_sheet = sheet.add_worksheet(title='consed', rows="100", cols="4")
        consed_sheet.append_row(["Data", "Título", "Descrição", "Link"])

    configurar_formato_data(sheet, 'consed', "A:A")

    base_url = "https://www.consed.org.br/noticias?page="
    data = []

    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz)
    elif isinstance(data_desejada, str):
        data_desejada = converter_data_para_objeto(data_desejada)

    already_scraped_urls = get_already_scraped_urls(sheet)
    page = 1

    while page <= max_pages:
        url = f"{base_url}{page}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao acessar Consed página {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        news_items = soup.find_all('a', href=True)

        if not news_items:
            break

        for item in news_items:
            title_tag = item.find('h2')
            date_tag = item.find('small')
            description_tag = item.find('p')

            if title_tag and date_tag and description_tag:
                title = title_tag.text.strip()
                date_raw = date_tag.text.strip()
                description = description_tag.text.strip()
                link = item['href']

                date_obj = converter_data_para_objeto(date_raw)
                if date_obj and date_obj.date() == data_desejada.date():
                    full_link = link if link.startswith("http") else f"https://www.consed.org.br{link}"

                    if full_link not in already_scraped_urls:
                        dados = [date_obj, title, description, full_link]
                        data.append(dados)
                        add_scraped_url(sheet, full_link)

        page += 1

    if data:
        consed_sheet.append_rows(data)
        print('Consed: Dados inseridos com sucesso.')
    else:
        print('Consed: Nenhum dado encontrado para a data especificada.')

# =============================================================================
# UNDIME - UNIÃO NACIONAL DOS DIRIGENTES MUNICIPAIS DE EDUCAÇÃO
# =============================================================================

def raspar_undime(data_desejada=None):
    """Raspa notícias da Undime"""
    sheet_id = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    
    try:
        sheet = initialize_sheet()
        undime_sheet = sheet.worksheet('undime')
    except gspread.exceptions.WorksheetNotFound:
        undime_sheet = sheet.add_worksheet(title='undime', rows="100", cols="4")
        undime_sheet.append_row(["Data", "Título", "Descrição", "Link"])

    configurar_formato_data(sheet, 'undime', "A:A")

    if data_desejada is None:
        tz = pytz.timezone('America/Sao_Paulo')
        data_desejada = datetime.now(tz)
    elif isinstance(data_desejada, str):
        data_desejada = converter_data_para_objeto(data_desejada)

    url = "https://undime.org.br/noticia/page/1"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar Undime: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    noticias = soup.find_all('div', class_='noticia mt-4 shadow2 p-3 border-radius')

    datas = []
    titulos = []
    descricoes = []
    links = []

    already_scraped_urls = get_already_scraped_urls(sheet)

    for noticia in noticias:
        link_elem = noticia.find('a', href=True)
        if link_elem:
            link = "https://undime.org.br" + link_elem['href']

            if link in already_scraped_urls:
                continue

            data_match = re.search(r'\d{2}-\d{2}-\d{4}', link)
            if data_match:
                data_str = data_match.group(0)
                data_obj = datetime.strptime(data_str, '%d-%m-%Y')
                
                if data_obj.date() == data_desejada.date():
                    datas.append(data_obj)
                    links.append(link)
                    add_scraped_url(sheet, link)
                else:
                    continue
            else:
                continue
        else:
            continue

        titulo_elem = noticia.find('h4')
        if titulo_elem:
            titulo = titulo_elem.text.strip()
            titulos.append(titulo)
        else:
            titulos.append(None)

        try:
            descricao_elem = noticia.select_one('p.acessibilidade > a')
            descricao = descricao_elem.text.strip() if descricao_elem else None
        except:
            descricao = None
        descricoes.append(descricao)

    dados_noticias = list(zip(datas, titulos, descricoes, links))
    
    if dados_noticias:
        linhas = [[data, titulo, descricao, link] for data, titulo, descricao, link in dados_noticias]
        undime_sheet.append_rows(linhas, value_input_option='USER_ENTERED')
        print('Undime: Dados inseridos com sucesso.')
    else:
        print('Undime: Nenhum dado encontrado para a data especificada.')

# =============================================================================
# FUNÇÃO PRINCIPAL PARA EXECUTAR TODAS AS RASPAGENS
# =============================================================================

def executar_todas_raspagens():
    """Executa todas as raspagens de notícias"""
    print("=== INICIANDO RASPAGEM DE NOTÍCIAS GOVERNAMENTAIS ===\n")
    
    try:
        print("1. Raspando Ministério do Esporte...")
        raspar_ministerio_esporte()
    except Exception as e:
        print(f"Erro na raspagem do Ministério do Esporte: {e}")
    
    try:
        print("\n2. Raspando Ministério da Educação...")
        raspar_ministerio_educacao()
    except Exception as e:
        print(f"Erro na raspagem do Ministério da Educação: {e}")
    
    try:
        print("\n3. Raspando Ministério da Saúde...")
        raspar_ministerio_saude()
    except Exception as e:
        print(f"Erro na raspagem do Ministério da Saúde: {e}")
    
    try:
        print("\n4. Raspando Povos Indígenas...")
        raspar_povos_indigenas()
    except Exception as e:
        print(f"Erro na raspagem dos Povos Indígenas: {e}")
    
    try:
        print("\n5. Raspando ANS...")
        raspar_ans()
    except Exception as e:
        print(f"Erro na raspagem da ANS: {e}")
    
    try:
        print("\n6. Raspando CFM...")
        raspar_cfm()
    except Exception as e:
        print(f"Erro na raspagem do CFM: {e}")
    
    try:
        print("\n7. Raspando Fiocruz...")
        raspar_fiocruz()
    except Exception as e:
        print(f"Erro na raspagem da Fiocruz: {e}")
    
    try:
        print("\n8. Raspando Igualdade Racial...")
        raspar_igualdade_racial()
    except Exception as e:
        print(f"Erro na raspagem da Igualdade Racial: {e}")
    
    try:
        print("\n9. Raspando Anvisa...")
        raspar_anvisa()
    except Exception as e:
        print(f"Erro na raspagem da Anvisa: {e}")
    
    try:
        print("\n10. Raspando Consed...")
        raspar_consed()
    except Exception as e:
        print(f"Erro na raspagem do Consed: {e}")
    
    try:
        print("\n11. Raspando Undime...")
        raspar_undime()
    except Exception as e:
        print(f"Erro na raspagem da Undime: {e}")
    
    print("\n=== RASPAGEM CONCLUÍDA ===")

# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    # Executar todas as raspagens
    executar_todas_raspagens()
    
    # Ou executar individualmente:
    # raspar_ministerio_esporte()
    # raspar_ministerio_educacao()
    # raspar_ministerio_saude()
    # raspar_povos_indigenas()
    # raspar_ans()
    # raspar_cfm()
    # raspar_fiocruz()
    # raspar_igualdade_racial()
    # raspar_anvisa()
    # raspar_consed()
    # raspar_undime()
