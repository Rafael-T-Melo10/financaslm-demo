<template>
  <div class="container">
    <h1>Cadastro</h1>

    <form @submit.prevent="fazerCadastro" class="formulario-cadastro">
      <div class="form-group">
        <label for="nome">Nome:</label>
        <InputText id="nome" v-model="nome" type="text" required placeholder="Seu nome" fluid />
      </div>

      <div class="form-group">
        <label for="email">Email:</label>
        <InputText id="email" v-model="email" type="email" required placeholder="seu@email.com" fluid />
      </div>

      <div class="form-group">
        <label for="senha">Senha:</label>
        <Password id="senha" v-model="senha" required placeholder="Sua senha" :feedback="false" toggle-mask fluid />
      </div>

      <Button type="submit" label="Cadastrar" class="btn-cadastrar" :loading="enviando" />
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import { useToast } from 'primevue/usetoast'
import { authAPI, usuariosAPI } from '../api/client'

const router = useRouter()
const nome = ref('')
const email = ref('')
const senha = ref('')
const enviando = ref(false)
const toast = useToast()

const fazerCadastro = async () => {
  enviando.value = true
  try {
    const payload = { nome: nome.value, email: email.value, senha: senha.value }
    await usuariosAPI.criar(payload)

    // login automático após o cadastro
    const login = await authAPI.login(email.value, senha.value)
    localStorage.setItem('token', login.data.access_token)
    localStorage.setItem('usuario', JSON.stringify(login.data.usuario))
    router.push('/')
  } catch (erro) {
    console.error('Erro no cadastro:', erro)
    toast.add({
      severity: 'error',
      summary: 'Não foi possível cadastrar',
      detail: erro.response?.data?.detail || 'Tente novamente em instantes.',
      life: 5000
    })
  } finally {
    enviando.value = false
  }
}
</script>

<style scoped>
.container {
  max-width: 480px;
  margin: 4rem auto;
  padding: 0 1rem;
}

h1 {
  color: var(--text);
  text-align: center;
  margin-bottom: 1.5rem;
}

.formulario-cadastro {
  background: var(--surface);
  padding: 1.5rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
}

.form-group { margin-bottom: 1rem }

label { display:block; margin-bottom: .5rem }

.btn-cadastrar { margin-top: .5rem; width: 100% }
</style>
