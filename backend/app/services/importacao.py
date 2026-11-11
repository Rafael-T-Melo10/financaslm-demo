import json
import re
from collections import Counter
from datetime import date, datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app import models
from app.services import classificacao as classificacao_service


def coerce_date(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor[:10])
        except ValueError:
            return None
    return None


def competencia_fatura(compras: list, vencimento: date | None) -> date:
    """Determina o mês de referência da fatura pelo mês mais frequente entre as
    datas das compras. O vencimento (mês seguinte ao fechamento, tipicamente)
    não representa o mês em que as compras foram feitas — usá-lo direto fazia a
    fatura ser contabilizada no mês errado quando ela fecha perto da virada."""
    meses_compras = []
    for compra in compras or []:
        valor_data = compra.get("data") if isinstance(compra, dict) else compra
        data_compra = coerce_date(valor_data)
        if data_compra:
            meses_compras.append(data_compra.replace(day=1))
    if meses_compras:
        mes_mais_frequente, _ = Counter(meses_compras).most_common(1)[0]
        return mes_mais_frequente

    vencimento_normalizado = coerce_date(vencimento)
    if vencimento_normalizado:
        return vencimento_normalizado.replace(day=1)

    return date.today().replace(day=1)


def normalizar_info_fatura(informacoes):
    resultado = {}
    for chave, valor in (informacoes or {}).items():
        if isinstance(valor, (date, datetime)):
            resultado[chave] = valor.isoformat()
        else:
            resultado[chave] = valor
    return resultado


def serializar_fatura(fatura: models.Fatura):
    return {
        "id": fatura.id,
        "usuario_id": fatura.usuario_id,
        "cartao_id": fatura.cartao_id,
        "despesa_id": fatura.despesa_id,
        "descricao": fatura.descricao,
        "valor_total": fatura.valor_total,
        "vencimento": fatura.vencimento,
        "data_referencia": fatura.data_referencia,
        "informacoes_fatura": json.loads(fatura.informacoes_json or "{}"),
        "itens": [
            {
                "id": item.id,
                "descricao": item.descricao,
                "valor": item.valor,
                "categoria": item.categoria,
                "data": item.data,
                "estabelecimento": item.estabelecimento,
            }
            for item in sorted(fatura.itens, key=lambda item: item.data)
        ],
        "data_criacao": fatura.data_criacao,
    }


def remover_faturas_importadas_existentes(
    db: Session,
    usuario_id: int,
    cartao_id: int,
    valor_total: float,
    vencimento: date | None,
    data_referencia: date,
):
    """Remove importações anteriores da mesma fatura antes de recriar."""
    query = db.query(models.Fatura).filter(
        models.Fatura.usuario_id == usuario_id,
        models.Fatura.cartao_id == cartao_id,
        models.Fatura.valor_total == valor_total,
    )

    if vencimento:
        query = query.filter(models.Fatura.vencimento == vencimento)
    else:
        query = query.filter(models.Fatura.data_referencia == data_referencia)

    faturas_existentes = query.all()
    despesa_ids = [fatura.despesa_id for fatura in faturas_existentes if fatura.despesa_id]

    for fatura in faturas_existentes:
        db.delete(fatura)

    if faturas_existentes:
        db.flush()

    if despesa_ids:
        db.query(models.Despesa).filter(
            models.Despesa.id.in_(despesa_ids),
            models.Despesa.usuario_id == usuario_id,
            models.Despesa.origem == "fatura",
        ).delete(synchronize_session=False)


_CHAVES_DATA = {"data", "vencimento", "data_inicio", "data_proxima_parcela", "emissao"}


def desserializar_dados_extraidos(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Converte de volta para date os campos de data que passaram por um
    round-trip JSON (ex: dados extraídos guardados em ImportacaoPendente).
    O parser sempre devolve objetos date nativos; só quem lê um JSON salvo
    (fila de revisão) precisa desta normalização antes de persistir."""

    def _normalizar(valor):
        if isinstance(valor, dict):
            return {
                chave: (coerce_date(sub) if chave in _CHAVES_DATA and isinstance(sub, str) else _normalizar(sub))
                for chave, sub in valor.items()
            }
        if isinstance(valor, list):
            return [_normalizar(item) for item in valor]
        return valor

    return _normalizar(dados)


class ImportacaoError(Exception):
    """Erro de negócio ao persistir dados extraídos de um PDF (mapeia para HTTP 400/404)."""

    def __init__(self, mensagem: str, status_code: int = 400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status_code = status_code


def chave_parcela_importada(descricao: str, valor_parcela, total_parcelas: int) -> tuple[str, float, int]:
    """Cria uma chave estável para a parcela mostrada nas faturas.

    O emissor altera apenas o sufixo ``01/03`` para ``02/03`` a cada mês.
    Esse sufixo não pode fazer a mesma compra virar uma nova parcela local.
    """
    descricao_base = re.sub(r"\s+(?<!\d)\d{2}/\d{2}(?!\d)", "", descricao or "").strip().upper()
    return descricao_base, float(valor_parcela), int(total_parcelas)


def persistir_holerite(db: Session, usuario: models.Usuario, dados: Dict[str, Any]) -> Dict[str, Any]:
    itens_por_competencia: Dict[Any, list] = {}
    for item_data in dados.get("itens", []):
        itens_por_competencia.setdefault(item_data["data"], []).append(item_data)

    receitas_extraidas = dados.get("receitas", [])
    receitas_importadas = 0
    for receita_data in receitas_extraidas:
        existente = db.query(models.Receita.id).filter(
            models.Receita.usuario_id == usuario.id,
            models.Receita.descricao == receita_data["descricao"],
            models.Receita.valor == receita_data["valor"],
            models.Receita.data == receita_data["data"],
            models.Receita.origem == "holerite",
        ).first()
        if existente:
            continue

        receita = models.Receita(
            usuario_id=usuario.id,
            descricao=receita_data["descricao"],
            valor=receita_data["valor"],
            data=receita_data["data"],
            origem="holerite"
        )
        db.add(receita)
        db.flush()

        for item_data in itens_por_competencia.get(receita_data["data"], []):
            db.add(models.ReceitaItem(
                receita_id=receita.id,
                descricao=item_data["descricao"],
                valor=item_data["valor"],
                tipo=item_data["tipo"],
            ))

        receitas_importadas += 1

    db.commit()

    if not receitas_extraidas:
        raise ImportacaoError("Não foi possível extrair receitas deste PDF. Verifique se é um holerite suportado.")

    return {"mensagem": "Holerite importado com sucesso", "receitas": receitas_importadas}


def persistir_fatura(db: Session, usuario: models.Usuario, cartao_id: int, dados: Dict[str, Any]) -> Dict[str, Any]:
    total_fatura = dados.get("total_fatura")
    informacoes_fatura = dados.get("informacoes_fatura", {})
    compras = dados.get("despesas", [])
    parcelas_futuras = dados.get("parcelas_futuras", [])

    if dados.get("erro"):
        raise ImportacaoError(dados["erro"])

    if total_fatura is None or not compras:
        raise ImportacaoError("Não foi possível encontrar uma fatura de cartão válida neste PDF.")

    for compra in compras:
        compra["categoria"] = classificacao_service.classificar(
            db, usuario.id, compra.get("descricao", ""), compra.get("categoria"), compra.get("estabelecimento")
        )

    vencimento = coerce_date(informacoes_fatura.get("vencimento"))
    data_referencia = competencia_fatura(compras, vencimento)

    cartao = db.query(models.CartaoCredito).filter(
        models.CartaoCredito.id == cartao_id,
        models.CartaoCredito.usuario_id == usuario.id,
    ).first()
    if not cartao:
        raise ImportacaoError("Cartão não encontrado", status_code=404)

    remover_faturas_importadas_existentes(
        db=db,
        usuario_id=usuario.id,
        cartao_id=cartao_id,
        valor_total=total_fatura,
        vencimento=vencimento,
        data_referencia=data_referencia,
    )

    if informacoes_fatura.get("limite_total_utilizado") is not None:
        cartao.saldo_usado = informacoes_fatura["limite_total_utilizado"]

    despesa = models.Despesa(
        usuario_id=usuario.id,
        cartao_id=cartao_id,
        descricao="Fatura do cartão",
        valor=total_fatura,
        categoria="Cartão de Crédito",
        data=data_referencia,
        origem="fatura"
    )
    db.add(despesa)
    db.flush()

    fatura = models.Fatura(
        usuario_id=usuario.id,
        cartao_id=cartao_id,
        despesa_id=despesa.id,
        descricao="Fatura do cartão",
        valor_total=total_fatura,
        vencimento=vencimento,
        data_referencia=data_referencia,
        informacoes_json=json.dumps(normalizar_info_fatura(informacoes_fatura), ensure_ascii=False),
    )
    db.add(fatura)
    db.flush()

    for compra in compras:
        item = models.FaturaItem(
            fatura_id=fatura.id,
            descricao=compra.get("descricao", "Compra"),
            valor=compra.get("valor", 0),
            categoria=compra.get("categoria", "Outros"),
            data=compra.get("data") or data_referencia,
            estabelecimento=compra.get("estabelecimento"),
        )
        db.add(item)

    parcelas_ativas = db.query(models.Parcela).filter(
        models.Parcela.usuario_id == usuario.id,
        models.Parcela.cartao_id == cartao_id,
        models.Parcela.pago == False,
    ).order_by(models.Parcela.id).all()
    parcelas_por_chave = {}
    for parcela in parcelas_ativas:
        # Parcelas criadas manualmente não têm o indicador 01/03 da fatura e
        # não devem ser quitadas por uma importação automática.
        if not re.search(r"(?<!\d)\d{2}/\d{2}(?!\d)", parcela.descricao or ""):
            continue
        chave = chave_parcela_importada(
            parcela.descricao, parcela.valor_parcela, parcela.total_parcelas
        )
        parcelas_por_chave.setdefault(chave, []).append(parcela)

    chaves_na_fatura = set()
    parcelas_importadas = 0
    for parcela_data in parcelas_futuras:
        chave = chave_parcela_importada(
            parcela_data["descricao"], parcela_data["valor_parcela"], parcela_data["total_parcelas"]
        )
        chaves_na_fatura.add(chave)
        existentes = parcelas_por_chave.get(chave, [])
        existente = existentes.pop(0) if existentes else None

        if existente:
            existente.descricao = parcela_data["descricao"]
            existente.valor_total = parcela_data["valor_total"]
            existente.parcelas_restantes = parcela_data["parcelas_restantes"]
            existente.total_parcelas = parcela_data["total_parcelas"]
            existente.data_inicio = parcela_data["data_inicio"]
            existente.data_proxima_parcela = parcela_data["data_proxima_parcela"]
            existente.pago = False
        else:
            db.add(models.Parcela(
                usuario_id=usuario.id,
                cartao_id=cartao_id,
                descricao=parcela_data["descricao"],
                valor_total=parcela_data["valor_total"],
                parcelas_restantes=parcela_data["parcelas_restantes"],
                total_parcelas=parcela_data["total_parcelas"],
                valor_parcela=parcela_data["valor_parcela"],
                data_inicio=parcela_data["data_inicio"],
                data_proxima_parcela=parcela_data["data_proxima_parcela"],
                pago=False,
            ))
        parcelas_importadas += 1

    # A seção "compras parceladas - próximas faturas" é uma fotografia das
    # parcelas que ainda faltam. As importadas anteriormente e ausentes nesta
    # fatura foram concluídas; mantém-se intacta qualquer parcela manual.
    for chave, parcelas in parcelas_por_chave.items():
        if chave not in chaves_na_fatura:
            for parcela in parcelas:
                parcela.parcelas_restantes = 0
                parcela.pago = True
        else:
            # Corrige duplicatas criadas pelas versões que usavam 01/03 como
            # parte da identidade da compra.
            for parcela in parcelas:
                parcela.pago = True

    db.commit()
    db.refresh(fatura)
    return {
        "mensagem": "Fatura importada com sucesso",
        "total_fatura": total_fatura,
        "compras_importadas": len(compras),
        "parcelas_importadas": parcelas_importadas,
        "informacoes_fatura": normalizar_info_fatura(informacoes_fatura),
        "fatura": serializar_fatura(fatura)
    }


def persistir_conta(db: Session, usuario: models.Usuario, dados: Dict[str, Any]) -> Dict[str, Any]:
    if dados.get("erro"):
        raise ImportacaoError(dados["erro"])

    despesas = dados.get("despesas", [])
    if not despesas:
        raise ImportacaoError("Não foi possível encontrar uma conta suportada neste PDF.")

    despesas_criadas = []
    chaves_processadas = set()
    for despesa_data in despesas:
        categoria = classificacao_service.classificar(
            db, usuario.id, despesa_data["descricao"], despesa_data.get("categoria", "Moradia")
        )
        chave = (
            despesa_data["data"],
            despesa_data["descricao"],
            despesa_data["valor"],
            categoria,
        )
        if chave in chaves_processadas:
            continue

        despesa_existente = db.query(models.Despesa.id).filter(
            models.Despesa.usuario_id == usuario.id,
            models.Despesa.data == despesa_data["data"],
            models.Despesa.descricao == despesa_data["descricao"],
            models.Despesa.valor == despesa_data["valor"],
            models.Despesa.categoria == categoria,
            models.Despesa.origem == "conta",
        ).first()
        if despesa_existente:
            chaves_processadas.add(chave)
            continue

        despesa = models.Despesa(
            usuario_id=usuario.id,
            descricao=despesa_data["descricao"],
            valor=despesa_data["valor"],
            categoria=categoria,
            data=despesa_data["data"],
            origem="conta",
        )
        db.add(despesa)
        despesas_criadas.append(despesa)
        chaves_processadas.add(chave)

    db.commit()
    for despesa in despesas_criadas:
        db.refresh(despesa)

    return {
        "mensagem": "Conta importada com sucesso",
        "despesas_importadas": len(despesas_criadas),
        "total": sum(despesa.valor for despesa in despesas_criadas),
        "informacoes_conta": normalizar_info_fatura(dados.get("informacoes_conta", {})),
        "despesas": despesas_criadas,
    }
