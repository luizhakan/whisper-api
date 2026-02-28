module.exports = {
  apps: [
    {
      name: "whisper-api",
      script: "uvicorn",
      args: "main:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      cwd: __dirname,
      env_file: ".env",
      watch: false,
      max_memory_restart: "2G",
      restart_delay: 5000,
      max_restarts: 10,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/whisper-api-error.log",
      out_file: "logs/whisper-api-out.log",
      merge_logs: true,
      autorestart: true,
    },
  ],
};
