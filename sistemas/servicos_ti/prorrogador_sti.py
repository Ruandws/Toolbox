import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

from openpyxl import Workbook, load_workbook
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

#Constantes globais de acesso
LOGIN_URL = "https://servicosti.ebserh.gov.br/#/login"
USER_URL_TEMPLATE = "https://servicosti.ebserh.gov.br/#/usuarios/{search_value}"

#Constantes globais de validação de acesso (login)
LOGIN_BUTTON_TEXT = "Entrar"
LOGIN_PASSWORD_SELECTOR = 'input[type="password"]'
PAGE_READY_TIMEOUT_MS = 15000
LOGIN_COMPLETION_TIMEOUT_MS = 10000
LOGIN_COMPLETION_POLL_INTERVAL_MS = 150
LOGIN_FAILED_WARNING_SELECTOR = (
    "[role='alert'], "
    ".alert, "
    ".alert-danger, "
    ".alert-warning, "
    ".toast, "
    ".toast-error, "
    ".toast-message, "
    ".swal2-popup"
)
LOGIN_FAILED_WARNING_PATTERN = re.compile(
    r"("
    r"login|entrar|autentic|credenc|usuario|usuário|senha"
    r").{0,80}("
    r"falh|inval|invál|incorret|negad|bloquead|expirad"
    r")|("
    r"falh|inval|invál|incorret|negad|bloquead|expirad"
    r").{0,80}("
    r"login|entrar|autentic|credenc|usuario|usuário|senha"
    r")",
    re.IGNORECASE,
)

#Constantes globais de data
DATE_INPUT_NAME = "__/__/____"
EXPIRATION_DATE_FORMAT = "%d/%m/%Y"
EXPIRATION_DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")

#Constantes globais de relatórios
REPORT_COLUMN_USER = "usuário"
REPORT_COLUMN_NAME = "relatório"
REPORT_HEADERS = (REPORT_COLUMN_USER,REPORT_COLUMN_NAME,)
USER_COLUMN_CANDIDATES = ("usuário","usuario","login","rede","REDE",)

#Constantes globais de usuários
USER_LOGIN_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9._@'-]+$")
USER_URL_SAFE_CHARS = "._@-'"
BATCH_ENTRY_PREPARED_USER = "_prepared_user"

#Constantes globais de planilha
SUPPORTED_EXTENSIONS = (".xlsx",)
Row = Dict[str, Any]


# -----------------------------
# Planilha / relatório
# -----------------------------

# Normaliza nome de coluna.
def normalize_column_name(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return text.lower()


# Identifica coluna de usuários.
def identify_user_column(headers: Sequence[str]) -> str:
    normalized_candidates = {
        normalize_column_name(candidate)
        for candidate in USER_COLUMN_CANDIDATES
    }

    for header in headers:
        if normalize_column_name(header) in normalized_candidates:
            return header

    expected_columns = ", ".join(USER_COLUMN_CANDIDATES)
    raise ValueError(
        "Coluna de usuários não encontrada. "
        f"A planilha deve conter uma destas colunas: {expected_columns}."
    )


# Gera nome do relatório.
def generate_report_filename(
    extension: str,
    now: Optional[datetime] = None
) -> str:
    reference_date = now or datetime.now()
    clean_extension = extension.lower().strip()

    if not clean_extension.startswith("."):
        clean_extension = f".{clean_extension}"

    timestamp = reference_date.strftime("%d_%m_%y_%Hh%M")

    return f"Resultado_{timestamp}{clean_extension}"


# Constrói caminho do relatório.
def build_report_path(
    report_directory: str,
    source_spreadsheet_path: str,
    now: Optional[datetime] = None
) -> Path:
    report_dir = Path(report_directory).expanduser()

    if not report_dir.exists():
        raise FileNotFoundError(
            f"A pasta de relatório não existe: {report_dir}"
        )

    if not report_dir.is_dir():
        raise NotADirectoryError(
            f"O caminho de relatório não é uma pasta: {report_dir}"
        )

    extension = validate_spreadsheet_extension(source_spreadsheet_path)
    filename = generate_report_filename(extension, now)
    report_path = report_dir / filename

    return get_available_report_path(report_path)


# Obtém caminho disponível.
def get_available_report_path(report_path: Path) -> Path:
    if not report_path.exists():
        return report_path

    counter = 2
    stem = report_path.stem
    suffix = report_path.suffix
    parent = report_path.parent

    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"

        if not candidate.exists():
            return candidate

        counter += 1


# Valida extensão da planilha.
def validate_spreadsheet_extension(spreadsheet_path: str) -> str:
    extension = Path(spreadsheet_path).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        raise ValueError(
            f"Formato de planilha não suportado: {extension}. "
            f"Use apenas: {supported}."
        )

    return extension


# Lê dados da planilha.
def read_spreadsheet(spreadsheet_path: str) -> Tuple[List[str], List[Row]]:
    source_path = Path(spreadsheet_path).expanduser()

    if not source_path.exists():
        raise FileNotFoundError(
            f"Planilha não encontrada: {source_path}"
        )

    validate_spreadsheet_extension(str(source_path))

    return read_xlsx(source_path)


# Lê arquivo Excel.
def read_xlsx(source_path: Path) -> Tuple[List[str], List[Row]]:
    workbook = load_workbook(source_path, data_only=True)
    worksheet = workbook.active

    if worksheet is None:
        raise ValueError("A planilha não possui aba ativa.")

    raw_headers = [
        cell.value
        for cell in next(worksheet.iter_rows(min_row=1, max_row=1))
    ]
    headers = make_unique_headers(raw_headers)
    rows: List[Row] = []

    for raw_row in worksheet.iter_rows(min_row=2, values_only=True):
        if is_empty_row(raw_row):
            continue

        row = build_row(headers, raw_row)
        rows.append(row)

    return headers, rows

# Garante cabeçalhos únicos.
def make_unique_headers(raw_headers: Sequence[Any]) -> List[str]:
    if not raw_headers:
        raise ValueError("A planilha não possui cabeçalho.")

    headers: List[str] = []
    seen: Dict[str, int] = {}

    for index, raw_header in enumerate(raw_headers, start=1):
        header = "" if raw_header is None else str(raw_header).strip()

        if not header:
            header = f"coluna_{index}"

        if header in seen:
            seen[header] += 1
            header = f"{header}_{seen[header]}"
        else:
            seen[header] = 1

        headers.append(header)

    return headers


# Constrói linha de dados.
def build_row(headers: Sequence[str], raw_row: Sequence[Any]) -> Row:
    row: Row = {}

    for index, header in enumerate(headers):
        row[header] = raw_row[index] if index < len(raw_row) else ""

    return row


# Verifica linha vazia.
def is_empty_row(raw_row: Sequence[Any]) -> bool:
    return all(
        value is None or str(value).strip() == ""
        for value in raw_row
    )


# Salva relatório em arquivo.
def write_report(
    source_spreadsheet_path: str,
    report_path: Path,
    rows: Sequence[Row]
) -> None:
    validate_spreadsheet_extension(source_spreadsheet_path)
    report_headers = get_report_headers()

    write_xlsx_report(report_path, report_headers, rows)

# Obtém cabeçalhos do relatório.
def get_report_headers() -> List[str]:
    return list(REPORT_HEADERS)

# Constrói linha limpa do relatório.
def build_report_row(user: Any, report: Any) -> Row:
    clean_user = "" if user is None else str(user).strip()
    clean_report = "" if report is None else str(report).strip()

    return {
        REPORT_COLUMN_USER: clean_user,
        REPORT_COLUMN_NAME: clean_report,
    }


# Salva relatório em Excel.
def write_xlsx_report(
    report_path: Path,
    headers: Sequence[str],
    rows: Sequence[Row]
) -> None:
    workbook = Workbook()
    worksheet = workbook.active

    if worksheet is None:
        raise ValueError("A planilha não possui aba ativa.")
    worksheet.title = "Relatório"

    worksheet.append(list(headers))

    for row in rows:
        worksheet.append([
            row.get(header, "")
            for header in headers
        ])

    workbook.save(report_path)

# -----------------------------
# Login alvo / validação
# -----------------------------

# Normaliza valor de usuário vindo da UI ou planilha.
def normalize_user_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


# Prepara usuário para execução individual.
def prepare_user_value(user_value: Any) -> str:
    if isinstance(user_value, bool):
        raise ValueError(
            "Usuário inválido: valor booleano não é aceito."
        )

    user = normalize_user_value(user_value)

    if not user:
        raise ValueError("Usuário não informado.")

    if any(char.isspace() for char in user):
        raise ValueError(
            "Usuário inválido: não use espaços."
        )

    if not USER_LOGIN_ALLOWED_PATTERN.fullmatch(user):
        raise ValueError(
            "Usuário inválido: use apenas letras, números, ponto, "
            "hífen, sublinhado, @ ou apóstrofo."
        )

    return user


# Prepara usuário para execução em lote.
def prepare_batch_user_value(user_value: Any) -> str:
    return prepare_user_value(user_value)


# Monta URL segura para usuário já validado/preparado.
def build_user_url(prepared_user_value: str) -> str:
    encoded_user = quote(
        prepared_user_value,
        safe=USER_URL_SAFE_CHARS
    )

    return USER_URL_TEMPLATE.format(
        search_value=encoded_user
    )

# -----------------------------
# Data / validação
# -----------------------------

# Normaliza e valida a nova data de expiração.
def normalize_expiration_date(value: Any) -> str:
    if value is None:
        raise ValueError("Nova data não informada.")

    if isinstance(value, bool):
        raise ValueError("Nova data inválida: valor booleano não é aceito.")

    if isinstance(value, datetime):
        return value.strftime(EXPIRATION_DATE_FORMAT)

    if isinstance(value, date):
        return value.strftime(EXPIRATION_DATE_FORMAT)

    text = str(value).strip()

    text = str(value).strip()

    if not text:
        raise ValueError("Nova data não informada.")

    digits = "".join(
        char for char in text
        if char.isdigit()
    )

    if text.isdigit() and len(text) == 8:
        text = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"

    if not EXPIRATION_DATE_PATTERN.fullmatch(text):
        raise ValueError(
            "Nova data inválida: use o formato dd/mm/aaaa."
        )

    try:
        parsed_date = datetime.strptime(
            text,
            EXPIRATION_DATE_FORMAT
        )
    except ValueError as exc:
        raise ValueError(
            "Nova data inválida: informe uma data real no formato dd/mm/aaaa."
        ) from exc

    return parsed_date.strftime(EXPIRATION_DATE_FORMAT)   

# -----------------------------
# Autenticação
# -----------------------------

# Obtém locator do campo de login.
def get_login_textbox_locator(page):
    return page.get_by_role("textbox").first


# Obtém locator do campo de senha do login.
def get_login_password_locator(page):
    return page.locator(LOGIN_PASSWORD_SELECTOR)


# Aguarda a tela de login carregar após DOMContentLoaded.
def wait_for_login_page_ready(page) -> None:
    get_login_textbox_locator(page).wait_for(
        state="visible",
        timeout=PAGE_READY_TIMEOUT_MS
    )
    get_login_password_locator(page).wait_for(
        state="visible",
        timeout=PAGE_READY_TIMEOUT_MS
    )


# Obtém locator do aviso de falha no login.
def get_login_failed_warning_locator(page):
    return page.locator(LOGIN_FAILED_WARNING_SELECTOR).filter(
        has_text=LOGIN_FAILED_WARNING_PATTERN
    )


# Extrai texto visível do aviso de falha no login.
def get_visible_login_failed_warning_text(page) -> Optional[str]:
    warnings = get_login_failed_warning_locator(page)

    for index in range(warnings.count()):
        warning = warnings.nth(index)

        if warning.is_visible():
            return " ".join(
                warning.inner_text(timeout=500).split()
            )

    return None


# Aguarda o login concluir sem usar espera fixa.
def wait_for_login_completion(page) -> None:
    deadline = time.monotonic() + (
        LOGIN_COMPLETION_TIMEOUT_MS / 1000
    )

    while time.monotonic() < deadline:
        failed_warning_text = get_visible_login_failed_warning_text(page)

        if failed_warning_text:
            raise RuntimeError(
                "Login falhou: aviso de falha detectado. "
                f"Mensagem do sistema: {failed_warning_text}"
            )

        if not get_login_password_locator(page).is_visible():
            return

        page.wait_for_timeout(LOGIN_COMPLETION_POLL_INTERVAL_MS)

    raise RuntimeError(
        "Login não concluído no tempo esperado. "
        "Verifique as credenciais, a disponibilidade do sistema "
        "ou mudança no fluxo de autenticação."
    )


# Realiza login no sistema.
def login_to_system(page, login: str, password: str) -> None:
    page.goto(
        LOGIN_URL,
        wait_until="domcontentloaded"
    )

    wait_for_login_page_ready(page)

    get_login_textbox_locator(page).fill(login)
    get_login_password_locator(page).fill(password)

    page.get_by_role(
        "button",
        name=LOGIN_BUTTON_TEXT
    ).click()

    wait_for_login_completion(page)

# Prorroga data do usuário validando/preparando o valor internamente.
def process_user(
    page,
    search_value: str,
    expiration_date: str
) -> str:
    prepared_user = prepare_user_value(search_value)
    normalized_expiration_date = normalize_expiration_date(expiration_date)

    return process_user_prepared_value(
        page,
        prepared_user,
        normalized_expiration_date
    )


# Prorroga data usando usuário já validado/preparado.
def process_user_prepared_value(
    page,
    prepared_user_value: str,
    expiration_date: str
) -> str:
    user = "" if prepared_user_value is None else str(
        prepared_user_value
    ).strip()

    if not user:
        raise ValueError("Usuário preparado não informado.")

    normalized_expiration_date = normalize_expiration_date(expiration_date)
    user_url = build_user_url(user)

    page.goto(
        user_url,
        wait_until="networkidle"
    )

    page.wait_for_timeout(3000)

    date_input = page.get_by_role(
        "textbox",
        name=DATE_INPUT_NAME
    ).first

    update_button = page.get_by_role(
        "button",
        name="Atualizar dados"
    )

    try:
        date_input.wait_for(
            state="visible",
            timeout=5000
        )
        update_button.wait_for(
            state="visible",
            timeout=5000
        )
    except PlaywrightTimeoutError:
        return "Usuário não Encontrado"

    date_input.click()
    page.keyboard.press("Escape")
    date_input.press("ControlOrMeta+A")
    date_input.fill("")
    date_input.type(normalized_expiration_date)

    update_button.click()
    page.wait_for_timeout(1000)

    return f"Data prorrogada para {normalized_expiration_date}"

# -----------------------------
# Entry points
# -----------------------------

# Executa automação individual.
def run_automation(
    login: str,
    password: str,
    search_value: str,
    expiration_date: str
) -> str:
    prepared_user = prepare_user_value(search_value)
    normalized_expiration_date = normalize_expiration_date(expiration_date)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False
        )
        context = browser.new_context()

        try:
            page = context.new_page()
            login_to_system(page, login, password)

            return process_user_prepared_value(
                page,
                prepared_user,
                normalized_expiration_date
            )
        finally:
            context.close()
            browser.close()


# Executa automação em lote.
def run_batch_automation(
    login: str,
    password: str,
    spreadsheet_path: str,
    report_directory: str,
    expiration_date: str
) -> str:
    normalized_expiration_date = normalize_expiration_date(expiration_date)

    headers, source_rows = read_spreadsheet(spreadsheet_path)
    user_column = identify_user_column(headers)
    report_path = build_report_path(
        report_directory,
        spreadsheet_path
    )

    batch_rows: List[Row] = []

    for source_row in source_rows:
        user_value = source_row.get(user_column, "")
        report_user = normalize_user_value(user_value)

        batch_row: Row = {
            REPORT_COLUMN_USER: report_user,
            REPORT_COLUMN_NAME: "",
            BATCH_ENTRY_PREPARED_USER: "",
        }

        try:
            prepared_user = prepare_batch_user_value(user_value)
            batch_row[REPORT_COLUMN_USER] = prepared_user
            batch_row[BATCH_ENTRY_PREPARED_USER] = prepared_user
        except ValueError as exc:
            batch_row[REPORT_COLUMN_NAME] = f"Erro: {str(exc)}"

        batch_rows.append(batch_row)

    has_prepared_rows = any(
        row.get(BATCH_ENTRY_PREPARED_USER)
        for row in batch_rows
    )

    if has_prepared_rows:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False
            )
            context = browser.new_context()

            try:
                page = context.new_page()
                login_to_system(page, login, password)

                for batch_row in batch_rows:
                    prepared_user = batch_row.get(
                        BATCH_ENTRY_PREPARED_USER,
                        ""
                    )

                    if not prepared_user:
                        continue

                    try:
                        report_message = process_user_prepared_value(
                            page,
                            prepared_user,
                            normalized_expiration_date
                        )
                    except Exception as exc:
                        report_message = f"Erro: {str(exc)}"

                    batch_row[REPORT_COLUMN_NAME] = report_message
            finally:
                context.close()
                browser.close()

    report_rows = [
        build_report_row(
            row.get(REPORT_COLUMN_USER, ""),
            row.get(REPORT_COLUMN_NAME, "")
        )
        for row in batch_rows
    ]

    write_report(
        spreadsheet_path,
        report_path,
        report_rows
    )

    return (
        f"Lote finalizado. {len(report_rows)} usuário(s) processado(s). "
        f"Relatório: {report_path}"
    )