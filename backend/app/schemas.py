from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator
from datetime import date, datetime
from typing import List, Literal, Optional, Dict, Any

# Usuário
class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr

class UsuarioCreate(UsuarioBase):
    senha: str

class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None

class Usuario(UsuarioBase):
    id: int
    data_criacao: datetime

    class Config:
        from_attributes = True

# Autenticação
class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: Usuario

# Receita
class ReceitaItem(BaseModel):
    id: int
    descricao: str
    valor: float
    tipo: str

    class Config:
        from_attributes = True

class ReceitaBase(BaseModel):
    descricao: str
    valor: float
    data: date
    origem: str = "manual"

class ReceitaCreate(ReceitaBase):
    pass

class ReceitaUpdate(BaseModel):
    descricao: Optional[str] = None
    valor: Optional[float] = None
    data: Optional[date] = None

class Receita(ReceitaBase):
    id: int
    usuario_id: int
    data_criacao: datetime
    itens: List[ReceitaItem] = []

    class Config:
        from_attributes = True

# Despesa
class DespesaBase(BaseModel):
    descricao: str
    valor: float
    categoria: str
    data: date
    origem: str = "manual"
    cartao_id: Optional[int] = None

class DespesaCreate(DespesaBase):
    pass

class DespesaUpdate(BaseModel):
    descricao: Optional[str] = None
    valor: Optional[float] = None
    categoria: Optional[str] = None
    data: Optional[date] = None

class Despesa(DespesaBase):
    id: int
    usuario_id: int
    data_criacao: datetime

    class Config:
        from_attributes = True

# Cartão de Crédito
class CartaoCreditoBase(BaseModel):
    nome: str
    bandeira: Optional[str] = None
    ultimos_digitos: Optional[str] = None
    limite: Optional[float] = None
    data_vencimento: int = 1

class CartaoCreditoCreate(CartaoCreditoBase):
    pass

class CartaoCreditoUpdate(BaseModel):
    nome: Optional[str] = None
    bandeira: Optional[str] = None
    ultimos_digitos: Optional[str] = None
    limite: Optional[float] = None
    data_vencimento: Optional[int] = None
    ativo: Optional[bool] = None

class CartaoCredito(CartaoCreditoBase):
    id: int
    usuario_id: int
    saldo_usado: float
    ativo: bool
    data_criacao: datetime

    class Config:
        from_attributes = True

# Despesa Recorrente
class DespesaRecorrenteBase(BaseModel):
    descricao: str
    valor: float
    categoria: str
    dia_vencimento: int = Field(ge=1, le=28)
    data_inicio: date
    cartao_id: Optional[int] = None

class DespesaRecorrenteCreate(DespesaRecorrenteBase):
    pass

class DespesaRecorrenteUpdate(BaseModel):
    descricao: Optional[str] = None
    valor: Optional[float] = None
    categoria: Optional[str] = None
    dia_vencimento: Optional[int] = Field(default=None, ge=1, le=28)
    cartao_id: Optional[int] = None
    ativo: Optional[bool] = None

class DespesaRecorrente(DespesaRecorrenteBase):
    id: int
    usuario_id: int
    ativo: bool
    ultima_geracao: Optional[date] = None
    data_criacao: datetime

    class Config:
        from_attributes = True

# Fatura
class FaturaItem(BaseModel):
    id: int
    descricao: str
    valor: float
    categoria: str
    data: date
    estabelecimento: Optional[str] = None

    class Config:
        from_attributes = True

class Fatura(BaseModel):
    id: int
    usuario_id: int
    cartao_id: int
    despesa_id: Optional[int] = None
    descricao: str
    valor_total: float
    vencimento: Optional[date] = None
    data_referencia: date
    informacoes_fatura: Dict[str, Any] = {}
    itens: List[FaturaItem] = []
    data_criacao: datetime

# Parcela
class ParcelaBase(BaseModel):
    descricao: str
    valor_total: float
    total_parcelas: int
    data_inicio: date
    cartao_id: int

class ParcelaCreate(ParcelaBase):
    pass

class ParcelaUpdate(BaseModel):
    descricao: Optional[str] = None
    valor_total: Optional[float] = None
    total_parcelas: Optional[int] = None
    data_inicio: Optional[date] = None
    data_proxima_parcela: Optional[date] = None
    cartao_id: Optional[int] = None
    parcelas_restantes: Optional[int] = None
    pago: Optional[bool] = None

class Parcela(ParcelaBase):
    id: int
    usuario_id: int
    parcelas_restantes: int
    valor_parcela: float
    data_proxima_parcela: date
    pago: bool
    data_criacao: datetime

    class Config:
        from_attributes = True

# Orçamento
class Orcamento(BaseModel):
    categoria: str
    limite: float

# Gmail
class GmailStatus(BaseModel):
    conectado: bool
    email_conectado: Optional[str] = None
    ativo: Optional[bool] = None
    ultima_sincronizacao: Optional[datetime] = None
    ultimo_erro: Optional[str] = None
    sincronizando: bool = False
    sync_total: Optional[int] = None
    sync_processados: Optional[int] = None
    ultimo_resumo_encontrados: Optional[int] = None
    ultimo_resumo_novos: Optional[int] = None
    ultimo_resumo_erros: Optional[int] = None


class NotificacaoLeitura(BaseModel):
    lida: bool


class Notificacao(BaseModel):
    id: int
    tipo: str
    severidade: str
    estado: str
    titulo: str
    mensagem: str
    rota: Optional[str] = None
    progresso_atual: Optional[int] = None
    progresso_total: Optional[int] = None
    lida_em: Optional[datetime] = None
    criada_em: datetime
    atualizada_em: datetime

    class Config:
        from_attributes = True


class FamiliaCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=100)


class FamiliaUpdate(BaseModel):
    nome: str = Field(min_length=2, max_length=100)


class MembroFamiliaCreate(BaseModel):
    email: EmailStr
    papel: str = "membro"


class MembroFamiliaUpdate(BaseModel):
    papel: str


class MembroFamilia(BaseModel):
    id: int
    usuario_id: int
    papel: str
    data_entrada: datetime
    usuario: Usuario

    class Config:
        from_attributes = True


class Familia(BaseModel):
    id: int
    nome: str
    data_criacao: datetime
    membros: List[MembroFamilia] = []

    class Config:
        from_attributes = True


class SenhaPdfInfo(BaseModel):
    configurada: bool
    legivel: bool
    atualizada_em: Optional[datetime] = None


class SenhasPdfStatus(BaseModel):
    itau: SenhaPdfInfo
    xp: SenhaPdfInfo
    naturgy: SenhaPdfInfo
    light: SenhaPdfInfo
    nio: SenhaPdfInfo
    contracheque: SenhaPdfInfo


class SenhasPdfUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    itau: Optional[SecretStr] = None
    xp: Optional[SecretStr] = None
    naturgy: Optional[SecretStr] = None
    light: Optional[SecretStr] = None
    nio: Optional[SecretStr] = None
    contracheque: Optional[SecretStr] = None

    @field_validator("itau", "xp", "naturgy", "light", "nio", "contracheque")
    @classmethod
    def validar_senha(cls, valor: Optional[SecretStr]) -> Optional[SecretStr]:
        if valor is not None and not valor.get_secret_value():
            raise ValueError("A senha não pode ser vazia. Use null para remover.")
        if valor is not None and len(valor.get_secret_value()) > 255:
            raise ValueError("A senha deve ter no máximo 255 caracteres.")
        return valor


class CategoriaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    cor: Optional[str] = None
    ativa: bool = True


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=100)
    cor: Optional[str] = None
    ativa: Optional[bool] = None


class Categoria(CategoriaBase):
    id: int
    sistema: bool

    class Config:
        from_attributes = True


class RegraClassificacaoBase(BaseModel):
    palavra_chave: str = Field(min_length=2, max_length=255)
    categoria: str = Field(min_length=1, max_length=100)
    prioridade: int = 0
    ativa: bool = True


class RegraClassificacaoCreate(RegraClassificacaoBase):
    pass


class RegraClassificacaoUpdate(BaseModel):
    palavra_chave: Optional[str] = Field(default=None, min_length=2, max_length=255)
    categoria: Optional[str] = Field(default=None, min_length=1, max_length=100)
    prioridade: Optional[int] = None
    ativa: Optional[bool] = None


class RegraClassificacao(RegraClassificacaoBase):
    id: int

    class Config:
        from_attributes = True


class NotificacoesResposta(BaseModel):
    items: List[Notificacao]
    nao_lidas: int

# Importação pendente
class ImportacaoPendenteUpdate(BaseModel):
    tipo_detectado: Optional[str] = None
    cartao_id_sugerido: Optional[int] = None
    dados_extraidos: Optional[Dict[str, Any]] = None

class ImportacaoPendenteConfirmar(BaseModel):
    cartao_id: Optional[int] = None

class ImportacaoPendente(BaseModel):
    id: int
    usuario_id: int
    gmail_message_id: str
    remetente: str
    assunto: Optional[str] = None
    data_recebimento: Optional[datetime] = None
    tipo_detectado: str
    cartao_id_sugerido: Optional[int] = None
    nome_cartao_detectado: Optional[str] = None
    dados_extraidos: Dict[str, Any] = {}
    status: str
    mensagem_erro: Optional[str] = None
    data_criacao: datetime
    data_revisao: Optional[datetime] = None

    class Config:
        from_attributes = True

class ImportacaoPendentePagina(BaseModel):
    items: List[ImportacaoPendente]
    total: int
    page: int
    page_size: int

# Análise
class AnaliseGastos(BaseModel):
    total_receitas: float
    total_despesas: float
    saldo: float
    despesas_por_categoria: dict
    gastos_mensais: dict
    cartoes_info: List[dict]
    previsao_futura: dict

# Assistente financeiro local (text2SQL com protocolo de verificação)
class AssistenteStatus(BaseModel):
    habilitado: bool
    disponivel: bool
    runtime: str = "ollama"
    modelo: Optional[str] = None
    quantizacao: Optional[str] = None
    digest: Optional[str] = None
    modelos_instalados: List[str] = []
    processamento_local: bool = True
    mensagem: Optional[str] = None

class AssistentePergunta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pergunta: str = Field(min_length=3, max_length=400)
    modelo: Optional[str] = Field(default=None, max_length=100)

class AssistenteCarregarModelo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelo: str = Field(min_length=1, max_length=100)

class AssistenteCarregarModeloResposta(BaseModel):
    carregado: bool
    mensagem: Optional[str] = None

class AssistenteModeloInfo(BaseModel):
    nome: Optional[str] = None
    quantizacao: Optional[str] = None
    parametros: Optional[str] = None
    digest: Optional[str] = None
    runtime: str = "ollama"
    local: bool = True

class AssistenteCobertura(BaseModel):
    estado: str
    percentual: Optional[float] = None
    fontes_esperadas: int = 0
    fontes_confirmadas: int = 0
    pendencias: List[str] = []

class AssistenteDados(BaseModel):
    """Espelha o protocolo ok/ressalva/nao_sei -- 'veredito' é a classificação
    obrigatória de toda resposta, não um campo opcional de qualidade."""
    sql: Optional[str] = None
    resultado: Optional[List[Dict[str, Any]]] = None
    veredito: Literal["ok", "ressalva", "nao_sei"]
    divergencia: Optional[str] = None
    premissas: List[str] = []
    falta: Optional[str] = None
    resposta: str
    data_solicitada: Optional[str] = None
    data_utilizada: Optional[str] = None
    modelo: AssistenteModeloInfo
    latencia_ms: Dict[str, int] = {}

class AssistenteResposta(BaseModel):
    """Envelope analítico do §9.2 do documento canônico de dados."""
    filtros_aplicados: Dict[str, Any] = {}
    cobertura: AssistenteCobertura
    dados: AssistenteDados
