import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List
from urllib.parse import quote
from app import models, schemas
from app.config import gmail_settings, whatsapp_settings
from app.database import SessionLocal, get_db
from app.security import autenticar_usuario, criar_token_acesso, gerar_hash_senha, get_current_user
from app.services.parser import extrair_dados_pdf, normalizar_texto_busca, SenhaInvalidaError
from app.services.analysis import calcular_analise_gastos, gerar_alertas, montar_dashboard, previsao_gastos, montar_relatorio_anual
from app.services.recorrencia import gerar_despesas_pendentes
from app.services import importacao as importacao_service
from app.services import gmail_auth
from app.services import notificacoes as notificacoes_service
from app.services import familia as familia_service
from app.services import classificacao as classificacao_service
from app.services import senhas_pdf as senhas_pdf_service
from app.services.assistente import servico as assistente_service
from app.services.whatsapp import servico as whatsapp_service
from app.services.gmail_sync import LOCK_TIMEOUT_MINUTOS, _baixar_anexo, sincronizar_gmail
from app.utils import intervalo_mes
import csv
import io
import json

router = APIRouter()
logger = logging.getLogger(__name__)


def _extrair_pdf_com_senhas_configuradas(
    db: Session,
    usuario: models.Usuario,
    arquivo,
    tipo: str,
    chave_preferida: str | None = None,
):
    chaves = senhas_pdf_service.chaves_para_tipo(tipo, chave_preferida)
    senhas = senhas_pdf_service.obter_senhas(db, usuario.id, chaves)
    return senhas_pdf_service.extrair_com_senhas(arquivo, tipo, senhas, extrair_dados_pdf)

def _filtro_mes_ano(mes: int | None, ano: int | None):
    """Valida a combinação mes/ano e devolve o intervalo de datas (ou None)."""
    if mes and not ano:
        raise HTTPException(status_code=422, detail="Informe o ano junto com o mês")
    if mes and ano:
        return intervalo_mes(mes, ano)
    if ano:
        return date(ano, 1, 1), date(ano, 12, 31)
    return None

# ==================== AUTENTICAÇÃO ====================

@router.post("/auth/login", response_model=schemas.Token, tags=["Autenticação"])
def login(credenciais: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Autenticar usuário e emitir token JWT"""
    usuario = autenticar_usuario(db, credenciais.email, credenciais.senha)
    if not usuario:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")

    return schemas.Token(access_token=criar_token_acesso(usuario.id), usuario=usuario)

# ==================== USUÁRIOS ====================

@router.post("/usuarios", response_model=schemas.Usuario, tags=["Usuários"])
def criar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """Criar novo usuário"""
    db_usuario = db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first()
    if db_usuario:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    novo_usuario = models.Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha=gerar_hash_senha(usuario.senha),
    )
    db.add(novo_usuario)
    db.flush()
    classificacao_service.seed_categorias_padrao(db, novo_usuario.id)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario

@router.get("/usuarios/me", response_model=schemas.Usuario, tags=["Usuários"])
def obter_usuario_logado(usuario: models.Usuario = Depends(get_current_user)):
    """Obter dados do usuário autenticado"""
    return usuario


# ==================== CATEGORIAS E REGRAS ====================

@router.get("/categorias", response_model=List[schemas.Categoria], tags=["Categorias"])
def listar_categorias(usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    classificacao_service.seed_categorias_padrao(db, usuario.id)
    db.commit()
    return db.query(models.Categoria).filter(models.Categoria.usuario_id == usuario.id).order_by(models.Categoria.nome).all()


@router.post("/categorias", response_model=schemas.Categoria, tags=["Categorias"])
def criar_categoria(dados: schemas.CategoriaCreate, usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(models.Categoria).filter(models.Categoria.usuario_id == usuario.id, models.Categoria.nome == dados.nome.strip()).first():
        raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")
    categoria = models.Categoria(usuario_id=usuario.id, nome=dados.nome.strip(), cor=dados.cor, ativa=dados.ativa)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.put("/categorias/{categoria_id}", response_model=schemas.Categoria, tags=["Categorias"])
def atualizar_categoria(categoria_id: int, dados: schemas.CategoriaUpdate, usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    categoria = db.query(models.Categoria).filter(models.Categoria.id == categoria_id, models.Categoria.usuario_id == usuario.id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    if dados.nome is not None:
        novo_nome = dados.nome.strip()
        colisao = db.query(models.Categoria).filter(models.Categoria.usuario_id == usuario.id, models.Categoria.nome == novo_nome, models.Categoria.id != categoria.id).first()
        if colisao:
            raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")
        categoria.nome = novo_nome
    if dados.cor is not None:
        categoria.cor = dados.cor
    if dados.ativa is not None:
        categoria.ativa = dados.ativa
    db.commit()
    db.refresh(categoria)
    return categoria


@router.get("/regras-classificacao", response_model=List[schemas.RegraClassificacao], tags=["Categorias"])
def listar_regras_classificacao(usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.RegraClassificacao).filter(models.RegraClassificacao.usuario_id == usuario.id).order_by(models.RegraClassificacao.prioridade.desc()).all()


@router.post("/regras-classificacao", response_model=schemas.RegraClassificacao, tags=["Categorias"])
def criar_regra_classificacao(dados: schemas.RegraClassificacaoCreate, usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    palavra_chave = classificacao_service.normalizar_chave(dados.palavra_chave)
    if db.query(models.RegraClassificacao).filter(models.RegraClassificacao.usuario_id == usuario.id, models.RegraClassificacao.palavra_chave == palavra_chave).first():
        raise HTTPException(status_code=409, detail="Já existe uma regra para esta palavra-chave.")
    regra = models.RegraClassificacao(usuario_id=usuario.id, palavra_chave=palavra_chave, categoria=dados.categoria, prioridade=dados.prioridade, ativa=dados.ativa)
    db.add(regra)
    db.commit()
    db.refresh(regra)
    return regra


@router.put("/regras-classificacao/{regra_id}", response_model=schemas.RegraClassificacao, tags=["Categorias"])
def atualizar_regra_classificacao(regra_id: int, dados: schemas.RegraClassificacaoUpdate, usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    regra = db.query(models.RegraClassificacao).filter(models.RegraClassificacao.id == regra_id, models.RegraClassificacao.usuario_id == usuario.id).first()
    if not regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    valores = dados.dict(exclude_unset=True)
    if "palavra_chave" in valores:
        valores["palavra_chave"] = classificacao_service.normalizar_chave(valores["palavra_chave"])
    for campo, valor in valores.items():
        setattr(regra, campo, valor)
    db.commit()
    db.refresh(regra)
    return regra


@router.delete("/regras-classificacao/{regra_id}", status_code=204, tags=["Categorias"])
def remover_regra_classificacao(regra_id: int, usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    regra = db.query(models.RegraClassificacao).filter(models.RegraClassificacao.id == regra_id, models.RegraClassificacao.usuario_id == usuario.id).first()
    if not regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    db.delete(regra)
    db.commit()


# ==================== FAMÍLIA ====================

@router.post("/familias", response_model=schemas.Familia, tags=["Família"])
def criar_familia(
    dados: schemas.FamiliaCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if familia_service.obter_membro(db, usuario.id):
        raise HTTPException(status_code=409, detail="O usuário já faz parte de uma família.")
    familia = models.Familia(nome=dados.nome.strip())
    db.add(familia)
    db.flush()
    db.add(models.MembroFamilia(familia_id=familia.id, usuario_id=usuario.id, papel="admin"))
    db.commit()
    return familia_service.obter_familia_do_usuario(db, usuario.id)


@router.get("/familias/minha", response_model=schemas.Familia, tags=["Família"])
def obter_minha_familia(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    familia = familia_service.obter_familia_do_usuario(db, usuario.id)
    if not familia:
        raise HTTPException(status_code=404, detail="Você ainda não faz parte de uma família.")
    return familia


@router.patch("/familias/minha", response_model=schemas.Familia, tags=["FamÃ­lia"])
def renomear_minha_familia(
    dados: schemas.FamiliaUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membro_admin = familia_service.exigir_admin(db, usuario.id)
    familia = db.query(models.Familia).filter(models.Familia.id == membro_admin.familia_id).first()
    if not familia:
        raise HTTPException(status_code=404, detail="FamÃ­lia nÃ£o encontrada.")
    familia.nome = dados.nome.strip()
    db.commit()
    return familia_service.obter_familia_do_usuario(db, usuario.id)


@router.delete("/familias/minha/participacao", status_code=204, tags=["FamÃ­lia"])
def sair_da_familia(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membro = familia_service.obter_membro(db, usuario.id)
    if not membro:
        raise HTTPException(status_code=404, detail="VocÃª ainda nÃ£o faz parte de uma famÃ­lia.")

    quantidade_membros = db.query(models.MembroFamilia).filter(
        models.MembroFamilia.familia_id == membro.familia_id
    ).count()
    if membro.papel == "admin" and familia_service.quantidade_admins(db, membro.familia_id) == 1:
        if quantidade_membros > 1:
            raise HTTPException(status_code=409, detail="Promova outro membro a administrador antes de sair da famÃ­lia.")
        familia = db.query(models.Familia).filter(models.Familia.id == membro.familia_id).first()
        if familia:
            db.delete(familia)
    else:
        db.delete(membro)
    db.commit()


@router.post("/familias/membros", response_model=schemas.Familia, tags=["Família"])
def adicionar_membro_familia(
    dados: schemas.MembroFamiliaCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membro_admin = familia_service.exigir_admin(db, usuario.id)
    convidado = db.query(models.Usuario).filter(models.Usuario.email == dados.email).first()
    if not convidado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado. Ele precisa criar uma conta antes do convite.")
    if familia_service.obter_membro(db, convidado.id):
        raise HTTPException(status_code=409, detail="Este usuário já faz parte de uma família.")
    db.add(models.MembroFamilia(
        familia_id=membro_admin.familia_id,
        usuario_id=convidado.id,
        papel=familia_service.validar_papel(dados.papel),
    ))
    db.commit()
    return familia_service.obter_familia_do_usuario(db, usuario.id)


@router.patch("/familias/membros/{membro_id}", response_model=schemas.Familia, tags=["Família"])
def atualizar_membro_familia(
    membro_id: int,
    dados: schemas.MembroFamiliaUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membro_admin = familia_service.exigir_admin(db, usuario.id)
    membro = db.query(models.MembroFamilia).filter(
        models.MembroFamilia.id == membro_id,
        models.MembroFamilia.familia_id == membro_admin.familia_id,
    ).first()
    if not membro:
        raise HTTPException(status_code=404, detail="Membro não encontrado.")
    novo_papel = familia_service.validar_papel(dados.papel)
    if membro.papel == "admin" and novo_papel != "admin" and familia_service.quantidade_admins(db, membro.familia_id) == 1:
        raise HTTPException(status_code=400, detail="A família precisa manter pelo menos um administrador.")
    membro.papel = novo_papel
    db.commit()
    return familia_service.obter_familia_do_usuario(db, usuario.id)


@router.delete("/familias/membros/{membro_id}", response_model=schemas.Familia, tags=["Família"])
def remover_membro_familia(
    membro_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membro_admin = familia_service.exigir_admin(db, usuario.id)
    membro = db.query(models.MembroFamilia).filter(
        models.MembroFamilia.id == membro_id,
        models.MembroFamilia.familia_id == membro_admin.familia_id,
    ).first()
    if not membro:
        raise HTTPException(status_code=404, detail="Membro não encontrado.")
    if membro.papel == "admin" and familia_service.quantidade_admins(db, membro.familia_id) == 1:
        raise HTTPException(status_code=400, detail="A família precisa manter pelo menos um administrador.")
    db.delete(membro)
    db.commit()
    return familia_service.obter_familia_do_usuario(db, usuario.id)


# ==================== CONFIGURAÃ‡Ã•ES ====================

@router.get("/configuracoes/senhas-pdf", response_model=schemas.SenhasPdfStatus, tags=["ConfiguraÃ§Ãµes"])
def obter_senhas_pdf(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return senhas_pdf_service.obter_status(db, usuario.id)


@router.patch("/configuracoes/senhas-pdf", response_model=schemas.SenhasPdfStatus, tags=["ConfiguraÃ§Ãµes"])
def atualizar_senhas_pdf(
    atualizacao: schemas.SenhasPdfUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for instituicao in atualizacao.model_fields_set:
        senha = getattr(atualizacao, instituicao)
        if senha is None:
            senhas_pdf_service.remover(db, usuario.id, instituicao)
        else:
            senhas_pdf_service.atualizar(db, usuario.id, instituicao, senha.get_secret_value())
    db.commit()
    return senhas_pdf_service.obter_status(db, usuario.id)

# ==================== RECEITAS ====================

@router.post("/receitas", response_model=schemas.Receita, tags=["Receitas"])
def criar_receita(
    receita: schemas.ReceitaCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Criar nova receita"""
    nova_receita = models.Receita(**receita.dict(), usuario_id=usuario.id)
    db.add(nova_receita)
    db.commit()
    db.refresh(nova_receita)
    return nova_receita

@router.get("/receitas", response_model=List[schemas.Receita], tags=["Receitas"])
def listar_receitas(
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar receitas do usuário"""
    query = db.query(models.Receita).filter(models.Receita.usuario_id == usuario.id)

    intervalo = _filtro_mes_ano(mes, ano)
    if intervalo:
        query = query.filter(models.Receita.data.between(*intervalo))

    return query.all()

@router.put("/receitas/{receita_id}", response_model=schemas.Receita, tags=["Receitas"])
def atualizar_receita(
    receita_id: int,
    receita: schemas.ReceitaUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualizar receita"""
    db_receita = db.query(models.Receita).filter(
        models.Receita.id == receita_id,
        models.Receita.usuario_id == usuario.id,
    ).first()
    if not db_receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    for field, value in receita.dict(exclude_unset=True).items():
        setattr(db_receita, field, value)

    db.commit()
    db.refresh(db_receita)
    return db_receita

@router.delete("/receitas/{receita_id}", status_code=204, tags=["Receitas"])
def deletar_receita(
    receita_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletar receita"""
    db_receita = db.query(models.Receita).filter(
        models.Receita.id == receita_id,
        models.Receita.usuario_id == usuario.id,
    ).first()
    if not db_receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    db.delete(db_receita)
    db.commit()

# ==================== DESPESAS ====================

@router.post("/despesas", response_model=schemas.Despesa, tags=["Despesas"])
def criar_despesa(
    despesa: schemas.DespesaCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Criar nova despesa"""
    nova_despesa = models.Despesa(**despesa.dict(), usuario_id=usuario.id)
    db.add(nova_despesa)
    db.commit()
    db.refresh(nova_despesa)
    return nova_despesa

@router.get("/despesas", response_model=List[schemas.Despesa], tags=["Despesas"])
def listar_despesas(
    mes: int = None,
    ano: int = None,
    categoria: str = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar despesas do usuário"""
    gerar_despesas_pendentes(db, usuario.id)

    query = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id)

    intervalo = _filtro_mes_ano(mes, ano)
    if intervalo:
        query = query.filter(models.Despesa.data.between(*intervalo))

    if categoria:
        query = query.filter(models.Despesa.categoria == categoria)

    return query.all()

@router.put("/despesas/{despesa_id}", response_model=schemas.Despesa, tags=["Despesas"])
def atualizar_despesa(
    despesa_id: int,
    despesa: schemas.DespesaUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualizar despesa"""
    db_despesa = db.query(models.Despesa).filter(
        models.Despesa.id == despesa_id,
        models.Despesa.usuario_id == usuario.id,
    ).first()
    if not db_despesa:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    for field, value in despesa.dict(exclude_unset=True).items():
        setattr(db_despesa, field, value)

    db.commit()
    db.refresh(db_despesa)
    return db_despesa

@router.delete("/despesas/{despesa_id}", status_code=204, tags=["Despesas"])
def deletar_despesa(
    despesa_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletar despesa"""
    db_despesa = db.query(models.Despesa).filter(
        models.Despesa.id == despesa_id,
        models.Despesa.usuario_id == usuario.id,
    ).first()
    if not db_despesa:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    faturas_vinculadas = db.query(models.Fatura).filter(models.Fatura.despesa_id == despesa_id).all()
    for fatura in faturas_vinculadas:
        db.delete(fatura)
    if faturas_vinculadas:
        db.flush()

    db.delete(db_despesa)
    db.commit()

# ==================== CARTÕES ====================

@router.post("/cartoes", response_model=schemas.CartaoCredito, tags=["Cartões"])
def criar_cartao(
    cartao: schemas.CartaoCreditoCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Criar novo cartão de crédito"""
    novo_cartao = models.CartaoCredito(**cartao.dict(), usuario_id=usuario.id)
    db.add(novo_cartao)
    db.commit()
    db.refresh(novo_cartao)
    return novo_cartao

@router.get("/cartoes", response_model=List[schemas.CartaoCredito], tags=["Cartões"])
def listar_cartoes(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar cartões do usuário"""
    return db.query(models.CartaoCredito).filter(models.CartaoCredito.usuario_id == usuario.id).all()

@router.put("/cartoes/{cartao_id}", response_model=schemas.CartaoCredito, tags=["Cartões"])
def atualizar_cartao(
    cartao_id: int,
    cartao: schemas.CartaoCreditoUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualizar cartão"""
    db_cartao = db.query(models.CartaoCredito).filter(
        models.CartaoCredito.id == cartao_id,
        models.CartaoCredito.usuario_id == usuario.id,
    ).first()
    if not db_cartao:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    for field, value in cartao.dict(exclude_unset=True).items():
        setattr(db_cartao, field, value)

    db.commit()
    db.refresh(db_cartao)
    return db_cartao

@router.delete("/cartoes/{cartao_id}", tags=["Cartões"])
def deletar_cartao(
    cartao_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remover cartão"""
    db_cartao = db.query(models.CartaoCredito).filter(
        models.CartaoCredito.id == cartao_id,
        models.CartaoCredito.usuario_id == usuario.id,
    ).first()
    if not db_cartao:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    db.delete(db_cartao)
    db.commit()
    return {"message": "Cartão removido com sucesso"}

# ==================== DESPESAS RECORRENTES ====================

@router.post("/despesas-recorrentes", response_model=schemas.DespesaRecorrente, tags=["Despesas Recorrentes"])
def criar_despesa_recorrente(
    recorrente: schemas.DespesaRecorrenteCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Criar nova despesa recorrente (assinatura, aluguel etc.)"""
    nova_recorrente = models.DespesaRecorrente(**recorrente.dict(), usuario_id=usuario.id)
    db.add(nova_recorrente)
    db.commit()
    db.refresh(nova_recorrente)
    return nova_recorrente

@router.get("/despesas-recorrentes", response_model=List[schemas.DespesaRecorrente], tags=["Despesas Recorrentes"])
def listar_despesas_recorrentes(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar despesas recorrentes do usuário e gerar as despesas do mês ainda pendentes"""
    gerar_despesas_pendentes(db, usuario.id)

    return db.query(models.DespesaRecorrente).filter(
        models.DespesaRecorrente.usuario_id == usuario.id,
    ).all()

@router.put("/despesas-recorrentes/{recorrente_id}", response_model=schemas.DespesaRecorrente, tags=["Despesas Recorrentes"])
def atualizar_despesa_recorrente(
    recorrente_id: int,
    recorrente: schemas.DespesaRecorrenteUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualizar despesa recorrente (valor, categoria, dia de vencimento, pausar/retomar)"""
    db_recorrente = db.query(models.DespesaRecorrente).filter(
        models.DespesaRecorrente.id == recorrente_id,
        models.DespesaRecorrente.usuario_id == usuario.id,
    ).first()
    if not db_recorrente:
        raise HTTPException(status_code=404, detail="Despesa recorrente não encontrada")

    for field, value in recorrente.dict(exclude_unset=True).items():
        setattr(db_recorrente, field, value)

    db.commit()
    db.refresh(db_recorrente)
    return db_recorrente

@router.delete("/despesas-recorrentes/{recorrente_id}", status_code=204, tags=["Despesas Recorrentes"])
def deletar_despesa_recorrente(
    recorrente_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remover despesa recorrente (não apaga despesas já geradas)"""
    db_recorrente = db.query(models.DespesaRecorrente).filter(
        models.DespesaRecorrente.id == recorrente_id,
        models.DespesaRecorrente.usuario_id == usuario.id,
    ).first()
    if not db_recorrente:
        raise HTTPException(status_code=404, detail="Despesa recorrente não encontrada")

    db.delete(db_recorrente)
    db.commit()

# ==================== FATURAS ====================

@router.get("/faturas", response_model=List[schemas.Fatura], tags=["Faturas"])
def listar_faturas(
    cartao_id: int = None,
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar faturas importadas com as compras detalhadas."""
    query = db.query(models.Fatura).filter(models.Fatura.usuario_id == usuario.id)

    if cartao_id:
        query = query.filter(models.Fatura.cartao_id == cartao_id)

    intervalo = _filtro_mes_ano(mes, ano)
    if intervalo:
        query = query.filter(models.Fatura.data_referencia.between(*intervalo))

    faturas = query.order_by(models.Fatura.data_referencia.desc(), models.Fatura.id.desc()).all()
    return [importacao_service.serializar_fatura(fatura) for fatura in faturas]

# ==================== PARCELAS ====================

@router.post("/parcelas", response_model=schemas.Parcela, tags=["Parcelas"])
def criar_parcela(
    parcela: schemas.ParcelaCreate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Criar nova parcela"""
    if parcela.total_parcelas <= 0:
        raise HTTPException(status_code=400, detail="Número de parcelas deve ser maior que zero")

    valor_parcela = parcela.valor_total / parcela.total_parcelas
    data_proxima = parcela.data_inicio + relativedelta(months=1)

    nova_parcela = models.Parcela(
        usuario_id=usuario.id,
        cartao_id=parcela.cartao_id,
        descricao=parcela.descricao,
        valor_total=parcela.valor_total,
        total_parcelas=parcela.total_parcelas,
        parcelas_restantes=parcela.total_parcelas,
        valor_parcela=valor_parcela,
        data_inicio=parcela.data_inicio,
        data_proxima_parcela=data_proxima
    )
    db.add(nova_parcela)
    db.commit()
    db.refresh(nova_parcela)
    return nova_parcela

@router.get("/parcelas", response_model=List[schemas.Parcela], tags=["Parcelas"])
def listar_parcelas(
    apenas_ativas: bool = True,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar parcelas do usuário"""
    query = db.query(models.Parcela).filter(models.Parcela.usuario_id == usuario.id)

    if apenas_ativas:
        query = query.filter(models.Parcela.pago == False)

    return query.all()

@router.put("/parcelas/{parcela_id}", response_model=schemas.Parcela, tags=["Parcelas"])
def atualizar_parcela(
    parcela_id: int,
    parcela: schemas.ParcelaUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualizar parcela."""
    db_parcela = db.query(models.Parcela).filter(
        models.Parcela.id == parcela_id,
        models.Parcela.usuario_id == usuario.id,
    ).first()
    if not db_parcela:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")

    dados = parcela.dict(exclude_unset=True)

    if "cartao_id" in dados:
        cartao = db.query(models.CartaoCredito).filter(
            models.CartaoCredito.id == dados["cartao_id"],
            models.CartaoCredito.usuario_id == usuario.id,
        ).first()
        if not cartao:
            raise HTTPException(status_code=404, detail="Cartão não encontrado")

    for field, value in dados.items():
        setattr(db_parcela, field, value)

    if "valor_total" in dados or "total_parcelas" in dados:
        if db_parcela.total_parcelas <= 0:
            raise HTTPException(status_code=400, detail="Número de parcelas deve ser maior que zero")
        db_parcela.valor_parcela = db_parcela.valor_total / db_parcela.total_parcelas

    if "total_parcelas" in dados and db_parcela.parcelas_restantes > db_parcela.total_parcelas:
        db_parcela.parcelas_restantes = db_parcela.total_parcelas

    db.commit()
    db.refresh(db_parcela)
    return db_parcela

@router.post("/parcelas/{parcela_id}/pagar", response_model=schemas.Parcela, tags=["Parcelas"])
def pagar_parcela(
    parcela_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registrar o pagamento de uma parcela: gera a despesa do mês e avança a próxima data."""
    db_parcela = db.query(models.Parcela).filter(
        models.Parcela.id == parcela_id,
        models.Parcela.usuario_id == usuario.id,
    ).first()
    if not db_parcela:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")

    if db_parcela.pago or db_parcela.parcelas_restantes <= 0:
        raise HTTPException(status_code=400, detail="Parcela já quitada")

    numero_parcela = db_parcela.total_parcelas - db_parcela.parcelas_restantes + 1
    despesa = models.Despesa(
        usuario_id=usuario.id,
        cartao_id=db_parcela.cartao_id,
        descricao=f"{db_parcela.descricao} ({numero_parcela}/{db_parcela.total_parcelas})",
        valor=db_parcela.valor_parcela,
        categoria="Cartão de Crédito",
        data=db_parcela.data_proxima_parcela,
        origem="parcela",
    )
    db.add(despesa)

    db_parcela.parcelas_restantes -= 1
    if db_parcela.parcelas_restantes <= 0:
        db_parcela.pago = True
    else:
        db_parcela.data_proxima_parcela = db_parcela.data_proxima_parcela + relativedelta(months=1)

    db.commit()
    db.refresh(db_parcela)
    return db_parcela

@router.delete("/parcelas/{parcela_id}", status_code=204, tags=["Parcelas"])
def deletar_parcela(
    parcela_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletar parcela."""
    db_parcela = db.query(models.Parcela).filter(
        models.Parcela.id == parcela_id,
        models.Parcela.usuario_id == usuario.id,
    ).first()
    if not db_parcela:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")

    db.delete(db_parcela)
    db.commit()

# ==================== IMPORTAÇÃO DE ARQUIVOS ====================

@router.post("/importar/holerite", tags=["Importação"])
def importar_holerite(
    file: UploadFile = File(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Importar holerite em PDF"""
    try:
        dados = _extrair_pdf_com_senhas_configuradas(db, usuario, file.file, "holerite")
        return importacao_service.persistir_holerite(db, usuario, dados)
    except importacao_service.ImportacaoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.mensagem)
    except senhas_pdf_service.SenhaConfiguradaInvalidaError:
        raise HTTPException(status_code=400, detail="Uma senha salva não pode ser lida. Recadastre-a em Configurações.")
    except SenhaInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Falha inesperada ao importar holerite para usuario_id=%s", usuario.id)
        raise HTTPException(status_code=500, detail="Não foi possível processar o arquivo. Tente novamente.")

@router.post("/importar/fatura", tags=["Importação"])
def importar_fatura(
    cartao_id: int,
    file: UploadFile = File(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Importar fatura em PDF"""
    try:
        cartao = db.query(models.CartaoCredito).filter(
            models.CartaoCredito.id == cartao_id,
            models.CartaoCredito.usuario_id == usuario.id,
        ).first()
        if not cartao:
            raise HTTPException(status_code=404, detail="Cartão não encontrado")
        chave_preferida = senhas_pdf_service.chave_para_cartao(cartao.nome)
        dados = _extrair_pdf_com_senhas_configuradas(db, usuario, file.file, "fatura", chave_preferida)
        return importacao_service.persistir_fatura(db, usuario, cartao_id, dados)
    except importacao_service.ImportacaoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.mensagem)
    except senhas_pdf_service.SenhaConfiguradaInvalidaError:
        raise HTTPException(status_code=400, detail="Uma senha salva não pode ser lida. Recadastre-a em Configurações.")
    except SenhaInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falha inesperada ao importar fatura para usuario_id=%s", usuario.id)
        raise HTTPException(status_code=500, detail="Não foi possível processar o arquivo. Tente novamente.")

@router.post("/importar/conta", tags=["Importação"])
def importar_conta(
    file: UploadFile = File(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Importar conta de consumo/serviço em PDF."""
    try:
        dados = _extrair_pdf_com_senhas_configuradas(db, usuario, file.file, "conta")
        return importacao_service.persistir_conta(db, usuario, dados)
    except importacao_service.ImportacaoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.mensagem)
    except senhas_pdf_service.SenhaConfiguradaInvalidaError:
        raise HTTPException(status_code=400, detail="Uma senha salva não pode ser lida. Recadastre-a em Configurações.")
    except SenhaInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Falha inesperada ao importar conta para usuario_id=%s", usuario.id)
        raise HTTPException(status_code=500, detail="Não foi possível processar o arquivo. Tente novamente.")

# ==================== GMAIL ====================

@router.get("/gmail/oauth/iniciar", tags=["Gmail"])
def gmail_oauth_iniciar(usuario: models.Usuario = Depends(get_current_user)):
    """Gera a URL de consentimento do Google para conectar a caixa do Gmail."""
    flow = gmail_auth.montar_flow(state=str(usuario.id))
    url_autorizacao, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return {"url": url_autorizacao}

@router.get("/gmail/oauth/callback", tags=["Gmail"])
def gmail_oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    """Troca o code do Google por um refresh token, grava a conexão do
    usuário e redireciona de volta para a tela de importações pendentes."""
    destino = f"{gmail_settings.frontend_base_url}/importacoes-pendentes"

    usuario_id = None
    usuario = None
    try:
        usuario_id = int(state)
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
        if not usuario:
            raise ValueError("Usuário não encontrado")

        flow = gmail_auth.montar_flow(state=state)
        flow.fetch_token(code=code)
        credenciais = flow.credentials

        if not credenciais.refresh_token:
            raise ValueError(
                "Google não retornou um refresh token. Revogue o acesso do app em "
                "myaccount.google.com/permissions e tente novamente."
            )

        conexao = db.query(models.GmailConexao).filter(models.GmailConexao.usuario_id == usuario.id).first()
        if not conexao:
            conexao = models.GmailConexao(usuario_id=usuario.id)
            db.add(conexao)

        conexao.email_conectado = usuario.email
        conexao.refresh_token = credenciais.refresh_token
        conexao.ativo = True
        conexao.ultimo_erro = None
        notificacoes_service.criar_ou_atualizar(
            db,
            usuario_id=usuario.id,
            chave="gmail:conexao",
            tipo="gmail",
            severidade="success",
            estado="concluida",
            titulo="Gmail conectado",
            mensagem=f"A caixa {conexao.email_conectado} foi conectada com sucesso.",
            rota="/importacoes-pendentes",
            forcar_nao_lida=True,
        )
        db.commit()

        return RedirectResponse(url=f"{destino}?gmail_conectado=1")
    except Exception as e:
        if usuario:
            notificacoes_service.criar_ou_atualizar(
                db,
                usuario_id=usuario_id,
                chave="gmail:conexao",
                tipo="gmail",
                severidade="critical",
                estado="erro",
                titulo="Não foi possível conectar o Gmail",
                mensagem=str(e),
                rota="/importacoes-pendentes",
                forcar_nao_lida=True,
            )
            db.commit()
        return RedirectResponse(url=f"{destino}?gmail_erro={quote(str(e))}")

def _montar_gmail_status(conexao: models.GmailConexao | None) -> schemas.GmailStatus:
    if not conexao:
        return schemas.GmailStatus(conectado=False)

    return schemas.GmailStatus(
        conectado=True,
        email_conectado=conexao.email_conectado,
        ativo=conexao.ativo,
        ultima_sincronizacao=conexao.ultima_sincronizacao,
        ultimo_erro=conexao.ultimo_erro,
        sincronizando=conexao.sincronizando,
        sync_total=conexao.sync_total,
        sync_processados=conexao.sync_processados,
        ultimo_resumo_encontrados=conexao.ultimo_resumo_encontrados,
        ultimo_resumo_novos=conexao.ultimo_resumo_novos,
        ultimo_resumo_erros=conexao.ultimo_resumo_erros,
    )

@router.get("/gmail/status", response_model=schemas.GmailStatus, tags=["Gmail"])
def gmail_status(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conexao = db.query(models.GmailConexao).filter(models.GmailConexao.usuario_id == usuario.id).first()
    return _montar_gmail_status(conexao)

@router.post("/gmail/conexao", response_model=schemas.GmailStatus, tags=["Gmail"])
def gmail_alternar_conexao(
    ativo: bool,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ativa ou desativa a sincronização automática sem apagar o refresh token."""
    conexao = db.query(models.GmailConexao).filter(models.GmailConexao.usuario_id == usuario.id).first()
    if not conexao:
        raise HTTPException(status_code=404, detail="Nenhuma conexão Gmail encontrada para este usuário.")

    conexao.ativo = ativo
    db.commit()

    return _montar_gmail_status(conexao)

def _executar_sync_usuario_background(usuario_id: int) -> None:
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
        if usuario:
            sincronizar_gmail(db, usuario, origem="manual")
    finally:
        db.close()

@router.post("/gmail/sync", tags=["Gmail"])
def gmail_sync_manual(
    background_tasks: BackgroundTasks,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dispara a sincronização com o Gmail em background e retorna imediatamente.
    O progresso fica disponível na central global de notificações."""
    conexao = db.query(models.GmailConexao).filter(
        models.GmailConexao.usuario_id == usuario.id,
        models.GmailConexao.ativo == True,
    ).first()
    if not conexao:
        raise HTTPException(status_code=404, detail="Nenhuma conexão Gmail ativa para este usuário.")

    if conexao.sincronizando:
        iniciado_em = conexao.sync_iniciado_em
        lock_ainda_valido = (
            iniciado_em is not None
            and datetime.utcnow() - iniciado_em < timedelta(minutes=LOCK_TIMEOUT_MINUTOS)
        )
        if lock_ainda_valido:
            return {"iniciado": False, "ja_em_andamento": True}

    background_tasks.add_task(_executar_sync_usuario_background, usuario.id)
    return {"iniciado": True}

# ==================== IMPORTAÇÕES PENDENTES ====================

def _serializar_importacao_pendente(item: models.ImportacaoPendente) -> dict:
    return {
        "id": item.id,
        "usuario_id": item.usuario_id,
        "gmail_message_id": item.gmail_message_id,
        "remetente": item.remetente,
        "assunto": item.assunto,
        "data_recebimento": item.data_recebimento,
        "tipo_detectado": item.tipo_detectado,
        "cartao_id_sugerido": item.cartao_id_sugerido,
        "nome_cartao_detectado": item.nome_cartao_detectado,
        "dados_extraidos": json.loads(item.dados_extraidos_json or "{}"),
        "status": item.status,
        "mensagem_erro": item.mensagem_erro,
        "data_criacao": item.data_criacao,
        "data_revisao": item.data_revisao,
    }

@router.get("/importacoes-pendentes", response_model=schemas.ImportacaoPendentePagina, tags=["Importações pendentes"])
def listar_importacoes_pendentes(
    status: str = None,
    page: int = 1,
    page_size: int = 15,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.ImportacaoPendente).filter(models.ImportacaoPendente.usuario_id == usuario.id)
    if status:
        query = query.filter(models.ImportacaoPendente.status == status)

    total = query.count()
    itens = (
        query.order_by(models.ImportacaoPendente.data_criacao.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_serializar_importacao_pendente(item) for item in itens],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/importacoes-pendentes/{item_id}", response_model=schemas.ImportacaoPendente, tags=["Importações pendentes"])
def obter_importacao_pendente(
    item_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.ImportacaoPendente).filter(
        models.ImportacaoPendente.id == item_id,
        models.ImportacaoPendente.usuario_id == usuario.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Importação pendente não encontrada")
    return _serializar_importacao_pendente(item)

@router.patch("/importacoes-pendentes/{item_id}", response_model=schemas.ImportacaoPendente, tags=["Importações pendentes"])
def atualizar_importacao_pendente(
    item_id: int,
    atualizacao: schemas.ImportacaoPendenteUpdate,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.ImportacaoPendente).filter(
        models.ImportacaoPendente.id == item_id,
        models.ImportacaoPendente.usuario_id == usuario.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Importação pendente não encontrada")
    if item.status != "pendente":
        raise HTTPException(status_code=400, detail="Somente importações pendentes podem ser editadas.")

    dados = atualizacao.dict(exclude_unset=True)
    if "tipo_detectado" in dados:
        item.tipo_detectado = dados["tipo_detectado"]
    if "cartao_id_sugerido" in dados:
        item.cartao_id_sugerido = dados["cartao_id_sugerido"]
    if "dados_extraidos" in dados and dados["dados_extraidos"] is not None:
        item.dados_extraidos_json = json.dumps(dados["dados_extraidos"], ensure_ascii=False, default=str)

    db.commit()
    db.refresh(item)
    return _serializar_importacao_pendente(item)

@router.post("/importacoes-pendentes/{item_id}/confirmar", tags=["Importações pendentes"])
def confirmar_importacao_pendente(
    item_id: int,
    confirmacao: schemas.ImportacaoPendenteConfirmar = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.ImportacaoPendente).filter(
        models.ImportacaoPendente.id == item_id,
        models.ImportacaoPendente.usuario_id == usuario.id,
    ).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail="Importação pendente não encontrada")
    if item.status != "pendente":
        raise HTTPException(status_code=400, detail="Esta importação já foi revisada.")

    # As persistências fazem commit próprio. Reservar o item antes de chamá-las
    # impede que dois cliques/requisições simultâneas confirmem o mesmo anexo.
    item.status = "processando"
    db.commit()

    dados = importacao_service.desserializar_dados_extraidos(json.loads(item.dados_extraidos_json or "{}"))

    try:
        if item.tipo_detectado == "holerite":
            resultado = importacao_service.persistir_holerite(db, usuario, dados)
        elif item.tipo_detectado == "fatura":
            cartao_id = (confirmacao.cartao_id if confirmacao else None) or item.cartao_id_sugerido
            if not cartao_id:
                raise importacao_service.ImportacaoError("Informe o cartão desta fatura para confirmar.")
            resultado = importacao_service.persistir_fatura(db, usuario, cartao_id, dados)
        elif item.tipo_detectado == "conta":
            resultado = importacao_service.persistir_conta(db, usuario, dados)
        else:
            raise importacao_service.ImportacaoError(f"Tipo de importação desconhecido: {item.tipo_detectado}")
    except importacao_service.ImportacaoError as e:
        item.status = "pendente"
        db.commit()
        raise HTTPException(status_code=e.status_code, detail=e.mensagem)
    except Exception:
        item.status = "pendente"
        db.commit()
        raise

    item.status = "confirmada"
    item.data_revisao = datetime.utcnow()
    db.commit()

    return resultado

@router.post("/importacoes-pendentes/{item_id}/rejeitar", response_model=schemas.ImportacaoPendente, tags=["Importações pendentes"])
def rejeitar_importacao_pendente(
    item_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.ImportacaoPendente).filter(
        models.ImportacaoPendente.id == item_id,
        models.ImportacaoPendente.usuario_id == usuario.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Importação pendente não encontrada")
    if item.status not in ("pendente", "erro"):
        raise HTTPException(status_code=400, detail="Esta importação já foi revisada.")

    item.status = "rejeitada"
    item.data_revisao = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serializar_importacao_pendente(item)

def _chave_senha_importacao(item: models.ImportacaoPendente) -> str | None:
    from app.services.gmail_sync import classificar_remetente

    regra = classificar_remetente(item.remetente or "", item.assunto or "")
    if regra:
        return regra.chave
    if item.tipo_detectado == "holerite":
        return "contracheque"
    if item.tipo_detectado == "fatura":
        nome_busca = normalizar_texto_busca(item.nome_cartao_detectado or item.assunto or item.remetente)
        if "ITAU" in nome_busca:
            return "itau"
        if "XP" in nome_busca:
            return "xp"
    return None

def _reprocessar_importacao_com_erro(
    db: Session,
    usuario: models.Usuario,
    item: models.ImportacaoPendente,
) -> None:
    if not item.gmail_message_id or not item.gmail_attachment_id:
        raise HTTPException(status_code=400, detail="Este item não tem referência do anexo do Gmail para reprocessar.")

    conexao = db.query(models.GmailConexao).filter(
        models.GmailConexao.usuario_id == usuario.id,
        models.GmailConexao.ativo == True,
    ).first()
    if not conexao:
        raise HTTPException(status_code=400, detail="Reconecte o Gmail para reprocessar este item.")

    try:
        servico = gmail_auth.montar_cliente_gmail(conexao.refresh_token)
        pdf_bytes = _baixar_anexo(servico, item.gmail_message_id, item.gmail_attachment_id)
        chave_senha = _chave_senha_importacao(item)
        chaves = senhas_pdf_service.chaves_para_tipo(item.tipo_detectado, chave_senha)
        senhas = senhas_pdf_service.obter_senhas(db, usuario.id, chaves)
        dados = senhas_pdf_service.extrair_com_senhas(
            io.BytesIO(pdf_bytes), item.tipo_detectado, senhas, extrair_dados_pdf
        )
    except senhas_pdf_service.SenhaConfiguradaInvalidaError:
        item.mensagem_erro = "Uma senha salva não pode ser lida. Recadastre-a em Configurações."
        db.commit()
        raise HTTPException(status_code=400, detail=item.mensagem_erro)
    except SenhaInvalidaError:
        item.mensagem_erro = "Senha incorreta ou ausente para abrir o PDF."
        db.commit()
        raise HTTPException(status_code=400, detail=item.mensagem_erro)
    except Exception as e:
        item.mensagem_erro = f"Erro ao processar anexo: {type(e).__name__}"
        db.commit()
        raise HTTPException(status_code=400, detail=item.mensagem_erro)

    if dados.get("erro"):
        item.mensagem_erro = dados["erro"]
        db.commit()
        raise HTTPException(status_code=400, detail=item.mensagem_erro)

    item.dados_extraidos_json = json.dumps(dados, ensure_ascii=False, default=str)
    item.mensagem_erro = None

@router.post("/importacoes-pendentes/{item_id}/reabrir", response_model=schemas.ImportacaoPendente, tags=["Importações pendentes"])
def reabrir_importacao_pendente(
    item_id: int,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Volta uma importacao rejeitada ou com erro para 'pendente', para
    corrigir uma rejeicao feita sem querer. Nao se aplica a itens ja
    confirmados, pois confirmar ja criou despesas/faturas reais."""
    item = db.query(models.ImportacaoPendente).filter(
        models.ImportacaoPendente.id == item_id,
        models.ImportacaoPendente.usuario_id == usuario.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Importação pendente não encontrada")
    if item.status not in ("rejeitada", "erro"):
        raise HTTPException(status_code=400, detail="Apenas importações rejeitadas ou com erro podem ser reabertas.")

    if item.status == "erro":
        _reprocessar_importacao_com_erro(db, usuario, item)

    item.status = "pendente"
    item.data_revisao = None
    db.commit()
    db.refresh(item)
    return _serializar_importacao_pendente(item)

# ==================== ANÁLISE ====================

def _montar_dashboard_usuario(
    db: Session,
    usuario: models.Usuario,
    mes: int,
    ano: int,
) -> dict:
    gerar_despesas_pendentes(db, usuario.id)
    receitas = db.query(models.Receita).filter(models.Receita.usuario_id == usuario.id).all()
    despesas = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id).all()
    faturas = db.query(models.Fatura).filter(models.Fatura.usuario_id == usuario.id).all()
    cartoes = db.query(models.CartaoCredito).filter(models.CartaoCredito.usuario_id == usuario.id).all()
    parcelas = db.query(models.Parcela).filter(models.Parcela.usuario_id == usuario.id).all()
    recorrentes = db.query(models.DespesaRecorrente).filter(
        models.DespesaRecorrente.usuario_id == usuario.id,
        models.DespesaRecorrente.ativo == True,  # noqa: E712
    ).all()
    configuracoes = db.query(models.Configuracao).filter(
        models.Configuracao.usuario_id == usuario.id,
        models.Configuracao.preferencia.like(f"{PREFIXO_ORCAMENTO}%"),
    ).all()
    orcamentos = [
        {"categoria": config.preferencia[len(PREFIXO_ORCAMENTO):], "limite": float(config.valor)}
        for config in configuracoes
    ]
    return montar_dashboard(
        receitas, despesas, faturas, cartoes, parcelas, recorrentes, orcamentos, mes, ano
    )

@router.get("/relatorio-anual", tags=["Análise"])
def obter_relatorio_anual(
    ano: int | None = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ano = ano or date.today().year
    receitas = db.query(models.Receita).filter(models.Receita.usuario_id == usuario.id).all()
    despesas = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id).all()
    faturas = db.query(models.Fatura).filter(models.Fatura.usuario_id == usuario.id).all()
    relatorio = montar_relatorio_anual(receitas, despesas, faturas, ano)
    relatorio["anos_disponiveis"] = sorted({item.data.year for item in receitas + despesas} | {item.data_referencia.year for item in faturas}, reverse=True)
    return relatorio


@router.get("/dashboard", tags=["Análise"])
def obter_dashboard(
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna a visão mensal consolidada usada pelo dashboard."""
    if mes is not None and not 1 <= mes <= 12:
        raise HTTPException(status_code=422, detail="O mês deve estar entre 1 e 12")

    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    dashboard = _montar_dashboard_usuario(db, usuario, mes, ano)
    notificacoes_service.sincronizar_alertas_financeiros(db, usuario.id, dashboard["alertas"])
    return dashboard


@router.get("/notificacoes", response_model=schemas.NotificacoesResposta, tags=["Notificações"])
def listar_notificacoes(
    limite: int = 20,
    atualizar_financeiro: bool = True,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    limite = max(1, min(limite, 50))
    if atualizar_financeiro:
        hoje = date.today()
        dashboard = _montar_dashboard_usuario(db, usuario, hoje.month, hoje.year)
        notificacoes_service.sincronizar_alertas_financeiros_se_necessario(
            db, usuario.id, dashboard["alertas"]
        )

    query_ativas = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == usuario.id,
        models.Notificacao.resolvida_em.is_(None),
    )
    nao_lidas = query_ativas.filter(models.Notificacao.lida_em.is_(None)).count()
    items = query_ativas.order_by(
        models.Notificacao.lida_em.is_(None).desc(),
        models.Notificacao.atualizada_em.desc(),
    ).limit(limite).all()
    return {"items": items, "nao_lidas": nao_lidas}


@router.patch("/notificacoes/{notificacao_id}", response_model=schemas.Notificacao, tags=["Notificações"])
def atualizar_leitura_notificacao(
    notificacao_id: int,
    dados: schemas.NotificacaoLeitura,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.Notificacao).filter(
        models.Notificacao.id == notificacao_id,
        models.Notificacao.usuario_id == usuario.id,
        models.Notificacao.resolvida_em.is_(None),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    item.lida_em = datetime.utcnow() if dados.lida else None
    db.commit()
    db.refresh(item)
    return item


@router.post("/notificacoes/marcar-todas-lidas", tags=["Notificações"])
def marcar_todas_notificacoes_lidas(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agora = datetime.utcnow()
    items = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == usuario.id,
        models.Notificacao.resolvida_em.is_(None),
        models.Notificacao.lida_em.is_(None),
    ).all()
    for item in items:
        item.lida_em = agora
    db.commit()
    return {"atualizadas": len(items)}

@router.get("/analise", response_model=schemas.AnaliseGastos, tags=["Análise"])
def obter_analise(
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obter análise de gastos"""
    gerar_despesas_pendentes(db, usuario.id)

    if not mes or not ano:
        hoje = date.today()
        mes = hoje.month
        ano = hoje.year

    receitas = db.query(models.Receita).filter(models.Receita.usuario_id == usuario.id).all()
    despesas = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id).all()
    cartoes = db.query(models.CartaoCredito).filter(models.CartaoCredito.usuario_id == usuario.id).all()
    parcelas = db.query(models.Parcela).filter(models.Parcela.usuario_id == usuario.id).all()

    return calcular_analise_gastos(receitas, despesas, cartoes, parcelas, mes, ano)

@router.get("/previsao", tags=["Análise"])
def obter_previsao(
    meses: int = 3,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obter previsão de gastos futuros"""
    despesas = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id).all()
    parcelas = db.query(models.Parcela).filter(models.Parcela.usuario_id == usuario.id).all()

    return previsao_gastos(despesas, parcelas, meses)

# ==================== ASSISTENTE ====================

@router.get("/assistente/status", response_model=schemas.AssistenteStatus, tags=["Assistente"])
def obter_status_assistente(
    usuario: models.Usuario = Depends(get_current_user),
):
    """Disponibilidade do runtime local (Ollama). Não consulta o banco --
    precisa responder mesmo com o banco de dados degradado."""
    return assistente_service.status()

@router.post("/assistente/carregar-modelo", response_model=schemas.AssistenteCarregarModeloResposta, tags=["Assistente"])
def carregar_modelo_assistente(
    dados: schemas.AssistenteCarregarModelo,
    usuario: models.Usuario = Depends(get_current_user),
):
    """Pré-carrega um modelo instalado em memória no Ollama, pra evitar que a
    primeira pergunta pague o custo de carregamento. Não consulta o banco."""
    return assistente_service.carregar_modelo(dados.modelo)

@router.post("/assistente/perguntar", response_model=schemas.AssistenteResposta, tags=["Assistente"])
def perguntar_ao_assistente(
    dados: schemas.AssistentePergunta,
    usuario: models.Usuario = Depends(get_current_user),
):
    """Assistente text2SQL somente leitura: converte a pergunta em SQL restrito
    às views reconciliadas, executa isolado por usuário e classifica a resposta
    em ok/ressalva/nao_sei. Nunca escreve no banco -- por isso não recebe `db`,
    a própria camada do assistente abre sua conexão dedicada e somente leitura.
    `dados.modelo` é opcional -- o usuário escolhe entre os modelos instalados
    (GET /assistente/status) na página; sem escolha, usa o padrão do servidor."""
    return assistente_service.responder(dados.pergunta, usuario.id, modelo=dados.modelo)

# ==================== WHATSAPP ====================
# Sem Depends(get_current_user): quem chama essas duas rotas é a Meta, não um
# usuário logado -- a autenticação é o verify_token (GET) e a assinatura
# HMAC do corpo (POST), não um JWT.

@router.get("/whatsapp/webhook", tags=["WhatsApp"])
def verificar_webhook_whatsapp(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Handshake de verificação exigido pela Meta ao cadastrar a Webhook URL."""
    if hub_mode != "subscribe" or hub_verify_token != whatsapp_settings.meta_verify_token:
        raise HTTPException(status_code=403, detail="verify_token inválido")
    return Response(content=hub_challenge, media_type="text/plain")

@router.post("/whatsapp/webhook", tags=["WhatsApp"])
async def receber_webhook_whatsapp(request: Request, background_tasks: BackgroundTasks):
    """Recebe eventos de mensagem da Meta. Responde 200 imediatamente e
    processa a pergunta em background -- o assistente pode levar vários
    segundos (chamadas ao Ollama) e a Meta exige um ack rápido."""
    corpo_bruto = await request.body()
    if not whatsapp_service.verificar_assinatura(corpo_bruto, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=403, detail="assinatura inválida")

    payload = json.loads(corpo_bruto)
    extraido = whatsapp_service.extrair_mensagem(payload)
    if extraido:
        wa_id, texto = extraido
        background_tasks.add_task(whatsapp_service.processar_mensagem_em_background, wa_id, texto)
    return {"status": "ok"}

# ==================== ORÇAMENTOS ====================

PREFIXO_ORCAMENTO = "orcamento:"

@router.get("/orcamentos", response_model=List[schemas.Orcamento], tags=["Orçamentos"])
def listar_orcamentos(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar orçamentos mensais por categoria"""
    configuracoes = db.query(models.Configuracao).filter(
        models.Configuracao.usuario_id == usuario.id,
        models.Configuracao.preferencia.like(f"{PREFIXO_ORCAMENTO}%"),
    ).all()

    return [
        schemas.Orcamento(
            categoria=config.preferencia[len(PREFIXO_ORCAMENTO):],
            limite=float(config.valor),
        )
        for config in configuracoes
    ]

@router.put("/orcamentos", response_model=schemas.Orcamento, tags=["Orçamentos"])
def definir_orcamento(
    orcamento: schemas.Orcamento,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Criar ou atualizar o orçamento mensal de uma categoria"""
    if orcamento.limite <= 0:
        raise HTTPException(status_code=400, detail="O limite do orçamento deve ser maior que zero")

    preferencia = f"{PREFIXO_ORCAMENTO}{orcamento.categoria}"
    config = db.query(models.Configuracao).filter(
        models.Configuracao.usuario_id == usuario.id,
        models.Configuracao.preferencia == preferencia,
    ).first()

    if config:
        config.valor = str(orcamento.limite)
        config.data_atualizacao = datetime.utcnow()
    else:
        config = models.Configuracao(
            usuario_id=usuario.id,
            preferencia=preferencia,
            valor=str(orcamento.limite),
        )
        db.add(config)

    db.commit()
    return orcamento

@router.delete("/orcamentos/{categoria}", status_code=204, tags=["Orçamentos"])
def remover_orcamento(
    categoria: str,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remover o orçamento de uma categoria"""
    config = db.query(models.Configuracao).filter(
        models.Configuracao.usuario_id == usuario.id,
        models.Configuracao.preferencia == f"{PREFIXO_ORCAMENTO}{categoria}",
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")

    db.delete(config)
    db.commit()

@router.get("/alertas", tags=["Análise"])
def obter_alertas(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obter alertas sobre a situação financeira"""
    receitas = db.query(models.Receita).filter(models.Receita.usuario_id == usuario.id).all()
    despesas = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id).all()
    cartoes = db.query(models.CartaoCredito).filter(models.CartaoCredito.usuario_id == usuario.id).all()
    parcelas = db.query(models.Parcela).filter(models.Parcela.usuario_id == usuario.id).all()

    return {"alertas": gerar_alertas(receitas, despesas, cartoes, parcelas)}

# ==================== EXPORTAÇÃO ====================

def _csv_response(cabecalho: List[str], linhas: List[list], nome_arquivo: str) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(cabecalho)
    writer.writerows(linhas)

    # BOM UTF-8: garante acentuação correta ao abrir no Excel do Windows
    conteudo = "﻿" + buffer.getvalue()

    return Response(
        content=conteudo,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )

def _nome_arquivo(prefixo: str, mes: int | None, ano: int | None) -> str:
    if mes and ano:
        return f"{prefixo}_{ano}-{mes:02d}.csv"
    if ano:
        return f"{prefixo}_{ano}.csv"
    return f"{prefixo}_todas.csv"

@router.get("/exportar/despesas", tags=["Exportação"])
def exportar_despesas(
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exportar despesas do usuário em CSV"""
    query = db.query(models.Despesa).filter(models.Despesa.usuario_id == usuario.id)
    intervalo = _filtro_mes_ano(mes, ano)
    if intervalo:
        query = query.filter(models.Despesa.data.between(*intervalo))

    despesas = query.order_by(models.Despesa.data).all()
    linhas = [
        [d.data.isoformat(), d.descricao, d.categoria, str(d.valor), d.origem]
        for d in despesas
    ]

    return _csv_response(
        ["Data", "Descrição", "Categoria", "Valor", "Origem"],
        linhas,
        _nome_arquivo("despesas", mes, ano),
    )

@router.get("/exportar/receitas", tags=["Exportação"])
def exportar_receitas(
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exportar receitas do usuário em CSV"""
    query = db.query(models.Receita).filter(models.Receita.usuario_id == usuario.id)
    intervalo = _filtro_mes_ano(mes, ano)
    if intervalo:
        query = query.filter(models.Receita.data.between(*intervalo))

    receitas = query.order_by(models.Receita.data).all()
    linhas = [
        [r.data.isoformat(), r.descricao, str(r.valor), r.origem]
        for r in receitas
    ]

    return _csv_response(
        ["Data", "Descrição", "Valor", "Origem"],
        linhas,
        _nome_arquivo("receitas", mes, ano),
    )

@router.get("/exportar/faturas", tags=["Exportação"])
def exportar_faturas(
    mes: int = None,
    ano: int = None,
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exportar itens de faturas do usuário em CSV (uma linha por compra)"""
    query = db.query(models.Fatura).filter(models.Fatura.usuario_id == usuario.id)
    intervalo = _filtro_mes_ano(mes, ano)
    if intervalo:
        query = query.filter(models.Fatura.data_referencia.between(*intervalo))

    faturas = query.order_by(models.Fatura.data_referencia).all()
    linhas = [
        [
            item.data.isoformat(),
            item.descricao,
            item.categoria,
            str(item.valor),
            fatura.cartao.nome if fatura.cartao else "",
            item.estabelecimento or "",
        ]
        for fatura in faturas
        for item in sorted(fatura.itens, key=lambda i: i.data)
    ]

    return _csv_response(
        ["Data", "Descrição", "Categoria", "Valor", "Cartão", "Estabelecimento"],
        linhas,
        _nome_arquivo("faturas", mes, ano),
    )
