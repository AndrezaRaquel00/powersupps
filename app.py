from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import uuid

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'produtos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)

# MODELOS
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    imagem = db.Column(db.String(200), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    avaliacoes = db.relationship('Avaliacao', backref='produto', lazy=True)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(100), nullable=False)
    pedidos = db.relationship('Pedido', backref='usuario', lazy=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    data = db.Column(db.DateTime, default=db.func.current_timestamp())
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True)
    endereco = db.relationship('Endereco', uselist=False, backref='pedido')

class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    produto = db.relationship('Produto')

class Avaliacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    nota = db.Column(db.Integer)
    comentario = db.Column(db.Text)
    data = db.Column(db.DateTime, default=db.func.current_timestamp())

class Endereco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    cep = db.Column(db.String(20))
    rua = db.Column(db.String(100))
    numero_endereco = db.Column(db.String(10))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(50))
    cidade = db.Column(db.String(50))
    estado = db.Column(db.String(50))

# ROTAS
@app.route('/')
def index():
    produtos_db = Produto.query.all()
    return render_template("index.html", produtos=produtos_db)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        usuario_db = Usuario.query.filter_by(nome=usuario, senha=senha).first()
        if usuario_db:
            session['usuario'] = usuario
            flash(f'Bem-vindo, {usuario}!')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Você saiu da conta')
    return redirect(url_for('index'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['usuario']
        senha = request.form['senha']
        if Usuario.query.filter_by(nome=nome).first():
            flash('Usuário já existe')
            return redirect(url_for('cadastro'))
        novo_usuario = Usuario(nome=nome, senha=senha)
        db.session.add(novo_usuario)
        db.session.commit()
        flash('Usuário cadastrado com sucesso! Faça login.')
        return redirect(url_for('login'))
    return render_template('cadastro.html')

@app.route('/carrinho')
def carrinho():
    if 'usuario' not in session:
        flash('Faça login para acessar o carrinho')
        return redirect(url_for('login'))
    carrinho_ids = session.get('carrinho', [])
    produtos_carrinho = Produto.query.filter(Produto.id.in_(carrinho_ids)).all()
    return render_template("carrinho.html", produtos=produtos_carrinho)

@app.route('/adicionar_ao_carrinho/<int:id>')
def adicionar_ao_carrinho(id):
    if 'usuario' not in session:
        flash('Faça login para adicionar produtos ao carrinho')
        return redirect(url_for('login'))
    carrinho = session.get('carrinho', [])
    if id not in carrinho:
        carrinho.append(id)
        session['carrinho'] = carrinho
    return redirect(url_for('index'))

@app.route('/remover_do_carrinho/<int:produto_id>', methods=['POST'])
def remover_do_carrinho(produto_id):
    carrinho = session.get('carrinho', [])
    if produto_id in carrinho:
        carrinho.remove(produto_id)
        session['carrinho'] = carrinho
        flash('Produto removido do carrinho com sucesso!')
    return redirect(url_for('carrinho'))

@app.route('/limpar_carrinho', methods=['POST'])
def limpar_carrinho():
    session['carrinho'] = []
    flash('Carrinho limpo com sucesso!')
    return redirect(url_for('carrinho'))

@app.route('/finalizar-compra', methods=['GET', 'POST'])
def finalizar_compra():
    if 'usuario' not in session:
        flash('Faça login para finalizar a compra')
        return redirect(url_for('login'))

    if request.method == 'POST':
        cep = request.form.get('cep')
        rua = request.form.get('rua')
        numero_endereco = request.form.get('numero')
        complemento = request.form.get('complemento')
        bairro = request.form.get('bairro')
        cidade = request.form.get('cidade')
        estado = request.form.get('estado')

        if not all([cep, rua, numero_endereco, bairro, cidade, estado]):
            flash('Por favor, preencha todos os campos obrigatórios.')
            return redirect(url_for('finalizar_compra'))

        usuario = Usuario.query.filter_by(nome=session['usuario']).first()
        pedido = Pedido(usuario_id=usuario.id)
        db.session.add(pedido)
        db.session.commit()

        endereco = Endereco(
            pedido_id=pedido.id,
            cep=cep,
            rua=rua,
            numero_endereco=numero_endereco,
            complemento=complemento,
            bairro=bairro,
            cidade=cidade,
            estado=estado
        )
        db.session.add(endereco)

        for id in session.get('carrinho', []):
            item = ItemPedido(pedido_id=pedido.id, produto_id=id)
            db.session.add(item)

        db.session.commit()
        session['carrinho'] = []

        return render_template('obrigado.html')

    return render_template('finalizar_compra.html')

@app.route('/avaliar/<int:produto_id>', methods=['POST'])
def avaliar(produto_id):
    if 'usuario' not in session:
        flash('Faça login para avaliar')
        return redirect(url_for('login'))

    nota = int(request.form['nota'])
    comentario = request.form['comentario']
    usuario = Usuario.query.filter_by(nome=session['usuario']).first()

    avaliacao = Avaliacao(usuario_id=usuario.id, produto_id=produto_id, nota=nota, comentario=comentario)
    db.session.add(avaliacao)
    db.session.commit()
    flash('Avaliação enviada com sucesso!')
    return redirect(url_for('index'))

@app.route('/meus-pedidos')
def meus_pedidos():
    if 'usuario' not in session:
        flash('Faça login para ver seus pedidos')
        return redirect(url_for('login'))

    usuario = Usuario.query.filter_by(nome=session['usuario']).first()
    pedidos = Pedido.query.filter_by(usuario_id=usuario.id).order_by(Pedido.data.desc()).all()
    return render_template('meus_pedidos.html', pedidos=pedidos)

@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if 'usuario' not in session:
        flash('Faça login para adicionar produtos')
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form['nome']
        preco = float(request.form['preco'])
        imagem = request.files['imagem']

        if imagem and allowed_file(imagem.filename):
            ext = imagem.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            imagem.save(caminho_completo)

            novo_produto = Produto(nome=nome, imagem=filename, preco=preco)
            db.session.add(novo_produto)
            db.session.commit()

            flash('Produto adicionado com sucesso!')
            return redirect(url_for('index'))
        else:
            flash("Formato de imagem inválido. Use .jpg, .png, .gif ou .jpeg")
            return redirect(url_for('adicionar'))

    return render_template("adicionar.html")

@app.route('/excluir/<int:id>', methods=['POST'])
def excluir(id):
    if 'usuario' not in session:
        flash('Faça login para excluir produtos')
        return redirect(url_for('login'))

    produto = Produto.query.get_or_404(id)
    caminho_img = os.path.join(app.config['UPLOAD_FOLDER'], produto.imagem)
    if os.path.exists(caminho_img):
        os.remove(caminho_img)

    db.session.delete(produto)
    db.session.commit()

    carrinho = session.get('carrinho', [])
    if id in carrinho:
        carrinho.remove(id)
        session['carrinho'] = carrinho

    flash('Produto excluído com sucesso!')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
