import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import urllib3

# Suprimir avisos SSL inseguros
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Inicializa a planilha pelo ID
def initialize_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key('1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY')

# Retorna ou cria uma worksheet com cabeçalhos
def get_or_create_worksheet(sheet, name, headers=None):
    try:
        ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="100", cols="20")
        if headers:
            ws.append_row(headers)
    return ws

# Busca a aba de URLs já raspadas (ou cria)
def get_already_scraped_urls(sheet):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    return set(urls_sheet.col_values(1)[1:])  # ignora cabeçalho

# Adiciona uma nova URL à aba de controle
def add_scraped_url(sheet, url):
    urls_sheet = get_or_create_worksheet(sheet, "URLs", headers=["URLs"])
    urls_sheet.append_row([url])

# Data de hoje como string (formato brasileiro)
def hoje_brasil_str():
    return datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y")

# Data de hoje como datetime.datetime sem tzinfo e com hora zerada
def hoje_brasil_dt():
    tz = pytz.timezone('America/Sao_Paulo')
    hoje = datetime.now(tz).date()  # tipo date
    return datetime.combine(hoje, datetime.min.time())  # datetime sem fuso
