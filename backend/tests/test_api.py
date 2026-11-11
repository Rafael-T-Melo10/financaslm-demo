def test_cadastro_nao_vaza_senha(client):
    resposta = client.post("/usuarios", json={"nome": "A", "email": "a@t.com", "senha": "x"})
    assert resposta.status_code == 200
    assert "senha" not in resposta.json()


def test_email_duplicado(client):
    client.post("/usuarios", json={"nome": "B", "email": "dup@t.com", "senha": "x"})
    resposta = client.post("/usuarios", json={"nome": "B2", "email": "dup@t.com", "senha": "y"})
    assert resposta.status_code == 400


def test_login_senha_errada(client, auth_headers):
    resposta = client.post("/auth/login", json={"email": "teste@t.com", "senha": "errada"})
    assert resposta.status_code == 401


def test_rotas_exigem_token(client):
    for rota in ["/despesas", "/receitas", "/cartoes", "/parcelas", "/faturas", "/analise", "/alertas"]:
        assert client.get(rota).status_code == 401, rota


def test_crud_despesa(client, auth_headers):
    criada = client.post("/despesas", headers=auth_headers, json={
        "descricao": "Mercado", "valor": 123.45, "categoria": "Alimentação", "data": "2026-07-01",
    })
    assert criada.status_code == 200
    despesa_id = criada.json()["id"]

    listadas = client.get("/despesas", headers=auth_headers, params={"mes": 7, "ano": 2026}).json()
    assert any(item["id"] == despesa_id for item in listadas)

    assert client.delete(f"/despesas/{despesa_id}", headers=auth_headers).status_code == 204


def test_mes_sem_ano_da_422(client, auth_headers):
    resposta = client.get("/despesas", headers=auth_headers, params={"mes": 7})
    assert resposta.status_code == 422


def test_usuario_nao_acessa_dados_de_outro(client, auth_headers):
    despesa_id = client.post("/despesas", headers=auth_headers, json={
        "descricao": "Privada", "valor": 10, "categoria": "Outros", "data": "2026-07-02",
    }).json()["id"]

    client.post("/usuarios", json={"nome": "Intruso", "email": "intruso@t.com", "senha": "i"})
    login = client.post("/auth/login", json={"email": "intruso@t.com", "senha": "i"})
    headers_intruso = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/despesas", headers=headers_intruso).json() == []
    assert client.delete(f"/despesas/{despesa_id}", headers=headers_intruso).status_code == 404
    assert client.put(f"/despesas/{despesa_id}", headers=headers_intruso, json={"valor": 1}).status_code == 404

    # dono ainda vê e consegue apagar
    assert client.delete(f"/despesas/{despesa_id}", headers=auth_headers).status_code == 204


def test_alertas(client, auth_headers):
    resposta = client.get("/alertas", headers=auth_headers)
    assert resposta.status_code == 200
    assert "alertas" in resposta.json()
