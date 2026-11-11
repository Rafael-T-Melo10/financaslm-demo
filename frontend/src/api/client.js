import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE
})

// Anexa o token JWT em toda requisição
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Sessão expirada/inválida: limpa credenciais e volta para o login
api.interceptors.response.use(
  (response) => response,
  (erro) => {
    if (erro.response?.status === 401 && !erro.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('usuario')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(erro)
  }
)

// Autenticação
export const authAPI = {
  login: (email, senha) => api.post('/auth/login', { email, senha })
}

// Usuários
export const usuariosAPI = {
  criar: (data) => api.post('/usuarios', data),
  me: () => api.get('/usuarios/me')
}

// Família
export const familiasAPI = {
  criar: (data) => api.post('/familias', data),
  minha: () => api.get('/familias/minha'),
  renomear: (data) => api.patch('/familias/minha', data),
  sair: () => api.delete('/familias/minha/participacao'),
  adicionarMembro: (data) => api.post('/familias/membros', data),
  atualizarMembro: (id, data) => api.patch(`/familias/membros/${id}`, data),
  removerMembro: (id) => api.delete(`/familias/membros/${id}`)
}

// Senhas usadas para abrir PDFs protegidos
export const senhasPdfAPI = {
  obter: () => api.get('/configuracoes/senhas-pdf'),
  atualizar: (data) => api.patch('/configuracoes/senhas-pdf', data)
}

// Receitas
export const receitasAPI = {
  criar: (data) => api.post('/receitas', data),
  listar: (mes = null, ano = null) => api.get('/receitas', { params: { mes, ano } }),
  atualizar: (id, data) => api.put(`/receitas/${id}`, data),
  deletar: (id) => api.delete(`/receitas/${id}`)
}

// Despesas
export const despesasAPI = {
  criar: (data) => api.post('/despesas', data),
  listar: (mes = null, ano = null, categoria = null) => api.get('/despesas', { params: { mes, ano, categoria } }),
  atualizar: (id, data) => api.put(`/despesas/${id}`, data),
  deletar: (id) => api.delete(`/despesas/${id}`)
}

// Cartões de Crédito
export const cartoesAPI = {
  criar: (data) => api.post('/cartoes', data),
  listar: () => api.get('/cartoes'),
  atualizar: (id, data) => api.put(`/cartoes/${id}`, data),
  deletar: (id) => api.delete(`/cartoes/${id}`)
}

// Parcelas
export const parcelasAPI = {
  criar: (data) => api.post('/parcelas', data),
  listar: (apenas_ativas = true) => api.get('/parcelas', { params: { apenas_ativas } }),
  atualizar: (id, data) => api.put(`/parcelas/${id}`, data),
  pagar: (id) => api.post(`/parcelas/${id}/pagar`),
  deletar: (id) => api.delete(`/parcelas/${id}`)
}

// Orçamentos por categoria
export const orcamentosAPI = {
  listar: () => api.get('/orcamentos'),
  definir: (categoria, limite) => api.put('/orcamentos', { categoria, limite }),
  remover: (categoria) => api.delete(`/orcamentos/${encodeURIComponent(categoria)}`)
}

// Catálogo pessoal e regras usadas nas importações
export const categoriasAPI = {
  listar: () => api.get('/categorias'),
  criar: (data) => api.post('/categorias', data),
  atualizar: (id, data) => api.put(`/categorias/${id}`, data)
}

export const regrasClassificacaoAPI = {
  listar: () => api.get('/regras-classificacao'),
  criar: (data) => api.post('/regras-classificacao', data),
  atualizar: (id, data) => api.put(`/regras-classificacao/${id}`, data),
  deletar: (id) => api.delete(`/regras-classificacao/${id}`)
}

// Despesas recorrentes (assinaturas, aluguel etc.)
export const despesasRecorrentesAPI = {
  criar: (data) => api.post('/despesas-recorrentes', data),
  listar: () => api.get('/despesas-recorrentes'),
  atualizar: (id, data) => api.put(`/despesas-recorrentes/${id}`, data),
  deletar: (id) => api.delete(`/despesas-recorrentes/${id}`)
}

// Exportação CSV
export const exportacaoAPI = {
  despesas: (mes = null, ano = null) => api.get('/exportar/despesas', { params: { mes, ano }, responseType: 'blob' }),
  receitas: (mes = null, ano = null) => api.get('/exportar/receitas', { params: { mes, ano }, responseType: 'blob' }),
  faturas: (mes = null, ano = null) => api.get('/exportar/faturas', { params: { mes, ano }, responseType: 'blob' })
}

// Importação
export const importacaoAPI = {
  contracheque: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/importar/holerite', formData)
  },
  holerite: (file) => importacaoAPI.contracheque(file),
  fatura: (cartao_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/importar/fatura?cartao_id=${cartao_id}`, formData)
  },
  conta: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/importar/conta', formData)
  }
}

// Faturas
export const faturasAPI = {
  listar: (cartao_id = null, mes = null, ano = null) => api.get('/faturas', { params: { cartao_id, mes, ano } })
}

// Importações pendentes (fila de revisão da importação automática via Gmail)
export const importacoesPendentesAPI = {
  listar: (status = null, page = 1, pageSize = 15) =>
    api.get('/importacoes-pendentes', { params: { status, page, page_size: pageSize } }),
  obter: (id) => api.get(`/importacoes-pendentes/${id}`),
  atualizar: (id, data) => api.patch(`/importacoes-pendentes/${id}`, data),
  confirmar: (id, data = {}) => api.post(`/importacoes-pendentes/${id}/confirmar`, data),
  rejeitar: (id) => api.post(`/importacoes-pendentes/${id}/rejeitar`),
  reabrir: (id) => api.post(`/importacoes-pendentes/${id}/reabrir`)
}

// Gmail (conexão OAuth e sincronização automática)
export const gmailAPI = {
  status: () => api.get('/gmail/status'),
  iniciarConexao: () => api.get('/gmail/oauth/iniciar'),
  alternarConexao: (ativo) => api.post('/gmail/conexao', null, { params: { ativo } }),
  sincronizarAgora: () => api.post('/gmail/sync')
}

// Central global de notificações
export const notificacoesAPI = {
  listar: (limite = 20, atualizarFinanceiro = true) => api.get('/notificacoes', {
    params: { limite, atualizar_financeiro: atualizarFinanceiro }
  }),
  marcarLida: (id, lida = true) => api.patch(`/notificacoes/${id}`, { lida }),
  marcarTodasLidas: () => api.post('/notificacoes/marcar-todas-lidas')
}

// Análise
export const analiseAPI = {
  obter: (mes = null, ano = null) => api.get('/analise', { params: { mes, ano } }),
  previsao: (meses = 3) => api.get('/previsao', { params: { meses } }),
  alertas: () => api.get('/alertas')
}

export const dashboardAPI = {
  obter: (mes, ano) => api.get('/dashboard', { params: { mes, ano } })
}

export const relatorioAPI = {
  anual: (ano) => api.get('/relatorio-anual', { params: { ano } })
}

// Assistente financeiro local (text2SQL, roda inteiramente na máquina do usuário)
export const assistenteAPI = {
  status: () => api.get('/assistente/status'),
  perguntar: (pergunta, modelo) => api.post('/assistente/perguntar', { pergunta, modelo: modelo || undefined }),
  carregarModelo: (modelo) => api.post('/assistente/carregar-modelo', { modelo })
}

export default api
