import os
import uuid


from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from dotenv import load_dotenv

# =========================
# Configuração básica / App
# =========================
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = os.getenv('FLASK_SECRET', 'sua_chave_secreta')

# =========================
# Configuração do e-mail
# =========================
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
# fallback: se não definir MAIL_DEFAULT_SENDER, usa o MAIL_USERNAME
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER') or app.config['MAIL_USERNAME']

mail = Mail(app)

# =========================
# Configuração do banco
# =========================
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'produtos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =========================
# Modelos
# =========================
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

# =========================
# Funções de e-mail
# =========================
def send_email(subject: str, recipients: list[str], body: str) -> None:
    """
    Envia e-mail simples em texto.
    Lança exceção se falhar (para podermos ver no log/flash).
    """
    msg = Message(subject=subject, recipients=recipients, body=body)
    mail.send(msg)

def enviar_confirmacao_cadastro(nome: str, email_destino: str) -> None:
    corpo = f"Olá {nome},\n\nSeu cadastro na Power Supps foi realizado com sucesso!\n\nObrigado por se juntar a nós!"
    send_email("Confirmação de cadastro - Power Supps", [email_destino], corpo)

def enviar_confirmacao_compra(email_destino: str, pedido_id: int, nome_cliente: str, total: float) -> None:
    corpo = (
        f"Olá {nome_cliente},\n\n"
        f"Recebemos seu pedido #{pedido_id}.\n"
        f"Valor total: R$ {total:.2f}\n\n"
        f"Em breve enviaremos novas atualizações.\n\nObrigado pela compra!"
    )
    send_email("Confirmação de Pedido - Power Supps", [email_destino], corpo)

def enviar_contato_para_admin(admin_email: str, nome: str, email: str, assunto: str, mensagem: str) -> None:
    corpo = (
        f"Novo contato recebido:\n\n"
        f"Nome: {nome}\n"
        f"E-mail: {email}\n"
        f"Assunto: {assunto}\n\n"
        f"Mensagem:\n{mensagem}"
    )
    send_email(f"[Power Supps] Contato: {assunto or 'Sem assunto'}", [admin_email], corpo)

def enviar_recuperacao(email_destino: str, link: str) -> None:
    corpo = (
        "Recebemos uma solicitação para redefinir sua senha na Power Supps.\n\n"
        f"Use o link abaixo para continuar:\n{link}\n\n"
        "Se você não solicitou, ignore este e-mail."
    )
    send_email("Recuperação de senha - Power Supps", [email_destino], corpo)

# =========================
# Rotas
# =========================
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
        email_cadastro = request.form.get('email')  # opcional: se o form tiver

        if Usuario.query.filter_by(nome=nome).first():
            flash('Usuário já existe')
            return redirect(url_for('cadastro'))

        novo_usuario = Usuario(nome=nome, senha=senha)
        db.session.add(novo_usuario)
        db.session.commit()

        # Envio do e-mail:
        try:
            if email_cadastro:
                enviar_confirmacao_cadastro(nome, email_cadastro)
            else:
                # Se não tiver email no formulário, notifica o admin
                admin_email = os.getenv('ADMIN_EMAIL') or app.config['MAIL_DEFAULT_SENDER']
                enviar_contato_para_admin(
                    admin_email,
                    nome,
                    admin_email,
                    "Novo cadastro",
                    f"O usuário '{nome}' acabou de se cadastrar (sem e-mail no formulário)."
                )
        except Exception as e:
            # Mantemos o fluxo mesmo com erro de e-mail
            print("Falha ao enviar e-mail de cadastro:", e)

        flash('Usuário cadastrado com sucesso! Faça login.')
        return redirect(url_for('login'))
    return render_template('cadastro.html')

@app.route('/carrinho')
def carrinho():
    if 'usuario' not in session:
        flash('Faça login para acessar o carrinho')
        return redirect(url_for('login'))
    carrinho_ids = session.get('carrinho', [])
    produtos_carrinho = Produto.query.filter(Produto.id.in_(carrinho_ids)).all() if carrinho_ids else []
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
        email_cliente = request.form.get('email')
        cep = request.form.get('cep')
        rua = request.form.get('rua')
        numero = request.form.get('numero')
        complemento = request.form.get('complemento')
        bairro = request.form.get('bairro')
        cidade = request.form.get('cidade')
        estado = request.form.get('estado')

        if not all([email_cliente, cep, rua, numero, bairro, cidade, estado]):
            flash('Preencha todos os campos obrigatórios.')
            return redirect(url_for('finalizar_compra'))

        usuario = Usuario.query.filter_by(nome=session['usuario']).first()

        # Criar pedido no banco
        pedido = Pedido(usuario_id=usuario.id)
        db.session.add(pedido)
        db.session.flush()  # gera ID do pedido

        endereco = Endereco(
            pedido_id=pedido.id,
            cep=cep,
            rua=rua,
            numero_endereco=numero,
            complemento=complemento,
            bairro=bairro,
            cidade=cidade,
            estado=estado
        )
        db.session.add(endereco)

        total = 0.0
        for pid in session.get('carrinho', []):
            produto = Produto.query.get(pid)
            if produto:
                total += float(produto.preco)
                item = ItemPedido(pedido_id=pedido.id, produto_id=pid)
                db.session.add(item)

        db.session.commit()
        session['carrinho'] = []

        # Enviar e-mail de confirmação
        try:
            msg = Message(
                subject="🎉 Obrigado pela sua compra - Gym Ware",
                recipients=[email_cliente],
                body=f"Olá {usuario.nome},\n\nSua compra foi finalizada com sucesso!\nValor total: R$ {total:.2f}\n\nObrigado por confiar na Gym Ware! 💪"
            )
            mail.send(msg)
        except Exception as e:
            print("Erro ao enviar e-mail:", e)

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
            # opcional: filename = secure_filename(filename)
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

@app.route('/contato', methods=['GET', 'POST'])
def contato():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        assunto = request.form.get('assunto')
        mensagem = request.form.get('mensagem')
        admin_email = os.getenv('ADMIN_EMAIL') or app.config['MAIL_DEFAULT_SENDER']
        try:
            enviar_contato_para_admin(admin_email, nome, email, assunto, mensagem)
            flash('Mensagem enviada! Em breve entraremos em contato.', 'success')
        except Exception as e:
            flash(f'Erro ao enviar mensagem: {e}', 'danger')
        return redirect(url_for('contato'))
    return render_template('contact.html')

@app.route('/recuperar', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form.get('email')
        token = 'TOKEN123456'
        link = url_for('login', _external=True) + f'?reset={token}'
        try:
            enviar_recuperacao(email, link)
            flash('E-mail de recuperação enviado.', 'info')
        except Exception as e:
            flash(f'Erro: {e}', 'danger')
        return redirect(url_for('recover'))
    return render_template('recover.html')

@app.route('/teste-email')
def teste_email():
    try:
        admin = os.getenv("ADMIN_EMAIL") or app.config['MAIL_DEFAULT_SENDER']
        msg = Message(
            subject="Teste de E-mail Flask",
            recipients=[admin],
            body="Este é um e-mail de teste enviado pelo Flask usando Gmail + .env"
        )
        mail.send(msg)
        return "✅ E-mail enviado com sucesso! Verifique sua caixa de entrada."
    except Exception as e:
        return f"❌ Erro ao enviar e-mail: {e}"

# =========================
# Execução
# =========================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # para desenvolvimento local
    app.run(host="127.0.0.1", port=5000, debug=True)



def enviar_confirmacao_compra(nome: str, email_destino: str, itens: list[dict], total: float) -> None:
    """
    Envia e-mail de confirmação de compra.
    itens deve ser uma lista de dicionários no formato:
        {"produto": "Nome", "quantidade": 2, "preco": 50.0}
    """
    try:
        lista_itens = "\n".join(
            [f"- {item['produto']} (x{item['quantidade']}) - R$ {item['preco'] * item['quantidade']:.2f}"
             for item in itens]
        )

        corpo = (
            f"Olá {nome},\n\n"
            f"Obrigado pela sua compra na Power Supps! 🎉\n\n"
            f"Aqui estão os detalhes do seu pedido:\n\n"
            f"{lista_itens}\n\n"
            f"Total: R$ {total:.2f}\n\n"
            f"Em breve você receberá mais informações sobre o envio.\n\n"
            f"Equipe Power Supps."
        )

        msg = Message(
            subject="Confirmação da sua compra - Power Supps",
            recipients=[email_destino],
            body=corpo
        )
        mail.send(msg)

    except Exception as e:
        print(f"❌ Erro ao enviar e-mail de compra: {e}")
        raise


