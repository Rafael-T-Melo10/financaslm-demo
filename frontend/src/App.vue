<template>
  <div id="app" :class="['app-shell', { 'app-dark': tema === 'dark' }]">
    <Navbar v-if="usuario" :tema="tema" @alternar-tema="alternarTema" />
    <aside class="portfolio-notice">PORTFOLIO DEMO · Dados inteiramente fictícios</aside>
    <router-view class="router-view" />
    <Toast position="top-right" />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { onBeforeUnmount, provide, ref, watch } from 'vue'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import Navbar from './components/Navbar.vue'
import { useRoute } from 'vue-router'
import { useNotifications } from './composables/useNotifications'

const route = useRoute()
const usuario = ref(null)
const tema = ref(obterTemaInicial())
const { iniciar: iniciarNotificacoes, parar: pararNotificacoes } = useNotifications()

provide('tema', tema)

const sincronizarUsuario = () => {
  const usuarioArmazenado = localStorage.getItem('usuario')
  usuario.value = usuarioArmazenado ? JSON.parse(usuarioArmazenado) : null
}

const aplicarTema = (valor) => {
  document.documentElement.classList.toggle('app-dark', valor === 'dark')
  localStorage.setItem('tema', valor)
}

const alternarTema = () => {
  tema.value = tema.value === 'dark' ? 'light' : 'dark'
}

watch(() => route.fullPath, sincronizarUsuario, { immediate: true })
watch(tema, aplicarTema, { immediate: true })
watch(usuario, (valor) => {
  if (valor) iniciarNotificacoes()
  else pararNotificacoes()
}, { immediate: true })

onBeforeUnmount(pararNotificacoes)

function obterTemaInicial() {
  const salvo = localStorage.getItem('tema')
  if (salvo === 'dark' || salvo === 'light') return salvo
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}
</script>

<style>
.portfolio-notice {
  padding: 8px 16px;
  text-align: center;
  font: 600 12px system-ui, sans-serif;
  letter-spacing: .04em;
  color: var(--text);
  background: var(--primary-soft);
  border-bottom: 1px solid var(--line);
}

:root {
  --bg: #f4f3ef;
  --surface: #ffffff;
  --surface-strong: #f4f3ef;
  --surface-muted: #eceae4;
  --surface-hover: #eceae4;
  --surface-inset: #f4f3ef;
  --text: #1a1917;
  --muted: #5c5b55;
  --muted-2: #8f8e86;
  --line: rgba(20, 18, 10, 0.09);
  --line-strong: rgba(20, 18, 10, 0.14);
  --primary: #d99500;
  --primary-strong: #b87e00;
  --primary-soft: rgba(217, 149, 0, 0.12);
  --primary-line: rgba(217, 149, 0, 0.4);
  --primary-contrast: #1a1400;
  --success: #059669;
  --success-soft: rgba(5, 150, 105, 0.12);
  --danger: #dc2626;
  --danger-soft: rgba(220, 38, 38, 0.12);
  --warning: #d97706;
  --shadow: 0 12px 32px -16px rgba(30, 20, 0, 0.22);
  --glow: rgba(245, 179, 1, 0.14);
  --page-bg:
    radial-gradient(1100px 520px at 12% -8%, var(--glow), transparent 60%),
    var(--bg);
  color-scheme: light;
}

.app-dark {
  --bg: #0a0a0c;
  --surface: #141417;
  --surface-strong: #1c1c21;
  --surface-muted: #1c1c21;
  --surface-hover: #26262c;
  --surface-inset: #1c1c21;
  --text: #f4f4f5;
  --muted: #a4a4ad;
  --muted-2: #6d6d78;
  --line: rgba(255, 255, 255, 0.06);
  --line-strong: rgba(255, 255, 255, 0.1);
  --primary: #f5b301;
  --primary-strong: #f7c948;
  --primary-soft: rgba(245, 179, 1, 0.14);
  --primary-line: rgba(245, 179, 1, 0.35);
  --primary-contrast: #1a1400;
  --success: #34d399;
  --success-soft: rgba(52, 211, 153, 0.14);
  --danger: #fb5b6d;
  --danger-soft: rgba(251, 91, 109, 0.14);
  --warning: #fbbf24;
  --shadow: 0 12px 40px -12px rgba(0, 0, 0, 0.6);
  --glow: rgba(245, 179, 1, 0.1);
  --page-bg:
    radial-gradient(1100px 520px at 12% -8%, var(--glow), transparent 60%),
    var(--bg);
  color-scheme: dark;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Manrope', system-ui, sans-serif;
  background: var(--page-bg);
  background-attachment: fixed;
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4,
.eyebrow,
.brand strong {
  font-family: 'Space Grotesk', 'Manrope', system-ui, sans-serif;
  letter-spacing: -0.02em;
}

#app {
  min-height: 100vh;
}

.app-shell {
  position: relative;
}

button,
input,
select,
textarea {
  font: inherit;
}

a {
  color: inherit;
}

.p-component {
  font-family: inherit;
}

.router-view {
  max-width: 80%;
  margin: 0 auto;
}

.p-card,
.metric-card.p-card,
.filters-panel.p-card,
.table-card.p-card {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.p-card .p-card-body,
.p-card .p-card-content,
.p-card .p-card-title,
.p-card .p-card-subtitle {
  color: inherit;
}

.metric-card.p-card .p-card-content {
  padding: 1.15rem 1.25rem;
}

.metric-card.p-card span {
  color: var(--muted);
}

.metric-card.p-card strong {
  color: var(--text);
}

.table-card.p-card .p-card-body {
  padding: 0;
}

.table-card.p-card .p-card-title {
  padding: 1.25rem 1.35rem 0.25rem;
  font-size: 1.2rem;
}

.table-card.p-card .p-card-subtitle {
  padding: 0 1.35rem 0.95rem;
  color: var(--muted);
}

.table-card.p-card .p-card-content {
  padding: 0;
}

.p-datatable {
  color: var(--text);
}

.p-datatable .p-datatable-thead > tr > th {
  background: var(--surface-muted);
  color: var(--text);
  border-color: var(--line);
  font-weight: 800;
  padding: 0.9rem 1rem;
}

.p-datatable .p-datatable-tbody > tr {
  background: var(--surface);
  color: var(--text);
}

.p-datatable.p-datatable-striped .p-datatable-tbody > tr.p-row-odd,
.p-datatable .p-datatable-tbody > tr:nth-child(even) {
  background: var(--surface-muted);
  color: var(--text);
}

.p-datatable .p-datatable-tbody > tr:hover,
.p-datatable.p-datatable-striped .p-datatable-tbody > tr.p-row-odd:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.p-datatable .p-datatable-tbody > tr > td {
  border-color: var(--line);
  padding: 0.95rem 1rem;
}

.p-inputtext,
.p-inputnumber,
.p-select,
.p-select-label,
.p-select-dropdown,
input,
select,
textarea {
  color: var(--text);
  background: var(--surface-strong);
  border-color: var(--line);
  border-radius: 12px;
}

.p-inputtext::placeholder,
input::placeholder,
textarea::placeholder,
.p-select-label.p-placeholder {
  color: var(--muted-2);
}

.p-inputtext:enabled:hover,
.p-inputnumber .p-inputtext:enabled:hover,
.p-select:not(.p-disabled):hover,
input:hover,
select:hover,
textarea:hover {
  border-color: var(--line-strong);
}

.p-inputtext:enabled:focus,
.p-inputnumber .p-inputtext:enabled:focus,
.p-select:not(.p-disabled).p-focus,
input:focus,
select:focus,
textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-soft);
  outline: none;
}

.p-select-overlay,
.p-datepicker-panel {
  background: var(--surface-strong);
  color: var(--text);
  border: 1px solid var(--line);
}

.p-select-option {
  color: var(--text);
}

.p-select-option:not(.p-select-option-selected):not(.p-disabled).p-focus {
  background: var(--surface-hover);
  color: var(--text);
}

.p-button {
  border-radius: 12px;
  font-weight: 700;
}

.p-button:not(.p-button-text):not(.p-button-outlined) {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--primary-contrast);
}

.p-button:not(.p-button-text):not(.p-button-outlined):enabled:hover {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
}

.p-button.p-button-secondary.p-button-outlined,
.p-button.p-button-outlined {
  color: var(--text);
  border-color: var(--line);
  background: var(--surface-strong);
}

.p-button.p-button-text {
  color: var(--muted);
}

.p-checkbox-box {
  border-color: var(--line-strong);
  border-radius: 6px;
}

.p-checkbox-checked .p-checkbox-box {
  background: var(--primary);
  border-color: var(--primary);
}

.p-tag {
  border-radius: 999px;
  font-weight: 800;
}

.p-tag-info {
  background: var(--primary-soft);
  color: var(--primary-strong);
}
</style>
