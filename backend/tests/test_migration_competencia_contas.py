import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def _carregar_migration():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_path = next(versions_dir.glob("*corrigir_competencia_contas.py"))
    spec = importlib.util.spec_from_file_location("corrigir_competencia_contas", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_corrige_apenas_contas_com_referencia_na_descricao():
    migration = _carregar_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(text("""
            create table despesas (
                id integer primary key,
                descricao varchar(255) not null,
                data date not null,
                origem varchar(50)
            )
        """))
        conn.execute(text("""
            create table importacoes_pendentes (
                id integer primary key,
                tipo_detectado varchar(20) not null,
                status varchar(20) not null,
                dados_extraidos_json text
            )
        """))
        conn.execute(text("""
            insert into despesas (id, descricao, data, origem) values
            (1, 'Conta de gas Naturgy JUN/2026', '2026-07-10', 'conta'),
            (2, 'Internet Nio JUL/2026', '2026-07-13', 'conta'),
            (3, 'Conta de luz Light JUN/2026', '2026-07-03', 'manual'),
            (4, 'Conta de agua', '2026-07-05', 'conta')
        """))
        conn.execute(text("""
            insert into importacoes_pendentes (id, tipo_detectado, status, dados_extraidos_json)
            values (
                5,
                'conta',
                'pendente',
                '{"informacoes_conta":{"referencia":"JUN/2026"},"despesas":[{"data":"2026-07-10"}]}'
            )
        """))

        migration.recalcular_competencia_contas(conn)
        registros = dict(conn.execute(text("select id, data from despesas order by id")).all())
        dados_pendentes = conn.execute(text(
            "select dados_extraidos_json from importacoes_pendentes where id = 5"
        )).scalar_one()

    assert str(registros[1]) == "2026-06-01"
    assert str(registros[2]) == "2026-07-01"
    assert str(registros[3]) == "2026-07-03"
    assert str(registros[4]) == "2026-07-05"
    assert '"data": "2026-06-01"' in dados_pendentes
