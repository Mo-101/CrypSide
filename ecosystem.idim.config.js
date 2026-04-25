module.exports = {
  apps: [
    {
      name: "idim-scanner",
      cwd: "/home/idona/MoStar/idim-ikang-observer",
      script: "/home/idona/MoStar/idim-ikang-observer/.venv/bin/python",
      args: "scanner.py",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "idim-api",
      cwd: "/home/idona/MoStar/idim-ikang-observer",
      script: "/home/idona/MoStar/idim-ikang-observer/.venv/bin/python",
      args: "-m uvicorn api:app --host 0.0.0.0 --port 8787",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "idim-outcome-tracker",
      cwd: "/home/idona/MoStar/idim-ikang-observer",
      script: "/home/idona/MoStar/idim-ikang-observer/.venv/bin/python",
      args: "outcome_tracker.py --loop",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
