<template>
  <header class="navbar">
    <div class="navbar-inner">
      <router-link to="/" class="navbar-brand">
        <span class="brand-mark">G</span>
        <span class="brand-copy">
          <strong>Gastos</strong>
          <small>controle financeiro</small>
        </span>
      </router-link>

      <nav class="nav-links" aria-label="Navegacao principal">
        <router-link
          v-for="item in items"
          :key="item.route"
          v-slot="{ href, navigate, isActive }"
          :to="item.route"
          custom
        >
          <a
            :href="href"
            :class="['nav-link', { active: isActive }]"
            @click="navigate"
          >
            <span :class="item.icon" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </a>
        </router-link>
      </nav>

      <div class="navbar-actions">
        <div class="import-menu">
          <Button
            type="button"
            class="import-button"
            :class="{ 'router-link-active': rotaImportarAtiva }"
            aria-haspopup="true"
            @click="toggleMenuImportar"
          >
            <span class="pi pi-upload" aria-hidden="true" />
            <span>Importar</span>
            <span class="pi pi-chevron-down import-caret" aria-hidden="true" />
          </Button>
          <Menu ref="menuImportarRef" :model="opcoesImportar" :popup="true" />
        </div>

        <div class="notifications-menu">
          <Button
            type="button"
            class="notification-button"
            icon="pi pi-bell"
            text
            rounded
            aria-label="Abrir notificações"
            aria-haspopup="true"
            @click="toggleNotificacoes"
          />
          <Badge v-if="naoLidas" class="notification-badge" :value="naoLidas > 99 ? '99+' : naoLidas" severity="danger" />

          <Popover ref="notificacoesRef" class="notifications-popover">
            <section class="notifications-panel" aria-label="Central de notificações">
              <header class="notifications-head">
                <div>
                  <strong>Notificações</strong>
                  <small>{{ naoLidas ? `${naoLidas} não lida(s)` : 'Tudo em dia' }}</small>
                </div>
                <Button
                  v-if="naoLidas"
                  label="Marcar todas como lidas"
                  size="small"
                  text
                  @click="marcarTodasLidas"
                />
              </header>

              <div v-if="carregandoNotificacoes && !notificacoes.length" class="notifications-empty">
                <i class="pi pi-spin pi-spinner" aria-hidden="true" />
                <span>Atualizando...</span>
              </div>
              <div v-else-if="notificacoes.length" class="notifications-list">
                <Button
                  v-for="item in notificacoes"
                  :key="item.id"
                  type="button"
                  class="notification-item"
                  :class="[`severity-${item.severidade}`, { unread: !item.lida_em }]"
                  text
                  @click="abrirNotificacao(item)"
                >
                  <span class="notification-icon" :class="iconeNotificacao(item)" aria-hidden="true" />
                  <span class="notification-copy">
                    <span class="notification-title-row">
                      <strong>{{ item.titulo }}</strong>
                      <span v-if="!item.lida_em" class="unread-dot" aria-label="Não lida" />
                    </span>
                    <span class="notification-message">{{ item.mensagem }}</span>
                    <ProgressBar
                      v-if="item.estado === 'em_andamento'"
                      :value="percentualNotificacao(item)"
                      :show-value="false"
                    />
                    <small>{{ formatarMomento(item.atualizada_em) }}</small>
                  </span>
                </Button>
              </div>
              <div v-else class="notifications-empty">
                <i class="pi pi-check-circle" aria-hidden="true" />
                <span>Nenhuma informação precisa da sua atenção.</span>
              </div>
            </section>
          </Popover>
        </div>

        <Button
          type="button"
          class="theme-button"
          :icon="tema === 'dark' ? 'pi pi-sun' : 'pi pi-moon'"
          :label="tema === 'dark' ? 'Claro' : 'Escuro'"
          outlined
          @click="$emit('alternar-tema')"
        />

        <Button
          type="button"
          class="config-button"
          icon="pi pi-cog"
          text
          rounded
          aria-label="Abrir configurações"
          :class="{ 'router-link-active': route.path === '/configuracoes' }"
          @click="router.push('/configuracoes')"
        />

        <Button type="button" class="logout-button" icon="pi pi-sign-out" label="Sair" outlined @click="logout" />
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import Popover from 'primevue/popover'
import ProgressBar from 'primevue/progressbar'
import { useRoute, useRouter } from 'vue-router'
import { useNotifications } from '../composables/useNotifications'

defineProps({
  tema: {
    type: String,
    default: 'light'
  }
})

defineEmits(['alternar-tema'])

const router = useRouter()
const route = useRoute()
const notificacoesRef = ref(null)
const {
  items: notificacoes,
  naoLidas,
  carregando: carregandoNotificacoes,
  marcarLida,
  marcarTodasLidas
} = useNotifications()

const items = [
  { label: 'Dashboard', icon: 'pi pi-chart-line', route: '/' },
  { label: 'Receitas', icon: 'pi pi-arrow-down-left', route: '/receitas' },
  { label: 'Despesas', icon: 'pi pi-arrow-up-right', route: '/despesas' },
  { label: 'Cartões', icon: 'pi pi-credit-card', route: '/cartoes' },
  { label: 'Parcelas', icon: 'pi pi-list-check', route: '/parcelas' },
  { label: 'Recorrentes', icon: 'pi pi-sync', route: '/recorrentes' },
  { label: 'Assistente', icon: 'pi pi-sparkles', route: '/assistente' }
]

const menuImportarRef = ref(null)

const opcoesImportar = [
  {
    label: 'Upload manual',
    icon: 'pi pi-upload',
    command: () => router.push('/importar')
  },
  {
    label: 'Gmail (automático)',
    icon: 'pi pi-inbox',
    command: () => router.push('/importacoes-pendentes')
  }
]

const rotaImportarAtiva = computed(() => (
  route.path === '/importar' || route.path === '/importacoes-pendentes'
))

const toggleMenuImportar = (evento) => {
  menuImportarRef.value.toggle(evento)
}

const toggleNotificacoes = (evento) => {
  notificacoesRef.value.toggle(evento)
}

const abrirNotificacao = async (item) => {
  try {
    if (!item.lida_em) await marcarLida(item)
  } finally {
    notificacoesRef.value.hide()
    if (item.rota) router.push(item.rota)
  }
}

const iconeNotificacao = (item) => {
  if (item.estado === 'em_andamento') return 'pi pi-spin pi-sync'
  if (item.tipo === 'gmail') return 'pi pi-inbox'
  if (item.severidade === 'critical') return 'pi pi-exclamation-circle'
  if (item.severidade === 'warning') return 'pi pi-exclamation-triangle'
  if (item.severidade === 'success') return 'pi pi-check-circle'
  return 'pi pi-info-circle'
}

const percentualNotificacao = (item) => {
  if (!item.progresso_total) return 0
  return Math.min(100, Math.round((Number(item.progresso_atual || 0) / item.progresso_total) * 100))
}

const formatarMomento = (valor) => {
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return ''
  const minutos = Math.max(0, Math.round((Date.now() - data.getTime()) / 60000))
  if (minutos < 1) return 'agora'
  if (minutos < 60) return `há ${minutos} min`
  const horas = Math.round(minutos / 60)
  if (horas < 24) return `há ${horas} h`
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' }).format(data)
}

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('usuario')
  router.push('/login')
}
</script>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: color-mix(in srgb, var(--surface-strong) 92%, transparent);
  border-bottom: 1px solid var(--line);
  box-shadow: var(--shadow);
  backdrop-filter: blur(16px);
}

.navbar-inner {
  min-height: 64px;
  margin: 0 auto;
  width: 100vw;
  padding: 0.65rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.navbar-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.85rem;
  margin-right: 0.25rem;
  text-decoration: none;
  color: var(--text);
  flex: 0 0 auto;
}

.navbar-brand strong {
  display: block;
  font-size: 0.98rem;
  letter-spacing: 0.02em;
  line-height: 1.1;
}

.navbar-brand small {
  display: block;
  color: var(--muted);
  font-size: 0.74rem;
  line-height: 1.2;
}

.brand-mark {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.75rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: var(--primary-contrast);
  background: linear-gradient(135deg, var(--primary), var(--primary-strong));
  box-shadow: 0 10px 22px color-mix(in srgb, var(--primary) 22%, transparent);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
  flex: 1 1 auto;
}

.navbar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 0 0 auto;
}

.nav-links::-webkit-scrollbar {
  display: none;
}

.nav-link {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--muted);
  border-radius: 10px;
  padding: 0.55rem 0.78rem;
  text-decoration: none;
  white-space: nowrap;
  transition: color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.nav-link:hover {
  color: var(--text);
  background: var(--primary-soft);
}

.nav-link.active {
  color: var(--primary-strong);
  background: var(--primary-soft);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--primary) 22%, transparent);
}

.import-menu {
  position: relative;
}

.import-button {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.9rem;
  border: none;
  border-radius: 10px;
  text-decoration: none;
  white-space: nowrap;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  color: var(--primary-contrast);
  background: var(--primary);
  box-shadow: 0 12px 24px color-mix(in srgb, var(--primary) 22%, transparent);
  transition: transform 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.import-button:hover,
.import-button.router-link-active {
  color: var(--primary-contrast);
  background: var(--primary-strong);
  box-shadow: 0 12px 24px color-mix(in srgb, var(--primary) 24%, transparent);
}

.import-button:hover {
  transform: translateY(-1px);
}

.import-button:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--primary) 55%, white);
  outline-offset: 2px;
}

.import-caret {
  font-size: 0.7rem;
  opacity: 0.85;
}

.notifications-menu {
  position: relative;
}

.notification-button.p-button {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--text);
  background: var(--surface-strong);
  border: 1px solid var(--line);
}

.notification-button.p-button:hover {
  color: var(--primary-strong);
  background: var(--primary-soft);
  border-color: color-mix(in srgb, var(--primary) 36%, transparent);
}

.notification-badge {
  position: absolute;
  top: -0.25rem;
  right: -0.35rem;
  min-width: 1.25rem;
  height: 1.25rem;
  font-size: 0.65rem;
  pointer-events: none;
}

:global(.notifications-popover) {
  max-width: calc(100vw - 1rem);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow);
}

.notifications-panel {
  width: min(25rem, calc(100vw - 2.5rem));
}

.notifications-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.2rem 0.25rem 0.85rem;
  border-bottom: 1px solid var(--line);
}

.notifications-head strong,
.notifications-head small {
  display: block;
}

.notifications-head small {
  margin-top: 0.15rem;
  color: var(--muted);
}

.notifications-list {
  max-height: 28rem;
  overflow-y: auto;
  display: grid;
  gap: 0.35rem;
  padding-top: 0.6rem;
}

.notification-item.p-button {
  width: 100%;
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr);
  align-items: start;
  gap: 0.7rem;
  padding: 0.75rem;
  border: 1px solid transparent;
  border-radius: 12px;
  color: var(--text);
  background: transparent;
  text-align: left;
  white-space: normal;
}

.notification-item.p-button:hover {
  background: var(--surface-hover);
  border-color: var(--line);
  color: var(--text);
}

.notification-item.unread {
  background: color-mix(in srgb, var(--primary-soft) 60%, var(--surface));
}

.notification-icon {
  width: 2rem;
  height: 2rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  color: var(--muted);
  background: var(--surface-muted);
}

.severity-critical .notification-icon { color: var(--danger); background: var(--danger-soft); }
.severity-warning .notification-icon { color: var(--warning); background: color-mix(in srgb, var(--warning) 14%, transparent); }
.severity-success .notification-icon { color: var(--success); background: var(--success-soft); }

.notification-copy,
.notification-title-row {
  min-width: 0;
}

.notification-copy {
  display: grid;
  gap: 0.28rem;
}

.notification-title-row {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 0.5rem;
}

.notification-title-row strong {
  font-size: 0.88rem;
  line-height: 1.25;
}

.notification-message {
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.35;
}

.notification-copy small {
  color: var(--muted-2);
  font-size: 0.72rem;
}

.notification-copy :deep(.p-progressbar) {
  height: 0.35rem;
  margin-top: 0.2rem;
}

.unread-dot {
  width: 0.45rem;
  height: 0.45rem;
  margin-top: 0.25rem;
  border-radius: 999px;
  flex: 0 0 auto;
  background: var(--primary);
}

.notifications-empty {
  min-height: 9rem;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 0.65rem;
  color: var(--muted);
  text-align: center;
  font-size: 0.86rem;
}

.notifications-empty .pi {
  color: var(--success);
  font-size: 1.4rem;
}

.theme-button.p-button, .config-button,
.logout-button.p-button {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  border-radius: 10px;
  background: var(--surface-strong);
  cursor: pointer;
  font-weight: 700;
  padding: 0.55rem 0.78rem;
  white-space: nowrap;
  transition: color 0.15s ease, background 0.15s ease, border-color 0.15s ease;
}

.theme-button.p-button,.config-button {
  border: 1px solid var(--line);
  color: var(--text);
}

.theme-button.p-button:hover, .config-button:hover {
  border-color: color-mix(in srgb, var(--primary) 36%, transparent);
  background: var(--primary-soft);
  color: var(--primary-strong);
}

.logout-button.p-button {
  border: 1px solid color-mix(in srgb, var(--danger) 24%, transparent);
  color: var(--danger);
}

.logout-button.p-button:hover {
  border-color: color-mix(in srgb, var(--danger) 40%, transparent);
  background: var(--danger-soft);
}

@media (max-width: 900px) {
  .navbar-inner {
    align-items: stretch;
    flex-direction: column;
    gap: 0.6rem;
  }

  .nav-links {
    padding-bottom: 0.1rem;
  }

  .navbar-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .import-button,
  .theme-button,
  .logout-button {
    align-self: flex-start;
  }

  .nav-link {
    padding-inline: 0.7rem;
  }
}

@media (max-width: 520px) {
  .brand-copy small {
    display: none;
  }
}
</style>
