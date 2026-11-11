# API notes

Use `/docs` on the backend for the generated OpenAPI contract. Sign in with `POST /auth/login` and JSON fields `email` and `senha`. Send the resulting token as `Authorization: Bearer <token>`; never put tokens in URLs or commit them.

| Feature | Endpoints |
|---|---|
| Current user | `GET /usuarios/me` |
| Income / expenses | `/receitas`, `/despesas` |
| Cards / installments | `/cartoes`, `/parcelas` |
| Recurring expenses | `/despesas-recorrentes` |
| Dashboard / analysis | `/dashboard`, `/analise`, `/relatorio-anual` |
| Payroll / bill imports | `POST /importar/holerite`, `/importar/conta` |
| Card statement import | `POST /importar/fatura?cartao_id={id}` |
| Pending-import review | `/importacoes-pendentes` |
| Optional assistant status | `GET /assistente/status` |

PDF imports use multipart form field `file`. Never test with real bank or payroll documents in a shared demo. The bundled fictional pay statement is suitable for the payroll route.

Ownership is enforced by the authenticated user on finance resources. The optional family-sharing feature deliberately allows configured sharing; no family is seeded, so Alex and Sam are independent accounts.

Gmail OAuth, sync and WhatsApp webhook handlers remain available in the source, but the demo configuration supplies no credentials and disables their workers. Their automated tests use controlled fixtures and mocks, not live providers.
