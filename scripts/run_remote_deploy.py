import subprocess

def deploy():
    print("1. Uploading deploy_code.tar.gz...")
    subprocess.run(["gcloud.cmd", "compute", "scp", "deploy_code.tar.gz", "dograh-server-us:/home/palav/deploy_code.tar.gz", "--zone=us-central1-a"], check=True)

    print("2. Uploading remote_script.py...")
    subprocess.run(["gcloud.cmd", "compute", "scp", "remote_script.py", "dograh-server-us:/tmp/remote_script.py", "--zone=us-central1-a"], check=True)

    print("3. Executing remote_script.py on GCP VM...")
    subprocess.run(["gcloud.cmd", "compute", "ssh", "dograh-server-us", "--zone=us-central1-a", "--command=python3 /tmp/remote_script.py"], check=True)

if __name__ == "__main__":
    deploy()
