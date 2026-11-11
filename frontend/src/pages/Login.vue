<template>
  <div class="container">
    <h1>Login</h1>

    <form @submit.prevent="fazerLogin" class="formulario-login">
      <div class="form-group">
        <label for="email">Email:</label>
        <InputText
          id="email"
          v-model="email"
          type="email"
          required
          placeholder="seu@email.com"
        />
      </div>

      <div class="form-group">
        <label for="senha">Senha:</label>
        <Password
          id="senha"
          v-model="senha"
          required
          placeholder="Sua senha"
          :feedback="false"
          toggle-mask
          fluid
        />
      </div>

      <Button type="submit" label="Entrar" class="btn-entrar" :loading="enviando" />

      <div class="links">
        <p>Não tem conta? <router-link to="/cadastro">Cadastre-se</router-link></p>
      </div>
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
import { authAPI } from '../api/client'

const router = useRouter()
const email = ref('')
const senha = ref('')
const enviando = ref(false)
const toast = useToast()

const fazerLogin = async () => {
  enviando.value = true
  try {
    const response = await authAPI.login(email.value, senha.value)

    localStorage.setItem('token', response.data.access_token)
    localStorage.setItem('usuario', JSON.stringify(response.data.usuario))

    router.push('/')
  } catch (erro) {
    toast.add({
      severity: 'error',
      summary: 'Não foi possível entrar',
      detail: erro.response?.data?.detail || 'Verifique suas credenciais e tente novamente.',
      life: 5000
    })
  } finally {
    enviando.value = false
  }
}
</script>

<style scoped>
.container {
  max-width: 400px;
  margin: 5rem auto;
  padding: 0 1rem;
}

h1 {
  color: var(--text);
  text-align: center;
  margin-bottom: 2rem;
}

.formulario-login {
  background: var(--surface);
  padding: 2rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text);
}

.form-group :deep(.p-inputtext) {
  width: 100%;
}

.btn-entrar {
  width: 100%;
}

.links {
  text-align: center;
  margin-top: 1.5rem;
  color: var(--muted);
}

.links a {
  color: var(--primary-strong);
  text-decoration: none;
}

.links a:hover {
  text-decoration: underline;
}
</style>
