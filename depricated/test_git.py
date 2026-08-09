import git
import os

repo_path = os.path.join(os.path.expanduser('~'), '.mindpalace_sync_repo')
print(f'Repo path: {repo_path}')

if os.path.exists(repo_path):
    try:
        repo = git.Repo(repo_path)
        print(f'✅ Repository exists')
        print(f'Branch: {repo.active_branch.name}')
        print(f'Remote URL: {repo.remotes.origin.url}')
        
        print('Checking remote connection...')
        repo.remotes.origin.fetch(dry_run=True)
        print('✅ Remote connection successful!')
        
        if repo.head.is_valid():
            print(f'Last commit: {repo.head.commit.message.strip()}')
            print(f'Last commit time: {repo.head.commit.committed_datetime}')
    except Exception as e:
        print(f'❌ Error: {e}')
else:
    print('❌ Repository not found locally')
    print('Click "Sync Now" in the app Settings to clone it')
