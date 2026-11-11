<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Compromissos</p>
        <h1>Parcelas</h1>
        <p>Compras parceladas e compromissos futuros por cartão.</p>
      </div>
      <Button
        :label="mostrarFormulario ? 'Cancelar' : 'Nova parcela'"
        :icon="mostrarFormulario ? 'pi pi-times' : 'pi pi-plus'"
        @click="alternarFormulario"
      />
    </section>

    <section class="metric-grid">
      <div class="metric-card">
        <span>Parcelas ativas</span>
        <strong>{{ parcelasAtivas.length }}</strong>
        <small>{{ parcelas.length }} registro(s) no total</small>
      </div>
      <div class="metric-card">
        <span>Próximas parcelas</span>
        <strong>{{ formatarMoeda(totalProximasParcelas) }}</strong>
        <small>Soma das parcelas em aberto</small>
      </div>
      <div class="metric-card">
        <span>Saldo parcelado</span>
        <strong>{{ formatarMoeda(saldoParcelado) }}</strong>
        <small>Estimativa ainda em aberto</small>
      </div>
    </section>

    <Formulario
      v-if="mostrarFormulario"
      :key="formKey"
      class="form-panel"
      :campos="camposParcela"
      :botao-texto="parcelaEditando ? 'Salvar parcela' : 'Adicionar parcela'"
      @enviar="salvarParcela"
    />

    <section class="toolbar">
      <InputText v-model="busca" type="search" placeholder="Buscar por descrição ou cartão" />
      <Select v-model="statusFiltro" :options="statusOptions" option-label="label" option-value="value" />
    </section>

    <Card class="table-card">
      <template #title>Compras parceladas</template>
      <template #subtitle>{{ parcelasFiltradas.length }} registro(s) exibido(s)</template>
      <template #content>
        <DataTable :value="parcelasFiltradas" data-key="id" responsive-layout="scroll" striped-rows :row-class="classeLinha">
          <Column field="data_proxima_parcela" header="Próxima">
            <template #body="{ data }">{{ formatarData(data.data_proxima_parcela) }}</template>
          </Column>
          <Column field="descricao" header="Descrição">
            <template #body="{ data }">
              <strong>{{ data.descricao }}</strong>
              <small>{{ data.total_parcelas }}x de {{ formatarMoeda(data.valor_parcela) }}</small>
            </template>
          </Column>
          <Column field="cartao_id" header="Cartão">
            <template #body="{ data }">{{ nomeCartao(data.cartao_id) }}</template>
          </Column>
          <Column header="Restantes">
            <template #body="{ data }">
              <Tag :value="`${data.parcelas_restantes} de ${data.total_parcelas}`" severity="info" />
            </template>
          </Column>
          <Column field="valor_parcela" header="Parcela" body-class="right" header-class="right">
            <template #body="{ data }">
              <span class="valor">{{ formatarMoeda(data.valor_parcela) }}</span>
            </template>
          </Column>
          <Column header="Saldo aberto" body-class="right" header-class="right">
            <template #body="{ data }">
              <span class="valor">{{ formatarMoeda(data.valor_parcela * data.parcelas_restantes) }}</span>
            </template>
          </Column>
          <Column header="Ações" body-class="right" header-class="right">
            <template #body="{ data }">
              <div class="action-buttons">
                <button type="button" class="action-button" @click.stop="editarParcela(data)">
                  <i class="pi pi-pencil" aria-hidden="true"></i>
                  <span>Editar</span>
                </button>
                <button
                  v-if="!data.pago"
                  type="button"
                  class="action-button ok-action"
                  title="Registra a despesa do mês e avança para a próxima parcela"
                  @click.stop="pagarParcela(data)"
                >
                  <i class="pi pi-check" aria-hidden="true"></i>
                  <span>Pagar</span>
                </button>
                <button
                  v-if="!data.pago"
                  type="button"
                  class="action-button ok-action"
                  @click.stop="marcarComoPaga(data)"
                >
                  <i class="pi pi-check-circle" aria-hidden="true"></i>
                  <span>Quitar</span>
                </button>
                <button type="button" class="action-button delete-action" @click.stop="deletarParcela(data.id)">
                  <i class="pi pi-trash" aria-hidden="true"></i>
                  <span>Apagar</span>
                </button>
              </div>
            </template>
          </Column>
          <template #empty>
            <div class="empty-state">
              <strong>Nenhuma parcela encontrada</strong>
              <p>Cadastre uma compra parcelada para acompanhar compromissos futuros.</p>
            </div>
          </template>
        </DataTable>
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
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Formulario from '../components/Formulario.vue'
import { parcelasAPI, cartoesAPI } from '../api/client'

const mostrarFormulario = ref(false)
const parcelaEditando = ref(null)
const parcelas = ref([])
const cartoes = ref([])
const busca = ref('')
const statusFiltro = ref('ativas')
const statusOptions = [
  { label: 'Ativas', value: 'ativas' },
  { label: 'Todas', value: 'todas' },
  { label: 'Pagas', value: 'pagas' }
]

const cartaoOptions = computed(() => cartoes.value.map((cartao) => `${cartao.id}-${cartao.nome}`))
const formKey = computed(() => parcelaEditando.value ? `editar-${parcelaEditando.value.id}` : 'nova-parcela')

const camposParcela = computed(() => [
  {
    nome: 'descricao',
    label: 'Descrição',
    tipo: 'text',
    obrigatorio: true,
    placeholder: 'Ex: Notebook',
    valor: parcelaEditando.value?.descricao || ''
  },
  {
    nome: 'cartao_id',
    label: 'Cartão de crédito',
    tipo: 'select',
    obrigatorio: true,
    opcoes: cartaoOptions.value,
    valor: parcelaEditando.value ? `${parcelaEditando.value.cartao_id}-${nomeCartao(parcelaEditando.value.cartao_id)}` : ''
  },
  {
    nome: 'valor_total',
    label: 'Valor total',
    tipo: 'number',
    obrigatorio: true,
    placeholder: '0.00',
    step: '0.01',
    min: '0',
    valor: parcelaEditando.value?.valor_total ?? ''
  },
  {
    nome: 'total_parcelas',
    label: 'Número de parcelas',
    tipo: 'number',
    obrigatorio: true,
    placeholder: '3',
    min: '1',
    valor: parcelaEditando.value?.total_parcelas ?? ''
  },
  {
    nome: 'data_inicio',
    label: 'Data de início',
    tipo: 'date',
    obrigatorio: true,
    valor: parcelaEditando.value?.data_inicio || ''
  },
  ...(parcelaEditando.value ? [
    {
      nome: 'parcelas_restantes',
      label: 'Parcelas restantes',
      tipo: 'number',
      obrigatorio: true,
      min: '0',
      valor: parcelaEditando.value.parcelas_restantes ?? ''
    },
    {
      nome: 'data_proxima_parcela',
      label: 'Próxima parcela',
      tipo: 'date',
      obrigatorio: true,
      valor: parcelaEditando.value.data_proxima_parcela || ''
    }
  ] : [])
])

const parcelasAtivas = computed(() => parcelas.value.filter((parcela) => !parcela.pago))
const totalProximasParcelas = computed(() => (
  parcelasAtivas.value.reduce((total, parcela) => total + Number(parcela.valor_parcela || 0), 0)
))
const saldoParcelado = computed(() => (
  parcelasAtivas.value.reduce(
    (total, parcela) => total + Number(parcela.valor_parcela || 0) * Number(parcela.parcelas_restantes || 0),
    0
  )
))

const parcelasOrdenadas = computed(() => (
  [...parcelas.value].sort((a, b) => String(a.data_proxima_parcela).localeCompare(String(b.data_proxima_parcela)))
))

const parcelasFiltradas = computed(() => {
  const termo = busca.value.trim().toLowerCase()

  return parcelasOrdenadas.value.filter((parcela) => {
    const combinaBusca = !termo
      || parcela.descricao?.toLowerCase().includes(termo)
      || nomeCartao(parcela.cartao_id).toLowerCase().includes(termo)
    const combinaStatus = statusFiltro.value === 'todas'
      || (statusFiltro.value === 'ativas' && !parcela.pago)
      || (statusFiltro.value === 'pagas' && parcela.pago)

    return combinaBusca && combinaStatus
  })
})

onMounted(async () => {
  await carregarDados()
})

const carregarDados = async () => {
  try {
    const [parcelasResponse, cartoesResponse] = await Promise.all([
      parcelasAPI.listar(false),
      cartoesAPI.listar()
    ])

    parcelas.value = parcelasResponse.data
    cartoes.value = cartoesResponse.data
  } catch (erro) {
    console.error('Erro ao carregar parcelas:', erro)
  }
}

const alternarFormulario = () => {
  if (mostrarFormulario.value) {
    fecharFormulario()
  } else {
    parcelaEditando.value = null
    mostrarFormulario.value = true
  }
}

const fecharFormulario = () => {
  mostrarFormulario.value = false
  parcelaEditando.value = null
}

const editarParcela = (parcela) => {
  parcelaEditando.value = parcela
  mostrarFormulario.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const salvarParcela = async (dados) => {
  try {
    const cartaoId = parseInt(String(dados.cartao_id).split('-')[0], 10)
    const payload = {
      descricao: dados.descricao,
      cartao_id: cartaoId,
      valor_total: Number(dados.valor_total),
      total_parcelas: Number(dados.total_parcelas),
      data_inicio: dados.data_inicio
    }

    if (parcelaEditando.value) {
      payload.parcelas_restantes = Number(dados.parcelas_restantes)
      payload.data_proxima_parcela = dados.data_proxima_parcela
      payload.pago = payload.parcelas_restantes === 0
      await parcelasAPI.atualizar(parcelaEditando.value.id, payload)
    } else {
      await parcelasAPI.criar(payload)
    }

    fecharFormulario()
    await carregarDados()
  } catch (erro) {
    console.error('Erro ao salvar parcela:', erro)
    alert('Erro ao salvar parcela: ' + (erro.response?.data?.detail || erro.message))
  }
}

const pagarParcela = async (parcela) => {
  try {
    await parcelasAPI.pagar(parcela.id)
    await carregarDados()
  } catch (erro) {
    console.error('Erro ao pagar parcela:', erro)
    alert('Erro ao pagar parcela: ' + (erro.response?.data?.detail || erro.message))
  }
}

const marcarComoPaga = async (parcela) => {
  try {
    await parcelasAPI.atualizar(parcela.id, { pago: true, parcelas_restantes: 0 })
    await carregarDados()
  } catch (erro) {
    console.error('Erro ao atualizar parcela:', erro)
    alert('Erro ao atualizar parcela')
  }
}

const deletarParcela = async (id) => {
  if (!confirm('Apagar esta parcela?')) return

  try {
    await parcelasAPI.deletar(id)
    parcelas.value = parcelas.value.filter((parcela) => parcela.id !== id)
    if (parcelaEditando.value?.id === id) {
      fecharFormulario()
    }
  } catch (erro) {
    console.error('Erro ao apagar parcela:', erro)
    alert('Erro ao apagar parcela')
  }
}

const nomeCartao = (cartaoId) => {
  const cartao = cartoes.value.find((item) => item.id === cartaoId)
  return cartao ? cartao.nome : `Cartão ${cartaoId}`
}

const classeLinha = (parcela) => ({ pago: parcela.pago })

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
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
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
.metric-card small {
  color: var(--muted);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.metric-card,
.toolbar {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: var(--shadow);
}

.table-card {
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.metric-card {
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

.form-panel {
  margin-bottom: 1rem;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 0.75rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.toolbar :deep(.p-inputtext),
.toolbar :deep(.p-select) {
  width: 100%;
}

.right {
  text-align: right;
}

.valor {
  font-weight: 800;
}

:deep(.p-datatable-tbody) tr.pago {
  opacity: 0.62;
}

.action-buttons {
  display: inline-flex;
  justify-content: flex-end;
  gap: 0.75rem;
  white-space: nowrap;
}

.action-button {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 8px;
  color: var(--muted);
  cursor: pointer;
  display: inline-flex;
  gap: 0.45rem;
  min-height: 2rem;
  padding: 0.35rem 0.45rem;
}

.action-button:hover {
  background: var(--surface-hover);
}

.action-button:hover,
.action-button:focus-visible {
  color: var(--primary-strong);
}

.ok-action {
  color: var(--success);
}

.ok-action:hover,
.ok-action:focus-visible {
  color: var(--success);
}

.delete-action {
  color: var(--danger);
}

.delete-action:hover,
.delete-action:focus-visible {
  color: var(--danger);
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

@media (max-width: 900px) {
  .page-head,
  .metric-grid,
  .toolbar {
    display: grid;
    grid-template-columns: 1fr;
  }
}
</style>
