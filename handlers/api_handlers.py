from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/project-structure', methods=['GET'])
def project_structure():
    structure = {}
    for root, dirs, files in os.walk('.'):
        structure[root] = {"dirs": dirs, "files": files}
    return jsonify(structure)

if __name__ == "__main__":
    app.run(debug=True)