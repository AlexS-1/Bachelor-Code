import subprocess

def get_comment_data(repo_path, tag="-target=HEAD", jar_path="/Users/as/Library/Mobile Documents/com~apple~CloudDocs/Dokumente/Studium/Bachelor-Thesis/CommentLister/target/CommentLister.jar"):
    try:
        result = subprocess.run(
            ['java', '-jar', jar_path, repo_path, tag],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running CommentLister: {e.stderr}")
        return None