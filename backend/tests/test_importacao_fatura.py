from datetime import date

from app.api import routes


def _criar_cartao(client, auth_headers, nome):
    resposta = client.post(
        "/cartoes",
        headers=auth_headers,
        json={
            "nome": nome,
            "bandeira": "Visa",
            "ultimos_digitos": "1234",
            "limite": 12000,
            "data_vencimento": 10,
        },
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_importar_fatura_nao_expoe_erro_interno(client, auth_headers, monkeypatch):
    def falhar(*_args, **_kwargs):
        raise RuntimeError("segredo-interno")

    monkeypatch.setattr(routes, "extrair_dados_pdf", falhar)
    cartao = _criar_cartao(client, auth_headers, "Cartao Erro Sanitizado")

    resposta = client.post(
        f"/importar/fatura?cartao_id={cartao['id']}",
        headers=auth_headers,
        files={"file": ("fatura.pdf", b"%PDF-1.4 teste", "application/pdf")},
    )

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == "Não foi possível processar o arquivo. Tente novamente."
    assert "segredo-interno" not in resposta.text


def test_importar_fatura_persiste_competencia_pelo_mes_das_compras(client, auth_headers, monkeypatch):
    def fake_extrair_dados_pdf(*_args, **_kwargs):
        return {
            "total_fatura": 3074.34,
            "informacoes_fatura": {"vencimento": date(2026, 7, 10)},
            "despesas": [
                {"descricao": "Compra maio", "valor": 118.94, "categoria": "Saude", "data": date(2026, 5, 25)},
                {"descricao": "Compra junho 1", "valor": 704.09, "categoria": "Outros", "data": date(2026, 6, 4)},
                {"descricao": "Compra junho 2", "valor": 2251.31, "categoria": "Alimentação", "data": date(2026, 6, 15)},
            ],
            "parcelas_futuras": [],
        }

    monkeypatch.setattr(routes, "extrair_dados_pdf", fake_extrair_dados_pdf)
    cartao = _criar_cartao(client, auth_headers, "Cartao Competencia Junho")

    resposta = client.post(
        f"/importar/fatura?cartao_id={cartao['id']}",
        headers=auth_headers,
        files={"file": ("fatura.pdf", b"%PDF-1.4 teste", "application/pdf")},
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    fatura_id = corpo["fatura"]["id"]

    assert corpo["fatura"]["data_referencia"] == "2026-06-01"

    faturas_junho = client.get("/faturas", headers=auth_headers, params={"mes": 6, "ano": 2026}).json()
    assert any(item["id"] == fatura_id and item["data_referencia"] == "2026-06-01" for item in faturas_junho)

    faturas_julho = client.get("/faturas", headers=auth_headers, params={"mes": 7, "ano": 2026}).json()
    assert all(item["id"] != fatura_id for item in faturas_julho)

    despesas_junho = client.get("/despesas", headers=auth_headers, params={"mes": 6, "ano": 2026}).json()
    assert any(
        item["descricao"] == "Fatura do cartão"
        and item["origem"] == "fatura"
        and item["data"] == "2026-06-01"
        for item in despesas_junho
    )


def test_importar_fatura_sem_datas_validas_cai_no_mes_do_vencimento(client, auth_headers, monkeypatch):
    def fake_extrair_dados_pdf(*_args, **_kwargs):
        return {
            "total_fatura": 490.50,
            "informacoes_fatura": {"vencimento": date(2026, 7, 10)},
            "despesas": [
                {"descricao": "Compra sem data", "valor": 490.50, "categoria": "Outros", "data": None},
            ],
            "parcelas_futuras": [],
        }

    monkeypatch.setattr(routes, "extrair_dados_pdf", fake_extrair_dados_pdf)
    cartao = _criar_cartao(client, auth_headers, "Cartao Competencia Vencimento")

    resposta = client.post(
        f"/importar/fatura?cartao_id={cartao['id']}",
        headers=auth_headers,
        files={"file": ("fatura.pdf", b"%PDF-1.4 teste", "application/pdf")},
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()

    assert corpo["fatura"]["data_referencia"] == "2026-07-01"

    despesas_julho = client.get("/despesas", headers=auth_headers, params={"mes": 7, "ano": 2026}).json()
    assert any(
        item["descricao"] == "Fatura do cartão"
        and item["origem"] == "fatura"
        and item["data"] == "2026-07-01"
        for item in despesas_julho
    )


def test_importar_fatura_atualiza_e_quita_parcelas_que_nao_aparecem_mais(client, auth_headers, monkeypatch):
    faturas = [
        {
            "total_fatura": 500,
            "informacoes_fatura": {"vencimento": date(2026, 7, 10)},
            "despesas": [{"descricao": "Compra junho", "valor": 500, "categoria": "Outros", "data": date(2026, 6, 20)}],
            "parcelas_futuras": [
                {"descricao": "Notebook 01/03", "valor_parcela": 100, "valor_total": 300, "parcelas_restantes": 3, "total_parcelas": 3, "data_inicio": date(2026, 6, 20), "data_proxima_parcela": date(2026, 8, 10)},
                {"descricao": "Fone 01/01", "valor_parcela": 50, "valor_total": 50, "parcelas_restantes": 1, "total_parcelas": 1, "data_inicio": date(2026, 6, 20), "data_proxima_parcela": date(2026, 8, 10)},
            ],
        },
        {
            "total_fatura": 600,
            "informacoes_fatura": {"vencimento": date(2026, 8, 10)},
            "despesas": [{"descricao": "Compra julho", "valor": 600, "categoria": "Outros", "data": date(2026, 7, 20)}],
            "parcelas_futuras": [
                {"descricao": "Notebook 02/03", "valor_parcela": 100, "valor_total": 200, "parcelas_restantes": 2, "total_parcelas": 3, "data_inicio": date(2026, 6, 20), "data_proxima_parcela": date(2026, 9, 10)},
            ],
        },
    ]

    monkeypatch.setattr(routes, "extrair_dados_pdf", lambda *_args, **_kwargs: faturas.pop(0))
    cartao = _criar_cartao(client, auth_headers, "Cartao Parcelas Atualizadas")

    for _ in range(2):
        resposta = client.post(
            f"/importar/fatura?cartao_id={cartao['id']}", headers=auth_headers,
            files={"file": ("fatura.pdf", b"%PDF-1.4 teste", "application/pdf")},
        )
        assert resposta.status_code == 200, resposta.text

    ativas = client.get("/parcelas", headers=auth_headers).json()
    assert len(ativas) == 1
    assert ativas[0]["descricao"] == "Notebook 02/03"
    assert ativas[0]["parcelas_restantes"] == 2
    assert ativas[0]["data_proxima_parcela"] == "2026-09-10"

    todas = client.get("/parcelas", headers=auth_headers, params={"apenas_ativas": False}).json()
    fone = next(parcela for parcela in todas if parcela["descricao"] == "Fone 01/01")
    assert fone["pago"] is True
    assert fone["parcelas_restantes"] == 0
