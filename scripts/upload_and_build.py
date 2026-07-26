import subprocess
import sys

def upload_and_build():
    print("Step 1: Uploading deploy_code.tar.gz and remote_script.py...")
    scp_cmd = [
        "gcloud.cmd", "compute", "scp",
        "deploy_code.tar.gz", "remote_script.py",
        "dograh-server-us:/home/palav/",
        "--zone=us-central1-a"
    ]
    res1 = subprocess.run(scp_cmd, capture_output=True, text=True)
    print("SCP STDOUT:", res1.stdout)
    print("SCP STDERR:", res1.stderr)
    if res1.returncode != 0:
        print("SCP Failed!")
        sys.exit(1)

    print("Step 2: Executing remote_script.py on remote server...")
    ssh_cmd = [
        "gcloud.cmd", "compute", "ssh", "dograh-server-us",
        "--zone=us-central1-a",
        "--command=python3 /home/palav/remote_script.py"
    ]
    res2 = subprocess.run(ssh_cmd, capture_output=True, text=True)
    print("SSH STDOUT:", res2.stdout)
    print("SSH STDERR:", res2.stderr)
    if res2.returncode != 0:
        print("Remote deployment failed!")
        sys.exit(1)

if __name__ == "__main__":
    upload_and_build()
