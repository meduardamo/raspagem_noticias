from utils import initialize_sheet
from ministerios import (
    processar_esporte, processar_mec, processar_saude,
    processar_povos_indigenas, processar_igualdade,
)
from instituicoes import (
    processar_fiocruz, raspar_noticias_ans, raspar_noticias_undime,
    raspar_noticias_consed, raspar_anvisa_do_dia, scrape_cfm_news
)

if __name__ == "__main__":
    sheet = initialize_sheet()

    processar_esporte(sheet, "https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte")
    processar_mec(sheet, "https://www.gov.br/mec/pt-br/assuntos/noticias")
    processar_saude(sheet, "https://www.gov.br/saude/pt-br/assuntos/noticias")
    processar_povos_indigenas(sheet, "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/06-1")
    processar_igualdade(sheet, "https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias")

    # Instituições
    processar_fiocruz(sheet)
    raspar_noticias_ans(sheet)
    raspar_noticias_consed(sheet)
    raspar_noticias_undime(sheet)
    raspar_anvisa_do_dia(sheet)
    scrape_cfm_news("https://portal.cfm.org.br/noticias/?s=", sheet)

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import urllib3
from datetime import datetime
import pytz

# CFM

# Suprimir avisos de requisição insegura
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Mapeamento dos meses em inglês
MESES_EN = {
    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
    'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
}

def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
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

def scrape_cfm_news(url, sheet):
    headers = {'User-Agent': 'Mozilla/5.0'}
    data_list = []

    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        already_scraped_urls = get_already_scraped_urls(sheet)

        # Captura do título
        title_tag = soup.find('h3')
        title = title_tag.text.strip() if title_tag else 'N/A'

        # Captura do link
        link_tag = soup.find('a', class_='c-default', href=True)
        link = link_tag['href'] if link_tag else 'N/A'

        if link in already_scraped_urls:
            print(f"🔁 URL já raspada: {link}")
            return

        # Captura da data no formato: <h3>dia</h3> e <div>mês<br>ano</div>
        date_div = soup.find('div', class_='noticia-date')
        day_tag = date_div.find('h3') if date_div else None
        month_year_div = date_div.find('div') if date_div else None

        day = day_tag.text.strip().zfill(2) if day_tag else '01'

        if month_year_div:
            parts = list(month_year_div.stripped_strings)
            if len(parts) >= 2:
                month_abbr = parts[0][:3].capitalize()
                month = MESES_EN.get(month_abbr, '01')
                year = parts[1].strip()
            else:
                month, year = '01', '2025'
        else:
            month, year = '01', '2025'

        # Cria datetime com hora zerada
        tz = pytz.timezone("America/Sao_Paulo")
        data_dt = datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y")
        hoje_dt = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

        if data_dt.date() != hoje_dt.date():
            print(f"📌 Notícia ignorada – data diferente de hoje: {data_dt.strftime('%d/%m/%Y')}")
            return

        # Captura da descrição
        description_tag = soup.find('p')
        description = description_tag.text.strip() if description_tag else 'N/A'

        # Envia como datetime
        data_completa = datetime.combine(data_dt.date(), datetime.min.time())
        data_list.append([data_completa, title, description, link])

        worksheet = sheet.worksheet("cfm")
        worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
        add_scraped_url(sheet, link)

        print(f"✅ Notícia do dia inserida: {data_dt.strftime('%d/%m/%Y')} | {title}")

    except requests.exceptions.RequestException as err:
        print(f"❌ Erro na requisição: {err}")

# Executar
if __name__ == "__main__":
    sheet = initialize_sheet()
    url = "https://portal.cfm.org.br/noticias/?s="
    scrape_cfm_news(url, sheet)

import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

def initialize_sheet(sheet_id, aba_nome):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).worksheet(aba_nome)

def get_or_create_url_sheet(sheet):
    try:
        return sheet.spreadsheet.worksheet("URLs")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.spreadsheet.add_worksheet(title="URLs", rows="1", cols="1")
        ws.append_row(["URLs"])
        return ws

def get_already_scraped_urls(sheet):
    url_sheet = get_or_create_url_sheet(sheet)
    return set(url_sheet.col_values(1)[1:])  # Ignora cabeçalho

def add_scraped_url(sheet, url):
    url_sheet = get_or_create_url_sheet(sheet)
    url_sheet.append_row([url])

def raspar_noticias_consed(sheet, data_desejada=None, max_pages=5):
    base_url = "https://www.consed.org.br/noticias?page="
    tz = pytz.timezone('America/Sao_Paulo')

    if not data_desejada:
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")

    urls_lidas = get_already_scraped_urls(sheet)
    novas_linhas = []
    page = 1

    while page <= max_pages:
        url = f"{base_url}{page}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro ao acessar a página {url}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        noticias = soup.find_all('a', href=True)

        if not noticias:
            break

        for item in noticias:
            titulo_tag = item.find('h2')
            data_tag = item.find('small')
            descricao_tag = item.find('p')

            if not (titulo_tag and data_tag and descricao_tag):
                continue

            titulo = titulo_tag.text.strip()
            descricao = descricao_tag.text.strip()
            data_raw = data_tag.text.strip()
            link = item['href']
            full_link = link if link.startswith("http") else f"https://www.consed.org.br{link}"

            try:
                data_dt = datetime.strptime(data_raw, "%d/%m/%Y")
                data_fmt = data_dt.strftime("%d/%m/%Y")
            except ValueError:
                continue

            if data_fmt != data_desejada or full_link in urls_lidas:
                continue

            # 🔧 Corrigido: data como datetime.datetime com hora zerada
            data_completa = datetime.combine(data_dt.date(), datetime.min.time())

            novas_linhas.append([data_completa, titulo, descricao, full_link])
            add_scraped_url(sheet, full_link)

        page += 1

    if novas_linhas:
        sheet.append_rows(novas_linhas, value_input_option='USER_ENTERED')
        print(f"✅ {len(novas_linhas)} notícia(s) adicionada(s) da Consed.")
    else:
        print("ℹ️ Nenhuma nova notícia do Consed para hoje.")

# --- Execução ---
if __name__ == "__main__":
    SHEET_ID = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    aba = 'consed'
    sheet = initialize_sheet(SHEET_ID, aba)
    raspar_noticias_consed(sheet)

import re
import pytz
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

def initialize_sheet(sheet_id):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)

def get_or_create_worksheet(sheet, name, headers=None):
    try:
        ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="100", cols="20")
        if headers:
            ws.append_row(headers)
    return ws

def get_already_scraped_urls(sheet):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    return set(urls_sheet.col_values(1)[1:])  # ignora o cabeçalho

def add_scraped_url(sheet, url):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    urls_sheet.append_row([url])

def raspar_noticias_undime(sheet, data_desejada=None):
    tz = pytz.timezone('America/Sao_Paulo')
    if data_desejada is None:
        data_desejada = datetime.now(tz).strftime('%d/%m/%Y')

    url = "https://undime.org.br/noticia/page/1"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar o site: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    noticias = soup.find_all('div', class_='noticia mt-4 shadow2 p-3 border-radius')
    urls_ja_lidas = get_already_scraped_urls(sheet)
    undime_sheet = get_or_create_worksheet(sheet, "undime", headers=["Data", "Título", "Descrição", "URL"])

    novas_linhas = []

    for noticia in noticias:
        # LINK e data no link
        link_tag = noticia.find('a', href=True)
        if not link_tag:
            continue

        link = "https://undime.org.br" + link_tag['href']
        if link in urls_ja_lidas:
            continue

        data_match = re.search(r'\d{2}-\d{2}-\d{4}', link)
        if not data_match:
            continue

        try:
            data_dt = datetime.strptime(data_match.group(), '%d-%m-%Y')
            data_fmt = data_dt.strftime('%d/%m/%Y')
        except ValueError:
            continue

        if data_fmt != data_desejada:
            continue

        # Título
        titulo_tag = noticia.find('h4')
        titulo = titulo_tag.text.strip() if titulo_tag else "Título não disponível"

        # Descrição
        try:
            descricao_tag = noticia.select_one('p.acessibilidade > a')
            descricao = descricao_tag.text.strip() if descricao_tag else "Descrição não disponível"
        except:
            descricao = "Descrição não disponível"

        # 🔧 Corrigido: data como datetime.datetime com hora zerada
        data_completa = datetime.combine(data_dt.date(), datetime.min.time())

        novas_linhas.append([data_completa, titulo, descricao, link])
        add_scraped_url(sheet, link)

    if novas_linhas:
        undime_sheet.append_rows(novas_linhas, value_input_option='USER_ENTERED')
        print(f"✅ {len(novas_linhas)} notícia(s) adicionada(s) da Undime.")
    else:
        print("ℹ️ Nenhuma nova notícia da Undime para hoje.")

# ------------------------------
# Execução
if __name__ == "__main__":
    SHEET_ID = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    sheet = initialize_sheet(SHEET_ID)
    raspar_noticias_undime(sheet)

import requests
import gspread
import pytz
from bs4 import BeautifulSoup
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

def initialize_sheet(sheet_id):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)

def get_or_create_worksheet(sheet, name, headers=None):
    try:
        ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="100", cols="20")
        if headers:
            ws.append_row(headers)
    return ws

def get_already_scraped_urls(sheet):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    return set(urls_sheet.col_values(1)[1:])  # Ignora cabeçalho

def add_scraped_url(sheet, url):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    urls_sheet.append_row([url])

def raspar_noticias_ans(sheet, data_desejada=None):
    tz = pytz.timezone('America/Sao_Paulo')
    if data_desejada is None:
        data_desejada = datetime.now(tz).strftime("%d/%m/%Y")

    url = "https://www.gov.br/ans/pt-br/assuntos/noticias"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar {url}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    noticias = soup.find_all('div', class_='conteudo')
    urls_ja_lidas = get_already_scraped_urls(sheet)
    ans_sheet = get_or_create_worksheet(sheet, "ans", headers=["Data", "Ministério", "Subtítulo", "Título", "Link"])

    novas_linhas = []

    for noticia in noticias:
        try:
            subtitulo_tag = noticia.find('div', class_='subtitulo-noticia')
            subtitulo = subtitulo_tag.text.strip() if subtitulo_tag else "Subtítulo não disponível"

            titulo_tag = noticia.find('a', href=True)
            titulo = titulo_tag.text.strip() if titulo_tag else "Título não disponível"
            link = titulo_tag['href'] if titulo_tag else "Link não disponível"

            data_tag = noticia.find('span', class_='data')
            data_raw = data_tag.text.strip() if data_tag else None

            if not data_raw or not link or link in urls_ja_lidas:
                continue

            try:
                data_dt_bruta = datetime.strptime(data_raw, '%d/%m/%Y')
                data_completa = datetime.combine(data_dt_bruta.date(), datetime.min.time())
            except ValueError:
                continue

            if data_completa.strftime('%d/%m/%Y') != data_desejada:
                continue

            linha = [data_completa, "ANS", subtitulo, titulo, link]
            novas_linhas.append(linha)
            add_scraped_url(sheet, link)

        except Exception as e:
            print(f"Erro ao processar notícia: {e}")
            continue

    if novas_linhas:
        ans_sheet.append_rows(novas_linhas, value_input_option='USER_ENTERED')
        print(f"✅ {len(novas_linhas)} notícia(s) da ANS adicionada(s).")
    else:
        print("ℹ️ Nenhuma nova notícia da ANS para hoje.")

# ------------------------------
# Execução
if __name__ == "__main__":
    SHEET_ID = '1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY'
    sheet = initialize_sheet(SHEET_ID)
    raspar_noticias_ans(sheet)

# ANVISA

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import urllib3
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Suprimir avisos SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Inicializar planilha
def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key('1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY')

# Obter ou criar aba de URLs
def get_or_create_worksheet(sheet, name, headers=None):
    try:
        ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="100", cols="20")
        if headers:
            ws.append_row(headers)
    return ws

# URLs já raspadas
def get_already_scraped_urls(sheet):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    return set(urls_sheet.col_values(1)[1:])

def add_scraped_url(sheet, url):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    urls_sheet.append_row([url])

# Função principal de raspagem
def raspar_anvisa_do_dia(sheet):
    tz = pytz.timezone('America/Sao_Paulo')
    data_hoje = datetime.now(tz).date()
    data_hoje_str = data_hoje.strftime("%d/%m/%Y")

    url = 'https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar a Anvisa: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    noticias = soup.select('ul.noticias.listagem-noticias-com-foto > li')
    urls_existentes = get_already_scraped_urls(sheet)
    aba_anvisa = get_or_create_worksheet(sheet, "anvisa", headers=["Data", "Ministério", "Subtítulo", "Título", "Descrição", "URL"])

    novas_linhas = []

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
        if not descricao_tag:
            continue

        descricao_completa = descricao_tag.text.strip()
        partes = descricao_completa.split('-')
        data_lida_str = partes[0].strip()
        descricao = partes[1].strip() if len(partes) > 1 else descricao_completa

        try:
            data_dt = datetime.strptime(data_lida_str, "%d/%m/%Y").date()
        except ValueError:
            continue

        if data_dt != data_hoje:
            continue

        data_completa = datetime.combine(data_dt, datetime.min.time())
        linha = [data_completa, "ANVISA", subtitulo, titulo, descricao, link]
        novas_linhas.append(linha)
        add_scraped_url(sheet, link)

    if novas_linhas:
        aba_anvisa.append_rows(novas_linhas, value_input_option='USER_ENTERED')
        print(f"✅ {len(novas_linhas)} notícia(s) da ANVISA adicionada(s).")
    else:
        print("ℹ️ Nenhuma nova notícia da ANVISA para hoje.")

# Executar
if __name__ == "__main__":
    sheet = initialize_sheet()
    raspar_anvisa_do_dia(sheet)

import requests
import gspread
import pytz
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from utils import (
    initialize_sheet,
    get_or_create_worksheet,
    get_already_scraped_urls,
    add_scraped_url,
    hoje_brasil_dt  # retorna datetime com hora zerada
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def processar_fiocruz(sheet, url="https://fiocruz.br/noticias"):
    gov_sheet = get_or_create_worksheet(sheet, "fiocruz", headers=["Data", "Título", "Descrição", "URL"])
    urls_ja = get_already_scraped_urls(sheet)
    tz = pytz.timezone("America/Sao_Paulo")
    hoje = datetime.now(tz).date()
    hoje_str = hoje.strftime("%d/%m/%Y")

    resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    blocos = soup.select("div.views-row")
    novas = []

    for b in blocos:
        time_tag = b.find("div", class_="data-busca")
        text_data = time_tag.find("time").text.strip() if time_tag else ""
        if text_data != hoje_str:
            continue

        a = b.select_one("div.titulo-busca a")
        if not a: continue
        link = a["href"]
        link = link if link.startswith("http") else "https://www.fiocruz.br" + link
        if link in urls_ja:
            continue

        titulo = a.text.strip()
        desc_tag = b.find("div", class_="chamada-busca")
        descricao = desc_tag.text.strip() if desc_tag else ""
        data_dt = datetime.combine(hoje, datetime.min.time())

        novas.append([data_dt, titulo, descricao, link])
        add_scraped_url(sheet, link)

    if novas:
        gov_sheet.append_rows(novas, value_input_option="USER_ENTERED")
        print(f"✅ {len(novas)} notícia(s) da Fiocruz adicionadas.")
    else:
        print("ℹ️ Nenhuma notícia nova da Fiocruz hoje.")
