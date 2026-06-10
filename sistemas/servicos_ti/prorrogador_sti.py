import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


LOGIN_URL = "https://servicosti.ebserh.gov.br/#/login"
USER_URL_TEMPLATE = "https://servicosti.ebserh.gov.br/#/usuarios/{search_value}"
DATE_INPUT_NAME = "__/__/____"
REPORT_COLUMN_NAME = "relatório"
USER_COLUMN_CANDIDATES = (
    "usuário",
    "usuario",
    "login",
    "rede",
    "REDE",
)
SUPPORTED_EXTENSIONS = (".xlsx")


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
    headers: Sequence[str],
    rows: Sequence[Row]
) -> None:
    validate_spreadsheet_extension(source_spreadsheet_path)
    report_headers = get_report_headers(headers)

    write_xlsx_report(report_path, report_headers, rows)

# Obtém cabeçalhos do relatório.
def get_report_headers(headers: Sequence[str]) -> List[str]:
    report_headers = list(headers)

    if REPORT_COLUMN_NAME not in report_headers:
        report_headers.append(REPORT_COLUMN_NAME)

    return report_headers


# Salva relatório em Excel.
def write_xlsx_report(
    report_path: Path,
    headers: Sequence[str],
    rows: Sequence[Row]
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Relatório"

    worksheet.append(list(headers))

    for row in rows:
        worksheet.append([
            row.get(header, "")
            for header in headers
        ])

    workbook.save(report_path)

# -----------------------------
# Automação Web
# -----------------------------

# Realiza login no sistema.
def login_to_system(page, login: str, password: str) -> None:
    page.goto(
        LOGIN_URL,
        wait_until="networkidle"
    )

    page.get_by_role("textbox").first.fill(login)

    page.locator(
        'input[type="password"]'
    ).fill(password)

    page.get_by_role(
        "button",
        name="Entrar"
    ).click()

    page.wait_for_timeout(3000)


# Prorroga data do usuário.
def process_user(
    page,
    search_value: str,
    expiration_date: str
) -> str:
    user = str(search_value).strip()

    if not user:
        return "Usuário não informado"

    user_url = USER_URL_TEMPLATE.format(search_value=user)

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
    date_input.type(expiration_date)

    update_button.click()
    page.wait_for_timeout(1000)

    return f"Data prorrogada para {expiration_date}"


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
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False
        )
        context = browser.new_context()

        try:
            page = context.new_page()
            login_to_system(page, login, password)

            return process_user(
                page,
                search_value,
                expiration_date
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
    headers, rows = read_spreadsheet(spreadsheet_path)
    user_column = identify_user_column(headers)
    report_path = build_report_path(
        report_directory,
        spreadsheet_path
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False
        )
        context = browser.new_context()

        try:
            page = context.new_page()
            login_to_system(page, login, password)

            for row in rows:
                user_value = row.get(user_column, "")
                user = "" if user_value is None else str(user_value).strip()

                try:
                    row[REPORT_COLUMN_NAME] = process_user(
                        page,
                        user,
                        expiration_date
                    )
                except Exception as exc:
                    row[REPORT_COLUMN_NAME] = f"Erro: {str(exc)}"
        finally:
            context.close()
            browser.close()

    write_report(
        spreadsheet_path,
        report_path,
        headers,
        rows
    )

    return (
        f"Lote finalizado. {len(rows)} usuário(s) processado(s). "
        f"Relatório: {report_path}"
    )
