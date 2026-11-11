import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const saida = path.join(raiz, '.demo/e2e')
const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:3012'
const browser = await chromium.launch({ ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}), headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const resultados = []
const erros = []
const mensagensDialogo = []
page.on('pageerror', e => erros.push(e.message))
page.on('dialog', d => { mensagensDialogo.push(d.message()); return d.accept() })
await fs.mkdir(saida, { recursive: true })
const hoje = new Date().toISOString().slice(0, 10)
const email = `e2e-${Date.now()}@example.org`
const senha = 'Validacao2026!'
async function etapa(nome, acao) {
  try { await acao(); resultados.push({ nome, status: 'aprovado' }); console.log('OK', nome) }
  catch (e) { resultados.push({ nome, status: 'falha', erro: e.message }); await page.screenshot({ path: path.join(saida, 'falha-interface.png'), fullPage: true }); throw e }
  finally { await fs.writeFile(path.join(saida, 'interface.json'), JSON.stringify({ data: new Date().toISOString(), resultados, erros }, null, 2)) }
}
async function ir(rota) { await page.goto(base + rota); await page.waitForLoadState('networkidle') }
async function gravar(nome) { await page.screenshot({ path: path.join(saida, nome + '.png'), fullPage: true }) }
async function presente(texto) { await page.getByText(texto, { exact: true }).first().waitFor() }
async function selecionar(locator, nome) { await locator.click(); await page.getByRole('option', { name: nome, exact: true }).click() }

try {
 await etapa('Cadastro e login automatico', async () => {
  await ir('/cadastro'); await page.locator('#nome').fill('Validacao da entrega'); await page.locator('#email').fill(email)
  await page.getByPlaceholder('Sua senha').fill(senha); await page.getByRole('button', { name: 'Cadastrar', exact: true }).click()
  await page.waitForURL(base + '/'); await page.waitForLoadState('networkidle')
 })
 await etapa('Receita: cadastrar, recarregar, editar e exportar CSV', async () => {
  await ir('/receitas'); await page.getByRole('button', { name: 'Nova receita', exact: true }).click()
  await page.locator('#descricao').fill('Receita E2E'); await page.getByRole('spinbutton').fill('1000'); await page.locator('#data').fill(hoje)
  await page.getByRole('button', { name: 'Adicionar receita' }).click(); await presente('Receita E2E'); await page.reload(); await presente('Receita E2E')
  await page.getByRole('button', { name: 'Editar', exact: true }).click(); await page.locator('#descricao').fill('Receita E2E revisada')
  await page.getByRole('button', { name: 'Salvar receita' }).click(); await presente('Receita E2E revisada')
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: 'Exportar CSV' }).click()
  await (await download).saveAs(path.join(saida, 'receitas-sinteticas.csv')); await gravar('receitas')
 })
 await etapa('Despesa: cadastro, persistencia, edicao e exclusao', async () => {
  await ir('/despesas'); await page.getByRole('button', { name: 'Nova despesa' }).click()
  await page.locator('#descricao').fill('Despesa E2E'); await page.getByRole('spinbutton').fill('100'); await page.locator('#data').fill(hoje)
  await selecionar(page.locator('form').getByRole('combobox'), 'Alimentação')
  await page.getByRole('button', { name: 'Adicionar despesa' }).click(); await presente('Despesa E2E'); await page.reload(); await presente('Despesa E2E')
  await page.getByRole('button', { name: 'Editar', exact: true }).click(); await page.locator('#descricao').fill('Despesa E2E revisada')
  await page.getByRole('button', { name: 'Salvar despesa' }).click(); await presente('Despesa E2E revisada'); await gravar('despesas')
  await page.getByRole('button', { name: 'Apagar', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: 'Apagar', exact: true }).click()
  await page.getByText('Despesa E2E revisada', { exact: true }).waitFor({ state: 'hidden' })
 })
 await etapa('Cartao e compra parcelada', async () => {
  await ir('/cartoes'); await page.getByRole('button', { name: 'Novo cartão', exact: true }).click()
  await page.getByPlaceholder('Ex: Itaú Platinum').fill('Cartao E2E'); await page.getByPlaceholder('1234').fill('1234')
  await page.getByRole('spinbutton').first().fill('3000'); await selecionar(page.getByRole('combobox'), 'Visa')
  await page.getByRole('button', { name: 'Adicionar cartão' }).click(); await presente('Cartao E2E'); await page.reload(); await presente('Cartao E2E'); await gravar('cartoes')
  await ir('/parcelas'); await page.getByRole('button', { name: 'Nova parcela' }).click(); await page.locator('#descricao').fill('Notebook E2E')
  await selecionar(page.locator('form').getByRole('combobox'), /Cartao E2E$/)
  await page.getByRole('spinbutton').nth(0).fill('600'); await page.getByRole('spinbutton').nth(1).fill('3'); await page.locator('#data_inicio').fill(hoje)
  await page.getByRole('button', { name: 'Adicionar parcela' }).click(); await presente('Notebook E2E'); await page.reload(); await presente('Notebook E2E'); await gravar('parcelas')
 })
 await etapa('Recorrencia e persistencia', async () => {
  await ir('/recorrentes'); await page.getByRole('button', { name: 'Nova recorrência', exact: true }).click()
  await page.getByPlaceholder('Ex: Netflix, Aluguel').fill('Assinatura E2E'); await page.getByRole('spinbutton').first().fill('30')
  await page.locator('input[type=date]').fill(hoje); await page.getByRole('button', { name: 'Adicionar recorrência' }).click()
  await presente('Assinatura E2E'); await page.reload(); await presente('Assinatura E2E'); await gravar('recorrentes')
 })
 await etapa('Familia e configuracoes de PDF', async () => {
  await ir('/configuracoes'); await page.locator('#nome-familia').fill('Familia E2E'); await page.getByRole('button', { name: 'Criar família' }).click()
  await presente('Familia E2E'); await page.reload(); await presente('Familia E2E'); await gravar('familia')
  await page.getByRole('tab', { name: 'Senhas de PDF' }).click(); await page.locator('#senha-itau').fill('senha-pdf-sintetica')
  await page.getByRole('button', { name: 'Salvar alterações' }).click(); await page.waitForLoadState('networkidle'); await gravar('configuracoes-pdf')
 })
 await etapa('Importacao e Gmail sem conexao: estados e erro controlado', async () => {
  await ir('/importar'); await page.locator('#arquivo-contracheque').setInputFiles({ name: 'invalido.pdf', mimeType: 'application/pdf', buffer: Buffer.from('documento invalido') })
  await page.getByRole('button', { name: 'Importar contracheque' }).click(); await page.waitForLoadState('networkidle'); await gravar('importacao-erro')
  assert.ok(mensagensDialogo.some(m => m.startsWith('Erro ao importar contracheque:')))
  const pdfPage = await browser.newPage()
  await pdfPage.setContent('<h1>CONTRACHEQUE Folha 07/2026</h1><p>001 - SALARIO BASE 1.200,00</p><p>901 - INSS 200,00</p><p>LIQUIDO A RECEBER 1.000,00</p>')
  const pdf = await pdfPage.pdf(); await pdfPage.close()
  await page.locator('#arquivo-contracheque').setInputFiles({ name: 'holerite-sintetico.pdf', mimeType: 'application/pdf', buffer: pdf })
  const importado = page.waitForResponse(r => r.url().endsWith('/importar/holerite') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Importar contracheque' }).click()
  const resposta = await importado; assert.equal(resposta.status(), 200); assert.equal((await resposta.json()).receitas, 1)
  await gravar('importacao-sucesso')
  await ir('/importacoes-pendentes'); await presente('Nenhuma caixa de Gmail conectada'); await gravar('pendentes')
 })
 await etapa('Dashboard, orcamento e notificacoes', async () => {
  await ir('/'); await gravar('dashboard')
  const botao = page.getByRole('button', { name: 'Editar orçamentos' })
  if (!await botao.isVisible()) await page.getByRole('tab', { name: /Análises/ }).click()
  await botao.click(); const dialog = page.getByRole('dialog')
  await selecionar(dialog.getByRole('combobox'), 'Alimentação'); await dialog.getByRole('spinbutton').fill('500')
  await dialog.getByRole('spinbutton').press('Tab')
  await dialog.getByRole('button', { name: 'Adicionar', exact: true }).click(); await presente('R$ 500,00'); await gravar('orcamento')
  await page.keyboard.press('Escape'); await page.getByRole('button', { name: 'Abrir notificações' }).click(); await gravar('notificacoes')
 })
 await etapa('Assistente: modelos disponiveis e interface', async () => {
  await ir('/assistente'); await presente('assistente desabilitado por configuracao')
  await gravar('assistente')
 })
 await etapa('Layout movel sem transbordamento global', async () => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const rota of ['/', '/despesas', '/assistente', '/configuracoes']) {
   await ir(rota); const tamanho = await page.evaluate(() => ({ largura: document.documentElement.clientWidth, conteudo: document.documentElement.scrollWidth }))
   assert.ok(tamanho.conteudo <= tamanho.largura + 2, `${rota}: ${JSON.stringify(tamanho)}`)
   await gravar('movel-' + (rota.slice(1) || 'dashboard'))
  }
 })
 await etapa('Logout e erro de autenticacao', async () => {
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.getByRole('button', { name: 'Sair', exact: true }).click(); await page.waitForURL(base + '/login')
  await page.locator('#email').fill(email); await page.getByPlaceholder('Sua senha').fill('senha-errada'); await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await presente('Não foi possível entrar'); await gravar('login-erro')
  await page.getByPlaceholder('Sua senha').fill(senha); await page.getByRole('button', { name: 'Entrar', exact: true }).click(); await page.waitForURL(base + '/')
 })
 assert.deepEqual(erros, [], 'Erros JavaScript no navegador')
} finally { await browser.close() }
