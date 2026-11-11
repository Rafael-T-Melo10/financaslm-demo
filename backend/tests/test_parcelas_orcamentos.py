from datetime import date

from dateutil.relativedelta import relativedelta


def _criar_cartao(client, headers):
    return client.post("/cartoes", headers=headers, json={"nome": "Cartão Teste"}).json()["id"]


def test_pagar_parcela_gera_despesa_e_avanca_data(client, auth_headers):
    cartao_id = _criar_cartao(client, auth_headers)
    inicio = date.today().replace(day=15)

    parcela = client.post("/parcelas", headers=auth_headers, json={
        "descricao": "Notebook",
        "valor_total": 3000,
        "total_parcelas": 3,
        "data_inicio": inicio.isoformat(),
        "cartao_id": cartao_id,
    }).json()
    data_proxima_antes = parcela["data_proxima_parcela"]

    paga = client.post(f"/parcelas/{parcela['id']}/pagar", headers=auth_headers)
    assert paga.status_code == 200
    corpo = paga.json()
    assert corpo["parcelas_restantes"] == 2
    assert corpo["pago"] is False

    esperada = (date.fromisoformat(data_proxima_antes) + relativedelta(months=1)).isoformat()
    assert corpo["data_proxima_parcela"] == esperada

    despesas = client.get("/despesas", headers=auth_headers).json()
    geradas = [d for d in despesas if d["origem"] == "parcela" and "Notebook (1/3)" in d["descricao"]]
    assert len(geradas) == 1
    assert float(geradas[0]["valor"]) == 1000.0


def test_pagar_ultima_parcela_quita(client, auth_headers):
    cartao_id = _criar_cartao(client, auth_headers)
    parcela = client.post("/parcelas", headers=auth_headers, json={
        "descricao": "Fone",
        "valor_total": 200,
        "total_parcelas": 1,
        "data_inicio": date.today().isoformat(),
        "cartao_id": cartao_id,
    }).json()

    corpo = client.post(f"/parcelas/{parcela['id']}/pagar", headers=auth_headers).json()
    assert corpo["pago"] is True
    assert corpo["parcelas_restantes"] == 0

    # pagar de novo é erro
    de_novo = client.post(f"/parcelas/{parcela['id']}/pagar", headers=auth_headers)
    assert de_novo.status_code == 400


def test_orcamento_upsert_lista_e_remove(client, auth_headers):
    assert client.put("/orcamentos", headers=auth_headers,
                      json={"categoria": "Alimentação", "limite": 800}).status_code == 200
    # upsert atualiza em vez de duplicar
    assert client.put("/orcamentos", headers=auth_headers,
                      json={"categoria": "Alimentação", "limite": 900}).status_code == 200

    orcamentos = client.get("/orcamentos", headers=auth_headers).json()
    alimentacao = [o for o in orcamentos if o["categoria"] == "Alimentação"]
    assert len(alimentacao) == 1
    assert alimentacao[0]["limite"] == 900

    assert client.delete("/orcamentos/Alimentação", headers=auth_headers).status_code == 204
    restantes = client.get("/orcamentos", headers=auth_headers).json()
    assert not any(o["categoria"] == "Alimentação" for o in restantes)


def test_orcamento_limite_invalido(client, auth_headers):
    resposta = client.put("/orcamentos", headers=auth_headers,
                          json={"categoria": "Lazer", "limite": 0})
    assert resposta.status_code == 400


def test_orcamento_exige_token(client):
    assert client.get("/orcamentos").status_code == 401
