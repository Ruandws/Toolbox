from cadastro_pessoa_aghu import CadastroPessoaEntrada


def pessoa_valida(**sobrescritas):
    dados = {
        "nome_pessoa": "Joao Silva",
        "nome_mae": "Maria Silva",
        "sexo": "Masculino",
        "data_nascimento": "01/01/1990",
        "nacionalidade": "Brasileira",
        "naturalidade": "Brasilia/DF",
        "rg": "123456",
        "orgao_emissor": "SSP",
        "uf_rg": "DF",
        "cpf": "123.456.789-01",
        "ddd": "61",
        "telefone_celular": "999999999",
        "cep_cadastrado": "70000-000",
        "logradouro_nao_cadastrado": "Rua A",
        "bairro_nao_cadastrado": "Centro",
        "cep_nao_cadastrado": "71000-000",
        "municipio_nao_cadastrado": "Brasilia",
    }
    dados.update(sobrescritas)
    return CadastroPessoaEntrada(**dados)


class PageFake:
    def __init__(self):
        self.fechada = False
        self.goto_url = None

    def close(self):
        self.fechada = True

    def goto(self, url):
        self.goto_url = url


class ContextFake:
    def __init__(self):
        self.page = PageFake()

    def new_page(self):
        return self.page


FakePage = PageFake
FakeContext = ContextFake
