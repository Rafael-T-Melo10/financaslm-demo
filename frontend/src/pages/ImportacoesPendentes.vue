<template>
  <main class="page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Gmail</p>
        <h1>Importações pendentes</h1>
        <p>Revise o que foi encontrado automaticamente na sua caixa antes de lançar.</p>
      </div>
    </section>

    <Card class="gmail-panel">
      <template #content>
        <div class="gmail-status">
          <span class="gmail-dot" :class="{ conectado: gmailStatus.conectado }" aria-hidden="true"></span>
          <div>
            <strong v-if="gmailStatus.conectado">Conectado como {{ gmailStatus.email_conectado }}</strong>
            <strong v-else>Nenhuma caixa de Gmail conectada</strong>
            <small v-if="gmailStatus.conectado && gmailStatus.ultima_sincronizacao">
              Última sincronização {{ formatarDataHora(gmailStatus.ultima_sincronizacao) }}
            </small>
          </div>
        </div>

        <div class="gmail-actions">
          <span v-if="gmailStatus.ultimo_erro" class="gmail-error-pill">{{ gmailStatus.ultimo_erro }}</span>

          <Button
            v-if="!gmailStatus.conectado"
            :label="conectando ? 'Abrindo...' : 'Conectar Gmail'"
            icon="pi pi-google"
            :loading="conectando"
            @click="conectarGmail"
          />
          <Button
            v-else-if="precisaReconectarGmail"
            :label="conectando ? 'Abrindo...' : 'Reconectar Gmail'"
            icon="pi pi-google"
            :loading="conectando"
            @click="conectarGmail"
          />
          <Button
            v-else
            class="sync-button"
            :label="textoSincronizacao"
            icon="pi pi-refresh"
            :loading="sincronizacaoEmAndamento"
            @click="sincronizarAgora"
          />
        </div>

        <Message v-if="gmailErroLocal" severity="error" :closable="false">{{ gmailErroLocal }}</Message>
      </template>
    </Card>

    <Tabs v-model:value="statusAtivo" class="status-tabs">
      <TabList>
        <Tab v-for="aba in abas" :key="aba.valor" :value="aba.valor">
          <span class="tab-label">{{ aba.label }}</span>
          <span v-if="statusAtivo === aba.valor" class="tab-count">{{ totalItens }}</span>
        </Tab>
      </TabList>
    </Tabs>

    <div v-if="statusAtivo === 'pendente' && totalItens" class="all-actions" aria-label="Acoes para todos os itens pendentes">
      <Button
        :label="processandoLote ? textoProgressoLote : `Aceitar todos (${totalItens})`"
        icon="pi pi-check"
        :disabled="processandoLote"
        :loading="processandoLote"
        @click="confirmarTodos"
      />
      <Button
        label="Rejeitar todos"
        icon="pi pi-times"
        severity="danger"
        outlined
        :disabled="processandoLote"
        @click="rejeitarTodos"
      />
    </div>
    <div v-else-if="statusAtivo === 'erro' && totalItens" class="all-actions" aria-label="Acoes para todos os itens com erro">
      <Button
        :label="processandoLote ? textoProgressoLote : `Reprocessar todos (${totalItens})`"
        icon="pi pi-refresh"
        :disabled="processandoLote"
        :loading="processandoLote"
        @click="reprocessarTodos"
      />
      <span v-if="processandoLote" class="all-actions-progress" aria-live="polite">{{ textoProgressoLote }}</span>
    </div>

    <section class="import-grid">
      <Card class="list-card">
        <template #title>{{ totalItens }} item(ns)</template>
        <template #subtitle>Selecione um item para revisar os dados extraídos.</template>
        <template #content>
          <div v-if="statusAtivo === 'pendente' && selecionados.size" class="bulk-bar">
            <div class="bulk-summary">
              <div>
                <strong>{{ selecionados.size }} selecionado(s)</strong>
                <span>{{ selecionadosConfirmaveis.length }} pronto(s) para confirmar</span>
              </div>
              <div class="bulk-counts" aria-label="Resumo da seleção">
                <span class="bulk-chip ready">{{ selecionadosConfirmaveis.length }} confirmável(is)</span>
                <span v-if="selecionadosBloqueados.length" class="bulk-chip blocked">
                  {{ selecionadosBloqueados.length }} precisam de cartão
                </span>
              </div>
            </div>
            <Button
              class="bulk-action"
              :label="processandoLote ? 'Confirmando...' : `Confirmar selecionados (${selecionadosConfirmaveis.length})`"
              icon="pi pi-check"
              :disabled="!selecionadosConfirmaveis.length || processandoLote"
              :loading="processandoLote"
              @click="confirmarSelecionados"
            />
            <p v-if="selecionadosBloqueados.length" class="bulk-warning">
              {{ selecionadosBloqueados.length }} precisam de cartão antes de confirmar.
            </p>
          </div>

          <div v-if="itens.length" class="pending-list">
            <div v-for="item in itens" :key="item.id" class="pending-row">
              <Checkbox
                v-if="statusAtivo === 'pendente'"
                binary
                class="pending-checkbox"
                :model-value="selecionados.has(item.id)"
                :input-id="`importacao-pendente-${item.id}`"
                :aria-label="`Selecionar ${item.remetente}`"
                @update:model-value="alternarSelecao(item.id)"
                @click.stop
              />
              <Button
                type="button"
                unstyled
                class="pending-item"
                :class="{ active: itemSelecionadoId === item.id, selected: selecionados.has(item.id) }"
                @click="selecionarItem(item.id)"
              >
                <Tag
                  :value="rotuloTipo(item.tipo_detectado)"
                  :severity="severidadeTipo(item.tipo_detectado)"
                  :class="['pending-type-tag', `tipo-${item.tipo_detectado}`]"
                />
                <div class="pending-item-info">
                  <strong>{{ item.remetente }}</strong>
                  <small>{{ item.assunto || 'Sem assunto' }}</small>
                </div>
                <small class="pending-item-data">{{ formatarDataHora(item.data_recebimento) }}</small>
              </Button>
            </div>
          </div>

          <div v-else class="empty-state">
            <strong>Nada por aqui</strong>
            <p>Quando o Gmail encontrar novas contas ou faturas, elas aparecem nesta lista.</p>
          </div>

          <Paginator
            v-if="totalItens > tamanhoPagina"
            :rows="tamanhoPagina"
            :total-records="totalItens"
            :first="(paginaAtual - 1) * tamanhoPagina"
            @page="aoMudarPagina"
          />
        </template>
      </Card>

      <Card v-if="itemSelecionado" class="detail-card">
        <template #title>Detalhe</template>
        <template #subtitle>{{ itemSelecionado.remetente }}</template>
        <template #content>
          <a
            v-if="itemSelecionado.gmail_message_id"
            :href="linkGmail(itemSelecionado)"
            target="_blank"
            rel="noopener"
            class="link-gmail detail-gmail-link"
          >
            Abrir e-mail original no Gmail <i class="pi pi-external-link" aria-hidden="true"></i>
          </a>
          <template v-if="itemSelecionado.status === 'erro'">
            <div class="result erro">
              <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
              <div>
                <strong>Não foi possível processar este PDF</strong>
                <span>{{ itemSelecionado.mensagem_erro }}</span>
              </div>
            </div>
            <div class="detail-actions">
              <span class="detail-actions-copy">
                <strong>Este item não pôde ser processado</strong>
                <span>Reprocesse depois de corrigir o parser ou descarte para remover da fila de revisão.</span>
              </span>
              <div class="detail-actions-buttons">
                <Button label="Descartar" severity="secondary" outlined :disabled="processando" @click="rejeitarItem" />
                <Button
                  :label="processando ? 'Reprocessando...' : 'Reprocessar'"
                  icon="pi pi-refresh"
                  :disabled="processando"
                  :loading="processando"
                  @click="reabrirItem"
                />
              </div>
            </div>
          </template>

          <template v-else-if="itemSelecionado.status !== 'pendente'">
            <div class="detail-actions">
              <span class="detail-actions-copy">
                <strong>{{ rotuloStatus(itemSelecionado.status) }}</strong>
                <span v-if="itemSelecionado.status === 'confirmada'">Já lançado no sistema — não é possível reabrir.</span>
                <span v-else>Rejeitou por engano? Reabra para revisar novamente.</span>
              </span>
              <Button
                v-if="itemSelecionado.status === 'rejeitada'"
                label="Reabrir"
                severity="secondary"
                outlined
                :disabled="processando"
                @click="reabrirItem"
              />
            </div>
          </template>

          <template v-else>
            <div class="detail-top-row">
              <div class="detail-field" v-if="itemSelecionado.tipo_detectado === 'fatura'">
                <label for="cartao-pendente">Cartão</label>

                <div v-if="mostrarAvisoCartaoNaoEncontrado" class="aviso-alerta">
                  <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
                  <span>Não encontramos um cartão "{{ itemSelecionado.nome_cartao_detectado }}" cadastrado.</span>
                  <Button
                    :label="`Criar cartão ${itemSelecionado.nome_cartao_detectado}`"
                    size="small"
                    severity="warn"
                    outlined
                    @click="abrirNovoCartaoComNome(itemSelecionado.nome_cartao_detectado)"
                  />
                </div>

                <div class="cartao-select-row">
                  <Select
                    id="cartao-pendente"
                    v-model="cartaoSelecionado"
                    :options="cartoes"
                    option-label="nome"
                    option-value="id"
                    placeholder="Selecione um cartão"
                  />
                  <Button label="+ Novo cartão" severity="secondary" outlined @click="abrirNovoCartaoComNome()" />
                </div>
              </div>

              <div class="metric-grid">
                <Card v-if="itemSelecionado.tipo_detectado === 'fatura'" class="metric-card metric-card-hero">
                  <template #content>
                    <span>Total da fatura</span>
                    <strong>{{ formatarMoeda(itemSelecionado.dados_extraidos.total_fatura) }}</strong>
                  </template>
                </Card>
                <Card v-if="itemSelecionado.tipo_detectado === 'fatura'" class="metric-card">
                  <template #content>
                    <span>Compras</span>
                    <strong>{{ despesasDetalhe.length }}</strong>
                  </template>
                </Card>
                <Card v-if="itemSelecionado.tipo_detectado !== 'fatura'" class="metric-card metric-card-hero">
                  <template #content>
                    <span>{{ rotuloTotalDetalhe }}</span>
                    <strong>{{ formatarMoeda(totalDetalheSelecionado) }}</strong>
                  </template>
                </Card>
              </div>
            </div>

            <DataTable
              v-if="despesasDetalhe.length"
              :value="despesasVisiveis"
              data-key="descricao"
              paginator
              :rows="tamanhoPaginaDespesas"
              :total-records="despesasDetalhe.length"
              :first="paginaDespesas * tamanhoPaginaDespesas"
              paginator-template="FirstPageLink PrevPageLink CurrentPageReport NextPageLink LastPageLink"
              current-page-report-template="{first}-{last} de {totalRecords}"
              responsive-layout="scroll"
              striped-rows
              class="despesas-table"
              @page="aoMudarPaginaDespesas"
            >
              <Column v-if="itemSelecionado.tipo_detectado !== 'holerite'" field="data" header="Data">
                <template #body="{ data }">{{ formatarData(data.data) }}</template>
              </Column>
              <Column field="descricao" header="Descrição" />
              <Column v-if="itemSelecionado.tipo_detectado === 'holerite'" field="tipo" header="Tipo">
                <template #body="{ data }">
                  <Tag
                    :value="data.tipo === 'desconto' ? 'Desconto' : 'Provento'"
                    :severity="data.tipo === 'desconto' ? 'danger' : 'success'"
                  />
                </template>
              </Column>
              <Column field="valor" header="Valor" body-class="right" header-class="right">
                <template #body="{ data }">{{ formatarMoeda(data.valor) }}</template>
              </Column>
            </DataTable>

            <div v-else class="aviso-alerta">
              <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
              <span>Não conseguimos extrair itens deste documento. Revise o PDF original ou rejeite este item.</span>
            </div>

            <div class="detail-actions">
              <Button label="Rejeitar" severity="secondary" outlined :disabled="processando" @click="rejeitarItem" />
              <Button
                :label="processando ? 'Importando...' : 'Importar'"
                icon="pi pi-check"
                :disabled="processando || !despesasDetalhe.length || (itemSelecionado.tipo_detectado === 'fatura' && !cartaoIdConfirmacaoAtual)"
                :loading="processando"
                @click="confirmarItem"
              />
            </div>
          </template>
        </template>
      </Card>
    </section>

    <Dialog v-model:visible="mostrarNovoCartao" modal header="Novo cartão" :style="{ width: 'min(92vw, 560px)' }">
      <CartaoForm
        :key="novoCartaoFormKey"
        :nome-inicial="nomeCartaoInicial"
        :limite-inicial="limiteCartaoInicial"
        :vencimento-inicial="vencimentoCartaoInicial"
        @saved="aoCriarCartaoInline"
        @cancel="mostrarNovoCartao = false"
      />
    </Dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Paginator from 'primevue/paginator'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import CartaoForm from '../components/CartaoForm.vue'
import { cartoesAPI, gmailAPI, importacoesPendentesAPI } from '../api/client'
import { useNotifications } from '../composables/useNotifications'

const route = useRoute()
const router = useRouter()
const confirm = useConfirm()

const abas = [
  { valor: 'pendente', label: 'Pendentes' },
  { valor: 'confirmada', label: 'Confirmadas' },
  { valor: 'rejeitada', label: 'Rejeitadas' },
  { valor: 'erro', label: 'Com erro' }
]

const statusAtivo = ref('pendente')
const itens = ref([])
const cartoes = ref([])
const itemSelecionadoId = ref(null)
const cartaoSelecionado = ref('')
const mostrarNovoCartao = ref(false)
const nomeCartaoInicial = ref('')
const limiteCartaoInicial = ref(null)
const vencimentoCartaoInicial = ref(null)
const novoCartaoFormKey = ref(0)
const gmailStatus = ref({ conectado: false })
const conectando = ref(false)
const sincronizando = ref(false)
const gmailErroLocal = ref('')
const processando = ref(false)
const paginaAtual = ref(1)
const paginaDespesas = ref(0)
const totalItens = ref(0)
const tamanhoPagina = 5
const tamanhoPaginaDespesas = 5
const selecionados = ref(new Set())
const processandoLote = ref(false)
const progressoLote = ref({ atual: 0, total: 0, acao: '' })
const {
  items: notificacoesGlobais,
  notificacaoGmailAtiva,
  acompanharOperacao,
  atualizar: atualizarNotificacoes
} = useNotifications()

const itemSelecionado = computed(() => (
  itens.value.find((item) => item.id === itemSelecionadoId.value) || null
))

const despesasDetalhe = computed(() => {
  const dados = itemSelecionado.value?.dados_extraidos || {}
  return itemSelecionado.value?.tipo_detectado === 'holerite'
    ? (dados.itens || [])
    : (dados.despesas || [])
})

const despesasVisiveis = computed(() => {
  const inicio = paginaDespesas.value * tamanhoPaginaDespesas
  return despesasDetalhe.value.slice(inicio, inicio + tamanhoPaginaDespesas)
})

const rotuloTotalDetalhe = computed(() => (
  itemSelecionado.value?.tipo_detectado === 'holerite' ? 'Líquido' : 'Total'
))

const totalDetalheSelecionado = computed(() => {
  const dados = itemSelecionado.value?.dados_extraidos || {}
  if (itemSelecionado.value?.tipo_detectado === 'holerite') {
    return totalHolerite(dados)
  }
  return totalDespesas(despesasDetalhe.value)
})

const ehConfirmavelEmLote = (item) => (
  item.tipo_detectado !== 'fatura' || resolverCartaoIdItem(item) != null
)

const selecionadosConfirmaveis = computed(() => (
  itens.value.filter((item) => selecionados.value.has(item.id) && ehConfirmavelEmLote(item))
))

const selecionadosBloqueados = computed(() => (
  itens.value.filter((item) => selecionados.value.has(item.id) && !ehConfirmavelEmLote(item))
))

const textoProgressoLote = computed(() => {
  const { atual, total, acao } = progressoLote.value
  return total ? `${acao} ${atual} de ${total}...` : `${acao}...`
})

const textoSincronizacao = computed(() => {
  const notificacao = notificacaoGmailAtiva.value
  if (notificacao) {
    if (!notificacao.progresso_total) return 'Buscando emails...'
    return `Processando ${notificacao.progresso_atual ?? 0} de ${notificacao.progresso_total}...`
  }
  if (gmailStatus.value.sincronizando) {
    if (!gmailStatus.value.sync_total) return 'Buscando emails...'
    return `Processando ${gmailStatus.value.sync_processados ?? 0} de ${gmailStatus.value.sync_total}...`
  }
  return 'Sincronizar agora'
})

const sincronizacaoEmAndamento = computed(() => (
  // sincronizando.value = "eu acabei de clicar, requisição em voo" -- isso sim trava o botão.
  // gmailStatus.value.sincronizando é o espelho do estado no backend e NÃO deve travar o botão:
  // se uma sincronização anterior morreu sem limpar essa flag, ela só se destrava numa NOVA
  // tentativa (ver LOCK_TIMEOUT_MINUTOS em gmail_sync.py) -- travar o botão nessa condição cria
  // um impasse em que o usuário nunca consegue clicar no botão que resolveria o problema. Clicar
  // com uma sincronização de verdade em andamento é seguro: o backend devolve ja_em_andamento e
  // não faz nada.
  sincronizando.value || Boolean(notificacaoGmailAtiva.value)
))
const precisaReconectarGmail = computed(() => (
  String(gmailStatus.value.ultimo_erro || '').includes('RefreshError')
))
const ultimaNotificacaoGmail = computed(() => (
  notificacoesGlobais.value.find((item) => item.tipo === 'gmail') || null
))

const normalizarTextoBusca = (texto = '') => (
  String(texto || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9]/g, '')
    .toUpperCase()
)

const resolverCartaoIdItem = (item) => {
  if (!item || item.tipo_detectado !== 'fatura') return null
  if (item.cartao_id_sugerido != null) return item.cartao_id_sugerido

  const alvo = normalizarTextoBusca(item.nome_cartao_detectado)
  if (!alvo) return null

  const cartao = cartoes.value.find((itemCartao) => {
    const nomeCartao = normalizarTextoBusca(itemCartao.nome)
    return nomeCartao.includes(alvo) || alvo.includes(nomeCartao)
  })

  return cartao?.id ?? null
}

const cartaoIdConfirmacaoAtual = computed(() => (
  itemSelecionado.value?.tipo_detectado === 'fatura'
    ? (cartaoSelecionado.value || resolverCartaoIdItem(itemSelecionado.value) || null)
    : null
))

const mostrarAvisoCartaoNaoEncontrado = computed(() => (
  Boolean(
    itemSelecionado.value?.tipo_detectado === 'fatura'
    && itemSelecionado.value?.nome_cartao_detectado
    && !resolverCartaoIdItem(itemSelecionado.value)
    && !cartaoSelecionado.value
  )
))

const sincronizarCartaoSelecionado = (item) => {
  cartaoSelecionado.value = item?.cartao_id_sugerido || resolverCartaoIdItem(item) || ''
}

watch(itemSelecionado, (item) => {
  sincronizarCartaoSelecionado(item)
  paginaDespesas.value = 0
})

onMounted(async () => {
  if (route.query.gmail_conectado || route.query.gmail_erro) {
    if (route.query.gmail_erro) gmailErroLocal.value = String(route.query.gmail_erro)
    router.replace({ path: '/importacoes-pendentes' })
    await atualizarNotificacoes(false)
  }

  await Promise.all([carregarItens(), carregarCartoes(), carregarStatusGmail()])
})

watch(() => ultimaNotificacaoGmail.value ? `${ultimaNotificacaoGmail.value.id}:${ultimaNotificacaoGmail.value.estado}` : '', async (atual) => {
  if (atual.endsWith(':em_andamento')) {
    sincronizando.value = true
    return
  }
  if (atual && sincronizando.value) {
    sincronizando.value = false
    paginaAtual.value = 1
    await Promise.all([carregarStatusGmail(), carregarItens()])
  }
})

watch(statusAtivo, () => {
  itemSelecionadoId.value = null
  paginaAtual.value = 1
  selecionados.value = new Set()
  carregarItens()
})

const carregarItens = async () => {
  try {
    const response = await importacoesPendentesAPI.listar(statusAtivo.value, paginaAtual.value, tamanhoPagina)
    itens.value = response.data.items
    totalItens.value = response.data.total
    if (!itens.value.some((item) => item.id === itemSelecionadoId.value)) {
      itemSelecionadoId.value = itens.value[0]?.id || null
    }
  } catch (erro) {
    console.error('Erro ao carregar importações pendentes:', erro)
  }
}

const aoMudarPagina = (evento) => {
  const alvo = evento.page + 1
  if (alvo === paginaAtual.value) return
  paginaAtual.value = alvo
  itemSelecionadoId.value = null
  selecionados.value = new Set()
  carregarItens()
}

const aoMudarPaginaDespesas = (evento) => {
  paginaDespesas.value = evento.page
}

const alternarSelecao = (id) => {
  const novo = new Set(selecionados.value)
  if (novo.has(id)) {
    novo.delete(id)
  } else {
    novo.add(id)
  }
  selecionados.value = novo
}

const confirmarSelecionados = async () => {
  const alvos = selecionadosConfirmaveis.value
  if (!alvos.length) return

  processandoLote.value = true
  const resultados = await Promise.allSettled(
    alvos.map((item) => {
      const cartaoId = resolverCartaoIdItem(item)
      const dados = item.tipo_detectado === 'fatura' ? { cartao_id: cartaoId } : {}
      return importacoesPendentesAPI.confirmar(item.id, dados)
    })
  )
  processandoLote.value = false

  const falhas = resultados
    .map((resultado, indice) => ({ resultado, item: alvos[indice] }))
    .filter(({ resultado }) => resultado.status === 'rejected')

  selecionados.value = new Set()
  await carregarItens()

  if (falhas.length) {
    alert(
      `${falhas.length} item(ns) não confirmados:\n` +
      falhas.map(({ item, resultado }) => `${item.remetente}: ${resultado.reason?.response?.data?.detail || resultado.reason.message}`).join('\n')
    )
  }
}

const buscarTodosItens = async (status) => {
  const response = await importacoesPendentesAPI.listar(status, 1, Math.max(totalItens.value, 1))
  return response.data.items
}

const executarEmLote = async (alvos, executar, acao) => {
  processandoLote.value = true
  progressoLote.value = { atual: 0, total: alvos.length, acao }
  const resultados = []

  try {
    for (const item of alvos) {
      try {
        resultados.push({ status: 'fulfilled', value: await executar(item) })
      } catch (reason) {
        resultados.push({ status: 'rejected', reason })
      } finally {
        progressoLote.value = { ...progressoLote.value, atual: resultados.length }
      }
    }
  } finally {
    processandoLote.value = false
    selecionados.value = new Set()
    await carregarItens()
  }

  const falhas = resultados.filter((resultado) => resultado.status === 'rejected')
  if (falhas.length) {
    alert(`${falhas.length} item(ns) nao puderam ser processados. Revise-os individualmente.`)
  }
  return falhas.length
}

const confirmarTodos = () => {
  confirm.require({
    header: 'Aceitar todas as importacoes',
    message: `Confirmar todos os ${totalItens.value} itens pendentes? Esta acao vai criar os lancamentos correspondentes.`,
    acceptLabel: 'Aceitar todos',
    rejectLabel: 'Cancelar',
    accept: async () => {
      const pendentes = await buscarTodosItens('pendente')
      const confirmaveis = pendentes.filter(ehConfirmavelEmLote)
      const semCartao = pendentes.length - confirmaveis.length
      const falhas = await executarEmLote(confirmaveis, (item) => {
        const cartaoId = resolverCartaoIdItem(item)
        return importacoesPendentesAPI.confirmar(
          item.id,
          item.tipo_detectado === 'fatura' ? { cartao_id: cartaoId } : {}
        )
      }, 'Aceitando')
      if (semCartao || falhas) {
        alert(`${confirmaveis.length - falhas} item(ns) aceitos. ${semCartao} fatura(s) sem cartao associado ficaram pendentes.`)
      }
    }
  })
}

const rejeitarTodos = () => {
  confirm.require({
    header: 'Rejeitar todas as importacoes',
    message: `Rejeitar todos os ${totalItens.value} itens pendentes? Eles deixarao de aparecer na fila de revisao.`,
    acceptLabel: 'Rejeitar todos',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const pendentes = await buscarTodosItens('pendente')
      await executarEmLote(pendentes, (item) => importacoesPendentesAPI.rejeitar(item.id), 'Rejeitando')
    }
  })
}

const reprocessarTodos = () => {
  confirm.require({
    header: 'Reprocessar todas as importacoes com erro',
    message: `Reprocessar todos os ${totalItens.value} itens com erro? Os arquivos serao baixados novamente do Gmail.`,
    acceptLabel: 'Reprocessar todos',
    rejectLabel: 'Cancelar',
    accept: async () => {
      const itensComErro = await buscarTodosItens('erro')
      await executarEmLote(itensComErro, (item) => importacoesPendentesAPI.reabrir(item.id), 'Reprocessando')
    }
  })
}

const carregarCartoes = async () => {
  try {
    const response = await cartoesAPI.listar()
    cartoes.value = response.data
  } catch (erro) {
    console.error('Erro ao carregar cartões:', erro)
  }
}

const carregarStatusGmail = async () => {
  try {
    const response = await gmailAPI.status()
    gmailStatus.value = response.data
  } catch (erro) {
    console.error('Erro ao carregar status do Gmail:', erro)
  }
}

const selecionarItem = (id) => {
  itemSelecionadoId.value = id
}

const aoCriarCartaoInline = (cartao) => {
  cartoes.value.push(cartao)
  cartaoSelecionado.value = cartao.id
  mostrarNovoCartao.value = false
}

const abrirNovoCartaoComNome = (nome = '') => {
  const infoFatura = itemSelecionado.value?.dados_extraidos?.informacoes_fatura || {}
  const vencimento = infoFatura.vencimento ? new Date(`${infoFatura.vencimento}T00:00:00`) : null
  const nomeDetectado = itemSelecionado.value?.nome_cartao_detectado || ''
  const nomeInicial = String(nome || '').trim() || nomeDetectado

  nomeCartaoInicial.value = nomeInicial
  limiteCartaoInicial.value = typeof infoFatura.limite_total_credito === 'number' ? infoFatura.limite_total_credito : null
  vencimentoCartaoInicial.value = vencimento && !Number.isNaN(vencimento.getTime()) ? vencimento.getDate() : null
  novoCartaoFormKey.value += 1
  mostrarNovoCartao.value = true
}

const conectarGmail = async () => {
  try {
    conectando.value = true
    gmailErroLocal.value = ''
    const response = await gmailAPI.iniciarConexao()
    window.location.href = response.data.url
  } catch (erro) {
    gmailErroLocal.value = erro.response?.data?.detail || erro.message
  } finally {
    conectando.value = false
  }
}

const sincronizarAgora = async () => {
  try {
    sincronizando.value = true
    gmailErroLocal.value = ''
    const resposta = await gmailAPI.sincronizarAgora()
    if (!resposta.data.iniciado && !resposta.data.ja_em_andamento) {
      sincronizando.value = false
      return
    }
    await acompanharOperacao()
    await carregarStatusGmail()
  } catch (erro) {
    sincronizando.value = false
    gmailErroLocal.value = erro.response?.data?.detail || erro.message
  }
}

const confirmarItem = async () => {
  if (!itemSelecionado.value) return

  try {
    processando.value = true
    const dados = itemSelecionado.value.tipo_detectado === 'fatura'
      ? { cartao_id: cartaoIdConfirmacaoAtual.value }
      : {}
    await importacoesPendentesAPI.confirmar(itemSelecionado.value.id, dados)
    await carregarItens()
  } catch (erro) {
    alert('Erro ao confirmar importação: ' + (erro.response?.data?.detail || erro.message))
  } finally {
    processando.value = false
  }
}

const rejeitarItem = async () => {
  if (!itemSelecionado.value) return

  try {
    processando.value = true
    await importacoesPendentesAPI.rejeitar(itemSelecionado.value.id)
    await carregarItens()
  } catch (erro) {
    alert('Erro ao rejeitar importação: ' + (erro.response?.data?.detail || erro.message))
  } finally {
    processando.value = false
  }
}

const reabrirItem = async () => {
  if (!itemSelecionado.value) return

  try {
    processando.value = true
    await importacoesPendentesAPI.reabrir(itemSelecionado.value.id)
    await carregarItens()
  } catch (erro) {
    alert('Erro ao reabrir importação: ' + (erro.response?.data?.detail || erro.message))
  } finally {
    processando.value = false
  }
}

const totalDespesas = (despesas = []) => (
  despesas.reduce((total, despesa) => total + Number(despesa.valor || 0), 0)
)

const totalHolerite = (dados = {}) => {
  const totalReceitas = totalDespesas(dados.receitas || [])
  if (totalReceitas) return totalReceitas

  return (dados.itens || []).reduce((total, item) => {
    const valor = Number(item.valor || 0)
    return item.tipo === 'desconto' ? total - valor : total + valor
  }, 0)
}

const rotuloTipo = (tipo) => ({
  holerite: 'Contracheque',
  fatura: 'Fatura',
  conta: 'Conta'
}[tipo] || tipo)

const rotuloStatus = (status) => ({
  confirmada: 'Importação confirmada',
  rejeitada: 'Importação rejeitada'
}[status] || status)

const linkGmail = (item) => (
  `https://mail.google.com/mail/u/0/#all/${item.gmail_message_id}`
)

const severidadeTipo = (tipo) => ({
  fatura: 'info',
  conta: 'success',
  holerite: 'warn'
}[tipo] || 'secondary')

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

const formatarDataHora = (valor) => {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return String(valor)
  return data.toLocaleString('pt-BR')
}
</script>

<style scoped>
.page {
  max-width: 1600px;
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

.page-head p {
  color: var(--muted);
}

.gmail-panel {
  margin-bottom: 1rem;
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.all-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin: 0 0 1rem;
  flex-wrap: wrap;
}

.gmail-panel :deep(.p-card-content) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.gmail-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.gmail-status strong {
  display: block;
}

.gmail-status small {
  color: var(--muted);
}

.gmail-dot {
  flex: 0 0 auto;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--muted);
}

.gmail-dot.conectado {
  background: var(--success);
}

.gmail-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.sync-button.p-button:not(.p-button-text):not(.p-button-outlined) {
  min-height: 3rem;
  padding-inline: 1.25rem;
  background: linear-gradient(135deg, var(--primary), var(--primary-strong));
  border-color: color-mix(in srgb, var(--primary-strong) 82%, black);
  color: var(--primary-contrast);
  box-shadow: 0 14px 28px color-mix(in srgb, var(--primary) 30%, transparent);
}

.sync-button.p-button:not(.p-button-text):not(.p-button-outlined):enabled:hover {
  background: linear-gradient(135deg, var(--primary-strong), var(--primary));
  border-color: var(--primary-strong);
  box-shadow: 0 16px 32px color-mix(in srgb, var(--primary) 36%, transparent);
  transform: translateY(-1px);
}

.sync-button.p-button:enabled:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--primary) 45%, white);
  outline-offset: 2px;
}

.sync-button :deep(.p-button-icon) {
  font-size: 1.05rem;
}

.gmail-error-pill {
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  background: var(--danger-soft);
  border: 1px solid rgba(220, 38, 38, 0.25);
  color: var(--danger);
  font-size: 0.82rem;
  font-weight: 700;
}

.status-tabs {
  margin-bottom: 1rem;
}

.status-tabs :deep(.p-tab) {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.4rem;
  padding: 0.05rem 0.4rem;
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 800;
}

.import-grid {
  display: grid;
  grid-template-columns: minmax(380px, 460px) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

.list-card,
.detail-card {
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

.bulk-bar {
  border: 1px solid color-mix(in srgb, var(--line) 82%, white);
  border-radius: 18px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface-inset) 82%, white) 0%, var(--surface-inset) 100%);
  display: grid;
  gap: 0.9rem;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.bulk-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.bulk-summary strong {
  display: block;
  font-size: 1.05rem;
}

.bulk-summary span {
  color: var(--muted);
  font-size: 0.9rem;
}

.bulk-counts {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.bulk-chip {
  display: inline-flex;
  align-items: center;
  min-height: 2rem;
  padding: 0.3rem 0.8rem;
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 0.86rem;
  font-weight: 800;
  white-space: nowrap;
}

.bulk-chip.ready {
  background: var(--success-soft);
  color: var(--success);
}

.bulk-chip.blocked {
  background: var(--danger-soft);
  color: var(--danger);
}

.bulk-action {
  justify-self: start;
  min-height: 3rem;
  padding-inline: 1rem;
}

.bulk-warning {
  width: fit-content;
  border: 1px solid rgba(220, 38, 38, 0.25);
  border-radius: 999px;
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 0.9rem;
  font-weight: 700;
  margin: 0;
  padding: 0.45rem 0.8rem;
}

.pending-list {
  display: grid;
  gap: 0.5rem;
}

.pending-row {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
}

.list-card {
  min-width: 0;
}

.list-card :deep(.p-paginator) {
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.15rem;
  margin-top: 0.9rem;
  padding: 0.5rem 0;
  background: transparent;
  border: none;
}

.list-card :deep(.p-paginator .p-paginator-page),
.list-card :deep(.p-paginator .p-paginator-first),
.list-card :deep(.p-paginator .p-paginator-prev),
.list-card :deep(.p-paginator .p-paginator-next),
.list-card :deep(.p-paginator .p-paginator-last) {
  min-width: 2rem;
  height: 2rem;
}

.pending-checkbox {
  flex: 0 0 auto;
  margin-top: 0.95rem;
}

.pending-checkbox :deep(.p-checkbox-box) {
  width: 18px;
  height: 18px;
}

.pending-item {
  flex: 1 1 auto;
  min-width: 0;
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface-inset);
  color: var(--text);
  cursor: pointer;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.35rem 0.65rem;
  align-items: start;
  justify-content: stretch;
  padding: 0.75rem;
  text-align: left;
}

.pending-item:hover {
  background: var(--surface-hover);
  border-color: var(--line-strong);
  color: var(--text);
}

.pending-item :deep(.p-tag) {
  grid-row: 1 / span 2;
  align-self: start;
  flex: 0 0 auto;
  margin-top: 0.05rem;
}

.pending-item :deep(.pending-type-tag.tipo-fatura) {
  background: rgba(59, 130, 246, 0.16);
  border: 1px solid rgba(96, 165, 250, 0.2);
  color: #7dd3fc;
}

.pending-item :deep(.pending-type-tag.tipo-conta) {
  background: var(--success-soft);
  border: 1px solid rgba(52, 211, 153, 0.18);
  color: var(--success);
}

.pending-item :deep(.pending-type-tag.tipo-holerite) {
  background: rgba(245, 179, 1, 0.16);
  border: 1px solid rgba(245, 179, 1, 0.24);
  color: var(--primary-strong);
}

.pending-item-info {
  min-width: 0;
  display: grid;
  gap: 0.25rem;
}

.pending-item-info strong {
  color: var(--text);
  font-size: 0.95rem;
  line-height: 1.25;
  overflow-wrap: anywhere;
  white-space: normal;
}

.pending-item-info small {
  line-height: 1.25;
  overflow-wrap: anywhere;
  white-space: normal;
}

.pending-item small {
  color: var(--muted);
}

.pending-item-data {
  grid-column: 2;
  font-size: 0.78rem;
  line-height: 1.2;
  overflow-wrap: anywhere;
  white-space: normal;
}

.pending-item.selected {
  background: var(--primary-soft);
  border-color: var(--primary-line);
}

.pending-item.selected:hover {
  background: color-mix(in srgb, var(--primary-soft) 70%, var(--surface-hover));
  border-color: var(--primary-line);
}

.pending-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-soft);
}

.pending-item.selected.active {
  background: color-mix(in srgb, var(--primary-soft) 70%, var(--surface-inset));
}

.detail-top-row {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  align-items: start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.detail-field {
  display: grid;
  gap: 0.55rem;
  min-width: 0;
  margin-bottom: 0;
}

.aviso-alerta {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.65rem;
  border: 1px solid color-mix(in srgb, var(--warning) 35%, transparent);
  border-radius: 16px;
  background: color-mix(in srgb, var(--warning) 12%, transparent);
  color: var(--warning);
  font-size: 0.92rem;
  font-weight: 600;
  padding: 0.9rem 1rem;
}

.aviso-alerta i {
  font-size: 0.95rem;
}

.aviso-alerta span {
  flex: 1 1 auto;
  color: var(--text);
  font-weight: 500;
}

.detail-field label {
  font-weight: 800;
  font-size: 0.9rem;
}

.cartao-select-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: stretch;
}

.cartao-select-row :deep(.p-select) {
  min-width: 0;
}

.metric-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) minmax(160px, 0.8fr);
  align-items: stretch;
  gap: 0.75rem;
  min-width: 0;
}

.metric-card {
  display: flex;
  border: 1px solid var(--line);
  background: var(--surface-inset);
  border-radius: 18px;
}

.metric-card :deep(.p-card-body),
.metric-card :deep(.p-card-content) {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  justify-content: center;
  padding: 0.7rem 0.9rem;
}

.metric-card :deep(.p-card-content) span {
  color: var(--muted);
  display: block;
  font-size: 0.8rem;
  margin-bottom: 0.2rem;
}

.metric-card :deep(.p-card-content) strong {
  display: block;
  font-size: 1.2rem;
  white-space: nowrap;
}

.metric-card-hero {
  flex-grow: 1.6;
  background: linear-gradient(135deg, var(--success-soft), var(--surface-inset));
  border-color: rgba(31, 157, 99, 0.35);
}

.metric-card-hero :deep(.p-card-content) span {
  color: var(--success);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.72rem;
}

.metric-card-hero :deep(.p-card-content) strong {
  font-size: 1.45rem;
}

.despesas-table {
  margin-bottom: 0.5rem;
  overflow-x: auto;
}

.despesas-table :deep(.p-datatable-table) {
  min-width: 100%;
}

.despesas-table :deep(.right) {
  text-align: right;
  white-space: nowrap;
}

.despesas-table :deep(.p-datatable-footer) {
  background: transparent;
  border-top: 1px solid var(--line);
  padding: 0.9rem 0;
}

.despesas-table :deep(.p-paginator-bottom) {
  border-width: 1px 0 0;
  border-color: var(--line);
  background: transparent;
  padding: 0.9rem 0;
}

.despesas-table :deep(.p-paginator) {
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.despesas-table :deep(.p-paginator-content) {
  justify-content: center;
  flex-wrap: wrap;
  order: 2;
  flex: 1 1 auto;
}

.despesas-table :deep(.p-paginator-start),
.despesas-table :deep(.p-paginator-end) {
  display: flex;
  align-items: center;
}

.despesas-table :deep(.p-paginator-start) {
  order: 1;
}

.despesas-table :deep(.p-paginator-end) {
  justify-content: flex-end;
  order: 3;
}

.despesas-table :deep(.p-paginator-start .p-button),
.despesas-table :deep(.p-paginator-end .p-button) {
  min-width: 7.5rem;
}

.despesas-table :deep(.p-paginator-current) {
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 700;
}

.detail-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.75rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}

.detail-actions-inline {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.detail-actions-copy {
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

.detail-actions-copy strong {
  font-size: 0.92rem;
  color: var(--text);
}

.detail-actions-copy span {
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.35;
}

.detail-actions-buttons {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 0 0 auto;
}

.result {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  border-radius: 14px;
  margin-bottom: 1rem;
  padding: 1rem;
}

.result.erro {
  background: var(--danger-soft);
  color: var(--danger);
}

.result.erro i {
  font-size: 1.2rem;
  margin-top: 0.15rem;
}

.result strong,
.result span {
  display: block;
}

.link-gmail {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.5rem;
  color: inherit;
  font-weight: 700;
  text-decoration: underline;
}

.link-gmail i {
  font-size: 0.8rem;
}

.detail-gmail-link {
  margin-bottom: 1rem;
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
  .import-grid {
    grid-template-columns: 1fr;
  }

  .detail-top-row {
    grid-template-columns: 1fr;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .detail-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .detail-actions-buttons {
    width: 100%;
    justify-content: flex-start;
  }

  .despesas-table :deep(.p-paginator) {
    align-items: flex-start;
    flex-direction: column;
  }

  .despesas-table :deep(.p-paginator-content) {
    justify-content: flex-start;
    order: 2;
  }

  .despesas-table :deep(.p-paginator-end) {
    justify-content: flex-start;
    order: 3;
  }
}

@media (max-width: 640px) {
  .gmail-actions,
  .sync-button.p-button:not(.p-button-text):not(.p-button-outlined) {
    width: 100%;
  }

  .sync-button.p-button:not(.p-button-text):not(.p-button-outlined) {
    justify-content: center;
  }
}
</style>
