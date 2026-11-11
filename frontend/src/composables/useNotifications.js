import { computed, ref } from 'vue'
import { notificacoesAPI } from '../api/client'

const items = ref([])
const naoLidas = ref(0)
const carregando = ref(false)
const erro = ref('')
const iniciado = ref(false)

let timerId = null
let operacaoSolicitadaAte = 0

const emAndamento = computed(() => items.value.some((item) => item.estado === 'em_andamento'))
const notificacaoGmailAtiva = computed(() => (
  items.value.find((item) => item.tipo === 'gmail' && item.estado === 'em_andamento') || null
))

async function atualizar(atualizarFinanceiro = true) {
  if (carregando.value || !localStorage.getItem('token')) return
  carregando.value = true
  erro.value = ''
  try {
    const resposta = await notificacoesAPI.listar(20, atualizarFinanceiro)
    items.value = resposta.data.items
    naoLidas.value = resposta.data.nao_lidas
  } catch (causa) {
    erro.value = causa.response?.data?.detail || 'Não foi possível carregar as notificações.'
  } finally {
    carregando.value = false
  }
}

function pollingRapido() {
  return emAndamento.value || Date.now() < operacaoSolicitadaAte
}

function agendar(proximoEm = null) {
  if (timerId) clearTimeout(timerId)
  if (!iniciado.value || document.hidden) return
  const intervalo = proximoEm ?? (pollingRapido() ? 1500 : 60000)
  timerId = setTimeout(executarCiclo, intervalo)
}

async function executarCiclo() {
  await atualizar(!pollingRapido())
  agendar()
}

async function iniciar() {
  if (iniciado.value || !localStorage.getItem('token')) return
  iniciado.value = true
  document.addEventListener('visibilitychange', aoMudarVisibilidade)
  await atualizar(true)
  agendar()
}

function parar() {
  iniciado.value = false
  if (timerId) clearTimeout(timerId)
  timerId = null
  operacaoSolicitadaAte = 0
  items.value = []
  naoLidas.value = 0
  document.removeEventListener('visibilitychange', aoMudarVisibilidade)
}

async function acompanharOperacao() {
  operacaoSolicitadaAte = Date.now() + 10000
  agendar(350)
}

async function marcarLida(item, lida = true) {
  if (!item || Boolean(item.lida_em) === lida) return
  const estavaLida = Boolean(item.lida_em)
  const resposta = await notificacoesAPI.marcarLida(item.id, lida)
  const indice = items.value.findIndex((atual) => atual.id === item.id)
  if (indice >= 0) items.value.splice(indice, 1, resposta.data)
  if (!estavaLida && lida) naoLidas.value = Math.max(0, naoLidas.value - 1)
  if (estavaLida && !lida) naoLidas.value += 1
}

async function marcarTodasLidas() {
  if (!naoLidas.value) return
  await notificacoesAPI.marcarTodasLidas()
  const agora = new Date().toISOString()
  items.value = items.value.map((item) => ({ ...item, lida_em: item.lida_em || agora }))
  naoLidas.value = 0
}

async function aoMudarVisibilidade() {
  if (document.hidden) {
    if (timerId) clearTimeout(timerId)
    timerId = null
    return
  }
  await atualizar(!pollingRapido())
  agendar()
}

export function useNotifications() {
  return {
    items,
    naoLidas,
    carregando,
    erro,
    emAndamento,
    notificacaoGmailAtiva,
    iniciar,
    parar,
    atualizar,
    acompanharOperacao,
    marcarLida,
    marcarTodasLidas
  }
}
