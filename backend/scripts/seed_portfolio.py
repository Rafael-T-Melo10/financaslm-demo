"""Populate only an explicitly designated portfolio database with synthetic data."""
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal, engine
from app.models import Usuario, Receita, Despesa, CartaoCredito, Parcela, DespesaRecorrente, Configuracao
from app.security import gerar_hash_senha


def seed():
    if os.environ.get('PORTFOLIO_DEMO') != '1' or 'portfolio' not in str(engine.url.database):
        raise RuntimeError('Requires PORTFOLIO_DEMO=1 and a database name containing portfolio.')
    password = os.environ.get('DEMO_PASSWORD', '')
    if len(password) < 12:
        raise RuntimeError('Set DEMO_PASSWORD to at least 12 characters.')
    with SessionLocal.begin() as db:
        existing = db.query(Usuario).all()
        expected = {'alex@example.com', 'sam@example.com'}
        if existing:
            if {u.email for u in existing} == expected and all(u.nome.startswith('DEMO -') for u in existing):
                print('Portfolio users already exist; nothing changed.')
                return
            raise RuntimeError('Refusing to seed a database that already contains other users.')
        alex = Usuario(nome='DEMO - Alex', email='alex@example.com', senha=gerar_hash_senha(password))
        sam = Usuario(nome='DEMO - Sam', email='sam@example.com', senha=gerar_hash_senha(password))
        db.add_all([alex, sam])
        db.flush()
        today = date.today()
        for offset in range(3):
            month = (today.year * 12 + today.month - 1) - offset
            year, month = month // 12, month % 12 + 1
            db.add(Receita(usuario_id=alex.id, descricao='DEMO - Design project', valor=Decimal('4800'),
                          data=date(year, month, 1), origem='manual'))
            db.add(Receita(usuario_id=alex.id, descricao='DEMO - Support work', valor=Decimal('1200'),
                          data=date(year, month, 5), origem='manual'))
            for day, name, amount, category in [
                (2, 'Workspace', '950', 'Moradia'), (3, 'Groceries', '380', 'Alimentação'),
                (4, 'Transport', '120', 'Transporte'), (5, 'Software tools', '89', 'Assinaturas'),
                (6, 'Office supplies', '145', 'Outros'), (7, 'Coffee with team', '65', 'Alimentação'),
            ]:
                db.add(Despesa(usuario_id=alex.id, descricao='DEMO - ' + name, valor=Decimal(amount),
                              categoria=category, data=date(year, month, day), origem='manual'))
        card = CartaoCredito(usuario_id=alex.id, nome='DEMO - Example Card', bandeira='Demo',
                             ultimos_digitos='0000', limite=Decimal('3000'), data_vencimento=20)
        db.add(card)
        db.flush()
        db.add(Parcela(usuario_id=alex.id, cartao_id=card.id, descricao='DEMO - Office chair',
                       valor_total=Decimal('600'), parcelas_restantes=3, total_parcelas=3,
                       valor_parcela=Decimal('200'), data_inicio=today.replace(day=1),
                       data_proxima_parcela=today.replace(day=20)))
        db.add(DespesaRecorrente(usuario_id=alex.id, descricao='DEMO - Internet service', valor=Decimal('100'),
                                categoria='Moradia', dia_vencimento=15, data_inicio=today.replace(day=1)))
        db.add(Despesa(usuario_id=sam.id, descricao='DEMO - Private to Sam', valor=Decimal('42'),
                      categoria='Outros', data=today, origem='manual'))
    print('Created two separate fictional accounts and three months of sample finances.')


if __name__ == '__main__':
    seed()
