<template>
  <PrimeCard class="card">
    <template #title>
      <div class="card-header">
        <h2>{{ titulo }}</h2>
        <span v-if="valor" class="valor">{{ formatarValor(valor) }}</span>
      </div>
    </template>
    <template #content>
      <slot></slot>
    </template>
  </PrimeCard>
</template>

<script setup>
import PrimeCard from 'primevue/card'

defineProps({
  titulo: {
    type: String,
    required: true
  },
  valor: {
    type: Number,
    default: null
  }
})

const formatarValor = (valor) => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(valor)
}
</script>

<style scoped>
.card {
  margin-bottom: 1rem;
}

.card :deep(.p-card-body) {
  padding: 0;
}

.card :deep(.p-card-content) {
  padding: 1.2rem 1.35rem;
  color: var(--muted);
}

.card-header {
  background: var(--surface-muted);
  padding: 1.2rem 1.35rem;
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.card-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text);
}

.valor {
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--success);
  white-space: nowrap;
}
</style>
