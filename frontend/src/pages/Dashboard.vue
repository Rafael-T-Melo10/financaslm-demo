<template>
  <main class="dashboard">
    <section class="page-header">
      <div>
        <span class="eyebrow">Painel financeiro</span>
        <h1>Dashboard</h1>
        <p>Controle o mês, acompanhe compromissos e entenda para onde seu dinheiro está indo.</p>
      </div>

      <div class="period-picker">
        <span>Período analisado</span>
        <DatePicker v-model="dataPeriodo" view="month" date-format="mm/yy" show-icon :manual-input="false" />
      </div>
    </section>

    <Message v-if="erro" severity="error" :closable="false">{{ erro }}</Message>

    <div v-if="carregando" class="loading-grid" aria-label="Carregando dashboard">
      <Skeleton v-for="item in 6" :key="item" height="10rem" />
    </div>

    <template v-else-if="dashboard">
      <Message v-if="dashboard.periodo.status === 'futuro'" severity="info" :closable="false">
        Este é um mês futuro: os comparativos ficam indisponíveis e a projeção considera apenas compromissos cadastrados.
      </Message>

      <Tabs v-model:value="abaAtiva" class="dashboard-tabs">
        <TabList>
          <Tab value="resumo"><i class="pi pi-home" />Resumo</Tab>
          <Tab value="analises"><i class="pi pi-chart-bar" />Análises</Tab>
          <Tab value="movimentacoes"><i class="pi pi-list" />Movimentações</Tab>
        </TabList>

        <TabPanels>
          <TabPanel value="resumo">
            <section class="hero-grid">
              <Card class="projection-card" :class="classeSaldo(dashboard.resumo.saldo_projetado)">
                <template #content>
                  <span class="card-kicker">{{ dashboard.resumo.saldo_projetado >= 0 ? 'Margem projetada' : 'Déficit projetado' }}</span>
                  <strong>{{ formatarMoeda(Math.abs(dashboard.resumo.saldo_projetado)) }}</strong>
                  <p>
                    {{ dashboard.resumo.saldo_projetado >= 0
                      ? 'resultado estimado com os compromissos já cadastrados'
                      : 'faltará no mês se os compromissos forem mantidos' }}
                  </p>
                  <div class="projection-meta">
                    <span>Saldo já lançado</span>
                    <b>{{ formatarMoeda(dashboard.resumo.saldo_lancado) }}</b>
                  </div>
                </template>
              </Card>

              <Card class="comparison-card">
                <template #content>
                  <span class="card-kicker">Ritmo de gastos</span>
                  <div class="comparison-values">
                    <div>
                      <span>vs. mês anterior</span>
                      <strong :class="classeVariacao(dashboard.resumo.comparacao_mes_anterior)">
                        {{ textoVariacao(dashboard.resumo.comparacao_mes_anterior) }}
                      </strong>
                    </div>
                    <div>
                      <span>vs. média de 3 meses</span>
                      <strong :class="classeVariacao(dashboard.resumo.comparacao_media_3_meses)">
                        {{ textoVariacao(dashboard.resumo.comparacao_media_3_meses) }}
                      </strong>
                    </div>
                  </div>
                  <small>{{ legendaComparacao }}</small>
                </template>
              </Card>
            </section>

            <section class="metric-grid">
              <Card>
                <template #content>
                  <span>Receitas</span>
                  <strong class="positive">{{ formatarMoeda(dashboard.resumo.receitas) }}</strong>
                  <small>registradas no período</small>
                </template>
              </Card>
              <Card>
                <template #content>
                  <span>Despesas lançadas</span>
                  <strong>{{ formatarMoeda(dashboard.resumo.despesas_lancadas) }}</strong>
                  <small>já contabilizadas</small>
                </template>
              </Card>
              <Card>
                <template #content>
                  <span>Compromissos pendentes</span>
                  <strong class="warning">{{ formatarMoeda(dashboard.resumo.compromissos_pendentes) }}</strong>
                  <small>parcelas e recorrências a lançar</small>
                </template>
              </Card>
              <Card>
                <template #content>
                  <span>Economia projetada</span>
                  <strong :class="classeSaldo(dashboard.resumo.saldo_projetado)">
                    {{ dashboard.resumo.taxa_economia_projetada === null ? '—' : `${dashboard.resumo.taxa_economia_projetada.toFixed(0)}%` }}
                  </strong>
                  <small>{{ dashboard.resumo.taxa_economia_projetada === null ? 'sem receitas no período' : 'sobre as receitas registradas' }}</small>
                </template>
              </Card>
            </section>

            <section class="summary-grid">
              <Card class="spending-card">
                <template #title>Onde o dinheiro foi</template>
                <template #subtitle>Distribuição real das despesas no período</template>
                <template #content>
                  <div v-if="categoriasGasto.length" class="spending-layout">
                    <aside class="spending-overview">
                      <span>Total distribuído</span>
                      <strong>{{ formatarMoeda(totalCategoriasGasto) }}</strong>
                      <small>{{ categoriasGasto.length }} categoria(s) com movimentação</small>
                      <div v-if="categoriasGasto[0]" class="top-category">
                        <span>Maior categoria</span>
                        <b>{{ categoriasGasto[0].nome }}</b>
                        <small>{{ formatarMoeda(categoriasGasto[0].valor) }}</small>
                      </div>
                      <div v-if="ajusteCategoria" class="invoice-adjustment">
                        <span>Ajuste de fatura</span>
                        <b :class="classeSaldo(ajusteCategoria.valor)">{{ formatarMoeda(ajusteCategoria.valor) }}</b>
                      </div>
                    </aside>

                    <div class="category-breakdown">
                      <div v-for="categoria in categoriasVisiveis" :key="categoria.nome" class="category-row">
                        <div class="category-row-head">
                          <div>
                            <strong>{{ categoria.nome }}</strong>
                            <small>{{ textoComparacaoCategoria(categoria) }}</small>
                          </div>
                          <div class="category-value">
                            <strong>{{ formatarMoeda(categoria.valor) }}</strong>
                            <small>{{ categoria.percentual.toFixed(1) }}%</small>
                          </div>
                        </div>
                        <ProgressBar :value="categoria.percentual" :show-value="false" />
                      </div>
                      <Button
                        v-if="categoriasGasto.length > 6"
                        :label="mostrarTodasCategorias ? 'Mostrar principais' : `Ver todas (${categoriasGasto.length})`"
                        :icon="mostrarTodasCategorias ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
                        text
                        @click="mostrarTodasCategorias = !mostrarTodasCategorias"
                      />
                    </div>
                  </div>
                  <div v-else class="empty-copy">Ainda não há despesas categorizadas neste período.</div>
                </template>
              </Card>
            </section>
          </TabPanel>

          <TabPanel value="analises">
            <section class="chart-grid">
              <Card class="wide-card">
                <template #title>Evolução financeira</template>
                <template #subtitle>Receitas, despesas e saldo dos últimos 12 meses</template>
                <template #content>
                  <div v-if="ultimoMesEvolucao" class="chart-summary">
                    <span><small>Último período</small><strong>{{ rotuloMes(ultimoMesEvolucao.periodo) }}</strong></span>
                    <span><small>Receitas</small><strong class="positive">{{ formatarMoeda(ultimoMesEvolucao.receitas) }}</strong></span>
                    <span><small>Despesas</small><strong class="negative">{{ formatarMoeda(ultimoMesEvolucao.despesas) }}</strong></span>
                    <span><small>Saldo</small><strong :class="classeSaldo(ultimoMesEvolucao.saldo)">{{ formatarMoeda(ultimoMesEvolucao.saldo) }}</strong></span>
                  </div>
                  <VChart class="chart chart-large" :option="opcoesEvolucao" autoresize />
                </template>
              </Card>

              <Card>
                <template #title>Despesas por categoria</template>
                <template #subtitle>Valores do mês selecionado</template>
                <template #content>
                  <div v-if="categoriasPositivas.length" class="chart-context">{{ categoriasPositivas.length }} categoria(s) · percentuais sobre o gasto categorizado</div>
                  <VChart v-if="categoriasPositivas.length" class="chart" :option="opcoesCategorias" autoresize />
                  <div v-else class="empty-copy">Sem categorias para analisar.</div>
                </template>
              </Card>

              <Card>
                <template #title>Compromissos futuros</template>
                <template #subtitle>Parcelas e recorrências dos próximos seis meses</template>
                <template #content>
                  <div class="chart-context">{{ formatarMoeda(totalCompromissosFuturos) }} já comprometidos no horizonte</div>
                  <VChart class="chart" :option="opcoesCompromissos" autoresize />
                </template>
              </Card>
            </section>

            <Card class="budget-card">
              <template #title>Orçamentos por categoria</template>
              <template #subtitle>Acompanhe limites definidos para o período selecionado</template>
              <template #content>
                <div v-if="dashboard.orcamentos.length" class="budget-list">
                  <div v-for="item in dashboard.orcamentos" :key="item.categoria" class="budget-item">
                    <div class="budget-topline">
                      <strong>{{ item.categoria }}</strong>
                      <Tag :value="`${item.percentual.toFixed(0)}%`" :severity="severityOrcamento(item.status)" />
                    </div>
                    <ProgressBar :value="Math.min(item.percentual, 100)" :show-value="false" :class="item.status" />
                    <small>{{ formatarMoeda(item.gasto) }} de {{ formatarMoeda(item.limite) }}</small>
                  </div>
                </div>
                <div v-else class="empty-copy">Defina limites para receber alertas e acompanhar suas categorias.</div>
                <Button label="Editar orçamentos" icon="pi pi-sliders-h" outlined @click="dialogOrcamento = true" />
              </template>
            </Card>
          </TabPanel>

          <TabPanel value="movimentacoes">
            <Card>
              <template #title>Movimentações do período</template>
              <template #subtitle>Receitas e despesas lançadas; expanda faturas para consultar os itens.</template>
              <template #content>
                <div class="movement-summary">
                  <div><small>Exibindo</small><strong>{{ movimentacoesFiltradas.length }} movimentação(ões)</strong></div>
                  <div><small>Receitas</small><strong class="positive">{{ formatarMoeda(totaisMovimentacoes.receitas) }}</strong></div>
                  <div><small>Despesas</small><strong class="negative">{{ formatarMoeda(totaisMovimentacoes.despesas) }}</strong></div>
                  <Button v-if="busca || tipoFiltro !== 'todos'" label="Limpar filtros" icon="pi pi-filter-slash" text @click="limparFiltros" />
                </div>
                <div class="table-filters">
                  <InputText v-model="busca" placeholder="Buscar descrição ou categoria" />
                  <Select v-model="tipoFiltro" :options="tiposFiltro" option-label="label" option-value="value" />
                </div>
                <DataTable v-model:expanded-rows="linhasExpandidas" :value="movimentacoesFiltradas" data-key="id" paginator :rows="10" :rows-per-page-options="[10, 25, 50]" sort-field="data" :sort-order="-1" striped-rows responsive-layout="scroll">
                  <Column expander style="width: 3rem" />
                  <Column field="data" header="Data"><template #body="{ data }">{{ formatarData(data.data) }}</template></Column>
                  <Column field="descricao" header="Descrição"><template #body="{ data }"><strong>{{ data.descricao }}</strong></template></Column>
                  <Column field="tipo" header="Tipo"><template #body="{ data }"><Tag :value="data.tipo" :severity="data.tipo === 'Receita' ? 'success' : 'danger'" /></template></Column>
                  <Column field="categoria" header="Categoria"><template #body="{ data }">{{ data.categoria || '—' }}</template></Column>
                  <Column field="valor" header="Valor" header-class="right" body-class="right"><template #body="{ data }"><strong :class="data.tipo === 'Receita' ? 'positive' : 'negative'">{{ formatarMoeda(data.valor) }}</strong></template></Column>
                  <template #expansion="{ data }">
                    <div v-if="data.fatura_itens.length" class="invoice-items">
                      <strong>Itens da fatura</strong>
                      <DataTable :value="data.fatura_itens" size="small" striped-rows>
                        <Column field="data" header="Data"><template #body="{ data: item }">{{ formatarData(item.data) }}</template></Column>
                        <Column field="descricao" header="Compra" />
                        <Column field="categoria" header="Categoria" />
                        <Column field="valor" header="Valor" header-class="right" body-class="right"><template #body="{ data: item }">{{ formatarMoeda(item.valor) }}</template></Column>
                      </DataTable>
                    </div>
                    <div v-else class="empty-copy">Esta movimentação não possui itens detalhados.</div>
                  </template>
                  <template #empty><div class="empty-copy">Nenhuma movimentação encontrada.</div></template>
                </DataTable>
              </template>
            </Card>
          </TabPanel>

        </TabPanels>
      </Tabs>
    </template>

    <Dialog v-model:visible="dialogOrcamento" modal header="Editar orçamentos" :style="{ width: 'min(34rem, 92vw)' }">
      <div class="budget-editor">
        <div v-for="item in dashboard?.orcamentos || []" :key="item.categoria" class="budget-editor-row">
          <span>{{ item.categoria }}</span>
          <span>{{ formatarMoeda(item.limite) }}</span>
          <Button icon="pi pi-trash" severity="danger" text aria-label="Remover orçamento" @click="removerOrcamento(item.categoria)" />
        </div>
        <div class="budget-editor-form">
          <Select v-model="novaCategoria" :options="categoriasSemOrcamento" placeholder="Categoria" />
          <InputNumber v-model="novoLimite" mode="currency" currency="BRL" locale="pt-BR" placeholder="Limite" :min="1" />
          <Button label="Adicionar" :disabled="!novaCategoria || !novoLimite" @click="salvarOrcamento" />
        </div>
      </div>
    </Dialog>
  </main>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Skeleton from 'primevue/skeleton'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import VChart from 'vue-echarts'
import { dashboardAPI, orcamentosAPI } from '../api/client'
import { TEMAS_GRAFICO, corDaCategoria } from '../charts'

const temaAplicacao = inject('tema', ref('light'))
const abaAtiva = ref('resumo')
const carregando = ref(true)
const erro = ref('')
const dashboard = ref(null)
const periodoSelecionado = ref(periodoAtual())
const dialogOrcamento = ref(false)
const novaCategoria = ref(null)
const novoLimite = ref(null)
const busca = ref('')
const tipoFiltro = ref('todos')
const linhasExpandidas = ref({})
const mostrarTodasCategorias = ref(false)
let requisicaoAtual = 0

const tiposFiltro = [
  { label: 'Todas as movimentações', value: 'todos' },
  { label: 'Receitas', value: 'Receita' },
  { label: 'Despesas', value: 'Despesa' }
]
const CATEGORIAS_ORCAMENTO = ['Alimentação', 'Transporte', 'Saúde', 'Educação', 'Lazer', 'Moradia', 'Assinaturas', 'Roupas', 'Impostos', 'Cartão de Crédito', 'Outros']

const dataPeriodo = computed({
  get: () => {
    const [ano, mes] = periodoSelecionado.value.split('-').map(Number)
    return new Date(ano, mes - 1, 1)
  },
  set: (valor) => {
    if (valor instanceof Date && !Number.isNaN(valor.getTime())) {
      periodoSelecionado.value = `${valor.getFullYear()}-${String(valor.getMonth() + 1).padStart(2, '0')}`
    }
  }
})

const categoriasGasto = computed(() => (dashboard.value?.categorias || [])
  .filter((item) => item.valor > 0 && !item.eh_ajuste && item.percentual !== null)
  .sort((a, b) => b.valor - a.valor))
const categoriasPositivas = computed(() => categoriasGasto.value)
const categoriasVisiveis = computed(() => mostrarTodasCategorias.value ? categoriasGasto.value : categoriasGasto.value.slice(0, 6))
const ajusteCategoria = computed(() => (dashboard.value?.categorias || []).find((item) => item.eh_ajuste) || null)
const totalCategoriasGasto = computed(() => categoriasGasto.value.reduce((total, item) => total + Number(item.valor || 0), 0))
const ultimoMesEvolucao = computed(() => dashboard.value?.evolucao?.at(-1) || null)
const totalCompromissosFuturos = computed(() => (dashboard.value?.projecao_compromissos || []).reduce((total, item) => total + Number(item.total || 0), 0))
const categoriasSemOrcamento = computed(() => CATEGORIAS_ORCAMENTO.filter((categoria) => !(dashboard.value?.orcamentos || []).some((item) => item.categoria === categoria)))
const movimentacoesFiltradas = computed(() => {
  const termo = busca.value.trim().toLocaleLowerCase('pt-BR')
  return (dashboard.value?.movimentacoes || []).filter((item) => {
    const tipoOk = tipoFiltro.value === 'todos' || item.tipo === tipoFiltro.value
    const texto = `${item.descricao} ${item.categoria || ''} ${item.origem || ''}`.toLocaleLowerCase('pt-BR')
    return tipoOk && (!termo || texto.includes(termo))
  })
})
const totaisMovimentacoes = computed(() => movimentacoesFiltradas.value.reduce((totais, item) => {
  if (item.tipo === 'Receita') totais.receitas += Number(item.valor || 0)
  else totais.despesas += Number(item.valor || 0)
  return totais
}, { receitas: 0, despesas: 0 }))

const tema = computed(() => TEMAS_GRAFICO[temaAplicacao.value] || TEMAS_GRAFICO.light)
const tooltipPadrao = computed(() => ({
  trigger: 'axis',
  backgroundColor: tema.value.superficie,
  borderColor: tema.value.linha,
  textStyle: { color: tema.value.texto },
  axisPointer: { type: 'shadow', shadowStyle: { color: tema.value.linha } },
  valueFormatter: formatarMoeda
}))
const legendaPadrao = computed(() => ({
  top: 4,
  left: 'center',
  itemWidth: 18,
  itemHeight: 10,
  textStyle: { color: tema.value.mutado, fontSize: 12 }
}))

const opcoesEvolucao = computed(() => {
  const evolucao = dashboard.value?.evolucao || []
  return {
    color: [tema.value.bom, tema.value.critico, tema.value.atencao],
    tooltip: { ...tooltipPadrao.value, axisPointer: { type: 'line', lineStyle: { color: tema.value.mutado } } },
    legend: { ...legendaPadrao.value, data: ['Receitas', 'Despesas', 'Saldo'] },
    grid: { left: 12, right: 20, bottom: 18, top: 58, containLabel: true },
    xAxis: {
      type: 'category',
      data: evolucao.map((item) => rotuloMes(item.periodo)),
      axisLabel: { color: tema.value.mutado, hideOverlap: true, margin: 14 },
      axisLine: { lineStyle: { color: tema.value.linha } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: abreviarMoeda, color: tema.value.mutado, margin: 12 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tema.value.linha } }
    },
    series: [
      {
        name: 'Receitas', type: 'bar', barMaxWidth: 28,
        data: evolucao.map((item) => item.receitas),
        itemStyle: { borderRadius: [6, 6, 0, 0] },
        emphasis: { focus: 'series' }
      },
      {
        name: 'Despesas', type: 'bar', barMaxWidth: 28,
        data: evolucao.map((item) => item.despesas),
        itemStyle: { borderRadius: [6, 6, 0, 0] },
        emphasis: { focus: 'series' }
      },
      {
        name: 'Saldo', type: 'line', smooth: 0.28, symbol: 'circle', symbolSize: 7,
        data: evolucao.map((item) => ({
          value: item.saldo,
          itemStyle: { color: item.saldo < 0 ? tema.value.critico : tema.value.atencao }
        })),
        lineStyle: { width: 3, color: tema.value.atencao },
        itemStyle: { borderWidth: 2, borderColor: tema.value.superficie }
      }
    ]
  }
})

const opcoesCategorias = computed(() => {
  const categorias = categoriasPositivas.value.slice(0, 8).reverse()
  return {
    tooltip: tooltipPadrao.value,
    grid: { left: 8, right: 112, top: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { formatter: abreviarMoeda, color: tema.value.mutado },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tema.value.linha } }
    },
    yAxis: {
      type: 'category',
      data: categorias.map((item) => item.nome),
      axisLabel: { color: tema.value.texto, width: 110, overflow: 'truncate' },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [{
      type: 'bar',
      barMaxWidth: 30,
      data: categorias.map((item) => ({
        value: item.valor,
        percentual: item.percentual,
        itemStyle: { color: corDaCategoria(item.nome, tema.value), borderRadius: [0, 6, 6, 0] }
      })),
      label: {
        show: true,
        position: 'right',
        color: tema.value.texto,
        fontWeight: 700,
        formatter: ({ data }) => `${formatarMoeda(data.value)} · ${data.percentual.toFixed(0)}%`
      }
    }]
  }
})

const opcoesCompromissos = computed(() => {
  const projecao = dashboard.value?.projecao_compromissos || []
  return {
    color: [tema.value.atencao, tema.value.neutro],
    tooltip: tooltipPadrao.value,
    legend: { ...legendaPadrao.value, data: ['Parcelas', 'Recorrências'] },
    grid: { left: 10, right: 18, bottom: 18, top: 58, containLabel: true },
    xAxis: {
      type: 'category',
      data: projecao.map((item) => rotuloMes(item.periodo)),
      axisLabel: { color: tema.value.mutado, margin: 12 },
      axisLine: { lineStyle: { color: tema.value.linha } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: abreviarMoeda, color: tema.value.mutado },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tema.value.linha } }
    },
    series: [
      {
        name: 'Parcelas', type: 'bar', stack: 'total', barMaxWidth: 46,
        data: projecao.map((item) => item.parcelas),
        itemStyle: { borderRadius: [0, 0, 4, 4] }
      },
      {
        name: 'Recorrências', type: 'bar', stack: 'total', barMaxWidth: 46,
        data: projecao.map((item) => item.recorrentes),
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      },
      {
        name: 'Total', type: 'line', symbol: 'none',
        data: projecao.map((item) => item.total),
        lineStyle: { opacity: 0 },
        itemStyle: { opacity: 0 },
        label: { show: true, position: 'top', color: tema.value.texto, fontWeight: 700, formatter: ({ value }) => abreviarMoeda(value) },
        tooltip: { show: false }
      }
    ]
  }
})

const legendaComparacao = computed(() => dashboard.value?.periodo.status === 'atual' ? 'comparação até o dia de hoje' : 'comparação de meses completos')

watch(periodoSelecionado, carregarDashboard, { immediate: true })

async function carregarDashboard() {
  const [ano, mes] = periodoSelecionado.value.split('-').map(Number)
  const id = ++requisicaoAtual
  carregando.value = true
  erro.value = ''
  try {
    const resposta = await dashboardAPI.obter(mes, ano)
    if (id === requisicaoAtual) {
      dashboard.value = resposta.data
      mostrarTodasCategorias.value = false
    }
  } catch (causa) {
    if (id === requisicaoAtual) erro.value = causa.response?.data?.detail || 'Não foi possível carregar o dashboard.'
  } finally {
    if (id === requisicaoAtual) carregando.value = false
  }
}

async function salvarOrcamento() {
  if (!novaCategoria.value || !novoLimite.value) return
  await orcamentosAPI.definir(novaCategoria.value, Number(novoLimite.value))
  novaCategoria.value = null
  novoLimite.value = null
  await carregarDashboard()
}

async function removerOrcamento(categoria) {
  await orcamentosAPI.remover(categoria)
  await carregarDashboard()
}

function limparFiltros() { busca.value = ''; tipoFiltro.value = 'todos' }
function textoComparacaoCategoria(categoria) {
  const variacao = categoria.variacao_anterior
  if (variacao === null || variacao === undefined) return 'sem base no mês anterior'
  if (Math.abs(variacao) < 1) return 'estável em relação ao mês anterior'
  return `${Math.abs(variacao).toFixed(0)}% ${variacao > 0 ? 'acima' : 'abaixo'} do mês anterior`
}
function periodoAtual() { const hoje = new Date(); return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}` }
function formatarMoeda(valor) { return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(valor || 0)) }
function abreviarMoeda(valor) { return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1 }).format(Number(valor || 0)) }
function formatarData(valor) { if (!valor) return '—'; const [ano, mes, dia] = String(valor).split('-'); return ano && mes && dia ? `${dia}/${mes}/${ano}` : String(valor) }
function rotuloMes(valor) { const [ano, mes] = String(valor).split('-'); return ano && mes ? `${mes}/${ano.slice(2)}` : valor }
function classeSaldo(valor) { return Number(valor) < 0 ? 'negative' : 'positive' }
function classeVariacao(valor) { return valor === null || valor === undefined ? 'muted' : (valor > 0 ? 'negative' : 'positive') }
function textoVariacao(valor) { if (valor === null || valor === undefined) return '—'; return `${valor > 0 ? '▲' : '▼'} ${Math.abs(valor).toFixed(0)}%` }
function severityOrcamento(status) { return status === 'critico' ? 'danger' : (status === 'atencao' ? 'warning' : 'success') }
</script>

<style scoped>
.dashboard.router-view {
  width: 80%;
  max-width: none;
  padding: 2rem 0 3.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 2rem;
  margin-bottom: 1.25rem;
}

.eyebrow,
.card-kicker {
  color: var(--primary-strong);
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

h1 {
  font-size: clamp(2.15rem, 4vw, 3rem);
  line-height: 1;
  margin: 0.35rem 0 0.65rem;
}

.page-header p,
small,
.empty-copy,
.chart-context {
  color: var(--muted);
}

.period-picker {
  min-width: 13rem;
  display: grid;
  gap: 0.4rem;
  color: var(--muted);
  font-size: 0.85rem;
}

.dashboard-tabs { margin-top: 0.75rem; }
.dashboard-tabs :deep(.p-tablist-tab-list) { gap: 0.35rem; border: 0; flex-wrap: wrap; }
.dashboard-tabs :deep(.p-tab) { border: 0; border-radius: 10px; gap: 0.45rem; }
.dashboard-tabs :deep(.p-tabpanels) { background: transparent; padding: 1.25rem 0 0; }

.hero-grid,
.metric-grid,
.summary-grid,
.chart-grid,
.loading-grid,
.budget-list {
  display: grid;
  gap: 1rem;
}

.hero-grid { grid-template-columns: minmax(0, 1.25fr) minmax(19rem, 0.75fr); }
.projection-card :deep(.p-card-content),
.comparison-card :deep(.p-card-content) { min-height: 11rem; display: grid; align-content: space-between; gap: 0.8rem; }
.projection-card :deep(.p-card-content) > strong { font-size: clamp(2.2rem, 4vw, 3.5rem); line-height: 1; }
.projection-card.positive { border-color: color-mix(in srgb, var(--success) 35%, var(--line)); background: color-mix(in srgb, var(--success-soft) 55%, var(--surface)); }
.projection-card.negative { border-color: color-mix(in srgb, var(--danger) 35%, var(--line)); background: color-mix(in srgb, var(--danger-soft) 55%, var(--surface)); }
.projection-meta { display: flex; justify-content: space-between; gap: 1rem; border-top: 1px solid var(--line); padding-top: 0.75rem; color: var(--muted); }

.comparison-values { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
.comparison-values span,
.metric-grid span { display: block; color: var(--muted); font-size: 0.84rem; }
.comparison-values strong { display: block; font-size: 1.3rem; margin-top: 0.25rem; }

.metric-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 1rem 0; }
.metric-grid :deep(.p-card-content) { min-height: 7.25rem; display: grid; align-content: space-between; }
.metric-grid strong { display: block; font-size: clamp(1.15rem, 2vw, 1.4rem); margin: 0.25rem 0; overflow-wrap: anywhere; }
.positive { color: var(--success); }
.negative { color: var(--danger); }
.warning { color: var(--warning); }
.muted { color: var(--muted); }

.summary-grid { grid-template-columns: minmax(0, 1fr); }
.spending-layout { display: grid; grid-template-columns: minmax(14rem, 0.34fr) minmax(0, 1fr); gap: 1.5rem; align-items: start; }
.spending-overview { min-height: 100%; padding: 1.1rem; border: 1px solid var(--line); border-radius: 14px; background: var(--surface-strong); display: grid; align-content: start; gap: 0.35rem; }
.spending-overview > span,
.top-category span,
.invoice-adjustment span { color: var(--muted); font-size: 0.82rem; }
.spending-overview > strong { font-size: clamp(1.8rem, 3vw, 2.5rem); margin: 0.15rem 0; }
.top-category,
.invoice-adjustment { display: grid; gap: 0.18rem; padding-top: 0.9rem; margin-top: 0.55rem; border-top: 1px solid var(--line); }
.category-breakdown { display: grid; gap: 0.85rem; }
.category-row { display: grid; gap: 0.5rem; }
.category-row-head { display: flex; justify-content: space-between; gap: 1rem; align-items: start; }
.category-row-head strong,
.category-row-head small { display: block; }
.category-row-head small { margin-top: 0.12rem; font-size: 0.78rem; }
.category-value { text-align: right; flex: 0 0 auto; }
.category-value small { margin-top: 0.1rem; }
.category-row :deep(.p-progressbar) { height: 0.5rem; background: var(--surface-muted); }
.category-row :deep(.p-progressbar-value) { background: linear-gradient(90deg, var(--primary), var(--primary-strong)); }

.chart-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.wide-card { grid-column: 1 / -1; }
.chart { height: 21rem; width: 100%; }
.chart-large { height: 25rem; }
.chart-context { min-height: 1.25rem; font-size: 0.82rem; margin-bottom: 0.35rem; }
.chart-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin-bottom: 0.3rem; }
.chart-summary span { padding: 0.65rem 0.75rem; border-radius: 10px; background: var(--surface-strong); border: 1px solid var(--line); }
.chart-summary small,
.chart-summary strong { display: block; }
.chart-summary strong { margin-top: 0.18rem; font-size: 0.92rem; }

.budget-card { margin-top: 1rem; }
.budget-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.budget-item { padding: 0.85rem; border: 1px solid var(--line); border-radius: 12px; }
.budget-topline { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; margin-bottom: 0.6rem; }
.budget-item small { display: block; margin-top: 0.4rem; }
.budget-item :deep(.p-progressbar) { height: 0.55rem; }
.budget-item :deep(.p-progressbar-value) { background: var(--success); }
.budget-item :deep(.p-progressbar.atencao .p-progressbar-value) { background: var(--warning); }
.budget-item :deep(.p-progressbar.critico .p-progressbar-value) { background: var(--danger); }

.movement-summary { display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; padding: 0.8rem 0; margin-bottom: 0.75rem; border-bottom: 1px solid var(--line); }
.movement-summary div { display: grid; gap: 0.12rem; }
.movement-summary .p-button { margin-left: auto; }
.table-filters { display: flex; gap: 0.75rem; margin-bottom: 1rem; }
.table-filters .p-inputtext { flex: 1; }
.table-filters .p-select { width: min(19rem, 100%); }
:deep(.right) { text-align: right; }
.invoice-items { padding: 0.75rem 1rem; display: grid; gap: 0.75rem; }

.loading-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.budget-editor { display: grid; gap: 0.75rem; }
.budget-editor-row { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--line); }
.budget-editor-form { display: grid; grid-template-columns: 1fr 1fr auto; gap: 0.6rem; margin-top: 0.4rem; }

@media (max-width: 1100px) {
  .hero-grid { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-grid { grid-template-columns: 1fr; }
  .wide-card { grid-column: auto; }
}

@media (max-width: 760px) {
  .dashboard.router-view { width: calc(100% - 1.25rem); padding-top: 1.25rem; }
  .page-header { align-items: stretch; flex-direction: column; gap: 1rem; }
  .period-picker { max-width: 15rem; }
  .spending-layout { grid-template-columns: 1fr; }
  .chart-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .budget-list,
  .loading-grid { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .metric-grid,
  .comparison-values,
  .chart-summary { grid-template-columns: 1fr; }
  .table-filters,
  .budget-editor-form { grid-template-columns: 1fr; display: grid; }
  .table-filters .p-select { width: 100%; }
  .movement-summary { align-items: stretch; display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
  .movement-summary div:first-child,
  .movement-summary .p-button { grid-column: 1 / -1; margin-left: 0; }
  .category-row-head { gap: 0.5rem; }
  .chart,
  .chart-large { height: 20rem; }
}
</style>
