import csv
import io
from datetime import date


def test_exportar_despesas_csv(client, auth_headers):
    client.post("/despesas", headers=auth_headers, json={
        "descricao": "Mercadão", "valor": 250.75, "categoria": "Alimentação", "data": "2026-07-03",
    })

    resposta = client.get("/exportar/despesas", headers=auth_headers, params={"mes": 7, "ano": 2026})
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/csv")
    assert "attachment" in resposta.headers["content-disposition"]

    texto = resposta.text.lstrip("﻿")
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert linhas[0] == ["Data", "Descrição", "Categoria", "Valor", "Origem"]
    assert any(linha[1] == "Mercadão" for linha in linhas[1:])


def test_exportar_receitas_csv(client, auth_headers):
    client.post("/receitas", headers=auth_headers, json={
        "descricao": "Salário", "valor": 5000, "data": "2026-07-05",
    })

    resposta = client.get("/exportar/receitas", headers=auth_headers)
    assert resposta.status_code == 200
    texto = resposta.text.lstrip("﻿")
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert linhas[0] == ["Data", "Descrição", "Valor", "Origem"]
    assert any(linha[1] == "Salário" for linha in linhas[1:])


def test_exportar_faturas_csv_vazio_ainda_retorna_cabecalho(client, auth_headers):
    resposta = client.get("/exportar/faturas", headers=auth_headers)
    assert resposta.status_code == 200
    texto = resposta.text.lstrip("﻿")
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert linhas[0] == ["Data", "Descrição", "Categoria", "Valor", "Cartão", "Estabelecimento"]


def test_exportar_respeita_ownership(client, auth_headers):
    client.post("/despesas", headers=auth_headers, json={
        "descricao": "Privada", "valor": 10, "categoria": "Outros", "data": date.today().isoformat(),
    })

    client.post("/usuarios", json={"nome": "Outro", "email": "outroexport@t.com", "senha": "x"})
    login = client.post("/auth/login", json={"email": "outroexport@t.com", "senha": "x"})
    headers_outro = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resposta = client.get("/exportar/despesas", headers=headers_outro)
    texto = resposta.text.lstrip("﻿")
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert not any(linha and linha[1] == "Privada" for linha in linhas[1:])


def test_exportar_exige_token(client):
    assert client.get("/exportar/despesas").status_code == 401
