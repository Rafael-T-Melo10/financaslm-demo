import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def _carregar_migration():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_path = next(versions_dir.glob("*corrigir_competencia_faturas_legadas.py"))
    spec = importlib.util.spec_from_file_location("corrigir_competencia_faturas_legadas", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_corrige_competencia_legada_e_despesa_vinculada():
    migration = _carregar_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(text("""
            create table despesas (
                id integer primary key,
                data date not null
            )
        """))
        conn.execute(text("""
            create table faturas (
                id integer primary key,
                despesa_id integer,
                vencimento date,
                data_referencia date not null
            )
        """))
        conn.execute(text("""
            create table fatura_itens (
                id integer primary key,
                fatura_id integer not null,
                data date
            )
        """))

        conn.execute(text("insert into despesas (id, data) values (8, '2026-07-10')"))
        conn.execute(text("""
            insert into faturas (id, despesa_id, vencimento, data_referencia)
            values (7, 8, '2026-07-10', '2026-07-10')
        """))
        conn.execute(text("insert into fatura_itens (id, fatura_id, data) values (1, 7, '2026-05-25')"))
        conn.execute(text("insert into fatura_itens (id, fatura_id, data) values (2, 7, '2026-06-04')"))
        conn.execute(text("insert into fatura_itens (id, fatura_id, data) values (3, 7, '2026-06-15')"))

        migration.recalcular_competencia_faturas(conn)

        data_fatura = conn.execute(text("select data_referencia from faturas where id = 7")).scalar_one()
        data_despesa = conn.execute(text("select data from despesas where id = 8")).scalar_one()

    assert str(data_fatura) == "2026-06-01"
    assert str(data_despesa) == "2026-06-01"
