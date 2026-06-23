module.exports = {
  apps: [
    {
      name: 'voiceai-web',
      script: 'venv/bin/python',
      args: 'app.py',
      cwd: '/home/elektro/ai-audio',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        PORT: '15000',
        DISPLAY: ':0',
      },
      error_file: '/home/elektro/ai-audio/pm2-error-web.log',
      out_file: '/home/elektro/ai-audio/pm2-out-web.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },
    ],
};