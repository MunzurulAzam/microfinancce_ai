const path = require('path');
const PROJECT = path.resolve(__dirname);

module.exports = {
  apps: [
    {
      name: 'microfinance-backend',
      script: path.join(PROJECT, '.venv/bin/uvicorn'),
      args: 'asgi:app --host 0.0.0.0 --port 5001',
      cwd: PROJECT,
      interpreter: 'none',
      env_file: path.join(PROJECT, '.env'),
      autorestart: true,
      watch: false,
    },
    {
      name: 'microfinance-frontend',
      script: 'npm',
      args: 'run dev',
      cwd: path.join(PROJECT, 'frontend'),
      interpreter: 'none',
      autorestart: true,
      watch: false,
    },
  ],
};
