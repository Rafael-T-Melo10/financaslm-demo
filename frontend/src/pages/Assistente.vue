<template>
  <main class="page">
    <div class="layout">
      <aside class="sidebar">
        <Card class="local-card">
          <template #content>
            <div class="local-linha">
              <span class="local-icone"><i class="pi pi-shield" aria-hidden="true" /></span>
              <div class="local-texto">
                <div class="local-titulo">
                  Local
                  <span
                    class="local-ponto"
                    :class="statusAssistente?.disponivel ? 'local-ponto-ok' : 'local-ponto-erro'"
                    aria-hidden="true"
                  />
                </div>
                <p>{{ statusAssistente?.disponivel ? 'Inferência pelo Ollama configurado' : (statusAssistente?.mensagem || 'Verificando disponibilidade...') }}</p>
              </div>
              <Button
                icon="pi pi-refresh"
                text
                rounded
                size="small"
                :loading="carregandoStatus"
                aria-label="Atualizar status"
                @click="carregarStatus"
              />
            </div>
          </template>
        </Card>

        <Card class="modelos-card">
          <template #content>
            <div class="modelos-cabecalho">
              <div>
                <span class="sidebar-titulo">Modelos</span>
                <p class="sidebar-subtitulo">Marque vários para comparar respostas</p>
              </div>
              <span v-if="modelosDisponiveis.length" class="modelos-contagem">
                {{ modelosSelecionados.length }} de {{ modelosDisponiveis.length }}
              </span>
            </div>

            <div v-if="carregandoStatus && !statusAssistente" class="modelos-aviso">
              <ProgressSpinner style="width: 1.25rem; height: 1.25rem" stroke-width="6" />
              <span>Consultando modelos instalados...</span>
            </div>

            <div v-else-if="!statusAssistente?.disponivel" class="modelos-aviso">
              <i class="pi pi-wifi" aria-hidden="true" />
              <span>Não foi possível consultar os modelos instalados.</span>
            </div>

            <div v-else-if="!modelosDisponiveis.length" class="modelos-aviso">
              <i class="pi pi-inbox" aria-hidden="true" />
              <span>Nenhum modelo instalado. Rode <code>ollama pull llama3.1</code> e atualize.</span>
            </div>

            <ul v-else class="modelos-lista" role="group" aria-label="Escolha do modelo">
              <li
                v-for="modelo in modelosDisponiveis"
                :key="modelo.id"
                class="modelo-item"
                :class="{ 'modelo-item-selecionado': modeloEstaSelecionado(modelo.id) }"
                role="checkbox"
                :aria-checked="modeloEstaSelecionado(modelo.id)"
                tabindex="0"
                @click="alternarSelecaoModelo(modelo.id)"
                @keydown.enter.prevent="alternarSelecaoModelo(modelo.id)"
                @keydown.space.prevent="alternarSelecaoModelo(modelo.id)"
              >
                <div class="modelo-item-linha">
                  <Checkbox
                    :model-value="modeloEstaSelecionado(modelo.id)"
                    :binary="true"
                    tabindex="-1"
                    class="modelo-item-checkbox"
                    aria-hidden="true"
                  />
                  <strong class="modelo-item-nome">{{ modelo.rotulo }}</strong>
                  <i v-if="modelo.aviso" class="pi pi-exclamation-triangle modelo-item-aviso" aria-hidden="true" title="Ver detalhes" />
                </div>
                <p class="modelo-item-descritor">{{ modelo.descritorCurto }}</p>

                <button type="button" class="modelo-item-detalhes" @click.stop="alternarDetalhes(modelo.id)">
                  detalhes
                  <i class="pi" :class="modelosExpandidos.has(modelo.id) ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true" />
                </button>
                <p v-if="modelosExpandidos.has(modelo.id)" class="modelo-item-nota">{{ modelo.nota }}</p>
              </li>
            </ul>
          </template>
        </Card>

        <Card class="sugestoes-card">
          <template #content>
            <span class="sidebar-titulo">Sugestões</span>
            <div class="sugestoes-lista">
              <button
                v-for="sugestao in perguntasSugeridas"
                :key="sugestao"
                type="button"
                class="sugestao-item"
                :disabled="!statusAssistente?.disponivel || enviando"
                @click="usarSugestao(sugestao)"
              >
                {{ sugestao }}
              </button>
            </div>
          </template>
        </Card>
      </aside>

      <div class="conteudo">
        <section class="page-head">
          <p class="eyebrow">Inteligência local</p>
          <h1>Assistente</h1>
          <p>Pergunte sobre seus gastos. Somente leitura — nada aqui altera seus dados.</p>
        </section>

        <div class="conversa-caixa">
          <section v-if="historico.length" class="historico">
            <div class="historico-cabecalho">
              <span class="sidebar-titulo">Conversa</span>
              <Button label="Limpar conversa" icon="pi pi-trash" text size="small" @click="limparConversa" />
            </div>

            <div v-for="item in historico" :key="item.id" class="turno">
              <p class="pergunta-feita">
                {{ item.pergunta }}
                <i class="pi pi-user" aria-hidden="true" />
              </p>

              <div class="respostas-grid" :class="{ 'respostas-grid-unica': item.respostas.length === 1 }">
                <Card
                  v-for="r in item.respostas"
                  :key="r.modeloId"
                  class="resposta-card"
                  :class="vereditoClasse(r.resposta?.veredito)"
                >
                  <template #content>
                    <div v-if="item.respostas.length > 1" class="resposta-modelo-cabecalho">
                      <strong>{{ r.modeloRotulo }}</strong>
                    </div>

                    <div v-if="!r.resposta && !r.erro" class="carregando-resposta">
                      <ProgressSpinner style="width: 1.75rem; height: 1.75rem" stroke-width="5" />
                      <span>Pensando...</span>
                    </div>

                    <Message v-else-if="r.erro" severity="error" :closable="false">{{ r.erro }}</Message>

                    <template v-else-if="r.resposta">
                      <div class="resposta-cabecalho">
                        <Tag :value="rotuloVeredito(r.resposta.veredito)" :severity="severidadeVeredito(r.resposta.veredito)" />
                        <Tag v-if="item.respostas.length === 1" severity="secondary" :value="r.modeloRotulo" class="modelo-tag-historico" />
                        <small v-if="r.resposta.latencia_ms?.total != null" class="latencia">
                          {{ r.resposta.latencia_ms.total }} ms
                        </small>
                      </div>

                      <p class="resposta-texto">{{ r.resposta.resposta }}</p>

                      <Message v-if="r.resposta.divergencia" severity="warn" :closable="false">
                        {{ r.resposta.divergencia }}
                      </Message>
                      <Message v-if="r.resposta.falta" severity="warn" :closable="false">
                        {{ r.resposta.falta }}
                      </Message>
                      <Message v-if="r.resposta.premissas?.length" severity="info" :closable="false">
                        <strong>Premissas assumidas:</strong>
                        <ul class="premissas-lista">
                          <li v-for="premissa in r.resposta.premissas" :key="premissa">{{ premissa }}</li>
                        </ul>
                      </Message>

                      <Accordion v-if="r.resposta.sql" :value="null">
                        <AccordionPanel value="evidencias">
                          <AccordionHeader>Como isso foi calculado</AccordionHeader>
                          <AccordionContent>
                            <pre class="sql-block"><code>{{ r.resposta.sql }}</code></pre>
                            <DataTable
                              v-if="r.resposta.resultado?.length"
                              :value="r.resposta.resultado"
                              size="small"
                              striped-rows
                              class="resultado-tabela"
                            >
                              <Column
                                v-for="campo in Object.keys(r.resposta.resultado[0])"
                                :key="campo"
                                :field="campo"
                                :header="campo"
                              />
                            </DataTable>
                            <p v-else class="sem-resultado">A consulta não retornou nenhuma linha.</p>
                          </AccordionContent>
                        </AccordionPanel>
                      </Accordion>
                    </template>
                  </template>
                </Card>
              </div>
            </div>
          </section>

          <div v-else class="empty-state">
            <i class="pi pi-sparkles" aria-hidden="true" />
            <strong>Pergunte em português</strong>
            <p>Escolha uma sugestão ao lado ou escreva abaixo. Marque mais de um modelo para ver as respostas lado a lado.</p>
          </div>
        </div>

        <div class="input-barra">
          <Textarea
            v-model="perguntaAtual"
            class="pergunta-textarea"
            auto-resize
            rows="2"
            maxlength="400"
            placeholder="Ex: Quanto eu gastei em julho? · Enter envia, Shift+Enter quebra linha"
            :disabled="!statusAssistente?.disponivel || enviando"
            @keydown.enter="aoTeclarEnter"
          />
          <div class="input-rodape">
            <small class="contador">
              {{ perguntaAtual.length }}/400
              <template v-if="modelosSelecionados.length > 1"> · respostas lado a lado</template>
            </small>
            <Button
              :label="rotuloBotaoEnviar"
              icon="pi pi-send"
              :loading="enviando"
              :disabled="!podePerguntar"
              @click="enviarPergunta"
            />
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import Accordion from 'primevue/accordion'
import AccordionContent from 'primevue/accordioncontent'
import AccordionHeader from 'primevue/accordionheader'
import AccordionPanel from 'primevue/accordionpanel'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { assistenteAPI } from '../api/client'

const toast = useToast()
const statusAssistente = ref(null)
const carregandoStatus = ref(false)
const perguntaAtual = ref('')
const enviando = ref(false)
const historico = ref([])
// Sempre multi-seleção: 1 modelo escolhido = pergunta normal, 2+ = compara
// automaticamente as respostas lado a lado -- sem alternar um "modo" à parte.
const modelosSelecionados = ref([])
const modelosExpandidos = reactive(new Set())

// Descritores de arquitetura; desempenho depende de dados, protocolo e hardware.
// Resultados medidos e suas limitações ficam no relatório de avaliação.
const NOTAS_CONHECIDAS = {
  'llama3.1:latest': {
    rotulo: 'Llama 3.1 (8B)',
    descritorCurto: 'Modelo local · 8 bilhões de parâmetros',
    nota: 'Compare as respostas com os dados consultados. O modelo pode errar a interpretação mesmo quando o SQL executa.'
  },
  'qwen3:4b': {
    rotulo: 'Qwen 3 (4B)',
    descritorCurto: 'Modelo local · 4 bilhões de parâmetros',
    nota: 'Velocidade e qualidade variam conforme a pergunta e o equipamento. Trate descrições importadas como dados não confiáveis.'
  },
  'phi4-mini:latest': {
    rotulo: 'Phi-4 Mini',
    descritorCurto: 'Modelo local compacto',
    nota: 'Consulte o SQL e os resultados apresentados antes de usar uma resposta. Abstenção não é garantia de interpretação correta.'
  }
}

// Cards vêm sempre dos modelos REALMENTE instalados no Ollama (status().modelos_instalados)
// -- não de uma lista fixa -- pra qualquer modelo que o usuário baixar aparecer aqui sem
// precisar mexer no código.
const modelosDisponiveis = computed(() => (
  (statusAssistente.value?.modelos_instalados || []).map((id) => {
    const conhecido = NOTAS_CONHECIDAS[id]
    return conhecido
      ? { id, ...conhecido }
      : {
        id, rotulo: id, descritorCurto: 'Modelo instalado localmente',
        nota: 'Modelo instalado no Ollama configurado; desempenho não caracterizado nesta interface.'
      }
  })
))

const modeloSalvo = localStorage.getItem('assistente-modelo') || ''

// Só persiste enquanto for 1 modelo só -- a seleção múltipla de uma comparação
// pontual não deve virar o padrão salvo para a próxima visita.
watch(modelosSelecionados, (lista) => {
  if (lista.length === 1) localStorage.setItem('assistente-modelo', lista[0])
})

// Se a seleção atual ficar vazia (primeira carga, ou o(s) modelo(s)
// escolhido(s) não estiverem mais instalados), cai pro modelo salvo (se ainda
// instalado) ou pro primeiro disponível, em vez de deixar sem nada marcado.
watch(modelosDisponiveis, (lista) => {
  if (!lista.length) return
  const aindaValidos = modelosSelecionados.value.filter((id) => lista.some((m) => m.id === id))
  if (aindaValidos.length) {
    modelosSelecionados.value = aindaValidos
    return
  }
  const padrao = lista.some((m) => m.id === modeloSalvo) ? modeloSalvo : lista[0].id
  modelosSelecionados.value = [padrao]
}, { immediate: true })

const perguntasSugeridas = [
  'Quanto eu gastei este mês?',
  'Comparado ao mês passado, gastei mais ou menos?',
  'Qual foi meu maior gasto em Alimentação este mês?',
  'Como está o limite do meu cartão?',
  'Tenho parcelas em aberto?',
  'Quanto tenho de despesas recorrentes ativas?'
]

const rotuloBotaoEnviar = computed(() => (
  modelosSelecionados.value.length > 1
    ? `Comparar (${modelosSelecionados.value.length} modelos)`
    : 'Perguntar'
))

const podePerguntar = computed(() => (
  Boolean(statusAssistente.value?.disponivel)
  && perguntaAtual.value.trim().length >= 3
  && !enviando.value
  && modelosSelecionados.value.length >= 1
))

onMounted(carregarStatus)

async function carregarStatus() {
  carregandoStatus.value = true
  try {
    const resposta = await assistenteAPI.status()
    statusAssistente.value = resposta.data
  } catch (erro) {
    console.error('Erro ao consultar status do assistente:', erro)
    statusAssistente.value = { disponivel: false, mensagem: 'Não foi possível verificar o status do assistente.' }
  } finally {
    carregandoStatus.value = false
  }
}

function modeloEstaSelecionado(id) {
  return modelosSelecionados.value.includes(id)
}

function alternarSelecaoModelo(id) {
  if (enviando.value) return
  const indice = modelosSelecionados.value.indexOf(id)
  if (indice === -1) {
    modelosSelecionados.value = [...modelosSelecionados.value, id]
    return
  }
  // Sempre precisa sobrar pelo menos 1 modelo marcado -- clicar no único
  // selecionado de novo não desmarca, só re-selecionar outro troca a seleção.
  if (modelosSelecionados.value.length === 1) return
  modelosSelecionados.value = modelosSelecionados.value.filter((m) => m !== id)
}

function alternarDetalhes(id) {
  if (modelosExpandidos.has(id)) modelosExpandidos.delete(id)
  else modelosExpandidos.add(id)
}

function aoTeclarEnter(evento) {
  if (evento.shiftKey) return // Shift+Enter continua quebrando linha, só Enter sozinho envia
  evento.preventDefault()
  enviarPergunta()
}

function usarSugestao(sugestao) {
  perguntaAtual.value = sugestao
  enviarPergunta()
}

async function enviarPergunta() {
  const pergunta = perguntaAtual.value.trim()
  if (!podePerguntar.value || pergunta.length < 3) return

  const idsModelos = modelosSelecionados.value

  perguntaAtual.value = ''
  enviando.value = true

  // reactive(), não um objeto cru: precisamos mutar r.resposta/r.erro DEPOIS
  // de inserido no array, e uma referência crua guardada antes de virar reativa
  // não dispara re-render quando mutada (a mutação não passa pelo proxy do Vue).
  const item = reactive({
    id: `${Date.now()}-${Math.random()}`,
    pergunta,
    respostas: idsModelos.map((id) => ({
      modeloId: id,
      modeloRotulo: modelosDisponiveis.value.find((m) => m.id === id)?.rotulo || id,
      resposta: null,
      erro: null
    }))
  })
  historico.value.unshift(item)

  await Promise.allSettled(item.respostas.map(async (r) => {
    try {
      const resposta = await assistenteAPI.perguntar(pergunta, r.modeloId)
      r.resposta = resposta.data.dados
    } catch (erro) {
      console.error('Erro ao perguntar ao assistente:', erro)
      r.erro = erro.response?.data?.detail || 'Não foi possível obter uma resposta agora. Tente novamente.'
    }
  }))

  enviando.value = false
}

function limparConversa() {
  historico.value = []
}

function rotuloVeredito(veredito) {
  return { ok: 'Respondido', ressalva: 'Com ressalva', nao_sei: 'Não foi possível responder' }[veredito] || veredito
}

function severidadeVeredito(veredito) {
  return { ok: 'success', ressalva: 'warn', nao_sei: 'secondary' }[veredito] || 'secondary'
}

function vereditoClasse(veredito) {
  return veredito ? `resposta-card-${veredito}` : ''
}
</script>

<style scoped>
.page {
  margin: 0 auto;
  padding: 1.5rem 1.25rem 2rem;
  max-width: 84rem;
  height: calc(100vh - 4.5rem);
  box-sizing: border-box;
}

.layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) 1fr;
  gap: 1.25rem;
  height: 100%;
}

.sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 1rem;
  overflow-y: auto;
  padding-right: 0.15rem;
}

.sidebar :deep(.p-card-body) {
  padding: 0.9rem 1rem;
}

.local-card,
.modelos-card,
.sugestoes-card {
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 14px;
  flex-shrink: 0;
}

.local-linha {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.local-icone {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.1rem;
  height: 2.1rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
}

.local-texto {
  flex: 1;
  min-width: 0;
}

.local-titulo {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 800;
}

.local-ponto {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
}

.local-ponto-ok {
  background: var(--success);
}

.local-ponto-erro {
  background: var(--danger);
}

.local-texto p {
  margin: 0.1rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-titulo {
  display: block;
  color: var(--text);
  font-size: 0.85rem;
  font-weight: 800;
}

.sidebar-subtitulo {
  margin: 0.15rem 0 0;
  color: var(--muted-2);
  font-size: 0.75rem;
}

.modelos-cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.modelos-contagem {
  color: var(--muted-2);
  font-size: 0.75rem;
  font-weight: 700;
  white-space: nowrap;
}

.modelos-aviso {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  color: var(--muted);
  font-size: 0.8rem;
  padding: 0.5rem 0;
}

.modelos-aviso .pi {
  color: var(--primary);
  margin-top: 0.1rem;
}

.modelos-aviso code {
  background: var(--surface-muted);
  border-radius: 4px;
  padding: 0.05rem 0.25rem;
}

.modelos-lista {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.modelo-item {
  border: 1.5px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.modelo-item:hover {
  border-color: color-mix(in srgb, var(--primary) 45%, var(--line));
  background: var(--primary-soft);
}

.modelo-item:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--primary) 55%, white);
  outline-offset: 2px;
}

.modelo-item-selecionado {
  border-color: var(--primary);
  background: var(--primary-soft);
}

.modelo-item-linha {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modelo-item-checkbox {
  flex: 0 0 auto;
  pointer-events: none;
  /* o tema padrão do PrimeVue (--p-primary-color) é verde e diverge do
     dourado que o resto do app usa (var(--primary)); essas variáveis do
     Checkbox herdam pros elementos internos dele mesmo sem :deep(). */
  --p-checkbox-checked-background: var(--primary);
  --p-checkbox-checked-border-color: var(--primary);
  --p-checkbox-checked-hover-background: var(--primary-strong);
  --p-checkbox-checked-hover-border-color: var(--primary-strong);
  --p-checkbox-checked-focus-border-color: var(--primary);
}

.modelo-item-nome {
  flex: 1;
  min-width: 0;
  font-size: 0.88rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.modelo-item-aviso {
  color: var(--warning);
  font-size: 0.85rem;
}

.modelo-item-descritor {
  margin: 0.3rem 0 0.5rem;
  color: var(--muted);
  font-size: 0.76rem;
}

.modelo-metricas {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.4rem;
}

.modelo-metrica {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.modelo-metrica-label {
  width: 1.6rem;
  flex: 0 0 auto;
  color: var(--muted-2);
  font-size: 0.68rem;
  text-transform: uppercase;
}

.modelo-metrica-barra {
  flex: 1;
  height: 0.3rem;
  border-radius: 999px;
  background: var(--surface-muted);
  overflow: hidden;
}

.modelo-metrica-preenchimento {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--muted-2);
}

.modelo-metrica-preenchimento-prec {
  background: var(--primary);
}

.modelo-item-detalhes {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  border: none;
  background: none;
  padding: 0;
  color: var(--muted-2);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}

.modelo-item-detalhes:hover {
  color: var(--primary-strong);
}

.modelo-item-nota {
  margin: 0.4rem 0 0;
  color: var(--muted);
  font-size: 0.76rem;
  line-height: 1.4;
}

.sugestoes-lista {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.75rem;
}

.sugestao-item {
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 0.82rem;
  padding: 0.5rem 0.65rem;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.sugestao-item:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--primary) 45%, var(--line));
  background: var(--primary-soft);
}

.sugestao-item:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.conteudo {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.page-head {
  margin-bottom: 1rem;
  flex-shrink: 0;
}

.eyebrow {
  color: var(--primary-strong);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(1.9rem, 3.2vw, 2.6rem);
}

.page-head p {
  color: var(--muted);
  margin: 0.3rem 0 0;
}

.conversa-caixa {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border: 1px dashed var(--line);
  border-radius: 16px;
  padding: 1.25rem;
}

.empty-state {
  height: 100%;
  min-height: 16rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--muted);
  padding: 2rem;
}

.empty-state .pi {
  font-size: 1.6rem;
  color: var(--primary);
  margin-bottom: 0.6rem;
  display: block;
}

.empty-state strong {
  display: block;
  color: var(--text);
  font-size: 1.1rem;
  margin-bottom: 0.4rem;
}

.empty-state p {
  max-width: 28rem;
  margin: 0;
}

.historico {
  display: grid;
  gap: 1.35rem;
}

.historico-cabecalho {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.turno {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.pergunta-feita {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  align-self: flex-end;
  max-width: 85%;
  margin: 0;
  padding: 0.55rem 0.95rem;
  border-radius: 14px 14px 3px 14px;
  background: var(--primary-soft);
  color: var(--primary-strong);
  font-weight: 600;
  text-align: right;
}

.pergunta-feita .pi {
  color: var(--primary);
}

.respostas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.75rem;
}

.respostas-grid-unica {
  grid-template-columns: 1fr;
}

.resposta-card {
  border: 1px solid var(--line);
  border-left: 4px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 12px;
}

.resposta-card-ok {
  border-left-color: var(--success);
}

.resposta-card-ressalva {
  border-left-color: var(--warning);
}

.resposta-card-nao_sei {
  border-left-color: var(--muted-2);
}

.resposta-modelo-cabecalho {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--line);
}

.carregando-resposta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--muted);
  padding: 0.5rem 0;
}

.resposta-cabecalho {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}

.modelo-tag-historico {
  font-family: 'Space Grotesk', monospace;
  font-size: 0.72rem;
}

.latencia {
  color: var(--muted-2);
  font-size: 0.78rem;
}

.resposta-texto {
  margin: 0 0 0.5rem;
  line-height: 1.5;
}

.premissas-lista {
  margin: 0.3rem 0 0;
  padding-left: 1.1rem;
}

.sql-block {
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0.85rem;
  overflow-x: auto;
  font-size: 0.82rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.resultado-tabela {
  margin-top: 0.75rem;
  overflow-x: auto;
}

.sem-resultado {
  color: var(--muted);
  margin-top: 0.5rem;
}

.input-barra {
  flex-shrink: 0;
  margin-top: 1rem;
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  background: var(--surface);
}

.pergunta-textarea,
.pergunta-textarea.p-inputtextarea {
  width: 100%;
  box-sizing: border-box;
  border: none;
  padding-left: 0;
  padding-right: 0;
  box-shadow: none;
  background: transparent;
}

.input-rodape {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--line);
}

.contador {
  color: var(--muted-2);
  font-size: 0.78rem;
}

@media (max-width: 900px) {
  .page {
    height: auto;
    padding: 1.5rem 1.25rem 2rem;
  }

  .layout {
    grid-template-columns: minmax(0, 1fr);
    height: auto;
  }

  .sidebar {
    overflow-y: visible;
  }

  .conversa-caixa {
    min-height: 20rem;
  }
}

@media (max-width: 640px) {
  .input-rodape {
    flex-direction: column-reverse;
    align-items: stretch;
  }

  .input-rodape .p-button {
    width: 100%;
  }

  .pergunta-feita {
    max-width: 100%;
  }

  .respostas-grid {
    grid-template-columns: 1fr;
  }
}
</style>
