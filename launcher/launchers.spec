# -*- mode: python ; coding: utf-8 -*-
"""Spec único do PyInstaller para os launchers servicos_ti.

Prorrogador e Consultor são empacotados num único COLLECT (pasta "ServicosTI"),
compartilhando o mesmo _internal (runtime Python, Playwright, customtkinter e,
quando presente, o Chromium embutido em ms-playwright/). Isso elimina a
duplicação de ~150-300MB de dependências que existia com dois builds
separados. Para adicionar uma nova automação, basta um novo item em
LAUNCHERS (launcher/_spec_common.py) — não é preciso criar outro .spec.

O driver do Playwright é coletado automaticamente pelo hook que o próprio
pacote `playwright` registra junto ao PyInstaller; não precisa de `datas`
manual aqui.
"""
import sys
from pathlib import Path

LAUNCHER_DIR = Path(SPECPATH).resolve()  # noqa: F821 - injetado pelo PyInstaller
RAIZ = LAUNCHER_DIR.parent

sys.path.insert(0, str(LAUNCHER_DIR))
from _spec_common import LAUNCHERS, analysis_kwargs, exe_kwargs  # noqa: E402

analises = []
executaveis = []

for cfg in LAUNCHERS:
    analise = Analysis(**analysis_kwargs(RAIZ, cfg))  # noqa: F821
    pyz = PYZ(analise.pure)  # noqa: F821
    exe = EXE(pyz, analise.scripts, [], **exe_kwargs(LAUNCHER_DIR, cfg))  # noqa: F821
    analises.append(analise)
    executaveis.append(exe)

argumentos_collect = []
for analise, exe in zip(analises, executaveis):
    argumentos_collect.extend([exe, analise.binaries, analise.datas])

coll = COLLECT(*argumentos_collect, name="ServicosTI")  # noqa: F821
