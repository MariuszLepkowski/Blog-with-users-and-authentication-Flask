from datetime import date
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from decorators import admin_only
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
db = SQLAlchemy()
db.init_app(app)


# CONFIGURE TABLES

# TODO: Create a User table for all your registered users.
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    posts = db.relationship('BlogPost', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(250), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comments = db.relationship('Comment', backref='blog_post', lazy=True)


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)


with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user:
            flash("You've already signed up with that email. Please log in instead.")
            return redirect(url_for('login'))

        hashed_and_salted_password = generate_password_hash(
            password=request.form.get('password'),
            method='pbkdf2:sha256:600000',
            salt_length=8,
        )

        new_user = User(
            email=request.form.get('email'),
            password=hashed_and_salted_password,
            name=request.form.get('name'),
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user:
            if check_password_hash(pwhash=user.password, password=password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Wrong password.")
                return redirect(url_for('login'))
        else:
            flash("That email does not exist. Please try again")
            return redirect(url_for('login'))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['GET','POST'])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    comments = requested_post.comments

    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            comment_text_html = comment_form.comment.data
            soup = BeautifulSoup(comment_text_html, 'html.parser')
            comment_text_converted = soup.get_text()

            new_comment = Comment(
                text=comment_text_converted,
                author=current_user.name,
                author_id=current_user.id,
                parent_post_id=requested_post.id,
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=requested_post.id))
        else:
            flash("You need to log in or register to comment")
            return redirect(url_for('login'))


    return render_template("post.html", post=requested_post, form=comment_form, comments=comments)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user.name,
            author_id=current_user.id,
            date=date.today().isoformat()
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user.name
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
