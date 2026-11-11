import pytest

from app.services.assistente.validador import SqlRejeitadoError, validar


@pytest.mark.parametrize('dialeto', ['sqlite', 'postgres'])
def test_aspas_incompletas_sao_rejeitadas_sem_escapar_do_contrato(dialeto):
    with pytest.raises(SqlRejeitadoError, match='SQL invalido'):
        validar("SELECT * FROM vw_receitas WHERE descricao = 'incompleto", dialeto)
