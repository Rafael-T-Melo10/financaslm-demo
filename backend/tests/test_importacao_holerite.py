from datetime import date

from app.api import routes


def test_reimportar_holerite_nao_duplica_receita_ou_itens(client, monkeypatch):
    credenciais = {"email": "holerite-isolado@teste.com", "senha": "s3nha!"}
    assert client.post("/usuarios", json={"nome": "Holerite", **credenciais}).status_code == 200
    token = client.post("/auth/login", json=credenciais).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    dados = {
        "receitas": [
            {"descricao": "LIQUIDO A RECEBER", "valor": 6326.14, "data": date(2026, 7, 1)},
        ],
        "itens": [
            {"descricao": "SALARIO BASE", "valor": 8000, "tipo": "provento", "data": date(2026, 7, 1)},
            {"descricao": "INSS", "valor": 800, "tipo": "desconto", "data": date(2026, 7, 1)},
        ],
    }
    monkeypatch.setattr(routes, "_extrair_pdf_com_senhas_configuradas", lambda *_args, **_kwargs: dados)

    for esperadas in (1, 0):
        resposta = client.post(
            "/importar/holerite",
            headers=auth_headers,
            files={"file": ("holerite.pdf", b"%PDF-1.4 teste", "application/pdf")},
        )
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["receitas"] == esperadas

    receitas = client.get("/receitas", headers=auth_headers).json()
    assert len(receitas) == 1
    assert receitas[0]["descricao"] == "LIQUIDO A RECEBER"
    from app.database import SessionLocal
    from app import models
    with SessionLocal() as db:
        itens = db.query(models.ReceitaItem).filter_by(receita_id=receitas[0]["id"]).all()
        assert len(itens) == 2
        assert {item.descricao for item in itens} == {"SALARIO BASE", "INSS"}
