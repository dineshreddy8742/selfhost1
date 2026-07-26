import os
import tarfile

def create_tar():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tar_path = os.path.join(project_dir, 'deploy_code.tar.gz')
    
    includes = ['api', 'ui', 'docker-compose.yaml', '.dockerignore']
    exclude_dirs = {'.git', '.git.old', '.github', '.vscode', 'node_modules', '__pycache__', '.next', 'dist', 'build'}
    exclude_files = {'deploy.zip', 'deploy_code.tar.gz'}

    print(f"Creating tar.gz at {tar_path}...")
    with tarfile.open(tar_path, 'w:gz') as tar:
        for item in includes:
            item_path = os.path.join(project_dir, item)
            if not os.path.exists(item_path):
                continue
            if os.path.isfile(item_path):
                tar.add(item_path, arcname=item)
            elif os.path.isdir(item_path):
                for root, dirs, files in os.walk(item_path):
                    dirs[:] = [d for d in dirs if d not in exclude_dirs]
                    for file in files:
                        if file in exclude_files or file.endswith(('.pyc', '.pyo', '.tmp')):
                            continue
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, project_dir)
                        tar.add(file_path, arcname=rel_path.replace('\\', '/'))

    print(f"Tar creation completed! Size: {os.path.getsize(tar_path) / 1024 / 1024:.2f} MB")

if __name__ == '__main__':
    create_tar()
