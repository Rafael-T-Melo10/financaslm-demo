<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Entradas</p>
        <h1>Receitas</h1>
        <p>Salários, contracheques e outras entradas em um histórico limpo.</p>
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
          :label="mostrarFormulario ? 'Cancelar' : 'Nova receita'"
          :icon="mostrarFormulario ? 'pi pi-times' : 'pi pi-plus'"
          @click="alternarFormulario"
        />
      </div>
    </section>

    <section class="metric-grid">
      <Card class="metric-card">
        <template #content>
          <span>Total recebido</span>
          <strong>{{ formatarMoeda(totalReceitas) }}</strong>
          <small>{{ receitas.length }} lançamento(s)</small>
        </template>
      </Card>
      <Card class="metric-card">
        <template #content>
          <span>Última receita</span>
          <strong>{{ formatarMoeda(ultimaReceita?.valor || 0) }}</strong>
          <small>{{ ultimaReceita ? formatarData(ultimaReceita.data) : 'Sem dados' }}</small>
        </template>
      </Card>
      <Card class="metric-card">
        <template #content>
          <span>Origem principal</span>
          <strong>{{ origemPrincipal?.nome || '-' }}</strong>
          <small>{{ origemPrincipal ? formatarMoeda(origemPrincipal.valor) : 'Sem dados' }}</small>
        </template>
      </Card>
    </section>

    <Formulario
      v-if="mostrarFormulario"
      :key="formKey"
      class="form-panel"
      :campos="camposReceita"
      :botao-texto="receitaEditando ? 'Salvar receita' : 'Adicionar receita'"
      @enviar="salvarReceita"
    />

    <Card class="filters-panel">
      <template #content>
        <div class="period-filter">
          <span class="filter-label">Período</span>
          <div class="period-controls">
            <Button icon="pi pi-chevron-left" text rounded aria-label="Mês anterior" @click="alterarMes(-1)" />
            <InputText v-model="periodoSelecionado" type="month" />
            <Button icon="pi pi-chevron-right" text rounded aria-label="Próximo mês" @click="alterarMes(1)" />
            <Button label="Todos" severity="secondary" outlined @click="limparPeriodo" />
            <Button label="Mês atual" severity="secondary" outlined @click="irParaMesAtual" />
          </div>
        </div>

        <div class="search-filter">
          <label for="busca-receitas">Buscar</label>
          <div class="search-box">
            <InputText id="busca-receitas" v-model="busca" type="search" placeholder="Descrição ou origem" />
            <Button v-if="busca" icon="pi pi-times" text rounded aria-label="Limpar busca" class="clear-btn" @click="busca = ''" />
          </div>
        </div>

        <div class="select-filter">
          <label for="origem-receitas">Origem</label>
          <Select id="origem-receitas" v-model="origemFiltro" :options="origemOptions" option-label="label" option-value="value" />
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
      <template #title>Histórico de receitas</template>
      <template #subtitle>{{ receitasFiltradas.length }} registro(s) exibido(s)</template>
      <template #content>
        <DataTable :value="receitasFiltradas" data-key="id" responsive-layout="scroll" striped-rows>
          <Column field="data" header="Data">
            <template #body="{ data }">{{ formatarData(data.data) }}</template>
          </Column>
          <Column field="descricao" header="Descrição">
            <template #body="{ data }">
              <strong>{{ data.descricao }}</strong>
            </template>
          </Column>
          <Column field="origem" header="Origem">
            <template #body="{ data }">
              <Tag :value="formatarOrigem(data.origem)" severity="info" />
            </template>
          </Column>
          <Column field="valor" header="Valor" body-class="right" header-class="right">
            <template #body="{ data }">
              <span class="valor positivo">{{ formatarMoeda(data.valor) }}</span>
            </template>
          </Column>
          <Column header="Ações" body-class="right" header-class="right">
            <template #body="{ data }">
              <Button icon="pi pi-pencil" label="Editar" severity="secondary" text @click="editarReceita(data)" />
              <Button icon="pi pi-trash" label="Apagar" severity="danger" text @click="deletarReceita(data.id)" />
            </template>
          </Column>
          <template #empty>
            <div class="empty-state">
              <strong>Nenhuma receita encontrada</strong>
              <p>Importe um contracheque ou cadastre uma receita manualmente.</p>
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
import { receitasAPI, exportacaoAPI } from '../api/client'
import { baixarBlob } from '../download'

const mostrarFormulario = ref(false)
const receitaEditando = ref(null)
const receitas = ref([])
const busca = ref('')
const origemFiltro = ref('')
const periodoSelecionado = ref('')
const temFiltrosAtivos = computed(() => Boolean(periodoSelecionado.value || busca.value || origemFiltro.value))

const formKey = computed(() => receitaEditando.value ? `editar-${receitaEditando.value.id}` : 'nova-receita')

const camposReceita = computed(() => [
  {
    nome: 'descricao',
    label: 'Descrição',
    tipo: 'text',
    obrigatorio: true,
    placeholder: 'Ex: Salário',
    valor: receitaEditando.value?.descricao || ''
  },
  {
    nome: 'valor',
    label: 'Valor',
    tipo: 'number',
    obrigatorio: true,
    placeholder: '0.00',
    step: '0.01',
    valor: receitaEditando.value?.valor ?? ''
  },
  {
    nome: 'data',
    label: 'Data',
    tipo: 'date',
    obrigatorio: true,
    valor: receitaEditando.value?.data || ''
  }
])

const receitasOrdenadas = computed(() => (
  [...receitas.value].sort((a, b) => String(b.data).localeCompare(String(a.data)))
))

const receitasFiltradas = computed(() => {
  const termo = busca.value.trim().toLowerCase()

  return receitasOrdenadas.value.filter((receita) => {
    const combinaBusca = !termo
      || receita.descricao?.toLowerCase().includes(termo)
      || receita.origem?.toLowerCase().includes(termo)
    const combinaOrigem = !origemFiltro.value || receita.origem === origemFiltro.value
    const combinaPeriodo = !periodoSelecionado.value || dataEstaNoPeriodo(receita.data, periodoSelecionado.value)

    return combinaBusca && combinaOrigem && combinaPeriodo
  })
})

const totalReceitas = computed(() => (
  receitasFiltradas.value.reduce((total, receita) => total + Number(receita.valor || 0), 0)
))

const ultimaReceita = computed(() => receitasFiltradas.value[0] || null)

const origensDisponiveis = computed(() => (
  [...new Set(receitas.value.map((receita) => receita.origem || 'manual'))].sort()
))

const origemOptions = computed(() => [
  { label: 'Todas', value: '' },
  ...origensDisponiveis.value.map((origem) => ({ label: formatarOrigem(origem), value: origem }))
])

const origemPrincipal = computed(() => {
  const totais = receitasFiltradas.value.reduce((acc, receita) => {
    const origem = receita.origem || 'manual'
    acc[origem] = (acc[origem] || 0) + Number(receita.valor || 0)
    return acc
  }, {})

  const [nome, valor] = Object.entries(totais).sort((a, b) => b[1] - a[1])[0] || []
  return nome ? { nome: formatarOrigem(nome), valor } : null
})

onMounted(async () => {
  await carregarReceitas()
})

const carregarReceitas = async () => {
  try {
    const response = await receitasAPI.listar()
    receitas.value = response.data
  } catch (erro) {
    console.error('Erro ao carregar receitas:', erro)
  }
}

const alternarFormulario = () => {
  if (mostrarFormulario.value) {
    fecharFormulario()
  } else {
    receitaEditando.value = null
    mostrarFormulario.value = true
  }
}

const fecharFormulario = () => {
  mostrarFormulario.value = false
  receitaEditando.value = null
}

const editarReceita = (receita) => {
  receitaEditando.value = receita
  mostrarFormulario.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const salvarReceita = async (dados) => {
  try {
    const payload = {
      descricao: dados.descricao,
      valor: Number(dados.valor),
      data: dados.data
    }

    if (receitaEditando.value) {
      await receitasAPI.atualizar(receitaEditando.value.id, payload)
    } else {
      await receitasAPI.criar(payload)
    }

    fecharFormulario()
    await carregarReceitas()
  } catch (erro) {
    console.error('Erro ao salvar receita:', erro)
    alert('Erro ao salvar receita: ' + (erro.response?.data?.detail || erro.message))
  }
}

const alterarMes = async (delta) => {
  periodoSelecionado.value = deslocarPeriodo(periodoSelecionado.value || periodoAtual(), delta)
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
  origemFiltro.value = ''
}

const exportarCsv = async () => {
  try {
    const [ano, mes] = periodoSelecionado.value
      ? periodoSelecionado.value.split('-').map(Number)
      : [null, null]
    const response = await exportacaoAPI.receitas(mes, ano)
    const nomeArquivo = periodoSelecionado.value
      ? `receitas_${periodoSelecionado.value}.csv`
      : 'receitas_todas.csv'
    baixarBlob(response.data, nomeArquivo)
  } catch (erro) {
    console.error('Erro ao exportar receitas:', erro)
    alert('Erro ao exportar receitas')
  }
}

const deletarReceita = async (id) => {
  if (!confirm('Apagar esta receita?')) return

  try {
    await receitasAPI.deletar(id)
    receitas.value = receitas.value.filter((receita) => receita.id !== id)
    if (receitaEditando.value?.id === id) {
      fecharFormulario()
    }
  } catch (erro) {
    console.error('Erro ao deletar receita:', erro)
    alert('Erro ao deletar receita')
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
    holerite: 'Contracheque',
    manual: 'Manual'
  }

  return rotulos[origem] || origem || 'Manual'
}

function periodoAtual() {
  const hoje = new Date()
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`
}

function obterMesAno(periodo) {
  const [ano, mes] = String(periodo || periodoAtual()).split('-').map(Number)
  return { mes, ano }
}

function dataEstaNoPeriodo(valor, periodo) {
  return String(valor || '').startsWith(periodo)
}

function deslocarPeriodo(periodo, delta) {
  const { mes, ano } = obterMesAno(periodo)
  const data = new Date(ano, mes - 1 + delta, 1)
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}`
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
  display: grid;
  grid-template-columns: minmax(420px, max-content) minmax(280px, 1fr) minmax(190px, 220px) auto;
  gap: 1rem;
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
  grid-template-columns: 2.25rem 16rem 2.25rem auto auto;
  align-items: center;
  gap: 0.55rem;
}

.period-controls .p-inputtext {
  width: 16rem;
  min-width: 0;
}

.period-controls .p-button {
  min-width: 0;
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

.valor {
  font-weight: 800;
}

.positivo {
  color: var(--success);
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

@media (max-width: 800px) {
  .page-head,
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    display: grid;
  }

  .filters-panel :deep(.p-card-content) {
    grid-template-columns: 1fr;
  }

  .period-controls {
    grid-template-columns: 2.25rem minmax(0, 1fr) 2.25rem;
  }

  .period-controls .p-inputtext {
    width: 100%;
  }

  .period-controls .p-button:nth-of-type(3),
  .period-controls .p-button:nth-of-type(4) {
    grid-column: span 3;
    width: 100%;
  }
}
</style>
