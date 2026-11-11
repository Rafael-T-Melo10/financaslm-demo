import base64
import hashlib
import unicodedata
from datetime import datetime
from typing import Callable, Iterable

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app import models
from app.security import SECRET_KEY
from app.services.parser import SenhaInvalidaError


INSTITUICOES = ("itau", "xp", "naturgy", "light", "nio", "contracheque")
CHAVES_POR_TIPO = {
    "fatura": ("itau", "xp"),
    "conta": ("naturgy", "light", "nio"),
    "holerite": ("contracheque",),
}


class SenhaConfiguradaInvalidaError(Exception):
    """A senha cifrada não pode ser lida com a chave atual da aplicação."""


def _fernet() -> Fernet:
    material = f"gastos:senhas-pdf:v1:{SECRET_KEY}".encode("utf-8")
    chave = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(chave)


def _normalizar(valor: str) -> str:
    texto = unicodedata.normalize("NFD", (valor or "").upper())
    return "".join(caractere for caractere in texto if caractere.isalnum())


def chave_para_cartao(nome_cartao: str | None) -> str | None:
    nome = _normalizar(nome_cartao or "")
    if "ITAU" in nome:
        return "itau"
    if "XP" in nome:
        return "xp"
    return None


def chaves_para_tipo(tipo: str, preferida: str | None = None) -> list[str]:
    chaves = list(CHAVES_POR_TIPO.get(tipo, ()))
    if preferida in chaves:
        return [preferida, *[chave for chave in chaves if chave != preferida]]
    return chaves


def _decifrar(valor_criptografado: str) -> str:
    try:
        return _fernet().decrypt(valor_criptografado.encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as erro:
        raise SenhaConfiguradaInvalidaError from erro


def obter_status(db: Session, usuario_id: int) -> dict[str, dict]:
    registros = {
        registro.instituicao: registro
        for registro in db.query(models.SenhaPdf).filter(models.SenhaPdf.usuario_id == usuario_id).all()
    }
    status = {}
    for instituicao in INSTITUICOES:
        registro = registros.get(instituicao)
        legivel = False
        if registro:
            try:
                _decifrar(registro.valor_criptografado)
                legivel = True
            except SenhaConfiguradaInvalidaError:
                pass
        status[instituicao] = {
            "configurada": registro is not None,
            "legivel": legivel,
            "atualizada_em": registro.data_atualizacao if registro else None,
        }
    return status


def atualizar(db: Session, usuario_id: int, instituicao: str, senha: str) -> None:
    registro = db.query(models.SenhaPdf).filter(
        models.SenhaPdf.usuario_id == usuario_id,
        models.SenhaPdf.instituicao == instituicao,
    ).first()
    valor_criptografado = _fernet().encrypt(senha.encode("utf-8")).decode("utf-8")
    if registro:
        registro.valor_criptografado = valor_criptografado
        registro.data_atualizacao = datetime.utcnow()
        return
    db.add(models.SenhaPdf(
        usuario_id=usuario_id,
        instituicao=instituicao,
        valor_criptografado=valor_criptografado,
    ))


def remover(db: Session, usuario_id: int, instituicao: str) -> None:
    db.query(models.SenhaPdf).filter(
        models.SenhaPdf.usuario_id == usuario_id,
        models.SenhaPdf.instituicao == instituicao,
    ).delete(synchronize_session=False)


def obter_senhas(db: Session, usuario_id: int, instituicoes: Iterable[str]) -> list[str]:
    chaves = list(dict.fromkeys(chave for chave in instituicoes if chave in INSTITUICOES))
    if not chaves:
        return []
    registros = db.query(models.SenhaPdf).filter(
        models.SenhaPdf.usuario_id == usuario_id,
        models.SenhaPdf.instituicao.in_(chaves),
    ).all()
    por_chave = {registro.instituicao: registro for registro in registros}
    senhas = []
    for chave in chaves:
        registro = por_chave.get(chave)
        if not registro:
            continue
        senha = _decifrar(registro.valor_criptografado)
        if senha not in senhas:
            senhas.append(senha)
    return senhas


def extrair_com_senhas(
    arquivo,
    tipo: str,
    senhas: Iterable[str],
    extrator: Callable,
):
    """Tenta o PDF aberto e, se necessário, cada senha sem reutilizar o stream."""
    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
    try:
        return extrator(arquivo, tipo, senha=None)
    except SenhaInvalidaError as erro_original:
        for senha in senhas:
            if hasattr(arquivo, "seek"):
                arquivo.seek(0)
            try:
                return extrator(arquivo, tipo, senha=senha)
            except SenhaInvalidaError:
                continue
        raise erro_original
