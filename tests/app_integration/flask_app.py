from wsgiref.validate import validator

from flask import Flask, redirect, request

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/test')
def hello_world_2():
    return 'Hello, World 2!'

@app.route('/params_test')
def params_test():
    argstr = ''
    for arg_name, arg_value in request.args.items():
        argstr += '{}: {}\n'.format(arg_name, arg_value)
    return argstr

@app.route('/post_test', methods=['POST'])
def post_test():
    argstr = ''
    for arg_name, arg_value in request.form.items():
        argstr += '{}: {}\n'.format(arg_name, arg_value)
    return argstr

@app.route('/redirect')
def redirect_test():
    return redirect('/test')

app = validator(app)
