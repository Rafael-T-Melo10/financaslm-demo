<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Crédito</p>
        <h1>Cartões</h1>
        <p>Limites, uso atual e vencimentos dos cartões cadastrados.</p>
      </div>
      <Button label="Novo cartão" icon="pi pi-plus" @click="abrirNovoCartao" />
    </section>

    <section class="metric-grid">
      <div class="metric-card">
        <span>Limite total</span>
        <strong>{{ formatarMoeda(limiteTotal) }}</strong>
        <small>{{ cartoesAtivos.length }} cartão(ões) ativo(s)</small>
      </div>
      <div class="metric-card">
        <span>Limite utilizado</span>
        <strong>{{ formatarMoeda(saldoUsadoTotal) }}</strong>
        <small>{{ percentualUsoTotal.toFixed(0) }}% do limite ativo</small>
      </div>
      <div class="metric-card">
        <span>Disponível</span>
        <strong>{{ formatarMoeda(limiteDisponivelTotal) }}</strong>
        <small>{{ cartoesCriticos.length }} cartão(ões) acima de 80%</small>
      </div>
    </section>

    <section v-if="mostrarFormulario" class="form-panel">
      <div class="form-head">
        <div>
          <h2>{{ cartaoEditando ? 'Editar cartão' : 'Novo cartão' }}</h2>
          <p>{{ cartaoEditando ? 'Atualize os dados e o status do cartão.' : 'Cadastre um cartão para importar faturas e acompanhar limite.' }}</p>
        </div>
        <Button icon="pi pi-times" severity="secondary" text rounded aria-label="Fechar formulário" @click="fecharFormulario" />
      </div>

      <CartaoForm :cartao="cartaoEditando" @saved="aoSalvarCartao" @cancel="fecharFormulario" />
    </section>

    <section v-if="cartoes.length" class="toolbar">
      <div class="search-box">
        <i class="pi pi-search" aria-hidden="true"></i>
        <InputText v-model="busca" type="search" placeholder="Buscar por nome, bandeira ou final" />
      </div>
      <Select v-model="statusFiltro" :options="statusOptions" option-label="label" option-value="value" aria-label="Filtrar status" />
    </section>

    <section v-if="cartoesFiltrados.length" class="cards-grid">
      <article v-for="cartao in cartoesFiltrados" :key="cartao.id" class="credit-card" :class="{ inactive: !cartao.ativo }">
        <div class="card-top">
          <div>
            <span class="card-brand">{{ cartao.bandeira || 'Cartão' }}</span>
            <h2>{{ cartao.nome }}</h2>
            <p>{{ cartao.ultimos_digitos ? `Final ${cartao.ultimos_digitos}` : 'Final não informado' }}</p>
          </div>
          <span :class="['status', cartao.ativo ? 'ok' : 'off']">
            {{ cartao.ativo ? 'Ativo' : 'Inativo' }}
          </span>
        </div>

        <div class="usage-line">
          <div>
            <span>Uso do limite</span>
            <strong>{{ percentualCartao(cartao).toFixed(0) }}%</strong>
          </div>
          <span :class="['risk', riscoCartao(cartao).classe]">{{ riscoCartao(cartao).texto }}</span>
        </div>

        <div class="progress" :aria-label="`Uso de ${percentualCartao(cartao).toFixed(0)}% do limite`">
          <div
            class="progress-fill"
            :class="{ danger: percentualCartao(cartao) > 80, warning: percentualCartao(cartao) > 60 && percentualCartao(cartao) <= 80 }"
            :style="{ width: `${percentualCartao(cartao)}%` }"
          ></div>
        </div>

        <div class="card-values">
          <div>
            <span>Usado</span>
            <strong>{{ formatarMoeda(cartao.saldo_usado || 0) }}</strong>
          </div>
          <div>
            <span>Disponível</span>
            <strong>{{ formatarMoeda(disponivelCartao(cartao)) }}</strong>
          </div>
        </div>

        <footer>
          <span>Limite {{ formatarMoeda(cartao.limite || 0) }}</span>
          <span>Vence dia {{ cartao.data_vencimento || '-' }}</span>
        </footer>

        <div class="card-actions">
          <Button label="Editar" icon="pi pi-pencil" severity="secondary" outlined @click="editarCartao(cartao)" />
          <Button
            :label="cartao.ativo ? 'Desativar' : 'Ativar'"
            :icon="cartao.ativo ? 'pi pi-pause-circle' : 'pi pi-check-circle'"
            severity="secondary"
            outlined
            @click="alternarStatus(cartao)"
          />
          <Button label="Apagar" icon="pi pi-trash" severity="danger" outlined @click="removerCartao(cartao)" />
        </div>
      </article>
    </section>

    <section v-else class="empty-state">
      <strong>{{ cartoes.length ? 'Nenhum cartão encontrado' : 'Nenhum cartão cadastrado' }}</strong>
      <p>{{ cartoes.length ? 'Ajuste a busca ou o filtro de status.' : 'Cadastre um cartão para importar faturas e acompanhar limites.' }}</p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import CartaoForm from '../components/CartaoForm.vue'
import { cartoesAPI } from '../api/client'

const statusOptions = [
  { label: 'Todos', value: 'todos' },
  { label: 'Ativos', value: 'ativos' },
  { label: 'Inativos', value: 'inativos' }
]

const mostrarFormulario = ref(false)
const cartaoEditando = ref(null)
const cartoes = ref([])
const busca = ref('')
const statusFiltro = ref('todos')

const cartoesAtivos = computed(() => cartoes.value.filter((cartao) => cartao.ativo))

const cartoesCriticos = computed(() => (
  cartoesAtivos.value.filter((cartao) => percentualCartao(cartao) > 80)
))

const cartoesFiltrados = computed(() => {
  const termo = busca.value.trim().toLowerCase()

  return cartoesOrdenados.value.filter((cartao) => {
    const combinaBusca = !termo
      || cartao.nome?.toLowerCase().includes(termo)
      || cartao.bandeira?.toLowerCase().includes(termo)
      || cartao.ultimos_digitos?.includes(termo)
    const combinaStatus = statusFiltro.value === 'todos'
      || (statusFiltro.value === 'ativos' && cartao.ativo)
      || (statusFiltro.value === 'inativos' && !cartao.ativo)

    return combinaBusca && combinaStatus
  })
})

const cartoesOrdenados = computed(() => (
  [...cartoes.value].sort((a, b) => {
    if (a.ativo !== b.ativo) return a.ativo ? -1 : 1
    return percentualCartao(b) - percentualCartao(a)
  })
))

const limiteTotal = computed(() => (
  cartoesAtivos.value.reduce((total, cartao) => total + Number(cartao.limite || 0), 0)
))

const saldoUsadoTotal = computed(() => (
  cartoesAtivos.value.reduce((total, cartao) => total + Number(cartao.saldo_usado || 0), 0)
))

const limiteDisponivelTotal = computed(() => Math.max(limiteTotal.value - saldoUsadoTotal.value, 0))
const percentualUsoTotal = computed(() => (
  limiteTotal.value > 0 ? Math.min((saldoUsadoTotal.value / limiteTotal.value) * 100, 100) : 0
))

onMounted(async () => {
  await carregarCartoes()
})

const carregarCartoes = async () => {
  try {
    const response = await cartoesAPI.listar()
    cartoes.value = response.data
  } catch (erro) {
    console.error('Erro ao carregar cartões:', erro)
  }
}

const abrirNovoCartao = () => {
  cartaoEditando.value = null
  mostrarFormulario.value = true
}

const editarCartao = (cartao) => {
  cartaoEditando.value = cartao
  mostrarFormulario.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const fecharFormulario = () => {
  mostrarFormulario.value = false
  cartaoEditando.value = null
}

const aoSalvarCartao = async () => {
  fecharFormulario()
  await carregarCartoes()
}

const alternarStatus = async (cartao) => {
  try {
    await cartoesAPI.atualizar(cartao.id, { ativo: !cartao.ativo })
    await carregarCartoes()
  } catch (erro) {
    console.error('Erro ao atualizar status do cartão:', erro)
    alert('Erro ao atualizar status do cartão')
  }
}

const removerCartao = async (cartao) => {
  if (!confirm(`Apagar o cartão ${cartao.nome}? Faturas e parcelas vinculadas também serão removidas.`)) return

  try {
    await cartoesAPI.deletar(cartao.id)
    cartoes.value = cartoes.value.filter((item) => item.id !== cartao.id)
  } catch (erro) {
    console.error('Erro ao apagar cartão:', erro)
    alert('Erro ao apagar cartão: ' + (erro.response?.data?.detail || erro.message))
  }
}

const disponivelCartao = (cartao) => Math.max(Number(cartao.limite || 0) - Number(cartao.saldo_usado || 0), 0)
const percentualCartao = (cartao) => {
  const limite = Number(cartao.limite || 0)
  if (!limite) return 0
  return Math.min((Number(cartao.saldo_usado || 0) / limite) * 100, 100)
}

const riscoCartao = (cartao) => {
  const percentual = percentualCartao(cartao)
  if (percentual > 80) return { texto: 'Atenção', classe: 'danger' }
  if (percentual > 60) return { texto: 'Moderado', classe: 'warning' }
  return { texto: 'Saudável', classe: 'ok' }
}

const formatarMoeda = (valor) => (
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(Number(valor || 0))
)
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

h1,
h2 {
  margin: 0;
}

h1 {
  font-size: clamp(2rem, 4vw, 2.8rem);
}

.page-head p,
.metric-card span,
.metric-card small,
.credit-card p,
.credit-card footer,
.card-values span,
.usage-line span,
.form-head p {
  color: var(--muted);
}

.metric-grid,
.cards-grid {
  display: grid;
  gap: 1rem;
}

.metric-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 1rem;
}

.cards-grid {
  grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
}

.metric-card,
.credit-card,
.form-panel,
.empty-state,
.toolbar {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
}

.metric-card,
.credit-card,
.empty-state,
.form-panel,
.toolbar {
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

.form-head,
.card-top,
.usage-line,
.card-values,
.credit-card footer,
.card-actions {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.form-head {
  align-items: flex-start;
  margin-bottom: 1rem;
}

.form-head h2 {
  font-size: 1.25rem;
  margin-bottom: 0.25rem;
}

.toolbar :deep(.p-inputtext),
.toolbar :deep(.p-select) {
  width: 100%;
  min-height: 40px;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.search-box {
  position: relative;
}

.search-box i {
  position: absolute;
  left: 0.8rem;
  top: 50%;
  color: var(--muted);
  transform: translateY(-50%);
}

.search-box :deep(.p-inputtext) {
  padding-left: 2.25rem;
}

.credit-card {
  display: grid;
  gap: 1rem;
}

.credit-card.inactive {
  opacity: 0.68;
}

.card-top {
  align-items: flex-start;
}

.card-brand {
  color: var(--primary-strong);
  display: block;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  margin-bottom: 0.35rem;
  text-transform: uppercase;
}

.card-top h2 {
  font-size: 1.2rem;
  margin-bottom: 0.25rem;
}

.status,
.risk {
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.35rem 0.7rem;
  white-space: nowrap;
}

.status.ok,
.risk.ok {
  background: var(--success-soft);
  color: var(--success);
}

.status.off {
  background: rgba(25, 50, 74, 0.08);
  color: var(--muted);
}

.risk.warning {
  background: var(--primary-soft);
  color: var(--warning);
}

.risk.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.usage-line,
.card-values,
.credit-card footer {
  align-items: center;
}

.usage-line strong,
.card-values strong {
  display: block;
  margin-top: 0.2rem;
}

.progress {
  height: 10px;
  border-radius: 999px;
  background: rgba(25, 50, 74, 0.08);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--success), #45c486);
}

.progress-fill.warning {
  background: linear-gradient(90deg, #d69e2e, #f6c85f);
}

.progress-fill.danger {
  background: linear-gradient(90deg, var(--danger), #ef7a82);
}

.card-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
  padding-top: 0.2rem;
}

.empty-state strong {
  display: block;
  margin-bottom: 0.35rem;
}

@media (max-width: 800px) {
  .page-head,
  .metric-grid,
  .toolbar {
    display: grid;
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .card-values,
  .credit-card footer {
    grid-template-columns: 1fr;
  }

  .card-actions :deep(.p-button) {
    flex: 1 1 9rem;
  }
}
</style>
