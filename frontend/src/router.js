import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'
import Receitas from './pages/Receitas.vue'
import Despesas from './pages/Despesas.vue'
import Cartoes from './pages/Cartoes.vue'
import Parcelas from './pages/Parcelas.vue'
import Recorrentes from './pages/Recorrentes.vue'
import Importar from './pages/Importar.vue'
import ImportacoesPendentes from './pages/ImportacoesPendentes.vue'
import Assistente from './pages/Assistente.vue'
import Login from './pages/Login.vue'
import Cadastro from './pages/Cadastro.vue'
import Configuracoes from './pages/Configuracoes.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/receitas',
    name: 'Receitas',
    component: Receitas,
    meta: { requiresAuth: true }
  },
  {
    path: '/despesas',
    name: 'Despesas',
    component: Despesas,
    meta: { requiresAuth: true }
  },
  {
    path: '/cartoes',
    name: 'Cartoes',
    component: Cartoes,
    meta: { requiresAuth: true }
  },
  {
    path: '/parcelas',
    name: 'Parcelas',
    component: Parcelas,
    meta: { requiresAuth: true }
  },
  {
    path: '/recorrentes',
    name: 'Recorrentes',
    component: Recorrentes,
    meta: { requiresAuth: true }
  },
  {
    path: '/importar',
    name: 'Importar',
    component: Importar,
    meta: { requiresAuth: true }
  },
  {
    path: '/importacoes-pendentes',
    name: 'ImportacoesPendentes',
    component: ImportacoesPendentes,
    meta: { requiresAuth: true }
  },
  {
    path: '/configuracoes',
    name: 'Configuracoes',
    component: Configuracoes,
    meta: { requiresAuth: true }
  },
  {
    path: '/assistente',
    name: 'Assistente',
    component: Assistente,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  }
  ,
  {
    path: '/cadastro',
    name: 'Cadastro',
    component: Cadastro
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  const temToken = Boolean(localStorage.getItem('token'))

  if (requiresAuth && !temToken) {
    next('/login')
  } else if (to.path === '/login' && temToken) {
    next('/')
  } else {
    next()
  }
})

export default router
