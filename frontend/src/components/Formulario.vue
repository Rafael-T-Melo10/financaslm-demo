<template>
  <form @submit.prevent="enviarFormulario" class="formulario">
    <div v-for="campo in campos" :key="campo.nome" class="form-group">
      <label :for="campo.nome">{{ campo.label }}</label>
      <Select
        v-if="campo.tipo === 'select'"
        :id="campo.nome"
        v-model="formData[campo.nome]"
        :options="campo.opcoes"
        :required="campo.obrigatorio"
        placeholder="Selecione..."
      />
      <InputNumber
        v-else-if="campo.tipo === 'number'"
        :id="campo.nome"
        v-model="formData[campo.nome]"
        :required="campo.obrigatorio"
        :placeholder="campo.placeholder"
        :step="Number(campo.step || 1)"
        :min="campo.min !== undefined ? Number(campo.min) : null"
        :max="campo.max !== undefined ? Number(campo.max) : null"
        :min-fraction-digits="campo.step === '0.01' ? 2 : 0"
        :max-fraction-digits="campo.step === '0.01' ? 2 : 0"
      />
      <Textarea
        v-else-if="campo.tipo === 'textarea'"
        :id="campo.nome"
        v-model="formData[campo.nome]"
        :required="campo.obrigatorio"
        :placeholder="campo.placeholder"
        rows="4"
      />
      <InputText
        v-else
        :id="campo.nome"
        v-model="formData[campo.nome]"
        :type="campo.tipo"
        :required="campo.obrigatorio"
        :placeholder="campo.placeholder"
        :step="campo.step"
        :min="campo.min"
        :max="campo.max"
      />
    </div>
    <div class="form-actions">
      <Button v-if="mostrarReset" type="button" label="Limpar" icon="pi pi-eraser" severity="secondary" outlined @click="resetar" />
      <Button type="submit" :label="botaoTexto" icon="pi pi-check" />
    </div>
  </form>
</template>

<script setup>
import { reactive } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'

const props = defineProps({
  campos: {
    type: Array,
    required: true
  },
  botaoTexto: {
    type: String,
    default: 'Enviar'
  },
  mostrarReset: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['enviar'])

const formData = reactive({})

const enviarFormulario = () => {
  emit('enviar', { ...formData })
}

const resetar = () => {
  props.campos.forEach(campo => {
    formData[campo.nome] = campo.tipo === 'number' ? null : ''
  })
}

// Inicializar valores vazios
props.campos.forEach(campo => {
  formData[campo.nome] = campo.valor !== undefined ? campo.valor : (campo.tipo === 'number' ? null : '')
})
</script>

<style scoped>
.formulario {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: 1rem 1.05rem;
  padding: 1.1rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--line, rgba(15, 23, 42, 0.11));
  border-radius: 18px;
  box-shadow: var(--shadow, 0 18px 44px rgba(15, 23, 42, 0.08));
}

.form-group {
  display: grid;
  flex: 1 1 190px;
  gap: 0.45rem;
  min-width: 0;
}

label {
  font-weight: 500;
  color: var(--muted, #6d7f92);
  font-size: 0.82rem;
  font-weight: 800;
}

.p-inputtext,
.p-inputnumber,
.p-select,
.p-textarea {
  width: 100%;
  min-height: 48px;
}

.p-inputnumber :deep(.p-inputtext) {
  width: 100%;
}

textarea {
  resize: vertical;
  min-height: 100px;
}

.form-actions {
  align-self: end;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  flex: 0 0 auto;
  justify-content: flex-end;
  margin-left: auto;
}

.form-actions :deep(.p-button) {
  min-height: 48px;
}

@media (max-width: 640px) {
  .formulario {
    display: grid;
    grid-template-columns: 1fr;
  }

  .form-group,
  .form-actions {
    width: 100%;
  }

  .form-actions :deep(.p-button) {
    flex: 1 1 10rem;
  }
}
</style>
