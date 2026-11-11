<template>
  <form class="card-form" @submit.prevent="salvarCartao">
    <label>
      Nome
      <InputText v-model.trim="form.nome" required placeholder="Ex: Itaú Platinum" />
    </label>

    <label>
      Bandeira
      <Select v-model="form.bandeira" :options="bandeiraOptions" option-label="label" option-value="value" />
    </label>

    <label>
      Últimos 4 dígitos
      <InputText v-model.trim="form.ultimos_digitos" maxlength="4" inputmode="numeric" placeholder="1234" />
    </label>

    <label>
      Limite
      <InputNumber v-model="form.limite" :min="0" :step="0.01" :min-fraction-digits="2" :max-fraction-digits="2" placeholder="0.00" />
    </label>

    <label>
      Dia do vencimento
      <InputNumber v-model="form.data_vencimento" :min="1" :max="31" show-buttons required />
    </label>

    <label v-if="cartao" class="toggle-row">
      <Checkbox v-model="form.ativo" binary input-id="cartao-ativo" />
      Cartão ativo
    </label>

    <div class="form-actions">
      <Button type="button" label="Cancelar" severity="secondary" outlined @click="$emit('cancel')" />
      <Button type="submit" :label="cartao ? 'Salvar alterações' : 'Adicionar cartão'" icon="pi pi-check" :loading="salvando" />
    </div>
  </form>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { useToast } from 'primevue/usetoast'
import { cartoesAPI } from '../api/client'

const props = defineProps({
  cartao: {
    type: Object,
    default: null
  },
  nomeInicial: {
    type: String,
    default: ''
  },
  limiteInicial: {
    type: Number,
    default: null
  },
  vencimentoInicial: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['saved', 'cancel'])
const salvando = ref(false)
const toast = useToast()

const bandeiras = ['Visa', 'Mastercard', 'American Express', 'Elo', 'Hipercard']
const bandeiraOptions = [
  { label: 'Sem bandeira', value: '' },
  ...bandeiras.map((bandeira) => ({ label: bandeira, value: bandeira }))
]

const estadoInicial = () => ({
  nome: '',
  bandeira: '',
  ultimos_digitos: '',
  limite: 0,
  data_vencimento: 10,
  ativo: true
})

const form = reactive(estadoInicial())

const preencherFormulario = (dados) => {
  Object.assign(form, dados)
}

const sincronizarComProp = (cartao) => {
  if (cartao) {
    preencherFormulario({
      nome: cartao.nome || '',
      bandeira: cartao.bandeira || '',
      ultimos_digitos: cartao.ultimos_digitos || '',
      limite: Number(cartao.limite || 0),
      data_vencimento: Number(cartao.data_vencimento || 10),
      ativo: Boolean(cartao.ativo)
    })
  } else {
    preencherFormulario({
      ...estadoInicial(),
      nome: props.nomeInicial || '',
      limite: props.limiteInicial ?? 0,
      data_vencimento: props.vencimentoInicial ?? 10
    })
  }
}

sincronizarComProp(props.cartao)

watch(() => props.cartao, (cartao) => {
  sincronizarComProp(cartao)
})

watch(() => [props.nomeInicial, props.limiteInicial, props.vencimentoInicial], () => {
  if (!props.cartao) {
    sincronizarComProp(null)
  }
})

const montarPayload = () => ({
  nome: form.nome,
  bandeira: form.bandeira || null,
  ultimos_digitos: form.ultimos_digitos || null,
  limite: Number(form.limite || 0),
  data_vencimento: Number(form.data_vencimento || 1),
  ativo: Boolean(form.ativo)
})

const salvarCartao = async () => {
  salvando.value = true
  try {
    const payload = montarPayload()

    const response = props.cartao
      ? await cartoesAPI.atualizar(props.cartao.id, payload)
      : await cartoesAPI.criar(payload)

    emit('saved', response.data)
  } catch (erro) {
    console.error('Erro ao salvar cartão:', erro)
    toast.add({
      severity: 'error',
      summary: 'Não foi possível salvar o cartão',
      detail: erro.response?.data?.detail || 'Tente novamente em instantes.',
      life: 5000
    })
  } finally {
    salvando.value = false
  }
}
</script>

<style scoped>
.card-form {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.85rem;
  align-items: end;
}

.card-form label {
  display: grid;
  gap: 0.4rem;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.card-form :deep(.p-inputtext),
.card-form :deep(.p-inputnumber),
.card-form :deep(.p-select) {
  width: 100%;
  min-height: 40px;
}

.card-form :deep(.p-inputnumber-input) {
  width: 100%;
}

.toggle-row {
  min-height: 40px;
  display: flex !important;
  align-items: center;
  gap: 0.55rem !important;
  color: var(--text) !important;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  grid-column: 1 / -1;
}

@media (max-width: 980px) {
  .card-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .card-form {
    grid-template-columns: 1fr;
    display: grid;
  }
}
</style>
