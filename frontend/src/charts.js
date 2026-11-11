import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'

// Registro tree-shaken: só os módulos usados entram no bundle
use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

// Paletas validadas (scripts/validate_palette.js da skill dataviz) contra as
// superfícies do app: #ffffff (claro) e #141417 (escuro).
export const TEMAS_GRAFICO = {
  light: {
    superficie: '#ffffff',
    texto: '#1a1917',
    mutado: '#5c5b55',
    linha: 'rgba(20, 18, 10, 0.09)',
    neutro: '#8f8e86',
    categorico: ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834'],
    bom: '#059669',
    atencao: '#d97706',
    critico: '#dc2626'
  },
  dark: {
    superficie: '#141417',
    texto: '#f4f4f5',
    mutado: '#a4a4ad',
    linha: 'rgba(255, 255, 255, 0.06)',
    neutro: '#6d6d78',
    categorico: ['#3987e5', '#199e70', '#c98500', '#008300', '#9085e9', '#e66767', '#d55181', '#d95926'],
    bom: '#34d399',
    atencao: '#fbbf24',
    critico: '#fb5b6d'
  }
}

// Cor segue a entidade: cada categoria conhecida tem um slot fixo da paleta,
// independente de filtro ou ordenação.
const SLOT_POR_CATEGORIA = {
  alimentacao: 0,
  transporte: 1,
  moradia: 2,
  saude: 3,
  lazer: 4,
  diversao: 4,
  assinaturas: 5,
  educacao: 6,
  roupas: 7,
  vestuario: 7,
  impostos: 5,
  'cartao de credito': 2,
  diversos: 4,
  ajustes: 3,
  'ajustes da fatura': 3
}

export const normalizar = (nome) => String(nome || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .trim()

export function corDaCategoria(nome, tema) {
  if (normalizar(nome) === 'outros') return tema.neutro
  const slot = SLOT_POR_CATEGORIA[normalizar(nome)]
  return slot === undefined ? tema.neutro : tema.categorico[slot]
}
