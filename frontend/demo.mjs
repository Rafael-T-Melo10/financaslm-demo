import { spawn } from 'node:child_process';
const child = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '3012', '--strictPort'], {
  stdio: 'inherit',
  env: { ...process.env, VITE_API_BASE: '/api', VITE_PROXY_TARGET: 'http://127.0.0.1:8012', VITE_PORT: '3012' }
});
child.on('exit', code => process.exit(code ?? 1));
