from flask import Flask, render_template, request, redirect, url_for, send_file
import pandas as pd
import os
from ssh.script import run_ssh_tasks  # ton script importé proprement

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run():
    run_ssh_tasks()
    return redirect(url_for('result'))

@app.route('/result')
def result():
    df = pd.read_excel('data/output.xlsx')
    return render_template('result.html', tables=[df.to_html(classes='table table-striped', index=False)], titles=df.columns.values)

@app.route('/download')
def download():
    path = "data/output.xlsx"
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
