<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Automático</p>
        <h1>Despesas recorrentes</h1>
        <p>Assinaturas, aluguel e contas fixas lançadas automaticamente todo mês.</p>
      </div>
      <Button label="Nova recorrência" icon="pi pi-plus" @click="abrirNova" />
    </section>

    <section class="metric-grid">
      <div class="metric-card">
        <span>Recorrências ativas</span>
        <strong>{{ recorrentesAtivas.length }}</strong>
        <small>{{ recorrentes.length }} cadastrada(s) no total</small>
      </div>
      <div class="metric-card">
        <span>Total mensal</span>
        <strong>{{ formatarMoeda(totalMensal) }}</strong>
        <small>Soma das recorrências ativas</small>
      </div>
    </section>

    <section v-if="mostrarFormulario" class="form-panel">
      <div class="form-head">
        <div>
          <h2>{{ recorrenteEditando ? 'Editar recorrência' : 'Nova recorrência' }}</h2>
          <p>{{ recorrenteEditando ? 'Atualize valor, categoria ou dia de vencimento.' : 'É lançada automaticamente como despesa todo mês, a partir da data de início.' }}</p>
        </div>
        <Button icon="pi pi-times" severity="secondary" text rounded aria-label="Fechar formulário" @click="fecharFormulario" />
      </div>

      <form class="card-form" @submit.prevent="salvarRecorrente">
        <label>
          Descrição
          <InputText v-model.trim="form.descricao" required placeholder="Ex: Netflix, Aluguel" />
        </label>

        <label>
          Valor mensal
          <InputNumber v-model="form.valor" :min="0.01" :step="0.01" :min-fraction-digits="2" :max-fraction-digits="2" placeholder="0.00" />
        </label>

        <label>
          Categoria
          <Select v-model="form.categoria" :options="categoriaOptions" option-label="label" option-value="value" required />
        </label>

        <label>
          Dia do vencimento
          <InputNumber v-model="form.dia_vencimento" :min="1" :max="28" show-buttons required />
        </label>

        <label>
          Início
          <input v-model="form.data_inicio" type="date" required />
        </label>

        <label v-if="recorrenteEditando" class="toggle-row">
          <Checkbox v-model="form.ativo" binary input-id="recorrente-ativa" />
          Recorrência ativa
        </label>

        <div class="form-actions">
          <Button type="button" label="Cancelar" severity="secondary" outlined @click="fecharFormulario" />
          <Button type="submit" :label="recorrenteEditando ? 'Salvar alterações' : 'Adicionar recorrência'" icon="pi pi-check" />
        </div>
      </form>
    </section>

    <section v-if="recorrentesOrdenadas.length" class="cards-grid">
      <article v-for="recorrente in recorrentesOrdenadas" :key="recorrente.id" class="credit-card" :class="{ inactive: !recorrente.ativo }">
        <div class="card-top">
          <div>
            <span class="card-brand">{{ recorrente.categoria }}</span>
            <h2>{{ recorrente.descricao }}</h2>
            <p>Vence dia {{ recorrente.dia_vencimento }}</p>
          </div>
          <span :class="['status', recorrente.ativo ? 'ok' : 'off']">
            {{ recorrente.ativo ? 'Ativa' : 'Pausada' }}
          </span>
        </div>

        <div class="card-values">
          <div>
            <span>Valor mensal</span>
            <strong>{{ formatarMoeda(recorrente.valor) }}</strong>
          </div>
          <div>
            <span>Início</span>
            <strong>{{ formatarData(recorrente.data_inicio) }}</strong>
          </div>
        </div>

        <footer>
          <span>Última geração: {{ recorrente.ultima_geracao ? formatarData(recorrente.ultima_geracao) : 'ainda não gerada' }}</span>
        </footer>

        <div class="card-actions">
          <button type="button" class="btn btn-ghost" @click="editarRecorrente(recorrente)">
            <i class="pi pi-pencil" aria-hidden="true"></i>
            Editar
          </button>
          <button type="button" class="btn btn-ghost" @click="alternarStatus(recorrente)">
            <i :class="recorrente.ativo ? 'pi pi-pause-circle' : 'pi pi-check-circle'" aria-hidden="true"></i>
            {{ recorrente.ativo ? 'Pausar' : 'Retomar' }}
          </button>
          <button type="button" class="btn btn-danger" @click="removerRecorrente(recorrente)">
            <i class="pi pi-trash" aria-hidden="true"></i>
            Apagar
          </button>
        </div>
      </article>
    </section>

    <section v-else class="empty-state">
      <strong>Nenhuma despesa recorrente cadastrada</strong>
      <p>Cadastre assinaturas ou contas fixas para que sejam lançadas automaticamente todo mês.</p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { despesasRecorrentesAPI } from '../api/client'

const CATEGORIAS = ['Alimentação', 'Transporte', 'Saúde', 'Educação', 'Lazer', 'Moradia', 'Assinaturas', 'Roupas', 'Impostos', 'Outros']
const categoriaOptions = CATEGORIAS.map((categoria) => ({ label: categoria, value: categoria }))

const estadoInicial = () => ({
  descricao: '',
  valor: 0,
  categoria: 'Assinaturas',
  dia_vencimento: 10,
  data_inicio: new Date().toISOString().slice(0, 10),
  ativo: true
})

const mostrarFormulario = ref(false)
const recorrenteEditando = ref(null)
const recorrentes = ref([])
const form = reactive(estadoInicial())

const recorrentesAtivas = computed(() => recorrentes.value.filter((r) => r.ativo))

const recorrentesOrdenadas = computed(() => (
  [...recorrentes.value].sort((a, b) => {
    if (a.ativo !== b.ativo) return a.ativo ? -1 : 1
    return a.descricao.localeCompare(b.descricao)
  })
))

const totalMensal = computed(() => (
  recorrentesAtivas.value.reduce((total, r) => total + Number(r.valor || 0), 0)
))

onMounted(async () => {
  await carregarRecorrentes()
})

const carregarRecorrentes = async () => {
  try {
    const response = await despesasRecorrentesAPI.listar()
    recorrentes.value = response.data
  } catch (erro) {
    console.error('Erro ao carregar despesas recorrentes:', erro)
  }
}

const abrirNova = () => {
  preencherFormulario(estadoInicial())
  recorrenteEditando.value = null
  mostrarFormulario.value = true
}

const editarRecorrente = (recorrente) => {
  preencherFormulario({
    descricao: recorrente.descricao,
    valor: Number(recorrente.valor || 0),
    categoria: recorrente.categoria,
    dia_vencimento: Number(recorrente.dia_vencimento || 10),
    data_inicio: recorrente.data_inicio,
    ativo: Boolean(recorrente.ativo)
  })
  recorrenteEditando.value = recorrente
  mostrarFormulario.value = true
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const fecharFormulario = () => {
  mostrarFormulario.value = false
  recorrenteEditando.value = null
  preencherFormulario(estadoInicial())
}

const preencherFormulario = (dados) => {
  Object.assign(form, dados)
}

const salvarRecorrente = async () => {
  try {
    if (recorrenteEditando.value) {
      await despesasRecorrentesAPI.atualizar(recorrenteEditando.value.id, {
        descricao: form.descricao,
        valor: Number(form.valor || 0),
        categoria: form.categoria,
        dia_vencimento: Number(form.dia_vencimento || 1),
        ativo: Boolean(form.ativo)
      })
    } else {
      await despesasRecorrentesAPI.criar({
        descricao: form.descricao,
        valor: Number(form.valor || 0),
        categoria: form.categoria,
        dia_vencimento: Number(form.dia_vencimento || 1),
        data_inicio: form.data_inicio
      })
    }

    fecharFormulario()
    await carregarRecorrentes()
  } catch (erro) {
    console.error('Erro ao salvar despesa recorrente:', erro)
    alert('Erro ao salvar despesa recorrente: ' + (erro.response?.data?.detail || erro.message))
  }
}

const alternarStatus = async (recorrente) => {
  try {
    await despesasRecorrentesAPI.atualizar(recorrente.id, { ativo: !recorrente.ativo })
    await carregarRecorrentes()
  } catch (erro) {
    console.error('Erro ao atualizar status da recorrência:', erro)
    alert('Erro ao atualizar status da recorrência')
  }
}

const removerRecorrente = async (recorrente) => {
  if (!confirm(`Apagar a recorrência "${recorrente.descricao}"? Despesas já geradas não serão apagadas.`)) return

  try {
    await despesasRecorrentesAPI.deletar(recorrente.id)
    recorrentes.value = recorrentes.value.filter((item) => item.id !== recorrente.id)
  } catch (erro) {
    console.error('Erro ao apagar recorrência:', erro)
    alert('Erro ao apagar recorrência: ' + (erro.response?.data?.detail || erro.message))
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
.form-head p {
  color: var(--muted);
}

.btn {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.7rem 0.95rem;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 700;
}

.btn-ghost {
  background: var(--surface-strong);
  color: var(--text);
  border: 1px solid var(--line);
}

.btn-danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.metric-grid,
.cards-grid {
  display: grid;
  gap: 1rem;
}

.metric-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-bottom: 1rem;
}

.cards-grid {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}

.metric-card,
.credit-card,
.form-panel,
.empty-state {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 18px;
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

.form-panel {
  margin-bottom: 1rem;
}

.form-head,
.card-top,
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

.card-form {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.85rem;
  align-items: end;
}

.card-form label {
  display: grid;
  gap: 0.4rem;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.card-form input[type="date"] {
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  min-height: 40px;
  background: var(--surface-strong);
  color: var(--text);
}

.card-form :deep(.p-inputtext),
.card-form :deep(.p-inputnumber),
.card-form :deep(.p-select) {
  width: 100%;
  min-height: 40px;
}

.card-form :deep(.p-inputnumber-input) {
  width: 100%;
}

.toggle-row {
  min-height: 40px;
  display: flex !important;
  align-items: center;
  gap: 0.55rem !important;
  color: var(--text) !important;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  grid-column: 1 / -1;
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

.status {
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.35rem 0.7rem;
  white-space: nowrap;
}

.status.ok {
  background: var(--success-soft);
  color: var(--success);
}

.status.off {
  background: rgba(25, 50, 74, 0.08);
  color: var(--muted);
}

.card-values {
  align-items: center;
}

.card-values strong {
  display: block;
  margin-top: 0.2rem;
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

@media (max-width: 980px) {
  .card-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 800px) {
  .page-head,
  .metric-grid {
    display: grid;
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .card-form,
  .card-values {
    grid-template-columns: 1fr;
  }

  .card-form {
    display: grid;
  }

  .card-actions .btn {
    flex: 1 1 9rem;
  }
}
</style>
