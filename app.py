from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.get('message')

    if data == "123":
        return jsonify({"response": "456"})
    else:
        return jsonify({"response": "Invalid input"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000,debug=True)