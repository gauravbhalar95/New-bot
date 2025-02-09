import subprocess

def update_dependencies():
    try:
        # Upgrade pip-tools
        subprocess.run(["pip", "install", "--upgrade", "pip-tools"], check=True)

        # Regenerate requirements.txt
        subprocess.run(["pip-compile", "--upgrade"], check=True)

        # Install updated dependencies
        subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)

        print("Dependencies updated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error while updating dependencies: {e}")

if __name__ == "__main__":
    update_dependencies()
