import os
import zipfile

def create_deploy_zip():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(project_dir, 'deploy.zip')
    
    includes = [
        'api',
        'ui',
        'config',
        'scripts',
        'docs',
        'deploy',
        'docker-compose.yaml',
        'remote_up.sh',
        '.dockerignore'
    ]
    
    # Patterns to exclude
    exclude_dirs = {'.git', '.git.old', '.github', '.vscode', 'node_modules', '__pycache__', '.next'}
    exclude_files = {'deploy.zip', 'zip_deploy.py'}
    exclude_exts = {'.pyc', '.pyo', '.tmp'}

    print(f"Creating zip at {zip_path} from project root {project_dir}...")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in includes:
            item_path = os.path.join(project_dir, item)
            if not os.path.exists(item_path):
                print(f"Warning: {item} does not exist, skipping.")
                continue
                
            if os.path.isfile(item_path):
                # Write file with forward slashes
                arcname = item.replace('\\', '/')
                zipf.write(item_path, arcname)
                print(f"Added file: {arcname}")
            elif os.path.isdir(item_path):
                for root, dirs, files in os.walk(item_path):
                    # Filter directory names in-place to prevent walking down excluded paths
                    dirs[:] = [d for d in dirs if d not in exclude_dirs]
                    
                    for file in files:
                        if file in exclude_files:
                            continue
                        if os.path.splitext(file)[1] in exclude_exts:
                            continue
                            
                        file_path = os.path.join(root, file)
                        # Compute relative path from project root
                        rel_path = os.path.relpath(file_path, project_dir)
                        # Force forward slashes in zip arcname
                        arcname = rel_path.replace('\\', '/')
                        zipf.write(file_path, arcname)
                        
    print("Zip creation completed successfully!")

if __name__ == '__main__':
    create_deploy_zip()
