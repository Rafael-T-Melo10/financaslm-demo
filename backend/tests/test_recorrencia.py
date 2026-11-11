from datetime import date

from dateutil.relativedelta import relativedelta

from app.services.recorrencia import gerar_despesas_pendentes
from app import models


def _criar_recorrente(client, headers, **overrides):
    payload = {
        "descricao": "Netflix",
        "valor": 39.90,
        "categoria": "Assinaturas",
        "dia_vencimento": 10,
        "data_inicio": (date.today() - relativedelta(months=1)).isoformat(),
    }
    payload.update(overrides)
    return client.post("/despesas-recorrentes", headers=headers, json=payload).json()


def test_crud_despesa_recorrente(client, auth_headers):
    criada = _criar_recorrente(client, auth_headers)
    assert criada["ativo"] is True
    assert criada["ultima_geracao"] is None

    listadas = client.get("/despesas-recorrentes", headers=auth_headers).json()
    assert any(r["id"] == criada["id"] for r in listadas)

    atualizada = client.put(f"/despesas-recorrentes/{criada['id']}", headers=auth_headers, json={
        "valor": 45.90, "ativo": False,
    })
    assert atualizada.status_code == 200
    assert atualizada.json()["valor"] == 45.90
    assert atualizada.json()["ativo"] is False

    assert client.delete(f"/despesas-recorrentes/{criada['id']}", headers=auth_headers).status_code == 204


def test_listar_gera_despesa_do_mes_uma_unica_vez(client, auth_headers):
    _criar_recorrente(client, auth_headers, descricao="Aluguel", valor=1500, dia_vencimento=5)

    # primeira listagem: gera a despesa do mês
    client.get("/despesas-recorrentes", headers=auth_headers)
    despesas = client.get("/despesas", headers=auth_headers).json()
    geradas = [d for d in despesas if d["origem"] == "recorrente" and d["descricao"] == "Aluguel"]
    assert len(geradas) == 1

    # segunda listagem no mesmo mês: não duplica
    client.get("/despesas-recorrentes", headers=auth_headers)
    despesas = client.get("/despesas", headers=auth_headers).json()
    geradas = [d for d in despesas if d["origem"] == "recorrente" and d["descricao"] == "Aluguel"]
    assert len(geradas) == 1


def test_recorrente_pausada_nao_gera(client, auth_headers):
    criada = _criar_recorrente(client, auth_headers, descricao="Academia", ativo=False)
    client.put(f"/despesas-recorrentes/{criada['id']}", headers=auth_headers, json={"ativo": False})

    client.get("/despesas-recorrentes", headers=auth_headers)
    despesas = client.get("/despesas", headers=auth_headers).json()
    assert not any(d["descricao"] == "Academia" and d["origem"] == "recorrente" for d in despesas)


def test_recorrente_futura_nao_gera_ainda(client, auth_headers):
    _criar_recorrente(
        client, auth_headers, descricao="Plano Futuro",
        data_inicio=(date.today() + relativedelta(months=1)).isoformat(),
    )

    client.get("/despesas-recorrentes", headers=auth_headers)
    despesas = client.get("/despesas", headers=auth_headers).json()
    assert not any(d["descricao"] == "Plano Futuro" for d in despesas)


def test_dia_vencimento_fora_do_intervalo_da_422(client, auth_headers):
    # dia_vencimento é limitado a 1-28 no schema (Field ge=1, le=28): datas como 29/30/31
    # não existem em todo mês, então o teto evita o caso "cai no mês errado".
    invalido = client.post("/despesas-recorrentes", headers=auth_headers, json={
        "descricao": "Invalida", "valor": 10, "categoria": "Outros",
        "dia_vencimento": 31, "data_inicio": date.today().isoformat(),
    })
    assert invalido.status_code == 422


def test_gerar_despesas_pendentes_usa_o_dia_configurado(client, auth_headers):
    _criar_recorrente(client, auth_headers, descricao="Conta Fixa", dia_vencimento=28)
    client.get("/despesas-recorrentes", headers=auth_headers)

    despesas = client.get("/despesas", headers=auth_headers).json()
    gerada = next(d for d in despesas if d["descricao"] == "Conta Fixa")
    assert gerada["data"].endswith("-28")


def test_gerar_despesas_pendentes_e_idempotente_chamando_o_servico_direto(client, auth_headers):
    """Chama o serviço diretamente (sem passar pela rota) para provar a idempotência do gate por mês."""
    from app.database import SessionLocal

    criada = _criar_recorrente(client, auth_headers, descricao="Serviço Direto", dia_vencimento=15)

    db = SessionLocal()
    usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()

    primeira = gerar_despesas_pendentes(db, usuario.id)
    segunda = gerar_despesas_pendentes(db, usuario.id)
    db.close()

    assert primeira == 1
    assert segunda == 0


def test_recorrente_exige_token(client):
    assert client.get("/despesas-recorrentes").status_code == 401
