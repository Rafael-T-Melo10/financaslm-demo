<template>
  <main class="page configuracoes-page">
    <section class="page-head">
      <div>
        <p class="eyebrow">Conta</p>
        <h1>Configurações</h1>
        <p>Gerencie sua família e as senhas usadas para importar PDFs protegidos.</p>
      </div>
    </section>

    <Message v-if="erro" severity="error" :closable="false">{{ erro }}</Message>

    <Tabs v-model:value="abaAtiva">
      <TabList>
        <Tab value="familia"><i class="pi pi-users" /> Família</Tab>
        <Tab value="senhas"><i class="pi pi-lock" /> Senhas de PDF</Tab>
      </TabList>

      <TabPanels>
        <TabPanel value="familia">
          <div v-if="carregandoFamilia" class="loading-copy">Carregando família...</div>

          <Card v-else-if="!familia" class="settings-card narrow-card">
            <template #title>Criar uma família</template>
            <template #subtitle>Você será o administrador e poderá adicionar pessoas já cadastradas.</template>
            <template #content>
              <form class="settings-form" @submit.prevent="criarFamilia">
                <label for="nome-familia">Nome da família</label>
                <InputText id="nome-familia" v-model.trim="nomeNovaFamilia" placeholder="Ex: Casa da família" required />
                <Button type="submit" label="Criar família" icon="pi pi-plus" :loading="salvandoFamilia" />
              </form>
            </template>
          </Card>

          <template v-else>
            <section class="family-summary">
              <Card class="settings-card">
                <template #title>{{ familia.nome }}</template>
                <template #subtitle>Você é {{ meuPapel === 'admin' ? 'administrador(a)' : 'membro' }} desta família.</template>
                <template #content>
                  <div class="family-actions">
                    <Button
                      v-if="meuPapel === 'admin'"
                      label="Renomear"
                      icon="pi pi-pencil"
                      severity="secondary"
                      outlined
                      @click="abrirRenomear"
                    />
                    <Button label="Sair da família" icon="pi pi-sign-out" severity="danger" outlined @click="confirmarSaida" />
                  </div>
                </template>
              </Card>

              <Card v-if="meuPapel === 'admin'" class="settings-card">
                <template #title>Adicionar membro</template>
                <template #subtitle>A pessoa precisa possuir uma conta no aplicativo.</template>
                <template #content>
                  <form class="member-form" @submit.prevent="adicionarMembro">
                    <InputText v-model.trim="emailNovoMembro" type="email" placeholder="email@exemplo.com" required />
                    <Select v-model="papelNovoMembro" :options="papeis" option-label="label" option-value="value" />
                    <Button type="submit" label="Adicionar" icon="pi pi-user-plus" :loading="salvandoFamilia" />
                  </form>
                </template>
              </Card>
            </section>

            <Card class="table-card members-card">
              <template #title>Membros</template>
              <template #subtitle>{{ familia.membros.length }} pessoa(s) na família</template>
              <template #content>
                <DataTable :value="familia.membros" data-key="id" striped-rows responsive-layout="scroll">
                  <Column header="Pessoa">
                    <template #body="{ data }">
                      <strong>{{ data.usuario.nome }}</strong>
                      <small class="member-email">{{ data.usuario.email }}</small>
                    </template>
                  </Column>
                  <Column header="Papel">
                    <template #body="{ data }">
                      <Select
                        v-if="meuPapel === 'admin' && data.usuario_id !== usuarioAtual?.id"
                        :model-value="data.papel"
                        :options="papeis"
                        option-label="label"
                        option-value="value"
                        @update:model-value="atualizarPapel(data, $event)"
                      />
                      <Tag v-else :value="data.papel === 'admin' ? 'Administrador' : 'Membro'" :severity="data.papel === 'admin' ? 'warn' : 'info'" />
                    </template>
                  </Column>
                  <Column v-if="meuPapel === 'admin'" header="Ações" header-class="right" body-class="right">
                    <template #body="{ data }">
                      <Button
                        v-if="data.usuario_id !== usuarioAtual?.id"
                        icon="pi pi-trash"
                        severity="danger"
                        text
                        rounded
                        :aria-label="`Remover ${data.usuario.nome}`"
                        @click="confirmarRemocao(data)"
                      />
                    </template>
                  </Column>
                </DataTable>
              </template>
            </Card>
          </template>
        </TabPanel>

        <TabPanel value="senhas">
          <Card class="settings-card passwords-card">
            <template #title>Senhas de PDFs</template>
            <template #subtitle>Os valores são cifrados no banco e nunca aparecem novamente nesta tela.</template>
            <template #content>
              <Message severity="info" :closable="false">
                Informe uma nova senha para substituir a cadastrada. PDFs sem proteção continuam funcionando sem configuração.
              </Message>

              <form class="passwords-form" @submit.prevent="salvarSenhas">
                <div v-for="item in instituicoes" :key="item.chave" class="password-row">
                  <div>
                    <strong>{{ item.nome }}</strong>
                    <small v-if="statusSenhas[item.chave]?.configurada && statusSenhas[item.chave]?.legivel">Senha cadastrada</small>
                    <small v-else-if="statusSenhas[item.chave]?.configurada">Recadastre esta senha</small>
                    <small v-else>Sem senha cadastrada</small>
                  </div>
                  <Password
                    v-model="novasSenhas[item.chave]"
                    :input-id="`senha-${item.chave}`"
                    :placeholder="statusSenhas[item.chave]?.configurada ? 'Nova senha (opcional)' : 'Cadastrar senha'"
                    :feedback="false"
                    toggle-mask
                    fluid
                  />
                  <Tag
                    :value="statusSenha(item.chave)"
                    :severity="statusSenhas[item.chave]?.legivel ? 'success' : statusSenhas[item.chave]?.configurada ? 'danger' : 'secondary'"
                  />
                  <Button
                    v-if="statusSenhas[item.chave]?.configurada"
                    icon="pi pi-trash"
                    severity="danger"
                    text
                    rounded
                    :aria-label="`Remover senha ${item.nome}`"
                    @click.prevent="confirmarRemoverSenha(item)"
                  />
                </div>

                <div class="password-actions">
                  <Button type="submit" label="Salvar alterações" icon="pi pi-save" :loading="salvandoSenhas" />
                </div>
              </form>
            </template>
          </Card>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <Dialog v-model:visible="dialogRenomear" modal header="Renomear família" :style="{ width: 'min(92vw, 28rem)' }">
      <form class="settings-form" @submit.prevent="renomearFamilia">
        <label for="novo-nome-familia">Novo nome</label>
        <InputText id="novo-nome-familia" v-model.trim="nomeFamiliaEditando" required />
        <Button type="submit" label="Salvar nome" :loading="salvandoFamilia" />
      </form>
    </Dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import { familiasAPI, senhasPdfAPI } from '../api/client'

const abaAtiva = ref('familia')
const familia = ref(null)
const statusSenhas = ref({})
const carregandoFamilia = ref(true)
const salvandoFamilia = ref(false)
const salvandoSenhas = ref(false)
const erro = ref('')
const nomeNovaFamilia = ref('')
const emailNovoMembro = ref('')
const papelNovoMembro = ref('membro')
const dialogRenomear = ref(false)
const nomeFamiliaEditando = ref('')
const novasSenhas = ref({ itau: '', xp: '', naturgy: '', light: '', nio: '', contracheque: '' })
const toast = useToast()
const confirm = useConfirm()
const usuarioAtual = ref(JSON.parse(localStorage.getItem('usuario') || 'null'))

const papeis = [
  { label: 'Membro', value: 'membro' },
  { label: 'Administrador', value: 'admin' }
]

const instituicoes = [
  { chave: 'itau', nome: 'Itaú' },
  { chave: 'xp', nome: 'XP' },
  { chave: 'naturgy', nome: 'Naturgy' },
  { chave: 'light', nome: 'Light' },
  { chave: 'nio', nome: 'Nio' },
  { chave: 'contracheque', nome: 'Contracheque' }
]

const meuPapel = computed(() => familia.value?.membros.find((item) => item.usuario_id === usuarioAtual.value?.id)?.papel || null)

onMounted(async () => {
  await Promise.all([carregarFamilia(), carregarSenhas()])
})

async function carregarFamilia () {
  carregandoFamilia.value = true
  try {
    const resposta = await familiasAPI.minha()
    familia.value = resposta.data
  } catch (erroResposta) {
    if (erroResposta.response?.status === 404) familia.value = null
    else erro.value = detalheErro(erroResposta)
  } finally {
    carregandoFamilia.value = false
  }
}

async function carregarSenhas () {
  try {
    statusSenhas.value = (await senhasPdfAPI.obter()).data
  } catch (erroResposta) {
    erro.value = detalheErro(erroResposta)
  }
}

async function criarFamilia () {
  salvandoFamilia.value = true
  try {
    familia.value = (await familiasAPI.criar({ nome: nomeNovaFamilia.value })).data
    nomeNovaFamilia.value = ''
    sucesso('Família criada')
  } catch (erroResposta) {
    falha(erroResposta)
  } finally {
    salvandoFamilia.value = false
  }
}

function abrirRenomear () {
  nomeFamiliaEditando.value = familia.value.nome
  dialogRenomear.value = true
}

async function renomearFamilia () {
  salvandoFamilia.value = true
  try {
    familia.value = (await familiasAPI.renomear({ nome: nomeFamiliaEditando.value })).data
    dialogRenomear.value = false
    sucesso('Nome da família atualizado')
  } catch (erroResposta) {
    falha(erroResposta)
  } finally {
    salvandoFamilia.value = false
  }
}

async function adicionarMembro () {
  salvandoFamilia.value = true
  try {
    familia.value = (await familiasAPI.adicionarMembro({ email: emailNovoMembro.value, papel: papelNovoMembro.value })).data
    emailNovoMembro.value = ''
    papelNovoMembro.value = 'membro'
    sucesso('Membro adicionado')
  } catch (erroResposta) {
    falha(erroResposta)
  } finally {
    salvandoFamilia.value = false
  }
}

async function atualizarPapel (membro, papel) {
  try {
    familia.value = (await familiasAPI.atualizarMembro(membro.id, { papel })).data
    sucesso('Papel atualizado')
  } catch (erroResposta) {
    falha(erroResposta)
  }
}

function confirmarRemocao (membro) {
  confirm.require({
    message: `Remover ${membro.usuario.nome} da família?`,
    header: 'Remover membro',
    acceptLabel: 'Remover',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        familia.value = (await familiasAPI.removerMembro(membro.id)).data
        sucesso('Membro removido')
      } catch (erroResposta) {
        falha(erroResposta)
      }
    }
  })
}

function confirmarSaida () {
  confirm.require({
    message: 'Deseja realmente sair desta família?',
    header: 'Sair da família',
    acceptLabel: 'Sair',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await familiasAPI.sair()
        familia.value = null
        sucesso('Você saiu da família')
      } catch (erroResposta) {
        falha(erroResposta)
      }
    }
  })
}

async function salvarSenhas () {
  const payload = Object.fromEntries(Object.entries(novasSenhas.value).filter(([, senha]) => senha))
  if (!Object.keys(payload).length) {
    toast.add({ severity: 'info', summary: 'Nenhuma alteração', detail: 'Informe ao menos uma nova senha para salvar.', life: 3500 })
    return
  }
  salvandoSenhas.value = true
  try {
    statusSenhas.value = (await senhasPdfAPI.atualizar(payload)).data
    novasSenhas.value = { itau: '', xp: '', naturgy: '', light: '', nio: '', contracheque: '' }
    sucesso('Senhas atualizadas')
  } catch (erroResposta) {
    falha(erroResposta)
  } finally {
    salvandoSenhas.value = false
  }
}

function confirmarRemoverSenha (item) {
  confirm.require({
    message: `Remover a senha de ${item.nome}?`,
    header: 'Remover senha',
    acceptLabel: 'Remover',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        statusSenhas.value = (await senhasPdfAPI.atualizar({ [item.chave]: null })).data
        novasSenhas.value[item.chave] = ''
        sucesso('Senha removida')
      } catch (erroResposta) {
        falha(erroResposta)
      }
    }
  })
}

function statusSenha (chave) {
  if (statusSenhas.value[chave]?.legivel) return 'Cadastrada'
  if (statusSenhas.value[chave]?.configurada) return 'Recadastrar'
  return 'Não cadastrada'
}

function detalheErro (erroResposta) {
  return erroResposta.response?.data?.detail || 'Tente novamente em instantes.'
}

function sucesso (detail) {
  toast.add({ severity: 'success', summary: 'Concluído', detail, life: 3500 })
}

function falha (erroResposta) {
  toast.add({ severity: 'error', summary: 'Não foi possível concluir', detail: detalheErro(erroResposta), life: 5000 })
}
</script>

<style scoped>
.configuracoes-page { padding-block: 2rem 3rem; }
.page-head { margin-bottom: 1.5rem; }
.page-head p { color: var(--muted); margin-top: .35rem; }
.settings-card { margin-top: 1.25rem; }
.narrow-card { max-width: 38rem; }
.settings-form { display: grid; gap: .75rem; }
.family-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.family-actions, .member-form, .password-actions { display: flex; gap: .7rem; align-items: center; flex-wrap: wrap; }
.member-form { display: grid; grid-template-columns: minmax(12rem, 1fr) 10rem auto; }
.members-card { margin-top: 1rem; }
.member-email { display: block; color: var(--muted); margin-top: .15rem; }
.passwords-card :deep(.p-message) { margin-bottom: 1rem; }
.passwords-form { display: grid; gap: .8rem; }
.password-row { display: grid; grid-template-columns: minmax(7rem, 1fr) minmax(14rem, 1.3fr) auto auto; gap: .75rem; align-items: center; padding: .8rem 0; border-bottom: 1px solid var(--line); }
.password-row small { display: block; color: var(--muted); margin-top: .2rem; }
.password-actions { justify-content: flex-end; margin-top: .5rem; }
.loading-copy { color: var(--muted); padding: 2rem 0; }

@media (max-width: 760px) {
  .family-summary { grid-template-columns: 1fr; }
  .member-form, .password-row { grid-template-columns: 1fr; }
  .password-actions { justify-content: stretch; }
  .password-actions :deep(.p-button) { width: 100%; }
}
</style>
