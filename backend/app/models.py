from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Date, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    senha = Column(String(255), nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    receitas = relationship("Receita", back_populates="usuario", cascade="all, delete-orphan")
    despesas = relationship("Despesa", back_populates="usuario", cascade="all, delete-orphan")
    cartoes = relationship("CartaoCredito", back_populates="usuario", cascade="all, delete-orphan")
    parcelas = relationship("Parcela", back_populates="usuario", cascade="all, delete-orphan")
    faturas = relationship("Fatura", back_populates="usuario", cascade="all, delete-orphan")
    despesas_recorrentes = relationship("DespesaRecorrente", back_populates="usuario", cascade="all, delete-orphan")
    gmail_conexao = relationship("GmailConexao", back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    importacoes_pendentes = relationship("ImportacaoPendente", back_populates="usuario", cascade="all, delete-orphan")
    notificacoes = relationship("Notificacao", back_populates="usuario", cascade="all, delete-orphan")
    membros_familia = relationship("MembroFamilia", back_populates="usuario", cascade="all, delete-orphan")
    senhas_pdf = relationship("SenhaPdf", back_populates="usuario", cascade="all, delete-orphan")


class Familia(Base):
    __tablename__ = "familias"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow, nullable=False)

    membros = relationship("MembroFamilia", back_populates="familia", cascade="all, delete-orphan")


class MembroFamilia(Base):
    __tablename__ = "membros_familia"
    __table_args__ = (
        UniqueConstraint("familia_id", "usuario_id", name="uq_membro_familia_usuario"),
        UniqueConstraint("usuario_id", name="uq_usuario_em_uma_familia"),
    )

    id = Column(Integer, primary_key=True)
    familia_id = Column(Integer, ForeignKey("familias.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    papel = Column(String(20), nullable=False, default="membro")  # admin, membro
    data_entrada = Column(DateTime, default=datetime.utcnow, nullable=False)

    familia = relationship("Familia", back_populates="membros")
    usuario = relationship("Usuario", back_populates="membros_familia")


class Categoria(Base):
    __tablename__ = "categorias"
    __table_args__ = (UniqueConstraint("usuario_id", "nome", name="uq_categoria_usuario_nome"),)

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    cor = Column(String(7), nullable=True)
    ativa = Column(Boolean, nullable=False, default=True)
    sistema = Column(Boolean, nullable=False, default=False)
    data_criacao = Column(DateTime, default=datetime.utcnow, nullable=False)


class RegraClassificacao(Base):
    __tablename__ = "regras_classificacao"
    __table_args__ = (UniqueConstraint("usuario_id", "palavra_chave", name="uq_regra_usuario_palavra"),)

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    palavra_chave = Column(String(255), nullable=False)
    categoria = Column(String(100), nullable=False)
    prioridade = Column(Integer, nullable=False, default=0)
    ativa = Column(Boolean, nullable=False, default=True)
    data_criacao = Column(DateTime, default=datetime.utcnow, nullable=False)

class Receita(Base):
    __tablename__ = "receitas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    data = Column(Date, nullable=False)
    origem = Column(String(50), default="manual")  # manual, holerite
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="receitas")
    itens = relationship("ReceitaItem", back_populates="receita", cascade="all, delete-orphan")

class ReceitaItem(Base):
    """Detalhamento de uma receita (ex: proventos/descontos de um contracheque)."""
    __tablename__ = "receita_itens"

    id = Column(Integer, primary_key=True)
    receita_id = Column(Integer, ForeignKey("receitas.id"), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    tipo = Column(String(20), nullable=False)  # provento, desconto
    data_criacao = Column(DateTime, default=datetime.utcnow)

    receita = relationship("Receita", back_populates="itens")

class Despesa(Base):
    __tablename__ = "despesas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    categoria = Column(String(50), nullable=False)
    data = Column(Date, nullable=False)
    origem = Column(String(50), default="manual")  # manual, fatura
    cartao_id = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="despesas")
    cartao = relationship("CartaoCredito", back_populates="despesas")

class CartaoCredito(Base):
    __tablename__ = "cartoes_credito"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    bandeira = Column(String(50))
    ultimos_digitos = Column(String(4))
    limite = Column(Numeric(10, 2))
    saldo_usado = Column(Numeric(10, 2), default=0)
    data_vencimento = Column(Integer, default=1)  # Dia do vencimento
    ativo = Column(Boolean, default=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="cartoes")
    despesas = relationship("Despesa", back_populates="cartao")
    parcelas = relationship("Parcela", back_populates="cartao", cascade="all, delete-orphan")
    faturas = relationship("Fatura", back_populates="cartao", cascade="all, delete-orphan")

class Fatura(Base):
    __tablename__ = "faturas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cartao_id = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=False)
    despesa_id = Column(Integer, ForeignKey("despesas.id"), nullable=True)
    descricao = Column(String(255), nullable=False, default="Fatura do cartao")
    valor_total = Column(Numeric(10, 2), nullable=False)
    vencimento = Column(Date, nullable=True)
    data_referencia = Column(Date, nullable=False)
    informacoes_json = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="faturas")
    cartao = relationship("CartaoCredito", back_populates="faturas")
    itens = relationship("FaturaItem", back_populates="fatura", cascade="all, delete-orphan")

class FaturaItem(Base):
    __tablename__ = "fatura_itens"

    id = Column(Integer, primary_key=True)
    fatura_id = Column(Integer, ForeignKey("faturas.id"), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    categoria = Column(String(50), nullable=False, default="Outros")
    data = Column(Date, nullable=False)
    estabelecimento = Column(String(255), nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    fatura = relationship("Fatura", back_populates="itens")

class Parcela(Base):
    __tablename__ = "parcelas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cartao_id = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor_total = Column(Numeric(10, 2), nullable=False)
    parcelas_restantes = Column(Integer, nullable=False)
    total_parcelas = Column(Integer, nullable=False)
    valor_parcela = Column(Numeric(10, 2), nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_proxima_parcela = Column(Date, nullable=False)
    pago = Column(Boolean, default=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="parcelas")
    cartao = relationship("CartaoCredito", back_populates="parcelas")

class DespesaRecorrente(Base):
    __tablename__ = "despesas_recorrentes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cartao_id = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=True)
    descricao = Column(String(255), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    categoria = Column(String(50), nullable=False)
    dia_vencimento = Column(Integer, nullable=False)  # 1-28
    ativo = Column(Boolean, default=True)
    data_inicio = Column(Date, nullable=False)
    ultima_geracao = Column(Date, nullable=True)  # primeiro dia do último mês já lançado
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="despesas_recorrentes")
    cartao = relationship("CartaoCredito")

class Configuracao(Base):
    __tablename__ = "configuracoes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    preferencia = Column(String(100), nullable=False)
    valor = Column(String(255), nullable=False)
    data_atualizacao = Column(DateTime, default=datetime.utcnow)


class SenhaPdf(Base):
    __tablename__ = "senhas_pdf"
    __table_args__ = (UniqueConstraint("usuario_id", "instituicao", name="uq_senha_pdf_usuario_instituicao"),)

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    instituicao = Column(String(30), nullable=False)
    valor_criptografado = Column(Text, nullable=False)
    data_atualizacao = Column(DateTime, default=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario", back_populates="senhas_pdf")


class Notificacao(Base):
    __tablename__ = "notificacoes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "chave", name="uq_notificacao_usuario_chave"),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    chave = Column(String(255), nullable=False)
    tipo = Column(String(50), nullable=False)
    severidade = Column(String(20), nullable=False, default="info")
    estado = Column(String(20), nullable=False, default="ativa")
    titulo = Column(String(255), nullable=False)
    mensagem = Column(Text, nullable=False)
    rota = Column(String(255), nullable=True)
    progresso_atual = Column(Integer, nullable=True)
    progresso_total = Column(Integer, nullable=True)
    lida_em = Column(DateTime, nullable=True)
    resolvida_em = Column(DateTime, nullable=True)
    criada_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizada_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    usuario = relationship("Usuario", back_populates="notificacoes")

class GmailConexao(Base):
    __tablename__ = "gmail_conexoes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, unique=True)
    email_conectado = Column(String(255), nullable=False)
    refresh_token = Column(Text, nullable=False)
    ativo = Column(Boolean, default=True)
    ultima_sincronizacao = Column(DateTime, nullable=True)
    ultimo_erro = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    sincronizando = Column(Boolean, default=False, nullable=False)
    sync_total = Column(Integer, nullable=True)
    sync_processados = Column(Integer, nullable=True)
    sync_iniciado_em = Column(DateTime, nullable=True)
    ultimo_resumo_encontrados = Column(Integer, nullable=True)
    ultimo_resumo_novos = Column(Integer, nullable=True)
    ultimo_resumo_erros = Column(Integer, nullable=True)

    usuario = relationship("Usuario", back_populates="gmail_conexao")

class ImportacaoPendente(Base):
    __tablename__ = "importacoes_pendentes"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id", "gmail_message_id", "hash_anexo",
            name="uq_importacao_pendente_usuario_mensagem_hash",
        ),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    gmail_message_id = Column(String(100), nullable=False)
    gmail_attachment_id = Column(Text, nullable=False, default="")
    hash_anexo = Column(String(64), nullable=False, default="")
    remetente = Column(String(255), nullable=False)
    assunto = Column(String(500), nullable=True)
    data_recebimento = Column(DateTime, nullable=True)
    tipo_detectado = Column(String(20), nullable=False)  # holerite, fatura, conta
    cartao_id_sugerido = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=True)
    nome_cartao_detectado = Column(String(100), nullable=True)
    dados_extraidos_json = Column(Text, nullable=True)
    status = Column(String(20), default="pendente")  # pendente, confirmada, rejeitada, erro
    mensagem_erro = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_revisao = Column(DateTime, nullable=True)

    usuario = relationship("Usuario", back_populates="importacoes_pendentes")
    cartao_sugerido = relationship("CartaoCredito")
