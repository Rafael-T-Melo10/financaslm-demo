<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">PDFs</p>
        <h1>Importar</h1>
        <p>Capture contracheques e faturas sem cadastrar tudo manualmente.</p>
      </div>
    </section>

    <section class="metric-grid">
      <div class="metric-card">
        <span>Faturas importadas</span>
        <strong>{{ faturas.length }}</strong>
        <small>{{ formatarMoeda(totalFaturas) }} em faturas</small>
      </div>
      <div class="metric-card">
        <span>Última fatura</span>
        <strong>{{ formatarMoeda(faturas[0]?.valor_total || 0) }}</strong>
        <small>{{ faturas[0] ? formatarData(faturas[0].data_referencia) : 'Sem faturas' }}</small>
      </div>
      <div class="metric-card">
        <span>Cartões disponíveis</span>
        <strong>{{ cartoes.length }}</strong>
        <small>Use um cartão para importar faturas</small>
      </div>
    </section>

    <section class="tabs">
      <Button
        v-for="aba in abas"
        :key="aba"
        type="button"
        :label="aba"
        :severity="abaAtiva === aba ? 'primary' : 'secondary'"
        :text="abaAtiva !== aba"
        @click="abaAtiva = aba"
      />
    </section>

    <section class="import-grid">
      <Card class="panel">
        <template #title>{{ tituloImportacao }}</template>
        <template #subtitle>{{ descricaoImportacao }}</template>
        <template #content>
          <form v-if="abaAtiva === 'Contracheque'" class="import-form" @submit.prevent="importarContracheque">
            <label for="arquivo-contracheque">Arquivo PDF</label>
            <input id="arquivo-contracheque" ref="inputContracheque" type="file" accept=".pdf" required />
            <Button type="submit" :label="carregandoContracheque ? 'Processando...' : 'Importar contracheque'" :disabled="carregandoContracheque" />
          </form>

          <form v-else-if="abaAtiva === 'Fatura'" class="import-form" @submit.prevent="importarFatura">
            <label for="cartao-select">Cartão</label>
            <Select
              id="cartao-select"
              v-model="cartaoSelecionado"
              :options="cartoes"
              option-label="nome"
              option-value="id"
              placeholder="Selecione um cartão"
              required
            />

            <label for="arquivo-fatura">Arquivo PDF</label>
            <input id="arquivo-fatura" ref="inputFatura" type="file" accept=".pdf" required />

            <Button type="submit" :label="carregandoFatura ? 'Processando...' : 'Importar fatura'" :disabled="carregandoFatura || !cartoes.length" />
          </form>

          <form v-else class="import-form" @submit.prevent="importarConta">
            <label for="arquivo-conta">Arquivo PDF</label>
            <input id="arquivo-conta" ref="inputConta" type="file" accept=".pdf" required />

            <Button type="submit" :label="carregandoConta ? 'Processando...' : 'Importar conta'" :disabled="carregandoConta" />
          </form>

          <div v-if="resultadoContracheque && abaAtiva === 'Contracheque'" class="result ok">
            <strong>{{ resultadoContracheque.mensagem }}</strong>
            <span>{{ resultadoContracheque.receitas }} receita(s) importada(s)</span>
          </div>

          <div v-if="resultadoFatura && abaAtiva === 'Fatura'" class="result ok">
            <strong>{{ resultadoFatura.mensagem }}</strong>
            <div class="result-grid">
              <span>Total: {{ formatarMoeda(resultadoFatura.total_fatura) }}</span>
              <span>Compras: {{ resultadoFatura.compras_importadas || 0 }}</span>
              <span>Parcelas: {{ resultadoFatura.parcelas_importadas || 0 }}</span>
              <span>Soma: {{ formatarMoeda(totalItens(resultadoFatura.fatura?.itens)) }}</span>
            </div>
          </div>

          <div v-if="resultadoConta && abaAtiva === 'Conta'" class="result ok">
            <strong>{{ resultadoConta.mensagem }}</strong>
            <div class="result-grid">
              <span>Total: {{ formatarMoeda(resultadoConta.total) }}</span>
              <span>Fornecedor: {{ resultadoConta.informacoes_conta?.fornecedor || '-' }}</span>
              <span>Vencimento: {{ formatarData(resultadoConta.informacoes_conta?.vencimento) }}</span>
            </div>
          </div>
        </template>
      </Card>

      <Card class="panel side-panel">
        <template #title>Conferência</template>
        <template #subtitle>Use o arquivo correto para cada importação.</template>
        <template #content>
          <ul class="check-list">
            <li>Contracheque salva apenas o líquido a receber.</li>
            <li>Fatura exige um cartão selecionado.</li>
            <li>Conta salva luz, gás ou internet como despesa de moradia.</li>
            <li>PDF errado na fatura é recusado antes de salvar.</li>
          </ul>
        </template>
      </Card>
    </section>

    <Card class="history-panel">
      <template #title>Faturas importadas</template>
      <template #subtitle>{{ faturas.length }} fatura(s) no histórico</template>
      <template #content>
      <div v-if="faturas.length" class="history-layout">
        <div class="invoice-list">
          <button
            v-for="fatura in faturas"
            :key="fatura.id"
            type="button"
            class="invoice-item"
            :class="{ active: faturaSelecionadaId === fatura.id }"
            @click="faturaSelecionadaId = fatura.id"
          >
            <span>{{ nomeCartao(fatura.cartao_id) }}</span>
            <strong>{{ formatarMoeda(fatura.valor_total) }}</strong>
            <small>{{ fatura.itens.length }} compra(s) - {{ formatarData(fatura.data_referencia) }}</small>
          </button>
        </div>

        <div v-if="faturaSelecionada" class="invoice-detail">
          <div class="summary-grid">
            <div>
              <span>Vencimento</span>
              <strong>{{ formatarData(faturaSelecionada.vencimento) }}</strong>
            </div>
            <div>
              <span>Valor total</span>
              <strong>{{ formatarMoeda(faturaSelecionada.valor_total) }}</strong>
            </div>
            <div>
              <span>Compras</span>
              <strong>{{ faturaSelecionada.itens.length }}</strong>
            </div>
          </div>

          <DataTable :value="faturaSelecionada.itens" data-key="id" responsive-layout="scroll" striped-rows>
            <Column field="data" header="Data">
              <template #body="{ data }">{{ formatarData(data.data) }}</template>
            </Column>
            <Column field="descricao" header="Compra" />
            <Column header="Categoria">
              <template #body="{ data }">
                <Tag :value="data.categoria || 'Outros'" severity="info" />
              </template>
            </Column>
            <Column field="valor" header="Valor" body-class="right" header-class="right">
              <template #body="{ data }">
                <span class="valor">{{ formatarMoeda(data.valor) }}</span>
              </template>
            </Column>
          </DataTable>
        </div>
      </div>

      <div v-else class="empty-state">
        <strong>Nenhuma fatura importada</strong>
        <p>Selecione a aba Fatura e envie o PDF do cartão.</p>
      </div>
      </template>
    </Card>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { cartoesAPI, faturasAPI, importacaoAPI } from '../api/client'

const abas = ['Contracheque', 'Fatura', 'Conta']
const abaAtiva = ref('Contracheque')
const inputContracheque = ref(null)
const inputFatura = ref(null)
const inputConta = ref(null)
const carregandoContracheque = ref(false)
const carregandoFatura = ref(false)
const carregandoConta = ref(false)
const resultadoContracheque = ref(null)
const resultadoFatura = ref(null)
const resultadoConta = ref(null)
const cartoes = ref([])
const faturas = ref([])
const cartaoSelecionado = ref('')
const faturaSelecionadaId = ref(null)


const tituloImportacao = computed(() => {
  if (abaAtiva.value === 'Contracheque') return 'Importar contracheque'
  if (abaAtiva.value === 'Fatura') return 'Importar fatura'
  return 'Importar conta'
})

const descricaoImportacao = computed(() => {
  if (abaAtiva.value === 'Contracheque') return 'O líquido a receber será salvo como receita.'
  if (abaAtiva.value === 'Fatura') return 'As compras serão separadas em itens da fatura.'
  return 'Contas de luz, gás e internet serão salvas como despesas de moradia.'
})

const faturaSelecionada = computed(() => (
  faturas.value.find((fatura) => fatura.id === faturaSelecionadaId.value)
))

const totalFaturas = computed(() => (
  faturas.value.reduce((total, fatura) => total + Number(fatura.valor_total || 0), 0)
))

onMounted(async () => {
  await carregarDados()
})

const carregarDados = async () => {
  try {
    const [cartoesResponse, faturasResponse] = await Promise.all([
      cartoesAPI.listar(),
      faturasAPI.listar()
    ])

    cartoes.value = cartoesResponse.data
    faturas.value = faturasResponse.data

    if (!faturaSelecionadaId.value && faturas.value.length) {
      faturaSelecionadaId.value = faturas.value[0].id
    }
  } catch (erro) {
    console.error('Erro ao carregar dados de importação:', erro)
  }
}

const importarContracheque = async () => {
  try {
    carregandoContracheque.value = true
    const arquivo = inputContracheque.value.files[0]
    const response = await importacaoAPI.contracheque(arquivo)

    resultadoContracheque.value = response.data
    inputContracheque.value.value = ''
  } catch (erro) {
    alert('Erro ao importar contracheque: ' + (erro.response?.data?.detail || erro.message))
  } finally {
    carregandoContracheque.value = false
  }
}

const importarFatura = async () => {
  try {
    carregandoFatura.value = true
    const arquivo = inputFatura.value.files[0]
    const response = await importacaoAPI.fatura(cartaoSelecionado.value, arquivo)

    resultadoFatura.value = response.data
    inputFatura.value.value = ''
    cartaoSelecionado.value = ''
    await carregarDados()

    if (response.data.fatura?.id) {
      faturaSelecionadaId.value = response.data.fatura.id
    }
  } catch (erro) {
    alert('Erro ao importar fatura: ' + (erro.response?.data?.detail || erro.message))
  } finally {
    carregandoFatura.value = false
  }
}


const importarConta = async () => {
  try {
    carregandoConta.value = true
    const arquivo = inputConta.value.files[0]
    const response = await importacaoAPI.conta(arquivo)

    resultadoConta.value = response.data
    inputConta.value.value = ''
    await carregarDados()
  } catch (erro) {
    alert('Erro ao importar conta: ' + (erro.response?.data?.detail || erro.message))
  } finally {
    carregandoConta.value = false
  }
}

const totalItens = (itens = []) => (
  itens.reduce((total, item) => total + Number(item.valor || 0), 0)
)

const nomeCartao = (cartaoId) => {
  const cartao = cartoes.value.find((item) => item.id === cartaoId)
  return cartao ? cartao.nome : `Cartão ${cartaoId}`
}

const formatarMoeda = (valor) => (
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(Number(valor || 0))
)

const formatarData = (valor) => {
  if (!valor) return '-'
  const [ano, mes, dia] = String(valor).split('-')
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : String(valor)
}
</script>

<style scoped>
.page {
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
}

.page-head {
  margin-bottom: 1.25rem;
}

.eyebrow {
  color: var(--primary-strong);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  margin-bottom: 0.4rem;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 2.8rem);
}

.page-head p,
.metric-card span,
.metric-card small,
.invoice-item small,
.summary-grid span {
  color: var(--muted);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.metric-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: var(--shadow);
  padding: 1.1rem;
}

.metric-card span {
  display: block;
  margin-bottom: 0.4rem;
}

.metric-card strong {
  display: block;
  font-size: 1.45rem;
}

.tabs {
  display: inline-flex;
  gap: 0.35rem;
  padding: 0.35rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
  margin-bottom: 1rem;
}

.import-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 1rem;
  margin-bottom: 1rem;
}

.panel,
.history-panel {
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.import-form {
  display: grid;
  gap: 0.8rem;
}

.import-form label {
  font-weight: 800;
}

.import-form input[type='file'] {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 12px;
  font: inherit;
  padding: 0.8rem 0.9rem;
}

.import-form :deep(.p-select) {
  width: 100%;
}

.result {
  border-radius: 14px;
  margin-top: 1rem;
  padding: 1rem;
}

.result.ok {
  background: rgba(31, 157, 99, 0.12);
  color: var(--success);
}

.result strong,
.result span {
  display: block;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  margin-top: 0.7rem;
}

.check-list {
  display: grid;
  gap: 0.8rem;
  color: var(--text);
  padding-left: 1.1rem;
}

.history-panel {
  margin-top: 1rem;
}

.history-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 1rem;
}

.invoice-list {
  display: grid;
  gap: 0.7rem;
  align-content: start;
}

.invoice-item {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface-inset);
  cursor: pointer;
  display: grid;
  gap: 0.2rem;
  padding: 0.9rem;
  text-align: left;
}

.invoice-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(44, 109, 223, 0.12);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.summary-grid > div {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.9rem;
  background: var(--surface-inset);
}

.summary-grid span,
.summary-grid strong {
  display: block;
}

.valor {
  font-weight: 800;
}

.right {
  text-align: right;
}

.empty-state {
  padding: 2rem;
  color: var(--muted);
}

.empty-state strong {
  color: var(--text);
  display: block;
  margin-bottom: 0.35rem;
}

@media (max-width: 920px) {
  .metric-grid,
  .import-grid,
  .history-layout,
  .summary-grid,
  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
