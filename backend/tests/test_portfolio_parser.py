from app.services.parser import extrair_lancamentos_xp


def test_statement_parser_ignores_fictional_holder_and_keeps_purchases():
    rows = [
        'DATA DESCRICAO VALOR',
        'Titular: PESSOA DEMO',
        '01/11/2026 DEMO PAPER SHOP 35,00',
        '02/11/2026 PAGAMENTO RECEBIDO -35,00',
    ]
    purchases = extrair_lancamentos_xp(rows, 2026)
    assert len(purchases) == 1
    assert purchases[0]['valor'] == 35.0
    assert 'DEMO PAPER SHOP' in purchases[0]['descricao']
