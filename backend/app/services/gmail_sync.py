import base64
import binascii
import hashlib
import io
import json
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import gmail_settings
from app.services.gmail_auth import montar_cliente_gmail
from app.services import notificacoes as notificacoes_service
from app.services import senhas_pdf as senhas_pdf_service
from app.services.parser import SenhaInvalidaError, extrair_dados_pdf, normalizar_texto_busca


class RegraClassificacao:
    def __init__(self, chave: str, tipo: str, marcadores: List[str], nome_cartao: Optional[str] = None):
        self.chave = chave
        self.tipo = tipo
        self.marcadores = marcadores
        self.nome_cartao = nome_cartao


REGRAS_CLASSIFICACAO: List[RegraClassificacao] = [
    RegraClassificacao("itau", "fatura", ["ITAU", "ITAÚ"], nome_cartao="itau"),
    RegraClassificacao("xp", "fatura", ["CARTAOXP", "CARTAO XP", " XP "], nome_cartao="xp"),
    RegraClassificacao("naturgy", "conta", ["NATURGY"]),
    RegraClassificacao("light", "conta", ["LIGHT"]),
    RegraClassificacao("nio", "conta", ["NIO FIBRA", "NIOFIBRA", "NIO"]),
    RegraClassificacao("contracheque", "holerite", ["CONTRACHEQUE", "HOLERITE", "FOLHA DE PAGAMENTO"]),
]

NOMES_CARTAO_EXIBICAO = {
    "itau": "Itaú",
    "xp": "XP",
}


def classificar_remetente(remetente: str, assunto: str) -> Optional[RegraClassificacao]:
    """Classifica um email pelo remetente/assunto usando marcadores tolerantes
    a acento/espaco (mesma normalizacao ja usada no parser de PDF)."""
    texto_busca = normalizar_texto_busca(f"{remetente} {assunto}")
    for regra in REGRAS_CLASSIFICACAO:
        for marcador in regra.marcadores:
            if normalizar_texto_busca(marcador) in texto_busca:
                return regra
    return None


def sugerir_cartao_id(db: Session, usuario_id: int, nome_cartao: Optional[str]) -> Optional[int]:
    if not nome_cartao:
        return None

    cartoes = db.query(models.CartaoCredito).filter(
        models.CartaoCredito.usuario_id == usuario_id,
        models.CartaoCredito.ativo == True,
    ).all()

    alvo = normalizar_texto_busca(nome_cartao)
    for cartao in cartoes:
        if alvo in normalizar_texto_busca(cartao.nome or ""):
            return cartao.id
    return None


def _extrair_header(headers: List[Dict[str, str]], nome: str) -> str:
    for header in headers or []:
        if header.get("name", "").lower() == nome.lower():
            return header.get("value", "")
    return ""


def _parsear_data_recebimento(valor: str) -> Optional[datetime]:
    if not valor:
        return None
    try:
        return parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None


def _encontrar_anexos_pdf(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Percorre recursivamente as partes da mensagem procurando anexos PDF."""
    anexos = []
    partes = [payload] if payload else []

    while partes:
        parte = partes.pop()
        nome_arquivo = parte.get("filename") or ""
        corpo = parte.get("body") or {}
        if nome_arquivo.lower().endswith(".pdf") and corpo.get("attachmentId"):
            anexos.append({
                "nome_arquivo": nome_arquivo,
                "attachment_id": corpo["attachmentId"],
            })
        partes.extend(parte.get("parts") or [])

    return anexos


def _baixar_anexo(servico, message_id: str, attachment_id: str) -> bytes:
    anexo = servico.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    dados_base64 = anexo.get("data", "")
    return base64.urlsafe_b64decode(dados_base64 + "=" * (-len(dados_base64) % 4))


LOCK_TIMEOUT_MINUTOS = 10


def _finalizar_sync(
    db: Session,
    conexao: models.GmailConexao,
    resumo: Dict[str, Any],
    notificacao_chave: str,
    origem: str,
) -> None:
    """Libera o lock de sincronizacao e grava o resumo da tentativa (mesmo
    que parcial/com erro), para que o polling do frontend saiba que acabou."""
    conexao.sincronizando = False
    conexao.sync_total = None
    conexao.sync_processados = None
    conexao.ultimo_resumo_encontrados = resumo["encontrados"]
    conexao.ultimo_resumo_novos = resumo["novos"]
    conexao.ultimo_resumo_erros = resumo["erros"]
    notificacoes_service.finalizar_sync_gmail(
        db,
        conexao.usuario_id,
        notificacao_chave,
        origem,
        resumo,
    )
    db.commit()


def sincronizar_gmail(
    db: Session,
    usuario: models.Usuario,
    origem: str = "automatica",
) -> Dict[str, Any]:
    """Busca emails novos na label configurada, extrai os PDFs anexados e
    enfileira o resultado em ImportacaoPendente. Idempotente: reprocessar a
    mesma caixa nao gera duplicatas (dedupe por gmail_message_id + hash do PDF).

    So um sync roda por vez por usuario (flag `sincronizando` em
    GmailConexao), para nao duplicar trabalho quando o job agendado do
    APScheduler e um disparo manual coincidem. Um lock "travado" (processo
    anterior morreu sem limpar a flag) e liberado apos LOCK_TIMEOUT_MINUTOS."""
    conexao = db.query(models.GmailConexao).filter(
        models.GmailConexao.usuario_id == usuario.id,
        models.GmailConexao.ativo == True,
    ).first()

    resumo = {"encontrados": 0, "novos": 0, "erros": 0}
    if not conexao:
        return resumo

    if conexao.sincronizando and conexao.sync_iniciado_em:
        tempo_decorrido = datetime.utcnow() - conexao.sync_iniciado_em
        if tempo_decorrido < timedelta(minutes=LOCK_TIMEOUT_MINUTOS):
            resumo["ja_em_andamento"] = True
            return resumo

    conexao.sincronizando = True
    conexao.sync_total = None
    conexao.sync_processados = 0
    conexao.sync_iniciado_em = datetime.utcnow()
    notificacao_chave = notificacoes_service.iniciar_sync_gmail(
        db,
        usuario.id,
        origem,
        conexao.sync_iniciado_em,
    )
    db.commit()

    try:
        servico = montar_cliente_gmail(conexao.refresh_token)
        labels_query = " OR ".join(f"label:{label}" for label in gmail_settings.labels_lista)
        query = f"({labels_query}) {gmail_settings.gmail_sync_query_extra}".strip()
        resposta = servico.users().messages().list(userId="me", q=query).execute()
        mensagens = resposta.get("messages", [])
        resumo["encontrados"] = len(mensagens)
        conexao.sync_total = len(mensagens)
        if origem == "manual":
            notificacoes_service.atualizar_sync_gmail(
                db, usuario.id, notificacao_chave, 0, conexao.sync_total
            )
        db.commit()

        for referencia in mensagens:
            message_id = referencia["id"]
            novos = _processar_mensagem(db, servico, usuario, message_id)
            resumo["novos"] += novos
            conexao.sync_processados += 1
            if origem == "manual":
                notificacoes_service.atualizar_sync_gmail(
                    db,
                    usuario.id,
                    notificacao_chave,
                    conexao.sync_processados,
                    conexao.sync_total,
                )
            db.commit()

        conexao.ultima_sincronizacao = datetime.utcnow()
        conexao.ultimo_erro = None
        _finalizar_sync(db, conexao, resumo, notificacao_chave, origem)
    except HttpError as e:
        status_code = e.status_code if hasattr(e, "status_code") else ""
        try:
            motivo = e.reason
        except Exception:
            motivo = str(e)
        conexao.ultimo_erro = f"Erro na API do Gmail ({status_code}): {motivo}".strip()
        resumo["erros"] += 1
        _finalizar_sync(db, conexao, resumo, notificacao_chave, origem)
    except Exception as e:
        conexao.ultimo_erro = f"Erro ao sincronizar: {type(e).__name__}"
        resumo["erros"] += 1
        _finalizar_sync(db, conexao, resumo, notificacao_chave, origem)

    return resumo


def _processar_mensagem(db: Session, servico, usuario: models.Usuario, message_id: str) -> int:
    """Processa os anexos PDF de uma mensagem. Retorna quantos itens novos
    foram criados (dedupe é por mensagem+hash do conteudo do PDF, ja que um
    e-mail pode trazer mais de um PDF relevante, ex: fatura + nota fiscal).
    O attachmentId da API do Gmail nao tem estabilidade garantida entre
    chamadas, por isso o dedupe usa o hash do conteudo baixado."""
    mensagem = servico.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = mensagem.get("payload", {})
    headers = payload.get("headers", [])

    remetente = _extrair_header(headers, "From")
    assunto = _extrair_header(headers, "Subject")
    data_recebimento = _parsear_data_recebimento(_extrair_header(headers, "Date"))

    regra = classificar_remetente(remetente, assunto)
    if not regra:
        return 0

    anexos = _encontrar_anexos_pdf(payload)
    if not anexos:
        return 0

    hashes_ja_processados = {
        hash_valor
        for (hash_valor,) in db.query(models.ImportacaoPendente.hash_anexo).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).all()
    }

    cartao_id_sugerido = sugerir_cartao_id(db, usuario.id, regra.nome_cartao) if regra.tipo == "fatura" else None
    nome_cartao_detectado = (
        NOMES_CARTAO_EXIBICAO.get(regra.nome_cartao, regra.nome_cartao) if regra.tipo == "fatura" else None
    )
    novos = 0
    for anexo in anexos:
        attachment_id = anexo["attachment_id"]
        pdf_bytes = _baixar_anexo(servico, message_id, attachment_id)
        hash_anexo = hashlib.sha256(pdf_bytes).hexdigest()
        if hash_anexo in hashes_ja_processados:
            continue

        try:
            senhas = senhas_pdf_service.obter_senhas(db, usuario.id, [regra.chave])
            dados = senhas_pdf_service.extrair_com_senhas(
                io.BytesIO(pdf_bytes), regra.tipo, senhas, extrair_dados_pdf
            )
            if not dados.get("despesas") and dados.get("erro"):
                # Emails de conta (ex: Naturgy) costumam trazer varios PDFs no
                # mesmo anexo (nota fiscal, informativo legal, etc) alem da
                # conta em si. Quando extrair_conta nao reconhece o documento
                # como uma conta suportada, o anexo nao e' a conta real -
                # ignora silenciosamente em vez de criar um item vazio/erro
                # na fila (o hash ja fica marcado como processado, entao nao
                # tenta de novo a cada sync).
                hashes_ja_processados.add(hash_anexo)
                continue
            db.add(models.ImportacaoPendente(
                usuario_id=usuario.id,
                gmail_message_id=message_id,
                gmail_attachment_id=attachment_id,
                hash_anexo=hash_anexo,
                remetente=remetente,
                assunto=assunto,
                data_recebimento=data_recebimento,
                tipo_detectado=regra.tipo,
                cartao_id_sugerido=cartao_id_sugerido,
                nome_cartao_detectado=nome_cartao_detectado,
                dados_extraidos_json=json.dumps(dados, ensure_ascii=False, default=str),
                status="pendente",
            ))
        except senhas_pdf_service.SenhaConfiguradaInvalidaError:
            db.add(models.ImportacaoPendente(
                usuario_id=usuario.id,
                gmail_message_id=message_id,
                gmail_attachment_id=attachment_id,
                hash_anexo=hash_anexo,
                remetente=remetente,
                assunto=assunto,
                data_recebimento=data_recebimento,
                tipo_detectado=regra.tipo,
                cartao_id_sugerido=cartao_id_sugerido,
                nome_cartao_detectado=nome_cartao_detectado,
                status="erro",
                mensagem_erro="Uma senha salva não pode ser lida. Recadastre-a em Configurações.",
            ))
        except SenhaInvalidaError:
            db.add(models.ImportacaoPendente(
                usuario_id=usuario.id,
                gmail_message_id=message_id,
                gmail_attachment_id=attachment_id,
                hash_anexo=hash_anexo,
                remetente=remetente,
                assunto=assunto,
                data_recebimento=data_recebimento,
                tipo_detectado=regra.tipo,
                cartao_id_sugerido=cartao_id_sugerido,
                nome_cartao_detectado=nome_cartao_detectado,
                status="erro",
                mensagem_erro="Senha incorreta ou ausente para abrir o PDF.",
            ))
        except (binascii.Error, ValueError) as e:
            db.add(models.ImportacaoPendente(
                usuario_id=usuario.id,
                gmail_message_id=message_id,
                gmail_attachment_id=attachment_id,
                hash_anexo=hash_anexo,
                remetente=remetente,
                assunto=assunto,
                data_recebimento=data_recebimento,
                tipo_detectado=regra.tipo,
                cartao_id_sugerido=cartao_id_sugerido,
                nome_cartao_detectado=nome_cartao_detectado,
                status="erro",
                mensagem_erro=f"Erro ao processar anexo: {type(e).__name__}",
            ))
        except Exception as e:
            # Um PDF corrompido ou incompatível com o motor de leitura não deve
            # interromper a sincronização dos demais anexos da caixa.
            db.add(models.ImportacaoPendente(
                usuario_id=usuario.id,
                gmail_message_id=message_id,
                gmail_attachment_id=attachment_id,
                hash_anexo=hash_anexo,
                remetente=remetente,
                assunto=assunto,
                data_recebimento=data_recebimento,
                tipo_detectado=regra.tipo,
                cartao_id_sugerido=cartao_id_sugerido,
                nome_cartao_detectado=nome_cartao_detectado,
                status="erro",
                mensagem_erro=f"Erro ao processar anexo: {type(e).__name__}",
            ))

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue

        hashes_ja_processados.add(hash_anexo)
        novos += 1

    return novos
