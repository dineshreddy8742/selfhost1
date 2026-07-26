import os
import subprocess
import sys
import time

def log(msg):
    print(f"\n[LOCAL RUNNER] {msg}\n", flush=True)

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)

    # 1. Start Docker backing databases
    log("Starting postgres, redis, and minio containers in background...")
    subprocess.run(["docker", "compose", "up", "-d", "postgres", "redis", "minio"], check=True)

    # 2. Set up virtual environment
    venv_dir = os.path.join(root_dir, "venv")
    venv_bin = os.path.join(venv_dir, "Scripts") if os.name == "nt" else os.path.join(venv_dir, "bin")
    pip_exe = os.path.join(venv_bin, "pip")
    uv_exe = os.path.join(venv_bin, "uv")

    if not os.path.exists(venv_dir):
        log("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

    # Install uv for fast dependency installation
    if not os.path.exists(uv_exe) and not os.path.exists(uv_exe + ".exe"):
        log("Installing uv...")
        subprocess.run([pip_exe, "install", "uv"], check=True)

    log("Installing python backend requirements (using uv)...")
    subprocess.run([uv_exe, "pip", "install", "-p", "venv", "-r", "api/requirements.txt"], check=True)
    subprocess.run([uv_exe, "pip", "install", "-p", "venv", "-e", "./pipecat"], check=True)

    # 3. Check and install UI node dependencies
    ui_dir = os.path.join(root_dir, "ui")
    node_modules_dir = os.path.join(ui_dir, "node_modules")
    if not os.path.exists(node_modules_dir):
        log("ui/node_modules not found. Installing UI dependencies...")
        subprocess.run(["npm", "install"], cwd=ui_dir, shell=True, check=True)

    # 4. Parse .env and set up environment variables for localhost mapping
    log("Parsing .env file...")
    env_vars = {}
    env_file_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_file_path):
        with open(env_file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    # Set up environmental overrides
    postgres_pass = env_vars.get("POSTGRES_PASSWORD", "postgres")
    redis_pass = env_vars.get("REDIS_PASSWORD", "redissecret")
    minio_user = env_vars.get("MINIO_ROOT_USER", "minioadmin")
    minio_pass = env_vars.get("MINIO_ROOT_PASSWORD", "minioadmin")
    jwt_secret = env_vars.get("OSS_JWT_SECRET", "supersecretjwt")

    local_env = os.environ.copy()
    local_env["ENVIRONMENT"] = "local"
    local_env["DATABASE_URL"] = f"postgresql+asyncpg://postgres:{postgres_pass}@localhost:5432/postgres"
    local_env["REDIS_URL"] = f"redis://:{redis_pass}@localhost:6379"
    local_env["MINIO_ENDPOINT"] = "localhost:9000"
    local_env["MINIO_ACCESS_KEY"] = minio_user
    local_env["MINIO_SECRET_KEY"] = minio_pass
    local_env["OSS_JWT_SECRET"] = jwt_secret

    # 5. Run Alembic migrations
    log("Running database migrations...")
    alembic_exe = os.path.join(venv_bin, "alembic")
    subprocess.run([alembic_exe, "-c", "api/alembic.ini", "upgrade", "head"], env=local_env, check=True)

    # 6. Start API (Uvicorn) and UI (Next.js) concurrently
    log("Launching local API and UI concurrently...")
    uvicorn_exe = os.path.join(venv_bin, "uvicorn")

    # Start FastAPI backend
    api_process = subprocess.Popen(
        [uvicorn_exe, "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        env=local_env
    )

    # Start Next.js frontend
    ui_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=ui_dir,
        shell=True
    )

    log("Local services are now starting!")
    print("--------------------------------------------------")
    print("- Frontend: http://localhost:3010 (or 3000)")
    print("- API Backend: http://localhost:8000")
    print("--------------------------------------------------")
    print("Press Ctrl+C here to terminate both services.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Shutting down API and UI services...")
        api_process.terminate()
        ui_process.terminate()
        api_process.wait()
        ui_process.wait()
        log("Services stopped.")

if __name__ == "__main__":
    main()
