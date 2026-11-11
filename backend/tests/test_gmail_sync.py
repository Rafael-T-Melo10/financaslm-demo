import base64
from datetime import datetime, timedelta

import pytest

from app import models
from app.config import gmail_settings
from app.database import SessionLocal
from app.services import gmail_sync


class _FakeAttachments:
    def __init__(self, conteudo_por_id):
        self._conteudo_por_id = conteudo_por_id

    def get(self, userId, messageId, id):
        conteudo = self._conteudo_por_id[id]
        return _FakeExecutable({"data": base64.urlsafe_b64encode(conteudo).decode()})

    def execute(self):
        raise NotImplementedError


class _FakeExecutable:
    def __init__(self, resultado):
        self._resultado = resultado

    def execute(self):
        return self._resultado


class _FakeMessages:
    def __init__(self, mensagem, conteudo_por_id, queries_capturadas=None):
        self._mensagem = mensagem
        self._attachments = _FakeAttachments(conteudo_por_id)
        self._queries_capturadas = queries_capturadas

    def get(self, userId, id, format):
        return _FakeExecutable(self._mensagem)

    def attachments(self):
        return self._attachments

    def list(self, userId, q):
        if self._queries_capturadas is not None:
            self._queries_capturadas.append(q)
        return _FakeExecutable({"messages": []})


class _FakeUsers:
    def __init__(self, mensagem, conteudo_por_id, queries_capturadas=None):
        self._messages = _FakeMessages(mensagem, conteudo_por_id, queries_capturadas)

    def messages(self):
        return self._messages


class _FakeServico:
    def __init__(self, mensagem, conteudo_por_id, queries_capturadas=None):
        self._users = _FakeUsers(mensagem, conteudo_por_id, queries_capturadas)

    def users(self):
        return self._users


def _mensagem_naturgy(attachment_id: str) -> dict:
    return {
        "payload": {
            "headers": [
                {"name": "From", "value": "faturas@naturgy.com.br"},
                {"name": "Subject", "value": "Naturgy - SUA CONTA DE GAS CHEGOU"},
                {"name": "Date", "value": "Sun, 12 Jul 2026 10:00:00 -0300"},
            ],
            "filename": "",
            "body": {},
            "parts": [
                {
                    "filename": "conta.pdf",
                    "body": {"attachmentId": attachment_id},
                }
            ],
        }
    }


@pytest.fixture
def usuario_gmail_sync(client, auth_headers):
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        return usuario.id
    finally:
        db.close()


def test_processar_mensagem_nao_duplica_quando_attachment_id_muda(
    monkeypatch, usuario_gmail_sync
):
    """Reproduz o bug: o attachmentId da API do Gmail pode mudar entre
    sincronizacoes, mas o conteudo do PDF e' o mesmo. O dedupe deve se basear
    no hash do conteudo, nao no attachmentId, para nao criar itens pendentes
    duplicados a cada execucao do job periodico."""
    monkeypatch.setattr(
        gmail_sync,
        "extrair_dados_pdf",
        lambda arquivo, tipo, senha: {"despesas": [{"descricao": "Conta Gas", "valor": 100.0, "data": "2026-07-01", "categoria": "Moradia"}]},
    )

    conteudo_pdf = b"%PDF-1.4 conteudo identico da fatura"
    message_id = "msg-naturgy-1"

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        servico_execucao_1 = _FakeServico(_mensagem_naturgy("attach-id-A"), {"attach-id-A": conteudo_pdf})
        novos_1 = gmail_sync._processar_mensagem(db, servico_execucao_1, usuario, message_id)
        db.commit()

        servico_execucao_2 = _FakeServico(_mensagem_naturgy("attach-id-B"), {"attach-id-B": conteudo_pdf})
        novos_2 = gmail_sync._processar_mensagem(db, servico_execucao_2, usuario, message_id)
        db.commit()

        total_pendentes = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).count()

        assert novos_1 == 1
        assert novos_2 == 0
        assert total_pendentes == 1
    finally:
        db.close()


def test_processar_mensagem_cria_itens_para_pdfs_realmente_diferentes(
    monkeypatch, usuario_gmail_sync
):
    monkeypatch.setattr(
        gmail_sync,
        "extrair_dados_pdf",
        lambda arquivo, tipo, senha: {"despesas": [{"descricao": "Conta Gas", "valor": 100.0, "data": "2026-07-01", "categoria": "Moradia"}]},
    )

    message_id = "msg-naturgy-2"

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        mensagem = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "faturas@naturgy.com.br"},
                    {"name": "Subject", "value": "Naturgy - SUA CONTA DE GAS CHEGOU"},
                    {"name": "Date", "value": "Sun, 12 Jul 2026 10:00:00 -0300"},
                ],
                "filename": "",
                "body": {},
                "parts": [
                    {"filename": "conta.pdf", "body": {"attachmentId": "attach-x"}},
                    {"filename": "comprovante.pdf", "body": {"attachmentId": "attach-y"}},
                ],
            }
        }
        conteudo_por_id = {"attach-x": b"%PDF conta", "attach-y": b"%PDF comprovante"}

        servico = _FakeServico(mensagem, conteudo_por_id)
        novos = gmail_sync._processar_mensagem(db, servico, usuario, message_id)
        db.commit()

        total_pendentes = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).count()

        assert novos == 2
        assert total_pendentes == 2
    finally:
        db.close()


def test_processar_mensagem_ignora_anexo_que_nao_e_conta_reconhecida(
    monkeypatch, usuario_gmail_sync
):
    """Email da Naturgy real costuma trazer 3 PDFs (nota fiscal/conta real +
    2 informativos legais/institucionais). Anexos que o parser nao reconhece
    como conta suportada (despesas vazias + chave 'erro') nao devem virar
    item na fila - so a conta real."""
    def _extrair_dados_fake(arquivo, tipo, senha):
        conteudo = arquivo.read()
        if conteudo == b"%PDF conta real":
            return {"despesas": [{"descricao": "Conta Gas", "valor": 100.0, "data": "2026-07-01", "categoria": "Moradia"}]}
        return {"despesas": [], "informacoes_conta": {}, "erro": "O arquivo enviado nao parece ser uma conta suportada."}

    monkeypatch.setattr(gmail_sync, "extrair_dados_pdf", _extrair_dados_fake)

    message_id = "msg-naturgy-3-anexos"

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        mensagem = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "faturas@naturgy.com.br"},
                    {"name": "Subject", "value": "Naturgy - SUA CONTA DE GAS CHEGOU"},
                    {"name": "Date", "value": "Sun, 12 Jul 2026 10:00:00 -0300"},
                ],
                "filename": "",
                "body": {},
                "parts": [
                    {"filename": "lei.pdf", "body": {"attachmentId": "attach-lei"}},
                    {"filename": "notafiscal.pdf", "body": {"attachmentId": "attach-nf"}},
                    {"filename": "fatura.pdf", "body": {"attachmentId": "attach-fatura"}},
                ],
            }
        }
        conteudo_por_id = {
            "attach-lei": b"%PDF informativo legal",
            "attach-nf": b"%PDF conta real",
            "attach-fatura": b"%PDF outro informativo",
        }

        servico = _FakeServico(mensagem, conteudo_por_id)
        novos = gmail_sync._processar_mensagem(db, servico, usuario, message_id)
        db.commit()

        itens = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).all()

        assert novos == 1
        assert len(itens) == 1
        assert itens[0].status == "pendente"
    finally:
        db.close()


def test_processar_mensagem_registra_erro_de_pdf_e_continua_outros_anexos(
    monkeypatch, usuario_gmail_sync
):
    class PdfiumError(Exception):
        pass

    def _extrair_dados_fake(arquivo, tipo, senha):
        if arquivo.read() == b"%PDF corrompido":
            raise PdfiumError("documento inválido")
        return {"despesas": [{"descricao": "Conta de luz", "valor": 80.0, "data": "2026-07-01", "categoria": "Moradia"}]}

    monkeypatch.setattr(gmail_sync, "extrair_dados_pdf", _extrair_dados_fake)
    message_id = "msg-pdf-corrompido"
    mensagem = {
        "payload": {
            "headers": [
                {"name": "From", "value": "faturas@naturgy.com.br"},
                {"name": "Subject", "value": "Naturgy - SUA CONTA DE GAS CHEGOU"},
            ],
            "parts": [
                {"filename": "invalido.pdf", "body": {"attachmentId": "anexo-invalido"}},
                {"filename": "conta.pdf", "body": {"attachmentId": "anexo-valido"}},
            ],
        }
    }
    servico = _FakeServico(mensagem, {
        "anexo-invalido": b"%PDF corrompido",
        "anexo-valido": b"%PDF conta valida",
    })

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()
        novos = gmail_sync._processar_mensagem(db, servico, usuario, message_id)
        db.commit()
        itens = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).order_by(models.ImportacaoPendente.gmail_attachment_id).all()

        assert novos == 2
        assert [item.status for item in itens] == ["erro", "pendente"]
        assert itens[0].mensagem_erro == "Erro ao processar anexo: PdfiumError"
    finally:
        db.close()


def _mensagem_itau_fatura(attachment_id: str) -> dict:
    return {
        "payload": {
            "headers": [
                {"name": "From", "value": "faturadigital@itau.com.br"},
                {"name": "Subject", "value": "Itaú Cartões - Fatura digital"},
                {"name": "Date", "value": "Sun, 12 Jul 2026 10:00:00 -0300"},
            ],
            "filename": "",
            "body": {},
            "parts": [
                {"filename": "fatura.pdf", "body": {"attachmentId": attachment_id}},
            ],
        }
    }


def test_processar_mensagem_grava_nome_cartao_detectado_sem_cartao_cadastrado(
    monkeypatch, usuario_gmail_sync
):
    """Sem um cartao 'Itau' cadastrado, cartao_id_sugerido fica None mas o
    nome de exibicao detectado ('Itau') deve ser gravado, para o frontend
    poder oferecer a criacao do cartao."""
    monkeypatch.setattr(
        gmail_sync,
        "extrair_dados_pdf",
        lambda arquivo, tipo, senha: {
            "total_fatura": 100.0,
            "informacoes_fatura": {"vencimento": "2026-07-10"},
            "despesas": [],
            "parcelas_futuras": [],
        },
    )

    message_id = "msg-itau-sem-cartao"

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        servico = _FakeServico(_mensagem_itau_fatura("attach-itau-1"), {"attach-itau-1": b"%PDF fatura itau"})
        novos = gmail_sync._processar_mensagem(db, servico, usuario, message_id)
        db.commit()

        item = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).first()

        assert novos == 1
        assert item.cartao_id_sugerido is None
        assert item.nome_cartao_detectado == "Itaú"
    finally:
        db.close()


def test_processar_mensagem_grava_nome_cartao_detectado_com_cartao_cadastrado(
    monkeypatch, usuario_gmail_sync
):
    """Com um cartao 'Itau Platinum' cadastrado, cartao_id_sugerido deve
    apontar pra ele e nome_cartao_detectado continua preenchido (o nome de
    exibicao nao depende de ter encontrado match)."""
    monkeypatch.setattr(
        gmail_sync,
        "extrair_dados_pdf",
        lambda arquivo, tipo, senha: {
            "total_fatura": 100.0,
            "informacoes_fatura": {"vencimento": "2026-07-10"},
            "despesas": [],
            "parcelas_futuras": [],
        },
    )

    message_id = "msg-itau-com-cartao"

    db = SessionLocal()
    cartao_criado = None
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        cartao_criado = models.CartaoCredito(
            usuario_id=usuario.id,
            nome="Itaú Platinum",
            data_vencimento=10,
            ativo=True,
        )
        db.add(cartao_criado)
        db.commit()

        servico = _FakeServico(_mensagem_itau_fatura("attach-itau-2"), {"attach-itau-2": b"%PDF fatura itau 2"})
        novos = gmail_sync._processar_mensagem(db, servico, usuario, message_id)
        db.commit()

        item = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).first()

        assert novos == 1
        assert item.cartao_id_sugerido == cartao_criado.id
        assert item.nome_cartao_detectado == "Itaú"
    finally:
        if cartao_criado:
            db.query(models.CartaoCredito).filter(models.CartaoCredito.id == cartao_criado.id).delete()
            db.commit()
        db.close()


def test_processar_mensagem_conta_nao_grava_nome_cartao_detectado(
    monkeypatch, usuario_gmail_sync
):
    """Emails classificados como 'conta' (ex: Naturgy) nao tem nocao de
    cartao, entao nome_cartao_detectado deve ficar None."""
    monkeypatch.setattr(
        gmail_sync,
        "extrair_dados_pdf",
        lambda arquivo, tipo, senha: {"despesas": [{"descricao": "Conta Gas", "valor": 100.0, "data": "2026-07-01", "categoria": "Moradia"}]},
    )

    message_id = "msg-naturgy-nome-cartao"

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        servico = _FakeServico(_mensagem_naturgy("attach-naturgy-nome"), {"attach-naturgy-nome": b"%PDF conta naturgy"})
        novos = gmail_sync._processar_mensagem(db, servico, usuario, message_id)
        db.commit()

        item = db.query(models.ImportacaoPendente).filter(
            models.ImportacaoPendente.usuario_id == usuario.id,
            models.ImportacaoPendente.gmail_message_id == message_id,
        ).first()

        assert novos == 1
        assert item.nome_cartao_detectado is None
    finally:
        db.close()


def test_sincronizar_gmail_busca_todos_os_labels_configurados(monkeypatch, usuario_gmail_sync):
    """A busca deve varrer todos os labels configurados (ex: 'contas' e
    'trabalho') combinados com OR, nao apenas o primeiro."""
    monkeypatch.setattr(gmail_settings, "gmail_sync_labels", "contas,trabalho")

    queries_capturadas = []
    servico = _FakeServico({}, {}, queries_capturadas)
    monkeypatch.setattr(gmail_sync, "montar_cliente_gmail", lambda refresh_token: servico)

    db = SessionLocal()
    conexao_criada = False
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_gmail_sync).first()

        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == usuario.id
        ).first()
        if not conexao:
            conexao = models.GmailConexao(
                usuario_id=usuario.id,
                email_conectado="teste@t.com",
                refresh_token="fake-token",
                ativo=True,
            )
            db.add(conexao)
            conexao_criada = True
        else:
            conexao.ativo = True
        db.commit()

        gmail_sync.sincronizar_gmail(db, usuario)

        assert len(queries_capturadas) == 1
        assert "label:contas" in queries_capturadas[0]
        assert "label:trabalho" in queries_capturadas[0]
        assert " OR " in queries_capturadas[0]
    finally:
        if conexao_criada:
            db.query(models.GmailConexao).filter(
                models.GmailConexao.usuario_id == usuario_gmail_sync
            ).delete()
            db.commit()
        db.close()


def _mensagem_com_anexo(remetente: str, assunto: str, attachment_id: str) -> dict:
    return {
        "payload": {
            "headers": [
                {"name": "From", "value": remetente},
                {"name": "Subject", "value": assunto},
                {"name": "Date", "value": "Sun, 12 Jul 2026 10:00:00 -0300"},
            ],
            "filename": "",
            "body": {},
            "parts": [
                {"filename": "conta.pdf", "body": {"attachmentId": attachment_id}},
            ],
        }
    }


class _FakeMessagesMultiplas:
    """Como _FakeMessages, mas list() retorna varias mensagens e get() resolve
    por message_id (necessario para exercitar o loop de progresso inteiro)."""

    def __init__(self, mensagens_por_id, conteudo_por_id):
        self._mensagens_por_id = mensagens_por_id
        self._conteudo_por_id = conteudo_por_id

    def get(self, userId, id, format):
        return _FakeExecutable(self._mensagens_por_id[id])

    def attachments(self):
        return _FakeAttachments(self._conteudo_por_id)

    def list(self, userId, q):
        return _FakeExecutable({"messages": [{"id": mid} for mid in self._mensagens_por_id]})


class _FakeUsersMultiplas:
    def __init__(self, mensagens_por_id, conteudo_por_id):
        self._messages = _FakeMessagesMultiplas(mensagens_por_id, conteudo_por_id)

    def messages(self):
        return self._messages


class _FakeServicoMultiplas:
    def __init__(self, mensagens_por_id, conteudo_por_id):
        self._users = _FakeUsersMultiplas(mensagens_por_id, conteudo_por_id)

    def users(self):
        return self._users


@pytest.fixture
def conexao_gmail_teste(usuario_gmail_sync):
    db = SessionLocal()
    try:
        criada = False
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == usuario_gmail_sync
        ).first()
        if not conexao:
            conexao = models.GmailConexao(
                usuario_id=usuario_gmail_sync,
                email_conectado="teste@t.com",
                refresh_token="fake-token",
                ativo=True,
            )
            db.add(conexao)
            criada = True
        else:
            conexao.ativo = True
            conexao.sincronizando = False
            conexao.sync_total = None
            conexao.sync_processados = None
            conexao.sync_iniciado_em = None
        db.commit()
        yield usuario_gmail_sync
    finally:
        if criada:
            db.query(models.GmailConexao).filter(
                models.GmailConexao.usuario_id == usuario_gmail_sync
            ).delete()
            db.commit()
        db.close()


def test_sincronizar_gmail_atualiza_resumo_e_libera_flag_ao_final(
    monkeypatch, conexao_gmail_teste
):
    monkeypatch.setattr(
        gmail_sync,
        "extrair_dados_pdf",
        lambda arquivo, tipo, senha: {"despesas": [{"descricao": "Conta", "valor": 10.0, "data": "2026-07-01", "categoria": "Moradia"}]},
    )

    mensagens_por_id = {
        "msg-progresso-1": _mensagem_com_anexo("faturas@naturgy.com.br", "Naturgy - CONTA", "attach-1"),
        "msg-progresso-2": _mensagem_com_anexo("faturas@naturgy.com.br", "Naturgy - CONTA", "attach-2"),
    }
    conteudo_por_id = {"attach-1": b"%PDF conta 1", "attach-2": b"%PDF conta 2"}
    servico = _FakeServicoMultiplas(mensagens_por_id, conteudo_por_id)
    monkeypatch.setattr(gmail_sync, "montar_cliente_gmail", lambda refresh_token: servico)

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == conexao_gmail_teste).first()
        resumo = gmail_sync.sincronizar_gmail(db, usuario)

        assert resumo["encontrados"] == 2
        assert resumo["novos"] == 2
        assert resumo["erros"] == 0

        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == conexao_gmail_teste
        ).first()
        assert conexao.sincronizando is False
        assert conexao.sync_total is None
        assert conexao.sync_processados is None
        assert conexao.ultimo_resumo_encontrados == 2
        assert conexao.ultimo_resumo_novos == 2
        assert conexao.ultimo_resumo_erros == 0
    finally:
        db.close()


def test_sincronizar_gmail_nao_reprocessa_quando_ja_em_andamento(
    monkeypatch, conexao_gmail_teste
):
    def _falha_se_chamado(refresh_token):
        raise AssertionError("montar_cliente_gmail nao deveria ser chamado com lock ativo")

    monkeypatch.setattr(gmail_sync, "montar_cliente_gmail", _falha_se_chamado)

    db = SessionLocal()
    try:
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == conexao_gmail_teste
        ).first()
        conexao.sincronizando = True
        conexao.sync_iniciado_em = datetime.utcnow()
        db.commit()

        usuario = db.query(models.Usuario).filter(models.Usuario.id == conexao_gmail_teste).first()
        resumo = gmail_sync.sincronizar_gmail(db, usuario)

        assert resumo.get("ja_em_andamento") is True
        assert resumo["encontrados"] == 0
    finally:
        db.close()


def test_sincronizar_gmail_recupera_lock_travado_por_timeout(
    monkeypatch, conexao_gmail_teste
):
    queries_capturadas = []
    servico = _FakeServico({}, {}, queries_capturadas)
    monkeypatch.setattr(gmail_sync, "montar_cliente_gmail", lambda refresh_token: servico)

    db = SessionLocal()
    try:
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == conexao_gmail_teste
        ).first()
        conexao.sincronizando = True
        conexao.sync_iniciado_em = datetime.utcnow() - timedelta(minutes=20)
        db.commit()

        usuario = db.query(models.Usuario).filter(models.Usuario.id == conexao_gmail_teste).first()
        resumo = gmail_sync.sincronizar_gmail(db, usuario)

        assert "ja_em_andamento" not in resumo
        assert len(queries_capturadas) == 1

        conexao_apos = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == conexao_gmail_teste
        ).first()
        assert conexao_apos.sincronizando is False
    finally:
        db.close()


def test_sincronizar_gmail_recupera_lock_travado_fecha_notificacao_orfa(
    monkeypatch, conexao_gmail_teste
):
    """A tentativa anterior travou sem chamar finalizar_sync_gmail -- a
    notificacao dela ficou orfa em 'em_andamento' para sempre (a chave e
    amarrada ao timestamp daquela tentativa especifica). Uma nova tentativa,
    ao detectar o lock obsoleto, precisa fechar essa notificacao orfa --
    senao o frontend acha para sempre que ha uma sincronizacao em curso,
    mesmo depois desta tentativa nova terminar com sucesso."""
    servico = _FakeServico({}, {})
    monkeypatch.setattr(gmail_sync, "montar_cliente_gmail", lambda refresh_token: servico)

    db = SessionLocal()
    try:
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == conexao_gmail_teste
        ).first()
        inicio_travado = datetime.utcnow() - timedelta(minutes=20)
        conexao.sincronizando = True
        conexao.sync_iniciado_em = inicio_travado

        notificacao_orfa = models.Notificacao(
            usuario_id=conexao_gmail_teste,
            chave=f"gmail:sync:{inicio_travado.isoformat(timespec='microseconds')}",
            tipo="gmail",
            severidade="info",
            estado="em_andamento",
            titulo="Sincronizando Gmail",
            mensagem="Buscando emails com contas e faturas...",
            progresso_atual=75,
            progresso_total=95,
        )
        db.add(notificacao_orfa)
        db.commit()
        notificacao_orfa_id = notificacao_orfa.id

        usuario = db.query(models.Usuario).filter(models.Usuario.id == conexao_gmail_teste).first()
        gmail_sync.sincronizar_gmail(db, usuario, origem="manual")

        orfa_apos = db.query(models.Notificacao).filter(models.Notificacao.id == notificacao_orfa_id).first()
        assert orfa_apos.estado == "resolvida"
    finally:
        db.close()


def test_sincronizar_gmail_libera_flag_mesmo_com_erro(monkeypatch, conexao_gmail_teste):
    def _levanta_erro(refresh_token):
        raise RuntimeError("falha simulada de rede")

    monkeypatch.setattr(gmail_sync, "montar_cliente_gmail", _levanta_erro)

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == conexao_gmail_teste).first()
        resumo = gmail_sync.sincronizar_gmail(db, usuario)

        assert resumo["erros"] == 1

        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == conexao_gmail_teste
        ).first()
        assert conexao.sincronizando is False
        assert conexao.ultimo_erro is not None
        assert conexao.ultimo_resumo_erros == 1
    finally:
        db.close()
