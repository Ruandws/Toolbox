"""Configuração compartilhada dos launchers servicos_ti (specs do PyInstaller).

Este módulo não referencia símbolos do PyInstaller (Analysis/EXE/PYZ/COLLECT)
porque estes só existem no namespace do arquivo .spec executado diretamente
pelo PyInstaller — um módulo importado normalmente não os recebe. Por isso,
aqui ficam apenas os dados/kwargs comuns; as chamadas Analysis()/EXE()/
COLLECT() continuam no .spec, mas usando a configuração montada aqui.
"""
import os
from pathlib import Path

LAUNCHERS = [
    {
        "nome": "Prorrogador",
        "entry": "ui_prorrogador.py",
        "icone": "prorrogador.ico",
        "descricao": "Prorrogador STI - Prorrogação de Usuário",
    },
    {
        "nome": "Consultor",
        "entry": "ui_consultor.py",
        "icone": "consultor.ico",
        "descricao": "Consultor STI - Consulta de Usuário",
    },
]

_VERSAO_PADRAO = "0.0.0.0"


def _versao_windows() -> str:
    """Versão no formato W.X.Y.Z exigido pelo VERSIONINFO do Windows."""
    versao = os.environ.get("LAUNCHER_VERSION", _VERSAO_PADRAO).strip()
    partes = (versao.split(".") + ["0", "0", "0", "0"])[:4]
    return ".".join(parte if parte.isdigit() else "0" for parte in partes)


def analysis_kwargs(raiz: Path, cfg: dict) -> dict:
    """Kwargs comuns de Analysis() para um launcher servicos_ti."""
    app_dir = raiz / "sistemas" / "servicos_ti"

    return {
        "scripts": [str(app_dir / cfg["entry"])],
        "pathex": [str(app_dir)],
        "binaries": [],
        "datas": [],
        "hiddenimports": [],
        "hookspath": [],
        "hooksconfig": {},
        "runtime_hooks": [],
        "excludes": [],
        "noarchive": False,
    }


def gerar_version_info(launcher_dir: Path, cfg: dict) -> str:
    """Gera o arquivo de VERSIONINFO do Windows (nome, versão, editor) e retorna seu caminho.

    A versão vem da variável de ambiente LAUNCHER_VERSION (definida pelo CI a
    partir da tag do release); localmente, sem a variável, usa 0.0.0.0.
    """
    versao = _versao_windows()
    versao_tupla = ", ".join(versao.split("."))
    destino = launcher_dir / "build" / "version_info" / f"{cfg['nome'].lower()}.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)

    conteudo = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({versao_tupla}),
    prodvers=({versao_tupla}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Extrator2'),
        StringStruct(u'FileDescription', u'{cfg["descricao"]}'),
        StringStruct(u'FileVersion', u'{versao}'),
        StringStruct(u'InternalName', u'{cfg["nome"]}'),
        StringStruct(u'OriginalFilename', u'{cfg["nome"]}.exe'),
        StringStruct(u'ProductName', u'Extrator2 - Serviços TI'),
        StringStruct(u'ProductVersion', u'{versao}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    destino.write_text(conteudo, encoding="utf-8")
    return str(destino)


def exe_kwargs(launcher_dir: Path, cfg: dict) -> dict:
    """Kwargs comuns de EXE() para um launcher servicos_ti."""
    return {
        "exclude_binaries": True,
        "name": cfg["nome"],
        "icon": str(launcher_dir / "icons" / cfg["icone"]),
        "console": False,
        "version": gerar_version_info(launcher_dir, cfg),
    }
