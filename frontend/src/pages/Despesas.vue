<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Saídas</p>
        <h1>Despesas</h1>
        <p>Compras, faturas e gastos manuais organizados por categoria.</p>
      </div>
      <div class="page-head-actions">
        <Button
          label="Exportar CSV"
          icon="pi pi-download"
          severity="secondary"
          outlined
          @click="exportarCsv"
        />
        <Button
          :label="mostrarFormulario ? 'Cancelar' : 'Nova despesa'"
          :icon="mostrarFormulario ? 'pi pi-times' : 'pi pi-plus'"
          @click="alternarFormulario"
        />
      </div>
    </section>

    <section class="metric-grid">
      <Card class="metric-card">
        <template #content>
          <span>Total gasto</span>
          <strong>{{ formatarMoeda(totalDespesas) }}</strong>
          <small>{{ despesas.length }} lançamento(s)</small>
        </template>
      </Card>
      <Card class="metric-card">
        <template #content>
          <span>Despesas deste mês</span>
          <strong>{{ formatarMoeda(totalDespesasMesAtual) }}</strong>
          <small>{{ despesasMesAtual.length }} lançamento(s) em {{ rotuloMesAtual }}</small>
        </template>
      </Card>
      <Card class="metric-card">
        <template #content>
          <span>Categoria principal</span>
          <strong>{{ categoriaPrincipal?.nome || '-' }}</strong>
          <small>{{ categoriaPrincipal ? formatarMoeda(categoriaPrincipal.valor) : 'Sem dados' }}</small>
        </template>
      </Card>
    </section>

    <Formulario
      v-if="mostrarFormulario"
      :key="formKey"
      class="form-panel"
      :campos="camposDespesa"
      :botao-texto="despesaEditando ? 'Salvar despesa' : 'Adicionar despesa'"
      @enviar="salvarDespesa"
    />

    <Dialog
      v-model:visible="mostrarConfirmacaoApagar"
      modal
      header="Apagar despesa"
      class="delete-dialog"
      :style="{ width: 'min(92vw, 420px)' }"
    >
      <p class="delete-dialog-text">
        Apagar {{ despesaParaApagar?.descricao || 'esta despesa' }}?
      </p>
      <div v-if="despesaParaApagar" class="delete-dialog-summary">
        <span>{{ formatarData(despesaParaApagar.data) }}</span>
        <strong>{{ formatarMoeda(despesaParaApagar.valor) }}</strong>
      </div>
      <template #footer>
        <Button label="Cancelar" severity="secondary" outlined @click="cancelarExclusao" />
        <Button label="Apagar" icon="pi pi-trash" severity="danger" @click="confirmarExclusao" />
      </template>
    </Dialog>

    <Card class="filters-panel">
      <template #content>
        <div class="period-filter">
          <span class="filter-label">Período</span>
          <div class="period-controls">
            <InputText v-model="periodoSelecionado" type="month" />
            <Button class="period-shortcut" label="Todos" severity="secondary" outlined @click="limparPeriodo" />
            <Button class="period-shortcut" label="Mês atual" severity="secondary" outlined @click="irParaMesAtual" />
          </div>
        </div>

        <div class="search-filter">
          <label for="busca-despesas">Buscar</label>
          <div class="search-box">
            <InputText id="busca-despesas" v-model="busca" type="search" placeholder="Descrição, categoria ou origem" />
            <Button v-if="busca" icon="pi pi-times" text rounded aria-label="Limpar busca" class="clear-btn" @click="busca = ''" />
          </div>
        </div>

        <div class="select-filter">
          <label for="categoria-despesas">Categoria</label>
          <Select id="categoria-despesas" v-model="categoriaFiltro" :options="categoriaOptions" option-label="label" option-value="value" />
        </div>

        <div class="select-filter">
          <label for="origem-despesas">Origem</label>
          <Select id="origem-despesas" v-model="origemFiltro" :options="origemOptions" option-label="label" option-value="value" />
        </div>

        <Button
          label="Limpar filtros"
          icon="pi pi-filter-slash"
          severity="secondary"
          outlined
          class="reset-btn"
          :disabled="!temFiltrosAtivos"
          @click="limparFiltros"
        />
      </template>
    </Card>

    <Card class="table-card">
      <template #title>Histórico de despesas</template>
      <template #subtitle>{{ despesasFiltradas.length }} registro(s) exibido(s)</template>
      <template #content>
        <DataTable :value="despesasFiltradas" data-key="id" responsive-layout="scroll" striped-rows>
          <Column field="data" header="Data">
            <template #body="{ data }">{{ formatarData(data.data) }}</template>
          </Column>
          <Column field="descricao" header="Descrição">
            <template #body="{ data }">
              <strong>{{ data.descricao }}</strong>
            </template>
          </Column>
          <Column field="categoria" header="Categoria">
            <template #body="{ data }">
              <Tag :value="data.categoria || 'Outros'" severity="info" />
            </template>
          </Column>
          <Column field="origem" header="Origem">
            <template #body="{ data }">{{ formatarOrigem(data.origem) }}</template>
          </Column>
          <Column field="valor" header="Valor" body-class="right" header-class="right">
            <template #body="{ data }">
              <span class="valor negativo">{{ formatarMoeda(data.valor) }}</span>
            </template>
          </Column>
          <Column header="Ações" body-class="right" header-class="right">
            <template #body="{ data }">
              <div class="action-buttons">
                <button type="button" class="action-button edit-action" @click.stop="editarDespesa(data)">
                  <i class="pi pi-pencil" aria-hidden="true"></i>
                  <span>Editar</span>
                </button>
                <button type="button" class="action-button delete-action" @click.stop="abrirConfirmacaoApagar(data)">
                  <i class="pi pi-trash" aria-hidden="true"></i>
                  <span>Apagar</span>
                </button>
              </div>
            </template>
          </Column>
          <template #empty>
            <div class="empty-state">
              <strong>Nenhuma despesa encontrada</strong>
              <p>Importe uma fatura ou cadastre uma despesa manualmente.</p>
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
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Formulario from '../components/Formulario.vue'
import { despesasAPI, exportacaoAPI } from '../api/client'
import { baixarBlob } from '../download'

const mostrarFormulario = ref(false)
const despesaEditando = ref(null)
const despesas = ref([])
const despesaParaApagar = ref(null)
const mostrarConfirmacaoApagar = ref(false)
const busca = ref('')
const categoriaFiltro = ref('')
const origemFiltro = ref('')
const periodoSelecionado = ref('')
const temFiltrosAtivos = computed(() => Boolean(periodoSelecionado.value || busca.value || categoriaFiltro.value || origemFiltro.value))

const formKey = computed(() => despesaEditando.value ? `editar-${despesaEditando.value.id}` : 'nova-despesa')

const camposDespesa = computed(() => [
  {
    nome: 'descricao',
    label: 'Descrição',
    tipo: 'text',
    obrigatorio: true,
    placeholder: 'Ex: Compra no supermercado',
    valor: despesaEditando.value?.descricao || ''
  },
  {
    nome: 'valor',
    label: 'Valor',
    tipo: 'number',
    obrigatorio: true,
    placeholder: '0.00',
    step: '0.01',
    valor: despesaEditando.value?.valor ?? ''
  },
  {
    nome: 'categoria',
    label: 'Categoria',
    tipo: 'select',
    obrigatorio: true,
    opcoes: ['Alimentação', 'Transporte', 'Saúde', 'Educação', 'Lazer', 'Moradia', 'Assinaturas', 'Roupas', 'Impostos', 'Ajustes', 'Outros'],
    valor: despesaEditando.value?.categoria || ''
  },
  {
    nome: 'data',
    label: 'Data',
    tipo: 'date',
    obrigatorio: true,
    valor: despesaEditando.value?.data || ''
  }
])

const despesasOrdenadas = computed(() => (
  [...despesas.value].sort((a, b) => String(b.data).localeCompare(String(a.data)))
))

const despesasFiltradas = computed(() => {
  const termo = busca.value.trim().toLowerCase()

  return despesasOrdenadas.value.filter((despesa) => {
    const combinaBusca = !termo
      || despesa.descricao?.toLowerCase().includes(termo)
      || despesa.categoria?.toLowerCase().includes(termo)
      || despesa.origem?.toLowerCase().includes(termo)
    const combinaCategoria = !categoriaFiltro.value || despesa.categoria === categoriaFiltro.value
    const combinaOrigem = !origemFiltro.value || despesa.origem === origemFiltro.value
    const combinaPeriodo = !periodoSelecionado.value || dataEstaNoPeriodo(despesa.data, periodoSelecionado.value)

    return combinaBusca && combinaCategoria && combinaOrigem && combinaPeriodo
  })
})

const totalDespesas = computed(() => (
  despesasFiltradas.value.reduce((total, despesa) => total + Number(despesa.valor || 0), 0)
))

const despesasMesAtual = computed(() => (
  despesas.value.filter((despesa) => dataEstaNoPeriodo(despesa.data, periodoAtual()))
))

const totalDespesasMesAtual = computed(() => (
  despesasMesAtual.value.reduce((total, despesa) => total + Number(despesa.valor || 0), 0)
))

const rotuloMesAtual = computed(() => (
  new Intl.DateTimeFormat('pt-BR', {
    month: 'short',
    year: 'numeric'
  }).format(new Date())
))

const categoriasDisponiveis = computed(() => (
  [...new Set(despesas.value.map((despesa) => despesa.categoria || 'Outros'))].sort()
))

const origensDisponiveis = computed(() => (
  [...new Set(despesas.value.map((despesa) => despesa.origem || 'manual'))].sort()
))

const categoriaOptions = computed(() => [
  { label: 'Todas', value: '' },
  ...categoriasDisponiveis.value.map((categoria) => ({ label: categoria, value: categoria }))
])

const origemOptions = computed(() => [
  { label: 'Todas', value: '' },
  ...origensDisponiveis.value.map((origem) => ({ label: formatarOrigem(origem), value: origem }))
])

const categoriaPrincipal = computed(() => {
  const totais = despesasFiltradas.value.reduce((acc, despesa) => {
    const categoria = despesa.categoria || 'Outros'
    acc[categoria] = (acc[categoria] || 0) + Number(despesa.valor || 0)
    return acc
  }, {})

  const [nome, valor] = Object.entries(totais).sort((a, b) => b[1] - a[1])[0] || []
  return nome ? { nome, valor } : null
})

onMounted(async () => {
  await carregarDespesas()
})

const carregarDespesas = async () => {
  try {
    const response = await despesasAPI.listar()
    despesas.value = response.data
  } catch (erro) {
    console.error('Erro ao carregar despesas:', erro)
  }
}

const alternarFormulario = () => {
  if (mostrarFormulario.value) {
    fecharFormulario()
  } else {
    despesaEditando.value = null
    mostrarFormulario.value = true
  }
}

const fecharFormulario = () => {
  mostrarFormulario.value = false
  despesaEditando.value = null
}

const editarDespesa = (despesa) => {
  despesaEditando.value = despesa
  mostrarFormulario.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const salvarDespesa = async (dados) => {
  try {
    const payload = {
      descricao: dados.descricao,
      valor: Number(dados.valor),
      categoria: dados.categoria,
      data: dados.data
    }

    if (despesaEditando.value) {
      await despesasAPI.atualizar(despesaEditando.value.id, payload)
    } else {
      await despesasAPI.criar(payload)
    }

    fecharFormulario()
    await carregarDespesas()
  } catch (erro) {
    console.error('Erro ao salvar despesa:', erro)
    alert('Erro ao salvar despesa: ' + (erro.response?.data?.detail || erro.message))
  }
}

const irParaMesAtual = async () => {
  periodoSelecionado.value = periodoAtual()
}

const limparPeriodo = () => {
  periodoSelecionado.value = ''
}

const limparFiltros = () => {
  periodoSelecionado.value = ''
  busca.value = ''
  categoriaFiltro.value = ''
  origemFiltro.value = ''
}

const exportarCsv = async () => {
  try {
    const [ano, mes] = periodoSelecionado.value
      ? periodoSelecionado.value.split('-').map(Number)
      : [null, null]
    const response = await exportacaoAPI.despesas(mes, ano)
    const nomeArquivo = periodoSelecionado.value
      ? `despesas_${periodoSelecionado.value}.csv`
      : 'despesas_todas.csv'
    baixarBlob(response.data, nomeArquivo)
  } catch (erro) {
    console.error('Erro ao exportar despesas:', erro)
    alert('Erro ao exportar despesas')
  }
}

const abrirConfirmacaoApagar = (despesa) => {
  despesaParaApagar.value = despesa
  mostrarConfirmacaoApagar.value = true
}

const cancelarExclusao = () => {
  mostrarConfirmacaoApagar.value = false
  despesaParaApagar.value = null
}

const confirmarExclusao = async () => {
  if (!despesaParaApagar.value) return

  const removida = await deletarDespesa(despesaParaApagar.value.id)
  if (removida) {
    cancelarExclusao()
  }
}

const deletarDespesa = async (id) => {
  try {
    await despesasAPI.deletar(id)
    despesas.value = despesas.value.filter((despesa) => despesa.id !== id)
    if (despesaEditando.value?.id === id) {
      fecharFormulario()
    }
    return true
  } catch (erro) {
    console.error('Erro ao deletar despesa:', erro)
    alert('Erro ao deletar despesa')
    return false
  }
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

const formatarOrigem = (origem) => {
  const rotulos = {
    fatura: 'Fatura',
    manual: 'Manual'
  }

  return rotulos[origem] || origem || 'Manual'
}

function periodoAtual() {
  const hoje = new Date()
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`
}

function dataEstaNoPeriodo(valor, periodo) {
  return String(valor || '').startsWith(periodo)
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

.page-head-actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
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
.filters-panel,
.table-card {
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.metric-card span {
  color: var(--muted);
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

.filters-panel {
  margin-bottom: 1rem;
}

.filters-panel :deep(.p-card-body),
.filters-panel :deep(.p-card-content) {
  padding: 0;
}

.filters-panel :deep(.p-card-content) {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  align-items: end;
  padding: 1.1rem;
}

.period-filter,
.search-filter,
.select-filter {
  display: grid;
  gap: 0.4rem;
  min-width: 0;
}

.period-filter {
  flex: 0 0 360px;
}

.search-filter {
  flex: 1 1 270px;
}

.select-filter {
  flex: 0 1 170px;
}

.filter-label,
.search-filter label,
.select-filter label {
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.period-controls,
.search-box {
  display: flex;
  gap: 0.45rem;
}

.period-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 4.1rem 5.5rem;
  align-items: center;
  gap: 0.45rem;
}

.period-controls .p-inputtext {
  width: 100%;
  min-width: 0;
}

.period-controls :deep(.p-button) {
  min-width: 0;
  min-height: 38px;
}

.period-shortcut {
  width: 100%;
  padding-inline: 0.55rem;
  white-space: nowrap;
}

.reset-btn {
  flex: 0 0 142px;
  justify-content: center;
  white-space: nowrap;
}

.search-box {
  position: relative;
}

.search-box .p-inputtext,
.select-filter .p-select {
  width: 100%;
}

.clear-btn {
  position: absolute;
  right: 0.35rem;
  top: 50%;
  transform: translateY(-50%);
}

.search-box .p-inputtext {
  padding-right: 2.8rem;
}

.reset-btn {
  align-self: end;
}

.right {
  text-align: right;
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

.edit-action:hover,
.edit-action:focus-visible {
  color: var(--primary-strong);
}

.delete-action {
  color: var(--danger);
}

.delete-action:hover,
.delete-action:focus-visible {
  color: var(--danger);
}

.delete-dialog-text {
  margin: 0 0 0.85rem;
}

.delete-dialog-summary {
  align-items: center;
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem;
}

.valor {
  font-weight: 800;
}

.negativo {
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
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    display: grid;
  }

  .filters-panel :deep(.p-card-content) {
    display: grid;
    grid-template-columns: 1fr;
  }

  .period-controls {
    grid-template-columns: 1fr;
  }

  .period-controls .p-inputtext {
    width: 100%;
  }

  .period-filter,
  .search-filter,
  .select-filter,
  .reset-btn {
    flex: none;
    width: 100%;
  }
}
</style>
